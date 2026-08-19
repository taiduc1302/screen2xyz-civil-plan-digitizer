"""Local screen, OCR, clipboard, and plan-value readers."""

from __future__ import annotations

import csv
import hashlib
import io
import math
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Callable, Hashable

from screen2xyz_civil import contracts as civil_contracts
from screen2xyz_civil.assisted_capture import (
    CandidateEvidence,
    ElevationUnderCursorService,
    SpatialCandidateIndex,
)
from screen2xyz_civil.detection import Rect
from screen2xyz_civil.models import PixelPoint
from screen2xyz_civil.ocr import TesseractOcrAdapter, WindowsOcrAdapter
from screen2xyz_m2.parsing import parse_number

from .capture import Reading
from .mapping import ChannelSource


class OcrUnavailableError(RuntimeError):
    """No supported local OCR engine is available."""


class OcrConfidenceError(ValueError):
    """OCR did not produce a safely parseable value above the gate."""


@dataclass(frozen=True)
class OcrPolicy:
    separator_mode: str = "point"
    numeric: bool = True
    confidence_min: float = 0.35
    numeric_range: tuple[float, float] | None = None
    precision_min: int | None = None
    consensus_min: int = 1
    whitelist: str = ""
    psm_modes: tuple[int, ...] = (7, 8, 13)
    rotation_angles: tuple[int, ...] = (0,)
    upscale: int = 4
    binarize: bool = True
    declared_format: str | None = None

    def __post_init__(self) -> None:
        if not 0.0 <= self.confidence_min <= 1.0:
            raise ValueError("OCR confidence gate must be between 0 and 1")
        if self.upscale < 1 or self.upscale > 6:
            raise ValueError("OCR upscale must be between 1 and 6")
        if self.precision_min is not None and self.precision_min < 1:
            raise ValueError("OCR minimum precision must be positive")
        if self.consensus_min < 1:
            raise ValueError("OCR consensus minimum must be at least one")
        if not self.psm_modes:
            raise ValueError("at least one Tesseract PSM mode is required")
        if not self.rotation_angles or any(abs(angle) > 30 for angle in self.rotation_angles):
            raise ValueError("OCR rotation angles must stay within 30 degrees")


@dataclass(frozen=True)
class _TesseractToken:
    text: str
    confidence: float
    left: float
    top: float
    width: float
    height: float


class ScreenOcrBackend:
    """Capture/crop bytes and run a bounded numeric OCR retry ladder."""

    def __init__(
        self,
        *,
        executable: Path | None = None,
        capture_provider: Callable[[tuple[int, int, int, int]], Any] | None = None,
        cursor_candidate_provider: Callable[[Any, OcrPolicy], tuple["CursorOcrCandidate", ...]] | None = None,
        cache_enabled: bool = True,
    ) -> None:
        self.repository_root = Path(__file__).resolve().parents[2]
        self.executable = executable or TesseractOcrAdapter.find_executable()
        self.capture_provider = capture_provider or self._capture_zone
        self.cursor_candidate_provider = (
            cursor_candidate_provider or self._cursor_candidates_tesseract
        )
        self.cache_enabled = cache_enabled
        self._cache: dict[Hashable, tuple[str, Reading]] = {}

    @property
    def available(self) -> bool:
        return self.executable is not None or sys.platform == "win32"

    @staticmethod
    def _png_bytes(image) -> bytes:
        output = io.BytesIO()
        image.convert("RGB").save(output, format="PNG")
        return output.getvalue()

    @staticmethod
    def _prepare_variants(image, policy: OcrPolicy):
        from PIL import Image, ImageOps

        source = image.convert("RGB")
        fill = source.getpixel((0, 0))
        # Tesseract versions differ in how reliably they auto-invert small
        # light-on-dark text. Normalize a dark background before building the
        # retry ladder so every platform sees dark glyphs on a light field.
        if sum(fill) / 3 < 128:
            source = ImageOps.invert(source)
            fill = source.getpixel((0, 0))
        variants = []
        for angle in policy.rotation_angles:
            rgb = (
                source
                if angle == 0
                else source.rotate(angle, expand=True, fillcolor=fill)
            )
            padded = ImageOps.expand(rgb, border=16, fill=fill)
            factor = (
                policy.upscale
                if image.height < 80 else max(1, policy.upscale - 1)
            )
            if factor > 1:
                padded = padded.resize(
                    (padded.width * factor, padded.height * factor),
                    resample=Image.Resampling.LANCZOS,
                )
            variants.append((f"color@{angle}", padded))
            if policy.binarize:
                gray = ImageOps.autocontrast(padded.convert("L"))
                variants.append((f"gray@{angle}", gray))
                for cutoff in (125, 155, 185):
                    threshold = gray.point(
                        lambda pixel, value=cutoff: 255 if pixel >= value else 0
                    )
                    variants.append((f"binary-{cutoff}@{angle}", threshold))
        return variants

    def read_zone(
        self,
        zone: tuple[int, int, int, int],
        *,
        policy: OcrPolicy | None = None,
    ) -> Reading:
        image = self.capture_provider(zone)
        return self.read_image(image, cache_key=("screen", zone), policy=policy)

    @staticmethod
    def _capture_zone(zone: tuple[int, int, int, int]):
        from PIL import Image
        import mss

        left, top, width, height = zone
        with mss.mss() as capture:
            shot = capture.grab(
                {"left": left, "top": top, "width": width, "height": height}
            )
        return Image.frombytes("RGB", shot.size, shot.rgb)

    def read_image_region(
        self,
        image_or_path,
        region: tuple[int, int, int, int],
        *,
        cache_key: Hashable | None = None,
        policy: OcrPolicy | None = None,
    ) -> Reading:
        from PIL import Image

        if isinstance(image_or_path, (str, Path)):
            with Image.open(image_or_path) as opened:
                image = opened.convert("RGB")
        else:
            image = image_or_path.convert("RGB")
        left, top, width, height = region
        crop = image.crop((left, top, left + width, top + height))
        return self.read_image(crop, cache_key=cache_key, policy=policy)

    def read_image(
        self,
        image,
        *,
        cache_key: Hashable | None = None,
        policy: OcrPolicy | None = None,
    ) -> Reading:
        policy = policy or OcrPolicy()
        png = self._png_bytes(image)
        digest = hashlib.sha256(png).hexdigest()
        key = None if cache_key is None else (cache_key, policy)
        cached = None if key is None or not self.cache_enabled else self._cache.get(key)
        if cached is not None and cached[0] == digest:
            prior = cached[1]
            return Reading(prior.raw_text, prior.confidence, digest, png, False)
        variants = self._prepare_variants(image, policy)
        reading = self._ocr(variants, policy, digest, png)
        if key is not None and self.cache_enabled:
            self._cache[key] = (digest, reading)
        return reading

    def _ocr(self, variants, policy: OcrPolicy, digest: str, png: bytes) -> Reading:
        if self.executable is not None:
            reading = self._ocr_tesseract(variants, policy, digest, png)
        elif sys.platform == "win32":
            reading = self._ocr_windows(variants[0][1], digest, png)
        else:
            raise OcrUnavailableError(
                "Tesseract was not found and Windows OCR is unavailable"
            )
        if (
            reading.confidence is not None
            and reading.confidence < policy.confidence_min
        ):
            raise OcrConfidenceError(
                f"OCR confidence {reading.confidence:.3f} is below "
                f"{policy.confidence_min:.3f}"
            )
        return reading

    def _ocr_tesseract(
        self, variants, policy: OcrPolicy, digest: str, png: bytes
    ) -> Reading:
        candidates: list[tuple[bool, float, str, str | None]] = []
        vote_variants: dict[str | None, set[str]] = {}
        for variant_name, _psm, tokens in self._tesseract_passes(variants, policy):
            entries = [
                (token.text.strip(), token.confidence)
                for token in tokens
                if token.text.strip()
            ]
            spans = (
                [(" ".join(text for text, _score in entries), entries)]
                if not policy.numeric else
                [
                    (
                        " ".join(text for text, _score in entries[start:end]),
                        entries[start:end],
                    )
                    for start in range(len(entries))
                    for end in range(start + 1, min(len(entries), start + 3) + 1)
                ]
            )
            pass_candidates: list[tuple[bool, float, str, str | None]] = []
            for candidate_text, span in spans:
                valid, candidate_text, normalized = self._parse_candidate(
                    candidate_text, policy
                )
                scores = [score for _text, score in span if score >= 0]
                confidence = (
                    0.0 if not scores else sum(scores) / len(scores) / 100.0
                )
                pass_candidates.append((valid, confidence, candidate_text, normalized))
                if (
                    policy.consensus_min == 1
                    and valid
                    and confidence >= max(0.85, policy.confidence_min)
                ):
                    return Reading(candidate_text, confidence, digest, png, True)
            best_for_pass: dict[str | None, tuple[bool, float, str, str | None]] = {}
            for item in pass_candidates:
                key = item[3] if item[0] else f"invalid:{item[2]}"
                if key not in best_for_pass or item[1] > best_for_pass[key][1]:
                    best_for_pass[key] = item
            candidates.extend(best_for_pass.values())
            for item in best_for_pass.values():
                if item[0]:
                    vote_variants.setdefault(item[3], set()).add(variant_name)
        valid_candidates = [item for item in candidates if item[0]]
        if not valid_candidates:
            observed = sorted({item[2] for item in candidates if item[2]})
            if policy.declared_format is not None:
                numeric_fragments = [
                    value for value in observed if any(ch.isdigit() for ch in value)
                ]
                if numeric_fragments:
                    value = max(
                        numeric_fragments,
                        key=lambda item: (
                            sum(ch.isdigit() for ch in item),
                            -len(item),
                        ),
                    )
                    raise OcrConfidenceError(
                        f"the value reads as {value}, which is not valid for "
                        f"the declared format {policy.declared_format}; check "
                        "the zone edges or the format setting"
                    )
            raise OcrConfidenceError(
                "OCR retry ladder produced no parseable value"
                + (f": {observed}" if observed else "")
            )
        if policy.consensus_min > 1:
            votes = {
                normalized: len(variant_names)
                for normalized, variant_names in vote_variants.items()
            }
            agreed = [
                (normalized, count)
                for normalized, count in votes.items()
                if count >= policy.consensus_min
            ]
            if not agreed:
                raise OcrConfidenceError(
                    f"OCR retry ladder did not reach {policy.consensus_min}-reading consensus"
                )
            if len(agreed) != 1:
                raise OcrConfidenceError(
                    "OCR retry ladder produced competing consensus values"
                )
            normalized, _count = agreed[0]
            _, confidence, text, _ = max(
                (item for item in valid_candidates if item[3] == normalized),
                key=lambda item: item[1],
            )
        else:
            _, confidence, text, _ = max(
                valid_candidates, key=lambda item: item[1]
            )
        return Reading(text, confidence, digest, png, True)

    def _tesseract_passes(
        self, variants, policy: OcrPolicy
    ) -> tuple[tuple[str, int, tuple[_TesseractToken, ...]], ...]:
        """Run every prepared image while amortizing Tesseract startup cost.

        Tesseract accepts a newline-delimited image list as a multi-page input.
        Using one process per PSM preserves per-variant evidence via TSV page
        numbers while avoiding one process launch per angle/threshold variant.
        A one-image path remains for focused unit tests and tiny policies.
        """

        if self.executable is None:
            raise OcrUnavailableError("Tesseract executable is unavailable")
        variants = tuple(variants)
        if len(variants) == 1:
            import pytesseract
            from pytesseract import Output

            pytesseract.pytesseract.tesseract_cmd = str(self.executable)
            variant_name, image = variants[0]
            passes = []
            for psm in policy.psm_modes:
                whitelist = (
                    f" -c tessedit_char_whitelist={policy.whitelist}"
                    if policy.numeric and policy.whitelist else ""
                )
                data = pytesseract.image_to_data(
                    image,
                    config=f"--psm {psm}{whitelist}",
                    output_type=Output.DICT,
                )
                passes.append((variant_name, psm, self._tokens_from_dict(data)))
            return tuple(passes)

        passes: list[tuple[str, int, tuple[_TesseractToken, ...]]] = []
        with tempfile.TemporaryDirectory(prefix="screen2xyz-ocr-") as temporary:
            root = Path(temporary)
            image_paths = []
            for index, (_variant_name, image) in enumerate(variants):
                path = root / f"variant-{index:03d}.png"
                image.save(path, format="PNG")
                image_paths.append(path)
            image_list = root / "images.txt"
            image_list.write_text(
                "".join(f"{path}\n" for path in image_paths), encoding="utf-8"
            )
            timeout_seconds = max(10.0, min(60.0, len(variants) * 0.75))
            def run_psm(psm: int):
                command = [
                    str(self.executable), str(image_list), "stdout",
                    "--psm", str(psm),
                ]
                if policy.numeric and policy.whitelist:
                    command.extend([
                        "-c", f"tessedit_char_whitelist={policy.whitelist}",
                    ])
                command.append("tsv")
                try:
                    return subprocess.run(
                        command,
                        check=False,
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="replace",
                        timeout=timeout_seconds,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                except subprocess.TimeoutExpired as exc:
                    raise OcrConfidenceError(
                        f"Tesseract OCR exceeded the {timeout_seconds:.1f}s safety timeout"
                    ) from exc

            # PSMs are independent passes over the same immutable files.
            # Launching them together removes the artificial serial wait from
            # live cursor reads while leaving all evidence and fail-closed
            # consensus rules unchanged.
            with ThreadPoolExecutor(max_workers=len(policy.psm_modes)) as pool:
                completed_by_psm = dict(zip(
                    policy.psm_modes,
                    pool.map(run_psm, policy.psm_modes),
                ))
            for psm in policy.psm_modes:
                completed = completed_by_psm[psm]
                if completed.returncode != 0:
                    raise OcrUnavailableError(
                        f"Tesseract OCR failed with exit code {completed.returncode}"
                    )
                page_tokens: list[list[_TesseractToken]] = [
                    [] for _variant in variants
                ]
                reader = csv.DictReader(io.StringIO(completed.stdout), delimiter="\t")
                for row in reader:
                    raw_text = str(row.get("text") or "").strip()
                    if not raw_text:
                        continue
                    try:
                        page_index = int(row.get("page_num") or 0) - 1
                        token = _TesseractToken(
                            raw_text,
                            float(row.get("conf") or -1),
                            float(row.get("left") or 0),
                            float(row.get("top") or 0),
                            float(row.get("width") or 0),
                            float(row.get("height") or 0),
                        )
                    except (TypeError, ValueError):
                        continue
                    if 0 <= page_index < len(variants):
                        page_tokens[page_index].append(token)
                for index, (variant_name, _image) in enumerate(variants):
                    passes.append((variant_name, psm, tuple(page_tokens[index])))
        return tuple(passes)

    @staticmethod
    def _tokens_from_dict(data) -> tuple[_TesseractToken, ...]:
        tokens = []
        size = len(data.get("text", ()))
        for index in range(size):
            tokens.append(_TesseractToken(
                str(data["text"][index]),
                float(data["conf"][index]),
                float(data.get("left", [0] * size)[index]),
                float(data.get("top", [0] * size)[index]),
                float(data.get("width", [0] * size)[index]),
                float(data.get("height", [0] * size)[index]),
            ))
        return tuple(tokens)

    @staticmethod
    def _parse_candidate(
        candidate_text: str, policy: OcrPolicy
    ) -> tuple[bool, str, str | None]:
        if not policy.numeric:
            return bool(candidate_text), candidate_text, candidate_text
        outcome = parse_number(
            candidate_text,
            separator_mode=policy.separator_mode,
            numeric_range=policy.numeric_range,
            declared_format=policy.declared_format,
        )
        if outcome.parse_status != "OK" and policy.declared_format is None:
            if (
                policy.separator_mode == "comma"
                and "." in candidate_text
                and "," not in candidate_text
            ):
                candidate_text = candidate_text.replace(".", ",")
            elif (
                policy.separator_mode == "point"
                and "," in candidate_text
                and "." not in candidate_text
            ):
                candidate_text = candidate_text.replace(",", ".")
            outcome = parse_number(
                candidate_text,
                separator_mode=policy.separator_mode,
                numeric_range=policy.numeric_range,
                declared_format=policy.declared_format,
            )
        valid = outcome.parse_status == "OK"
        if valid and policy.precision_min is not None:
            fraction = (outcome.normalized_value or "").partition(".")[2]
            valid = len(fraction) >= policy.precision_min
        return valid, candidate_text, outcome.normalized_value if valid else None

    def read_cursor(
        self,
        cursor: tuple[int, int],
        box_size: tuple[int, int],
        *,
        policy: OcrPolicy,
        snap_radius_px: float,
    ) -> Reading:
        width, height = box_size
        zone = (cursor[0] - width // 2, cursor[1] - height // 2, width, height)
        image = self.capture_provider(zone)
        return self.read_cursor_image(
            image, policy=policy, snap_radius_px=snap_radius_px
        )

    def read_cursor_image(
        self,
        image,
        *,
        policy: OcrPolicy,
        snap_radius_px: float,
        _allow_low_confidence_retry: bool = True,
    ) -> Reading:
        """Read an already-captured cursor box with the production policy.

        This lets deterministic image proof exercise the exact same spatial
        candidate and consensus path as live screen capture without requiring
        a desktop cursor or screen grab.
        """
        width, height = image.size
        candidates = self.cursor_candidate_provider(image, policy)
        usable = []
        for candidate in candidates:
            if candidate.confidence < policy.confidence_min:
                continue
            if (
                policy.numeric_range is not None
                and not policy.numeric_range[0] <= candidate.normalized_value <= policy.numeric_range[1]
            ):
                continue
            usable.append(candidate)
        if policy.consensus_min > 1 and any(item.variant_name for item in usable):
            grouped: dict[float, list[CursorOcrCandidate]] = {}
            for candidate in usable:
                grouped.setdefault(candidate.normalized_value, []).append(candidate)
            agreed: list[tuple[CursorOcrCandidate, int]] = []
            for group in grouped.values():
                for cluster in self._spatial_candidate_clusters(group):
                    support = len({item.variant_name for item in cluster})
                    if support < policy.consensus_min:
                        continue
                    representative = min(
                        cluster,
                        key=lambda item: (
                            sum(
                                self._center_distance_squared(item, other)
                                for other in cluster
                            ),
                            -item.confidence,
                        ),
                    )
                    agreed.append((
                        CursorOcrCandidate(
                            representative.raw_text,
                            representative.normalized_value,
                            max(item.confidence for item in cluster),
                            representative.bbox,
                            representative.rotation_angle,
                            "consensus",
                            representative.psm,
                        ),
                        support,
                    ))
            # Resolve evidence only within one physical label. Spatially
            # separate equal values remain separate candidates.  Two values
            # with comparable support are ambiguous and fail closed.  A
            # clearly dominant reading, however, must not be discarded merely
            # because a smaller group contains a punctuation hallucination.
            selected: list[CursorOcrCandidate] = []
            support_by_candidate = {candidate: support for candidate, support in agreed}
            for location in self._spatial_candidate_clusters(
                [candidate for candidate, _support in agreed]
            ):
                ranked = sorted(
                    location,
                    key=lambda candidate: (
                        support_by_candidate[candidate], candidate.confidence,
                    ),
                    reverse=True,
                )
                leader = ranked[0]
                if len(ranked) > 1:
                    runner_up = ranked[1]
                    if (
                        leader.normalized_value != runner_up.normalized_value
                        and support_by_candidate[leader]
                        < support_by_candidate[runner_up] * 2
                    ):
                        continue
                selected.append(leader)
            usable = selected
        evidence = [
            candidate.as_evidence(index) for index, candidate in enumerate(usable)
        ]
        service = ElevationUnderCursorService(
            SpatialCandidateIndex(evidence), snap_radius_px=snap_radius_px
        )
        suggestion = service.suggest(
            PixelPoint(width / 2, height / 2),
            capture_mode=civil_contracts.EXISTING_GROUND,
        )
        if not suggestion.can_capture or suggestion.evidence is None:
            # Keep the measured high-confidence policy as the normal path.
            # A few tightly rotated low-contrast labels only expose seven
            # spatially consistent readings just below that gate.  Retrying
            # only an otherwise empty result at 0.40 still requires the same
            # independent consensus and dominant-value safeguards; it never
            # replaces a successful high-confidence read.
            if _allow_low_confidence_retry and policy.confidence_min > 0.40:
                return self.read_cursor_image(
                    image,
                    policy=replace(policy, confidence_min=0.40),
                    snap_radius_px=snap_radius_px,
                    _allow_low_confidence_retry=False,
                )
            raise OcrConfidenceError("OCR found no numeric candidate near the cursor")
        selected = suggestion.evidence
        png = self._png_bytes(image)
        return Reading(
            selected.detected_text,
            selected.text_confidence,
            hashlib.sha256(png).hexdigest(),
            png,
            True,
        )

    @staticmethod
    def _center_distance_squared(
        first: "CursorOcrCandidate", second: "CursorOcrCandidate"
    ) -> float:
        return (
            (first.bbox.center.x - second.bbox.center.x) ** 2
            + (first.bbox.center.y - second.bbox.center.y) ** 2
        )

    @classmethod
    def _spatial_candidate_clusters(
        cls,
        candidates: list["CursorOcrCandidate"],
        *,
        radius_px: float = 20.0,
    ) -> list[list["CursorOcrCandidate"]]:
        """Complete-link clusters whose members all describe one location.

        Complete-link membership prevents a chain of slightly shifted OCR
        boxes from bridging two neighbouring labels. Splitting uncertain
        evidence is deliberately safer than manufacturing consensus.
        """

        clusters: list[list[CursorOcrCandidate]] = []
        radius_squared = radius_px ** 2
        ordered = sorted(
            candidates,
            key=lambda item: (
                item.bbox.center.x,
                item.bbox.center.y,
                item.normalized_value,
                item.variant_name,
                item.psm,
            ),
        )
        for candidate in ordered:
            eligible = [
                cluster for cluster in clusters
                if all(
                    cls._center_distance_squared(candidate, member)
                    <= radius_squared
                    for member in cluster
                )
            ]
            if not eligible:
                clusters.append([candidate])
                continue
            cluster = min(
                eligible,
                key=lambda items: sum(
                    cls._center_distance_squared(candidate, member)
                    for member in items
                ) / len(items),
            )
            cluster.append(candidate)
        return clusters

    def _cursor_candidates_tesseract(
        self, image, policy: OcrPolicy
    ) -> tuple["CursorOcrCandidate", ...]:
        if self.executable is None:
            raise OcrUnavailableError(
                "Cursor OCR requires Tesseract so confidence can be enforced"
            )
        from PIL import Image, ImageOps

        original = image.convert("RGB")
        if sum(original.getpixel((0, 0))) / 3 < 128:
            original = ImageOps.invert(original)
        # Rotation around a tight cursor crop clips the very labels that are
        # nearest the pointer.  Give every variant the same local border, then
        # translate its evidence back into the original cursor coordinates.
        border = 16
        source = ImageOps.expand(
            original, border=border, fill=original.getpixel((0, 0))
        )
        prepared_variants = []
        variant_metadata: dict[str, tuple[int, int]] = {}
        for angle in policy.rotation_angles:
            fill = source.getpixel((0, 0))
            rotated = source if angle == 0 else source.rotate(
                angle, expand=False, fillcolor=fill
            )
            variants = [(f"color@{angle}", rotated)]
            if policy.binarize:
                gray = ImageOps.autocontrast(rotated.convert("L"))
                variants.append((f"gray@{angle}", gray))
                for cutoff in (125, 155, 185):
                    variants.append((
                        f"binary-{cutoff}@{angle}",
                        gray.point(
                            lambda pixel, value=cutoff: 255 if pixel >= value else 0
                        ),
                    ))
            factor = policy.upscale
            for variant_name, variant in variants:
                prepared = variant.resize(
                    (variant.width * factor, variant.height * factor),
                    resample=Image.Resampling.LANCZOS,
                )
                prepared_variants.append((variant_name, prepared))
                variant_metadata[variant_name] = (angle, factor)
        candidates: list[CursorOcrCandidate] = []
        for variant_name, psm, tokens in self._tesseract_passes(
            prepared_variants, policy
        ):
            angle, factor = variant_metadata[variant_name]
            for token in tokens:
                raw = token.text.strip()
                if not raw:
                    continue
                confidence = token.confidence / 100.0
                valid, _normalized_text, normalized = self._parse_candidate(raw, policy)
                if not valid or normalized is None or confidence < 0:
                    continue
                left = token.left / factor
                top = token.top / factor
                width = token.width / factor
                height = token.height / factor
                rotated_bbox = Rect(left, top, left + width, top + height)
                mapped_bbox = self._source_bbox(
                    rotated_bbox, angle, source.width, source.height
                )
                candidates.append(CursorOcrCandidate(
                    normalized,
                    float(normalized),
                    confidence,
                    Rect(
                        mapped_bbox.x0 - border,
                        mapped_bbox.y0 - border,
                        mapped_bbox.x1 - border,
                        mapped_bbox.y1 - border,
                    ),
                    angle,
                    variant_name,
                    psm,
                ))
        return tuple(candidates)

    @staticmethod
    def _source_bbox(rect: Rect, angle: int, width: int, height: int) -> Rect:
        """Map an expand=False rotated-image box back to source coordinates."""

        if angle == 0:
            return rect
        center_x = width / 2.0
        center_y = height / 2.0
        radians = math.radians(angle)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        source_points = []
        for x, y in (
            (rect.x0, rect.y0), (rect.x1, rect.y0),
            (rect.x1, rect.y1), (rect.x0, rect.y1),
        ):
            dx = x - center_x
            dy = y - center_y
            source_points.append((
                center_x + cosine * dx - sine * dy,
                center_y + sine * dx + cosine * dy,
            ))
        xs = [max(0.0, min(float(width), point[0])) for point in source_points]
        ys = [max(0.0, min(float(height), point[1])) for point in source_points]
        return Rect(min(xs), min(ys), max(xs), max(ys))

    def _ocr_windows(self, image, digest: str, png: bytes) -> Reading:
        temporary_path: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as temporary:
                temporary_path = Path(temporary.name)
                image.save(temporary, format="PNG")
            result = WindowsOcrAdapter(self.repository_root).extract(temporary_path)
            confidences = [
                word.confidence
                for line in result.lines
                for word in line.words
                if word.confidence is not None
            ]
            confidence = None if not confidences else sum(confidences) / len(confidences)
            return Reading(result.raw_text, confidence, digest, png, True)
        finally:
            if temporary_path is not None:
                temporary_path.unlink(missing_ok=True)


@dataclass(frozen=True)
class CursorOcrCandidate:
    raw_text: str
    normalized_value: float
    confidence: float
    bbox: Rect
    rotation_angle: int
    variant_name: str = ""
    psm: int = 0

    def as_evidence(self, index: int) -> CandidateEvidence:
        return CandidateEvidence(
            candidate_id=f"screen-cursor-{index:04d}",
            page_index=0,
            page_label="screen",
            pixel=self.bbox.center,
            elevation=self.normalized_value,
            likely_type=civil_contracts.EXISTING_GROUND,
            source_method="SCREEN_CURSOR_OCR",
            detected_text=self.raw_text,
            normalized_text=str(self.normalized_value),
            text_confidence=self.confidence,
            symbol_type="NONE",
            symbol_confidence=None,
            association_confidence=None,
            classification_confidence=self.confidence,
            reasons=(f"OCR rotation {self.rotation_angle} degrees",),
            text_bbox=self.bbox.to_dict(),
            alternative_associations=(),
            rejected=False,
            rejection_category="",
        )


def current_cursor_position() -> tuple[int, int]:
    if sys.platform != "win32":
        raise OcrUnavailableError("live cursor capture requires Windows")
    import ctypes

    class Point(ctypes.Structure):
        _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

    point = Point()
    if not ctypes.windll.user32.GetCursorPos(ctypes.byref(point)):
        raise OcrUnavailableError("Windows GetCursorPos failed")
    return int(point.x), int(point.y)


class DefaultReader:
    def __init__(
        self,
        screen: ScreenOcrBackend | None = None,
        *,
        cursor_position_provider: Callable[[], tuple[int, int]] = current_cursor_position,
    ) -> None:
        self.screen = screen or ScreenOcrBackend()
        self.cursor_position_provider = cursor_position_provider

    def __call__(
        self, column: str, source: ChannelSource, context: dict[str, Any]
    ) -> Reading:
        if source.source_type == "screen_zone_ocr":
            assert source.zone is not None
            return self.screen.read_zone(
                source.zone,
                policy=OcrPolicy(
                    separator_mode=source.decimal_separator,
                    numeric=source.data_type != "text",
                    numeric_range=source.numeric_range,
                    declared_format=source.declared_format,
                    precision_min=source.precision_min,
                ),
            )
        if source.source_type == "screen_cursor_ocr":
            return self.screen.read_cursor(
                self.cursor_position_provider(),
                source.cursor_box_size,
                policy=cursor_ocr_policy(source),
                snap_radius_px=source.cursor_snap_radius_px,
            )
        if source.source_type in {"manual", "plan_click", "plan_label_ocr"}:
            value = context.get(column)
            if value is None:
                raise ValueError(f"{column} requires a capture-time value")
            confidence = context.get(f"{column}_confidence")
            return Reading(
                str(value), confidence,
                ocr_executed=source.source_type == "plan_label_ocr",
            )
        if source.source_type == "clipboard":
            import tkinter as tk

            root = tk.Tk()
            root.withdraw()
            try:
                return Reading(root.clipboard_get(), None, ocr_executed=False)
            finally:
                root.destroy()
        raise ValueError(f"unsupported source type {source.source_type}")


def cursor_ocr_policy(source: ChannelSource) -> OcrPolicy:
    """The measured elevation policy shared by production and proof harnesses."""
    return OcrPolicy(
        separator_mode=source.decimal_separator,
        numeric=True,
        numeric_range=source.numeric_range,
        declared_format=source.declared_format,
        precision_min=source.precision_min,
        consensus_min=7,
        confidence_min=0.60,
        psm_modes=(6, 7),
        rotation_angles=(
            0, -2, 2, -5, 5, -8, 8, -10, 10, -12, 12, -15, 15,
            -20, 20, -25, 25, -30, 30,
        ),
        upscale=2,
    )
