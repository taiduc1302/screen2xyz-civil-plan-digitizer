"""Public generic M2 parser (number/text/auto) — no baseline imports.

Implements data contracts §5: bounded raw preservation, the closed Unicode
sign policy, single-candidate number extraction (multiple candidates are
never auto-picked), separator modes, range/precision validation, and the
conservative auto mode.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

from .contracts import RAW_OCR_MAX_BYTES

# Minus-like glyphs accepted only directly adjacent to the first digit and
# normalized to ASCII '-'.
ACCEPTED_MINUS_VARIANTS = frozenset(
    "−‐‑‒–—﹣－"
)

_TOKEN_RE = re.compile(r"[+-]?\d[\d.,]*")
_POINT_PLAIN = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_POINT_GROUPED = re.compile(r"^[+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?$")
_COMMA_PLAIN = re.compile(r"^[+-]?\d+(?:,\d+)?$")
_COMMA_GROUPED = re.compile(r"^[+-]?\d{1,3}(?:\.\d{3})+(?:,\d+)?$")


@dataclass(frozen=True)
class RawBound:
    raw_text: str
    raw_truncated: bool
    raw_original_utf8_bytes: int | None


@dataclass(frozen=True)
class ParseOutcome:
    parse_status: str
    normalized_value: str | None = None
    value_kind: str = "number"
    sign_normalized: bool = False
    original_sign_code_point: str | None = None
    warning_codes: tuple[str, ...] = field(default_factory=tuple)


def bound_raw(text: str) -> RawBound:
    """Longest complete-code-point UTF-8 prefix within the byte bound."""

    data = text.encode("utf-8")
    if len(data) <= RAW_OCR_MAX_BYTES:
        return RawBound(text, False, len(data))
    # Keep the longest prefix ending on a complete code point. Only walk back
    # if the byte JUST PAST the bound is a continuation byte (i.e. a character
    # straddles the boundary); if data[bound] starts a new code point, the
    # prefix is already whole and must be kept intact.
    cut = RAW_OCR_MAX_BYTES
    if (data[cut] & 0xC0) == 0x80:
        while cut > 0 and (data[cut - 1] & 0xC0) == 0x80:
            cut -= 1
        if cut > 0:  # drop the incomplete lead byte
            cut -= 1
    prefix = data[:cut]
    return RawBound(prefix.decode("utf-8"), True, len(data))


def _is_disallowed_sign(character: str) -> bool:
    if character in "+-" or character in ACCEPTED_MINUS_VARIANTS:
        return False
    if unicodedata.category(character) == "Pd":
        return True
    try:
        name = unicodedata.name(character)
    except ValueError:
        return False
    upper = name.upper()
    return "MINUS" in upper or "PLUS" in upper


def _sign_glyph_violation(text: str) -> bool:
    """Closed rejection rule: a disallowed sign-like glyph, or any sign
    separated from its digit by whitespace, poisons the numeric parse."""

    for index, character in enumerate(text):
        rest = text[index + 1:]
        follows_digit_maybe_ws = bool(re.match(r"\s*\d", rest))
        if _is_disallowed_sign(character) and follows_digit_maybe_ws:
            return True
        if (character in "+-" or character in ACCEPTED_MINUS_VARIANTS):
            if re.match(r"\s+\d", rest):
                return True
    return False


def _normalize_signs(text: str) -> tuple[str, bool, str | None]:
    changed = False
    original: str | None = None
    output = []
    for index, character in enumerate(text):
        if character in ACCEPTED_MINUS_VARIANTS and index + 1 < len(text) \
                and text[index + 1].isdigit():
            output.append("-")
            changed = True
            original = original or f"U+{ord(character):04X}"
        else:
            output.append(character)
    return "".join(output), changed, original


def _letter_adjacent(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return before.isalpha() or after.isalpha()


def _interpret(token: str, mode: str) -> str | None:
    """Return canonical '-?d+(.d+)?' or None if token invalid in mode."""

    def canonical_point(value: str) -> str:
        return value.replace(",", "")

    def canonical_comma(value: str) -> str:
        return value.replace(".", "").replace(",", ".")

    if mode == "point":
        if _POINT_PLAIN.match(token):
            return token
        if _POINT_GROUPED.match(token):
            return canonical_point(token)
        return None
    if mode == "comma":
        if _COMMA_PLAIN.match(token):
            return canonical_comma(token)
        if _COMMA_GROUPED.match(token):
            return canonical_comma(token)
        return None
    point = _interpret(token, "point")
    comma = _interpret(token, "comma")
    if point is not None and comma is not None:
        return point if point == comma else None
    return point if point is not None else comma


def parse_number(
    text: str,
    *,
    separator_mode: str = "point",
    numeric_range: tuple[float, float] | None = None,
    precision_max: int | None = None,
) -> ParseOutcome:
    stripped = text.strip()
    if not stripped:
        return ParseOutcome("NO_NUMBER")
    if _sign_glyph_violation(stripped):
        return ParseOutcome("MALFORMED_NUMBER")
    working, sign_normalized, original_cp = _normalize_signs(stripped)

    candidates: list[str] = []
    malformed = False
    for match in _TOKEN_RE.finditer(working):
        token = match.group(0).rstrip(".,")
        # _TOKEN_RE requires a literal digit right after the optional sign,
        # so a leading decimal/thousands separator with no digit before it
        # (".5", "-.5", ",5") is excluded from the match entirely and
        # finditer silently re-anchors on the digit AFTER it - producing a
        # confidently-reported OK value at the wrong magnitude (".5" -> "5")
        # and, for "-.5", losing the sign too (independent audit BLOCKER).
        # Whether a leading "." was meant as a decimal point or unrelated
        # punctuation (an abbreviation, a sentence boundary) is genuinely
        # ambiguous - fail closed rather than guess.
        if match.start() > 0 and working[match.start() - 1] in ".,":
            malformed = True
            continue
        if _letter_adjacent(working, match.start(), match.end()):
            malformed = True
            continue
        canonical = _interpret(token, separator_mode)
        if canonical is None:
            malformed = True
            continue
        candidates.append(canonical)
    if len(candidates) > 1:
        return ParseOutcome("AMBIGUOUS_MULTIPLE_NUMBERS",
                            sign_normalized=sign_normalized,
                            original_sign_code_point=original_cp)
    if malformed:
        return ParseOutcome("MALFORMED_NUMBER",
                            sign_normalized=sign_normalized,
                            original_sign_code_point=original_cp)
    if not candidates:
        return ParseOutcome("NO_NUMBER")
    value = candidates[0]
    if value.startswith("+"):
        value = value[1:]
    fraction = value.partition(".")[2]
    if precision_max is not None and len(fraction) > precision_max:
        return ParseOutcome("MALFORMED_NUMBER",
                            sign_normalized=sign_normalized,
                            original_sign_code_point=original_cp)
    if numeric_range is not None:
        low, high = numeric_range
        if not (low <= float(value) <= high):
            return ParseOutcome("OUT_OF_RANGE", normalized_value=None,
                                sign_normalized=sign_normalized,
                                original_sign_code_point=original_cp)
    return ParseOutcome("OK", normalized_value=value,
                        sign_normalized=sign_normalized,
                        original_sign_code_point=original_cp)


_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WS_RE = re.compile(r"\s+")


def parse_text(text: str) -> ParseOutcome:
    normalized = _WS_RE.sub(" ", _CONTROL_RE.sub(" ", text)).strip()
    return ParseOutcome("OK", normalized_value=normalized, value_kind="text")


_RESIDUE_OK_RE = re.compile(r"^[\s\.,;:|/\\()\[\]{}%°'\"+-]*$")


def parse_auto(
    text: str,
    *,
    separator_mode: str = "point",
    numeric_range: tuple[float, float] | None = None,
    precision_max: int | None = None,
) -> ParseOutcome:
    stripped = text.strip()
    if not stripped:
        return ParseOutcome("NO_NUMBER", value_kind="text")
    # Owner ask (2026-07-21, competition deadline): "auto" is the
    # universal type, so it must understand a lat/long reading too - not
    # just plain numbers and text. Structural detection first (the same
    # hint heuristic), then the STRICT coordinate parser - which either
    # produces a range-validated decimal-degrees value, flags a physically
    # impossible one (SUSPECT_GLYPH_CONFUSION - a retained, safe error),
    # or declines (MALFORMED - falls through to the existing number/text
    # logic below, ending as preserved text). Trailing OCR noise glyphs
    # (bullets and the U+FFFD replacement char) are stripped before the
    # strict parse - a mechanical cleanup of characters that can never be
    # part of coordinate grammar, not a value guess.
    if looks_like_coordinate(stripped):
        candidate = stripped.rstrip("•·� \t")
        outcome = parse_coordinate(candidate)
        if outcome.parse_status == "SUSPECT_GLYPH_CONFUSION":
            return outcome
        if outcome.parse_status == "OK":
            # Adversarial review finding: this function's own contract two
            # lines above ("its range/precision result... is surfaced,
            # never masked") was silently bypassed for the coordinate
            # branch - a configured numeric_range/precision_max must apply
            # here exactly as it does on the plain-number path below.
            value = outcome.normalized_value
            fraction = value.partition(".")[2] if value else ""
            if precision_max is not None and len(fraction) > precision_max:
                return ParseOutcome("MALFORMED_NUMBER")
            if numeric_range is not None:
                low, high = numeric_range
                if not (low <= float(value) <= high):
                    return ParseOutcome("OUT_OF_RANGE")
            return outcome
    if not _sign_glyph_violation(stripped):
        working, _, _ = _normalize_signs(stripped)
        matches = list(_TOKEN_RE.finditer(working))
        if len(matches) == 1:
            match = matches[0]
            residue = working[:match.start()] + working[match.end():]
            clean = (not _letter_adjacent(working, match.start(), match.end())
                     and _RESIDUE_OK_RE.match(residue))
            if clean:
                # A single clean numeric candidate resolves as a number: its
                # range/precision result (incl. OUT_OF_RANGE / MALFORMED_NUMBER)
                # is surfaced, never masked as valid text.
                return parse_number(
                    stripped, separator_mode=separator_mode,
                    numeric_range=numeric_range, precision_max=precision_max)
    return parse_text(text)


# Real-target finding (owner test against Google Earth's coordinate
# readout, 2026-07-19; see M2_IMPLEMENTATION_REPORT.md Phase 1/§5k):
# Windows OCR reliably misread the degree symbol (°) as the digit "0" for
# this class of on-screen text - in EVERY successful real-target
# recognition this session produced. A plain "number" field fed
# "49°08'20.06"N" garbled to "49008'20.06"N" would find MULTIPLE digit
# runs (49008, 20.06) and correctly refuse as AMBIGUOUS_MULTIPLE_NUMBERS -
# but if the OWNER scoped a field tightly enough to isolate what should be
# just the degrees (e.g. "49°" alone), the SAME corruption collapses to a
# single clean digit run ("490"/"49008" depending on what else the tight
# region also captured) that a plain number parser accepts with
# `parse_status: OK` - silently 10-1000x too large. Deliberately does NOT
# try to detect or undo the specific ° -> 0 confusion (a leading-digit-run
# "490" is indistinguishable from a genuinely-typed 490 by content alone -
# guessing which one happened would just move the silent-wrongness
# problem, not fix it). Instead: structural DMS tokenization (degrees is
# whatever leads up to the first '/′ separator, whether or not a real °
# preceded it - so a corrupted or entirely-dropped degree symbol is
# absorbed into that leading run exactly as OCR produced it) plus range
# validation (degrees <=90 for N/S, <=180 for E/W or no hemisphere;
# minutes and seconds <60) - the corruption is caught because 49008 (or
# 490) fails the degrees bound, not because the parser recognized the
# specific glyph mistake. A real ° character is also accepted (optional in
# the pattern) for the case where OCR gets it right.
# Adversarial review 2026-07-21 (12 confirmed findings): the original
# pattern made ° optional even BETWEEN degrees and minutes, which let the
# regex engine backtrack a plain digit run into an arbitrary deg/min
# split with no separator at all - "12'10\"N" (feet-inches!) matched as
# deg=1/min=2/sec=10 -> 1.036111, and "20.41'18.46\"N" (° misread as '.')
# as deg=20.4/min=1 -> confidently wrong values on the clean OK path.
# Minutes are now reachable ONLY through a literal ° - the corrupted
# (°->0) shape is handled by the separate _CORRUPTED_DMS_RE +
# _recover_corrupted_degrees path below, never by backtracking here.
_COORD_RE = re.compile(
    r"^\s*(?P<sign>[+-])?\s*"
    r"(?P<deg>\d+(?:\.\d+)?)\s*"
    r"(?:°\s*"
    r"(?:(?P<min>\d+(?:\.\d+)?)\s*[′']\s*"
    r"(?:(?P<sec>\d+(?:\.\d+)?)\s*(?:″|\"|'')\s*)?)?)?"
    r"(?P<hemi>[NSEWnsew])?\s*$"
)

# The °->0-corrupted shape: a PURE digit run (>=4 digits - degrees, the
# misread '0', and two minutes digits) followed by real minutes/seconds
# punctuation. The hemisphere letter is optional for RECOGNIZING the
# shape (so a no-hemisphere variant is still flagged SUSPECT rather than
# falling to MALFORMED), but recovery itself requires it.
_CORRUPTED_DMS_RE = re.compile(
    r"^\s*(?P<sign>[+-])?\s*"
    r"(?P<run>\d{4,})\s*[′']\s*"
    r"(?P<sec>\d+(?:\.\d+)?)\s*(?:″|\"|'')\s*"
    r"(?P<hemi>[NSEWnsew])?\s*$"
)


def parse_coordinate(text: str) -> ParseOutcome:
    """Parses ONE lat/long-style value: plain decimal degrees ("49.137"),
    or DMS ("49°08'20.06"N", corrupted-degree-symbol-tolerant as described
    above). Never attempts to split multiple coordinates out of one string
    (e.g. a full "lat long" overlay line) - that structural decomposition,
    if wanted, belongs to a higher layer that knows the field's intended
    scope, not this primitive. A string with leftover content beyond one
    coordinate simply does not match and returns MALFORMED_NUMBER, the
    same failure class a non-numeric string gets from parse_number."""

    stripped = text.strip()
    if not stripped:
        return ParseOutcome("NO_NUMBER")
    match = _COORD_RE.match(stripped)
    if match:
        degrees = float(match.group("deg"))
        minutes = float(match.group("min")) if match.group("min") else 0.0
        seconds = float(match.group("sec")) if match.group("sec") else 0.0
        hemi = (match.group("hemi") or "").upper()
        if minutes >= 60 or seconds >= 60:
            return ParseOutcome("SUSPECT_GLYPH_CONFUSION")
        axis_max = 90.0 if hemi in ("N", "S") else 180.0
        # Adversarial review finding: the axis bound must gate the
        # COMPOSED total (degrees+min/60+sec/3600), not degrees alone -
        # "90°08'20\"N" has a valid 90-degree component but is a real
        # position 8+ minutes past the pole, physically impossible.
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if decimal > axis_max:
            return ParseOutcome("SUSPECT_GLYPH_CONFUSION")
        if match.group("sign") == "-" or hemi in ("S", "W"):
            decimal = -decimal
        return ParseOutcome("OK", normalized_value=f"{decimal:.6f}")
    corrupted = _CORRUPTED_DMS_RE.match(stripped)
    if corrupted:
        # Structurally DMS-shaped (a pure digit run standing in for
        # degrees+degree-symbol, then real minutes/seconds punctuation)
        # but _COORD_RE itself never matches this (no real ° present) -
        # exactly the shape a garbled degree symbol produces. Flagged
        # distinctly from a generic MALFORMED_NUMBER so the owner sees a
        # concrete hint ("looks like an OCR glyph mix-up"), and recovered
        # to a number when - and only when - that recovery is unambiguous.
        recovered = _recover_corrupted_degrees(corrupted)
        if recovered is not None:
            return recovered
        return ParseOutcome("SUSPECT_GLYPH_CONFUSION")
    return ParseOutcome("MALFORMED_NUMBER")


def _recover_corrupted_degrees(
        corrupted: "re.Match[str]") -> ParseOutcome | None:
    """Owner decision (2026-07-21, competition deadline): a full DMS
    reading whose degree symbol OCR misread as the digit '0' must yield a
    NUMERIC value, not only a safe flag - the flag alone left the owner's
    real recordings empty. This is NOT the open-ended glyph-guessing the
    Phase 1 audit rejected: `corrupted` already matched `_CORRUPTED_DMS_RE`
    (a pure digit run, real minutes/seconds punctuation, i.e. the specific
    documented °->0 shape), and this function only decides WHERE in that
    digit run the misread degree symbol actually sits.

    Adversarial review finding: a short run can have MORE THAN ONE '0'
    that could structurally be the misread symbol - e.g. "4008" splits
    validly as either 4°08' or 40°8'. Recovering either guess silently
    would just move the silent-wrongness problem the whole design exists
    to avoid. So every '0' position is tried as a candidate split
    (degrees=run before it, minutes=run after it, 1-2 digits - real
    minutes are never written longer than that); only when EXACTLY ONE
    candidate is physically valid (degrees/minutes/seconds/total all in
    range) does it count as recovered - two or more valid candidates
    means the corruption is genuinely ambiguous and stays flagged, not
    guessed. Requires the hemisphere letter (the strongest context there
    is - a bare digit run alone never recovers). Always labelled with the
    DEGREE_GLYPH_RECOVERED warning code, which flows into the journal/CSV
    next to the preserved raw text and crop, so every recovered value
    stays auditable."""

    hemi = (corrupted.group("hemi") or "").upper()
    if not hemi:
        return None
    seconds = float(corrupted.group("sec"))
    if seconds >= 60:
        return None
    run = corrupted.group("run")
    axis_max = 90.0 if hemi in ("N", "S") else 180.0
    candidates: list[float] = []
    for i, ch in enumerate(run):
        if ch != "0":
            continue
        deg_part, min_part = run[:i], run[i + 1:]
        if not deg_part or not (1 <= len(min_part) <= 2):
            continue
        degrees = float(deg_part)
        minutes = float(min_part)
        if degrees > axis_max or minutes >= 60:
            continue
        decimal = degrees + minutes / 60.0 + seconds / 3600.0
        if decimal > axis_max:
            continue
        candidates.append(decimal)
    if len(candidates) != 1:
        return None
    decimal = candidates[0]
    if corrupted.group("sign") == "-" or hemi in ("S", "W"):
        decimal = -decimal
    return ParseOutcome("OK", normalized_value=f"{decimal:.6f}",
                        warning_codes=("DEGREE_GLYPH_RECOVERED",))


# Real-owner finding (2026-07-19, after Phase 1 shipped): an owner whose
# field was still typed "number" (the default - never auto-changed, by
# design) hit exactly the danger case Phase 1 exists to catch: the
# corrupted DMS text correctly refused as AMBIGUOUS_MULTIPLE_NUMBERS /
# MALFORMED_NUMBER, but the field card's guidance ("redraw a tighter
# region") is actively WRONG advice here - the text is already scoped to
# one coordinate; redrawing tighter cannot fix a degree-symbol misread.
# This is a permissive, UI-hint-only heuristic (deliberately looser than
# _COORD_RE, and tolerant of trailing OCR noise like a stray bullet glyph)
# - it only ever changes what ADVICE is shown, never a parsed value, so it
# carries none of the silent-guessing risk parse_coordinate's own design
# rejected. See value_status_guidance's data_type/raw_text branch.
_LOOKS_LIKE_COORD_RE = re.compile(
    r"\d+\s*[°0]?\s*\d+\s*[′']\s*\d+(?:[.,]\d+)?\s*[″\"']{0,2}\s*[NSEWnsew]"
)


def looks_like_coordinate(text: str) -> bool:
    return bool(_LOOKS_LIKE_COORD_RE.search(text))


# Same day, owner ask: "I need it to recognize not just coordinates but
# also text, numbers, and NON-STANDARD numbers" - i.e. the same class of
# problem (a `number`-typed field whose content genuinely isn't a plain
# number, where the generic "redraw"/"check decimal separator" advice is
# wrong) generalized beyond just coordinates to alphanumeric codes/serial
# numbers (e.g. "SN-4829"). Deliberately conservative to avoid the
# opposite mistake: a clean number with a short trailing unit label
# ("87.05m", "14 m") is NOT a code - redrawing/upscaling is still the
# right fix there, so it is explicitly excluded. Likewise a LABEL prefix
# separated from a clean number by whitespace or ":"/"=" ("Elevation:
# 87.05", "Cursor 49, 22") is excluded - the number itself is clean, the
# fix is redrawing tighter around just it, not switching type. Only
# flagged when a letter is found directly touching a digit (optionally
# joined by '-'/'_', never plain whitespace) - the shape a genuine
# serial/ID code has and a "label: value" pair does not.
_TRAILING_UNIT_RE = re.compile(r"^[+-]?\d[\d.,]*\s*[a-zA-Zµ°%]{1,4}$")
_LETTER_DIGIT_TOUCH_RE = re.compile(r"[A-Za-z][\-_]?\d|\d[\-_]?[A-Za-z]")


def looks_like_alphanumeric_code(text: str) -> bool:
    stripped = text.strip()
    if not stripped or looks_like_coordinate(stripped):
        return False
    if _TRAILING_UNIT_RE.match(stripped):
        return False
    return bool(_LETTER_DIGIT_TOUCH_RE.search(stripped))


def parse_for_source(
    raw: RawBound,
    data_type: str,
    *,
    separator_mode: str = "point",
    numeric_range: tuple[float, float] | None = None,
    precision_max: int | None = None,
    line_part: int | None = None,
) -> ParseOutcome:
    """Full per-source parse honoring the truncation contract.

    `line_part` (Phase 2, M2_IMPLEMENTATION_REPORT.md §5k) supports several
    fields sharing ONE drawn region over a combined overlay line (e.g. a
    lat+long+elev readout on one thin line, where drawing three separate
    pixel-precise sub-regions is impractical). When set, only the
    line_part-th whitespace-separated token of the OCR'd text is parsed -
    everything else about the field (its own data_type, range, precision)
    applies exactly as if that token were the field's entire raw text. A
    region with fewer tokens than requested returns NO_NUMBER, the same
    status an empty/short field already uses - never silently reused from
    a neighbouring token or a prior tick."""

    if raw.raw_truncated:
        return ParseOutcome("INPUT_TRUNCATED",
                            warning_codes=("RAW_OCR_TRUNCATED",))
    text = raw.raw_text
    if line_part is not None:
        tokens = text.split()
        if line_part >= len(tokens):
            return ParseOutcome("NO_NUMBER")
        text = tokens[line_part]
    if data_type == "text":
        return parse_text(text)
    if data_type == "coordinate":
        return parse_coordinate(text)
    if data_type == "auto":
        return parse_auto(text, separator_mode=separator_mode,
                          numeric_range=numeric_range,
                          precision_max=precision_max)
    return parse_number(text, separator_mode=separator_mode,
                        numeric_range=numeric_range,
                        precision_max=precision_max)
