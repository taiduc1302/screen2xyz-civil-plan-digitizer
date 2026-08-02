"""Review session: candidates, immutable raw OCR, corrections, approval.

State rules enforced here:

- raw OCR text is written once per candidate and never mutated;
- original parsed values are preserved even after correction;
- corrections are stored separately and pass through the same parser and
  validator as OCR output;
- only explicitly APPROVED candidates can be exported;
- no automatic approval exists anywhere in this module.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from screen2xyz_lab.evidence import atomic_write_bytes, atomic_write_json, write_manifest
from screen2xyz_lab.exporters import csv_bytes, formula_safe_display, xyz_bytes
from screen2xyz_lab.parser import parse_reading
from screen2xyz_lab.pipeline import run_ocr
from screen2xyz_lab.temporal import TemporalClassifier
from screen2xyz_lab.validator import validate_reading

from .config import (
    EXPORT_METADATA,
    M1_VALIDATION_CONFIG,
    OCR_TIMEOUT_SECONDS,
    OUTPUT_CLASSIFICATION,
)
from .intake import SourceImage, validate_source_png

APPROVED = "APPROVED"
REJECTED = "REJECTED"
PENDING = "PENDING"

CANDIDATE_CSV_HEADER = (
    "candidate_id", "sequence", "source_name", "source_sha256", "longitude",
    "latitude", "elevation_m", "source_crs", "axis_order", "elevation_unit",
    "vertical_reference", "corrected", "decision",
)


class SessionError(RuntimeError):
    """A review-state rule was violated."""


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    sequence: int
    source_name: str
    source_sha256: str
    ocr_status: str
    ocr_error_code: str
    raw_text: str
    parsed_latitude: str
    parsed_longitude: str
    parsed_elevation_m: str
    validation_codes: tuple[str, ...]
    classification: str
    primary_code: str
    reference_candidate_id: str
    corrected_latitude: str = ""
    corrected_longitude: str = ""
    corrected_elevation_m: str = ""
    correction_codes: tuple[str, ...] = ()
    decision: str = PENDING
    decided_at: str = ""
    exported: bool = False

    @property
    def effective_latitude(self) -> str:
        return self.corrected_latitude or self.parsed_latitude

    @property
    def effective_longitude(self) -> str:
        return self.corrected_longitude or self.parsed_longitude

    @property
    def effective_elevation_m(self) -> str:
        return self.corrected_elevation_m or self.parsed_elevation_m

    @property
    def has_correction(self) -> bool:
        return bool(
            self.corrected_latitude or self.corrected_longitude or self.corrected_elevation_m
        )

    def approvable(self) -> bool:
        if self.has_correction:
            return not self.correction_codes
        return not self.validation_codes and bool(
            self.parsed_latitude and self.parsed_longitude and self.parsed_elevation_m
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_triplet(latitude: str, longitude: str, elevation: str):
    """Run candidate values through the same parser used for OCR text."""

    text = f"LAT: {latitude} LON: {longitude} ELEV: {elevation} m"
    parsed = parse_reading(text)
    codes = validate_reading(parsed, M1_VALIDATION_CONFIG)
    return parsed, codes


class ReviewSession:
    """One explicit user run over one or more selected PNG files."""

    def __init__(
        self,
        repository_root: Path,
        run_root: Path,
        run_id: str,
        *,
        ocr: Callable[..., Any] | None = None,
        now: Callable[[], str] = _utc_now,
    ) -> None:
        if not run_id or any(ch in run_id for ch in "\\/:*?\"<>| \t"):
            raise SessionError("run id must be a simple filesystem-safe token")
        self.repository_root = repository_root
        self.run_dir = run_root / run_id
        if self.run_dir.exists():
            raise SessionError(f"run directory already exists: {run_id}")
        self.run_dir.mkdir(parents=True)
        self.run_id = run_id
        self._ocr = ocr or (
            lambda image: run_ocr(repository_root, image, timeout_seconds=OCR_TIMEOUT_SECONDS)
        )
        self._now = now
        self._temporal = TemporalClassifier()
        self._candidates: list[Candidate] = []
        self.created_at = now()
        # Set to True only when the user explicitly invokes the optional
        # external-assistance boundary; recorded in the run summary.
        self.external_ai_used = False

    # -- intake and processing -------------------------------------------

    def process_image(self, path: Path) -> Candidate:
        """Validate, OCR, parse, validate, and classify one selected PNG."""

        source: SourceImage = validate_source_png(path)
        sequence = len(self._candidates) + 1
        candidate_id = f"C{sequence:03d}"
        observation = self._ocr(source.path)
        if observation.status == "SUCCESS":
            parsed = parse_reading(observation.raw_text)
            codes = validate_reading(parsed, M1_VALIDATION_CONFIG)
        else:
            parsed = parse_reading("")
            codes = (observation.error_code or "OCR_FAILURE",)
        triplet = (
            (parsed.latitude, parsed.longitude, parsed.elevation_m)
            if not codes
            and parsed.latitude is not None
            and parsed.longitude is not None
            and parsed.elevation_m is not None
            else None
        )
        temporal = self._temporal.classify(candidate_id, triplet, codes)
        candidate = Candidate(
            candidate_id=candidate_id,
            sequence=sequence,
            source_name=source.display_name,
            source_sha256=source.sha256,
            ocr_status=observation.status,
            ocr_error_code=observation.error_code,
            raw_text=observation.raw_text,
            parsed_latitude=format(parsed.latitude, ".6f") if parsed.latitude is not None else "",
            parsed_longitude=format(parsed.longitude, ".6f") if parsed.longitude is not None else "",
            parsed_elevation_m=format(parsed.elevation_m, ".2f") if parsed.elevation_m is not None else "",
            validation_codes=temporal.all_codes,
            classification=temporal.classification,
            primary_code=temporal.primary_code,
            reference_candidate_id=temporal.reference_scenario_id,
        )
        self._candidates.append(candidate)
        # Immutable raw OCR record: written exactly once, never replaced.
        atomic_write_json(
            self.run_dir / "raw" / f"{candidate_id}.json",
            {
                "candidate_id": candidate_id,
                "source_name": source.display_name,
                "source_sha256": source.sha256,
                "source_bytes": source.byte_size,
                "source_width_px": source.width_px,
                "source_height_px": source.height_px,
                "ocr_status": observation.status,
                "ocr_engine": observation.engine,
                "ocr_language": observation.language,
                "raw_text": observation.raw_text,
            },
        )
        return candidate

    # -- review state ----------------------------------------------------

    def candidates(self) -> tuple[Candidate, ...]:
        return tuple(self._candidates)

    def _index(self, candidate_id: str) -> int:
        for index, candidate in enumerate(self._candidates):
            if candidate.candidate_id == candidate_id:
                return index
        raise SessionError(f"unknown candidate: {candidate_id}")

    def correct(
        self, candidate_id: str, latitude: str, longitude: str, elevation_m: str
    ) -> Candidate:
        """Store a human correction separately from the original values."""

        index = self._index(candidate_id)
        candidate = self._candidates[index]
        if candidate.decision != PENDING:
            raise SessionError("cannot correct a decided candidate; reopen is not supported")
        parsed, codes = _parse_triplet(latitude, longitude, elevation_m)
        if codes:
            updated = replace(candidate, correction_codes=codes)
            self._candidates[index] = updated
            raise SessionError(f"correction rejected by validation: {'|'.join(codes)}")
        updated = replace(
            candidate,
            corrected_latitude=format(parsed.latitude, ".6f"),
            corrected_longitude=format(parsed.longitude, ".6f"),
            corrected_elevation_m=format(parsed.elevation_m, ".2f"),
            correction_codes=(),
        )
        self._candidates[index] = updated
        return updated

    def approve(self, candidate_id: str) -> Candidate:
        """Explicit human approval; never called automatically."""

        index = self._index(candidate_id)
        candidate = self._candidates[index]
        if candidate.decision != PENDING:
            raise SessionError("decision already recorded; decisions are final in M1")
        if not candidate.approvable():
            raise SessionError(
                "candidate is not approvable: correct it first or reject it "
                f"({'|'.join(candidate.correction_codes or candidate.validation_codes) or 'incomplete values'})"
            )
        updated = replace(candidate, decision=APPROVED, decided_at=self._now())
        self._candidates[index] = updated
        return updated

    def reject(self, candidate_id: str) -> Candidate:
        index = self._index(candidate_id)
        if self._candidates[index].decision != PENDING:
            raise SessionError("decision already recorded; decisions are final in M1")
        updated = replace(self._candidates[index], decision=REJECTED, decided_at=self._now())
        self._candidates[index] = updated
        return updated

    # -- export and provenance -------------------------------------------

    def export_approved(self) -> dict[str, Any]:
        """Write approved-only CSV and XYZ plus the provenance package."""

        approved = [c for c in self._candidates if c.decision == APPROVED]
        rows = [
            {
                "candidate_id": c.candidate_id,
                "sequence": c.sequence,
                "source_name": formula_safe_display(c.source_name),
                "source_sha256": c.source_sha256,
                "longitude": c.effective_longitude,
                "latitude": c.effective_latitude,
                "elevation_m": c.effective_elevation_m,
                "source_crs": EXPORT_METADATA["source_crs"],
                "axis_order": EXPORT_METADATA["axis_order"],
                "elevation_unit": EXPORT_METADATA["elevation_unit"],
                "vertical_reference": EXPORT_METADATA["vertical_reference"],
                "corrected": "true" if c.has_correction else "false",
                "decision": c.decision,
            }
            for c in sorted(approved, key=lambda c: c.sequence)
        ]
        # replace=True: re-export is a legitimate user action after deciding
        # further pending candidates; the export always reflects the full
        # current approved set, and raw records remain write-once.
        atomic_write_bytes(
            self.run_dir / "approved_points.csv",
            csv_bytes(rows, CANDIDATE_CSV_HEADER),
            replace=True,
        )
        atomic_write_bytes(self.run_dir / "approved_points.xyz", xyz_bytes(rows), replace=True)
        for index, candidate in enumerate(self._candidates):
            self._candidates[index] = replace(
                candidate, exported=candidate.decision == APPROVED
            )
        summary = self.write_state()
        write_manifest(self.run_dir, self.run_dir, replace=True)
        return summary

    def write_state(self) -> dict[str, Any]:
        """Persist the full candidate state and run summary."""

        state = [
            {
                "candidate_id": c.candidate_id,
                "sequence": c.sequence,
                "source_name": c.source_name,
                "source_sha256": c.source_sha256,
                "ocr_status": c.ocr_status,
                "ocr_error_code": c.ocr_error_code,
                "raw_text": c.raw_text,
                "raw_text_display": formula_safe_display(c.raw_text),
                "parsed_latitude": c.parsed_latitude,
                "parsed_longitude": c.parsed_longitude,
                "parsed_elevation_m": c.parsed_elevation_m,
                "validation_codes": list(c.validation_codes),
                "classification": c.classification,
                "primary_code": c.primary_code,
                "reference_candidate_id": c.reference_candidate_id,
                "corrected_latitude": c.corrected_latitude,
                "corrected_longitude": c.corrected_longitude,
                "corrected_elevation_m": c.corrected_elevation_m,
                "correction_codes": list(c.correction_codes),
                "decision": c.decision,
                "decided_at": c.decided_at,
                "exported": c.exported,
            }
            for c in self._candidates
        ]
        summary = {
            "schema_version": "1.0",
            "run_id": self.run_id,
            "created_at": self.created_at,
            "written_at": self._now(),
            "candidate_count": len(self._candidates),
            "approved_count": sum(c.decision == APPROVED for c in self._candidates),
            "rejected_count": sum(c.decision == REJECTED for c in self._candidates),
            "pending_count": sum(c.decision == PENDING for c in self._candidates),
            "corrected_count": sum(c.has_correction for c in self._candidates),
            "external_ai_used": self.external_ai_used,
            "output_classification": OUTPUT_CLASSIFICATION,
            "export_metadata": dict(EXPORT_METADATA),
        }
        atomic_write_json(self.run_dir / "candidates.json", state, replace=True)
        atomic_write_json(self.run_dir / "run_summary.json", summary, replace=True)
        return summary


def load_state(run_dir: Path) -> dict[str, Any]:
    return {
        "candidates": json.loads((run_dir / "candidates.json").read_text(encoding="utf-8")),
        "summary": json.loads((run_dir / "run_summary.json").read_text(encoding="utf-8")),
    }
