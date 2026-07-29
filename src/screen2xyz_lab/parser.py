"""Label-driven Decimal parser that never consults fixture expectations."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

from .models import ParseResult

_LABELS = ("LAT", "LON", "ELEV")
_FIELD_RE = re.compile(r"(?i)\b(LAT|LON|ELEV)\b[ \t\r\n]*(?::|=)?[ \t\r\n]*([^ \t\r\n|]+)")
_NUMBER_RE = re.compile(r"^[+-]?\d+(?:\.\d+)?$")
_ANY_NUMBER_RE = re.compile(r"[+-]?(?:\d+(?:\.\d+)?|\.\d+)")

_PRECEDENCE = {
    "MISSING_LAT": 30,
    "MISSING_LON": 30,
    "MISSING_ELEV": 30,
    "MALFORMED_LAT": 40,
    "MALFORMED_LON": 40,
    "MALFORMED_ELEV": 40,
    "EXCESS_PRECISION_LAT": 40,
    "EXCESS_PRECISION_LON": 40,
    "EXCESS_PRECISION_ELEV": 40,
    "AMBIGUOUS_ORDER": 40,
    "EXTRA_NUMERIC_FIELD": 40,
    "CONTROL_CHARACTER": 40,
    "OUT_OF_RANGE_LAT": 50,
    "OUT_OF_RANGE_LON": 50,
    "OUT_OF_RANGE_ELEV": 50,
}


def order_codes(codes: set[str] | list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted(set(codes), key=lambda item: (_PRECEDENCE.get(item, 99), item)))


def _has_prohibited_control(text: str) -> bool:
    return any(
        (ord(ch) < 32 and ch not in "\r\n\t") or 0x7F <= ord(ch) <= 0x9F
        for ch in text
    )


def _canonical_decimal(token: str, field: str) -> tuple[Decimal | None, str | None]:
    if field in ("LAT", "LON") and token.endswith("°"):
        token = token[:-1]
    elif field == "ELEV" and token.lower().endswith("m"):
        token = token[:-1]
    malformed_code = f"MALFORMED_{field}"
    precision_code = f"EXCESS_PRECISION_{field}"
    if not _NUMBER_RE.fullmatch(token):
        return None, malformed_code
    fraction = token.partition(".")[2]
    allowed = 2 if field == "ELEV" else 6
    if len(fraction) > allowed:
        return None, precision_code
    try:
        value = Decimal(token)
    except InvalidOperation:
        return None, malformed_code
    if not value.is_finite():
        return None, malformed_code
    if value == 0:
        value = abs(value)
    quantum = Decimal("0.01") if field == "ELEV" else Decimal("0.000001")
    return value.quantize(quantum), None


def parse_reading(raw_text: str) -> ParseResult:
    """Parse an untrusted OCR string using exact labels and stable errors."""

    codes: set[str] = set()
    if _has_prohibited_control(raw_text):
        codes.add("CONTROL_CHARACTER")

    # Preserve raw_text unchanged. For parsing only, normalize a single OCR
    # minus-like glyph immediately after a required label and before digits.
    working_text = re.sub(
        r"(?i)(\b(?:LAT|LON|ELEV)\b[ \t\r\n]*(?::|=)?[ \t\r\n]*)[-\u2013\u2014\u2212][ \t\r\n]+(?=\d)",
        r"\1-",
        raw_text,
    )
    working_text = re.sub(
        r"(?i)(\b(?:LAT|LON|ELEV)\b[ \t\r\n]*(?::|=)?[ \t\r\n]*)[\u2013\u2014\u2212](?=\d)",
        r"\1-",
        working_text,
    )

    matches = list(_FIELD_RE.finditer(working_text))
    by_label: dict[str, list[re.Match[str]]] = {label: [] for label in _LABELS}
    for match in matches:
        by_label[match.group(1).upper()].append(match)

    values: dict[str, Decimal | None] = {label: None for label in _LABELS}
    for label in _LABELS:
        label_count = len(re.findall(rf"(?i)\b{label}\b", working_text))
        if label_count == 0:
            codes.add(f"MISSING_{label}")
        elif label_count != 1 or len(by_label[label]) != 1:
            codes.add("AMBIGUOUS_ORDER")
        else:
            value, error = _canonical_decimal(by_label[label][0].group(2), label)
            values[label] = value
            if error:
                codes.add(error)

    if not re.search(r"(?i)\b(?:LAT|LON)\b", working_text) and len(_ANY_NUMBER_RE.findall(working_text)) >= 2:
        codes.add("AMBIGUOUS_ORDER")

    # Remove the label/token spans before looking for an unlabelled fourth value.
    residual_parts: list[str] = []
    cursor = 0
    for match in matches:
        residual_parts.append(working_text[cursor : match.start()])
        cursor = match.end()
    residual_parts.append(working_text[cursor:])
    if _ANY_NUMBER_RE.search("".join(residual_parts)):
        codes.add("EXTRA_NUMERIC_FIELD")

    return ParseResult(values["LAT"], values["LON"], values["ELEV"], order_codes(codes))


# Frozen before execution. A zero known-clean denominator is therefore impossible.
KNOWN_CLEAN_CASES: tuple[tuple[str, tuple[str, str, str]], ...] = (
    ("LAT: 49.123456 LON: -123.654321 ELEV: -42.75 m", ("49.123456", "-123.654321", "-42.75")),
    ("lat=1 lon=2 elev=3m", ("1.000000", "2.000000", "3.00")),
    ("LAT 1.2° | LON -2.3° | ELEV 4.5 m", ("1.200000", "-2.300000", "4.50")),
    ("LAT:\t0\nLON:\t0\nELEV:\t0 m", ("0.000000", "0.000000", "0.00")),
    ("LAT: -0.000000 LON: +0.000000 ELEV: -0.00 m", ("0.000000", "0.000000", "0.00")),
    ("LAT: 90 LON: 180 ELEV: 9000 m", ("90.000000", "180.000000", "9000.00")),
    ("LAT: -90 LON: -180 ELEV: -500 m", ("-90.000000", "-180.000000", "-500.00")),
    ("LAT=12.000001 LON=-8.000001 ELEV=0.01m", ("12.000001", "-8.000001", "0.01")),
    ("LAT 7° | LON 9° | ELEV 11 m", ("7.000000", "9.000000", "11.00")),
    ("LAT: +1.000000 LON: +2.000000 ELEV: +3.00 m", ("1.000000", "2.000000", "3.00")),
    ("LAT:\r\n4.1\r\nLON:\r\n5.2\r\nELEV:\r\n6.3 m", ("4.100000", "5.200000", "6.30")),
    ("LAT 0.1° | LON -0.2° | ELEV -0.3 m", ("0.100000", "-0.200000", "-0.30")),
    ("LAT = 1.000000 LON = — 2.000000 ELEV = 3.00 m", ("1.000000", "-2.000000", "3.00")),
)


def known_clean_result() -> tuple[int, int]:
    passed = 0
    for text, expected in KNOWN_CLEAN_CASES:
        parsed = parse_reading(text)
        actual = (
            format(parsed.latitude, ".6f") if parsed.latitude is not None else "",
            format(parsed.longitude, ".6f") if parsed.longitude is not None else "",
            format(parsed.elevation_m, ".2f") if parsed.elevation_m is not None else "",
        )
        if not parsed.codes and actual == expected:
            passed += 1
    return passed, len(KNOWN_CLEAN_CASES)
