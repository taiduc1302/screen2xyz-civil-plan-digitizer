"""Optional external-AI assistance boundary (disabled by default).

The deterministic pipeline is authoritative. An assistant may only produce
a human-readable review note about an ambiguous candidate; it can never
approve, export, or modify raw OCR. Only sanitized OCR text, parsed values,
and reason codes may ever be sent — never image bytes, file paths, or run
metadata.

No live network integration is implemented in M1. ``OpenAIAssistantBoundary``
is a clean provider seam that fails closed with instructions; tests use
mocks. Enabling a live provider requires (a) explicit per-run user opt-in in
the interface, (b) an API key supplied via the ``S2XYZ_ASSIST_API_KEY``
environment variable (never committed), and (c) an implementation written
against current official provider documentation.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class AssistRequest:
    """Sanitized, text-only view of one candidate."""

    raw_text_display: str
    parsed_latitude: str
    parsed_longitude: str
    parsed_elevation_m: str
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class AssistResult:
    available: bool
    note: str


class AssistantUnavailable(RuntimeError):
    """Raised when assistance is requested but no provider is enabled."""


class ReviewAssistant(Protocol):
    def review_note(self, request: AssistRequest) -> AssistResult: ...


class NullAssistant:
    """Default assistant: external AI is disabled."""

    def review_note(self, request: AssistRequest) -> AssistResult:
        return AssistResult(available=False, note="External AI assistance is disabled.")


class OpenAIAssistantBoundary:
    """Disabled-by-default seam for a future OpenAI-backed assistant.

    Intentionally contains no network code. The remaining integration step
    is documented in the M1 implementation report.
    """

    def __init__(self, *, opted_in: bool = False) -> None:
        self.opted_in = opted_in

    def review_note(self, request: AssistRequest) -> AssistResult:
        if not self.opted_in:
            return AssistResult(
                available=False,
                note="External AI assistance requires explicit opt-in.",
            )
        raise AssistantUnavailable(
            "No live external AI provider is implemented in M1. See "
            "M1_IMPLEMENTATION_REPORT.md for the exact remaining integration step."
        )
