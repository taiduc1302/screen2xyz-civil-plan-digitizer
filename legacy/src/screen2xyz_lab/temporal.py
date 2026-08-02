"""Deterministic stale and duplicate classification."""

from __future__ import annotations

from decimal import Decimal

from .models import TemporalResult


class TemporalClassifier:
    def __init__(self) -> None:
        self._first_accepted: dict[tuple[Decimal, Decimal, Decimal], str] = {}
        self._previous_accepted: tuple[tuple[Decimal, Decimal, Decimal], str] | None = None

    def classify(
        self,
        scenario_id: str,
        triplet: tuple[Decimal, Decimal, Decimal] | None,
        existing_codes: tuple[str, ...],
    ) -> TemporalResult:
        if existing_codes or triplet is None:
            self._previous_accepted = None
            primary = existing_codes[0] if existing_codes else "MISSING_LAT"
            return TemporalResult("REJECTED", primary, existing_codes or (primary,), "")

        if self._previous_accepted and self._previous_accepted[0] == triplet:
            reference = self._previous_accepted[1]
            self._previous_accepted = None
            return TemporalResult("REJECTED", "STALE_READING", ("STALE_READING",), reference)

        if triplet in self._first_accepted:
            reference = self._first_accepted[triplet]
            self._previous_accepted = None
            return TemporalResult("REJECTED", "DUPLICATE_READING", ("DUPLICATE_READING",), reference)

        self._first_accepted[triplet] = scenario_id
        self._previous_accepted = (triplet, scenario_id)
        return TemporalResult("ACCEPTED", "", (), "")
