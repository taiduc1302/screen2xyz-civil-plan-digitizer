from __future__ import annotations

import time
import unittest

from screen2xyz_civil import contracts as C
from screen2xyz_civil.assisted_capture import (
    CandidateEvidence,
    ElevationUnderCursorService,
    SpatialCandidateIndex,
    build_candidate_evidence,
)
from screen2xyz_civil.detection import Rect, SymbolCandidate, TextCandidate
from screen2xyz_civil.models import PixelPoint
from screen2xyz_civil.workflow import WorkflowError

from .helpers_civil import project_and_workflow


def _text(
    candidate_id: str,
    text: str,
    *,
    x: float,
    y: float,
    context: str = "",
) -> TextCandidate:
    return TextCandidate(
        id=candidate_id,
        text=text,
        page_index=2,
        bbox=Rect(x, y, x + 12, y + 8),
        confidence=0.96,
        source_method=C.PDF_TEXT,
        context=context,
    )


def _evidence(
    candidate_id: str,
    *,
    x: float,
    y: float,
    point_type: str,
    rejected: bool = False,
    rejection_category: str | None = None,
) -> CandidateEvidence:
    return CandidateEvidence(
        candidate_id=candidate_id,
        page_index=2,
        page_label="3",
        pixel=PixelPoint(x, y),
        elevation=None if rejected else 49.25,
        likely_type=point_type,
        source_method=C.PDF_TEXT,
        detected_text="49.25",
        normalized_text="49.25",
        text_confidence=0.96,
        symbol_type="NONE",
        symbol_confidence=None,
        association_confidence=None,
        classification_confidence=0.8,
        reasons=("synthetic evidence",),
        text_bbox={"x0": x, "y0": y, "x1": x + 8, "y1": y + 4},
        alternative_associations=(),
        rejected=rejected,
        rejection_category=(
            rejection_category
            if rejection_category is not None
            else C.SLOPE_ANNOTATION
            if rejected
            else ""
        ),
    )


class AssistedCaptureTests(unittest.TestCase):
    def test_index_build_does_not_mutate_point_cart(self):
        project, _flow = project_and_workflow()
        candidates = [
            _text("grade", "49.25", x=48, y=48),
            _text("slope", "2.0%", x=75, y=48),
            _text("rim", "48.80", x=95, y=48, context="MH RIM"),
        ]
        evidence = build_candidate_evidence(project, candidates)
        self.assertEqual(project.points, [])
        self.assertEqual(len(evidence), 3)
        by_id = {item.candidate_id: item for item in evidence}
        self.assertTrue(by_id["grade"].capturable)
        self.assertEqual(
            by_id["slope"].rejection_category, C.SLOPE_ANNOTATION
        )
        self.assertEqual(by_id["rim"].rejection_category, C.UTILITY_RIM)

    def test_missing_decimal_glyph_uses_page_local_pattern_cautiously(self):
        project, _flow = project_and_workflow()
        candidates = [
            _text("anchor-1", "49.25", x=20, y=20),
            _text("anchor-2", "51.05", x=40, y=20),
            _text("anchor-3", "52.10", x=60, y=20),
            _text("missing-dot", "5146", x=80, y=20),
            _text("unrelated-id", "44994", x=100, y=20),
        ]
        evidence = build_candidate_evidence(project, candidates)
        by_id = {item.candidate_id: item for item in evidence}
        self.assertEqual(by_id["missing-dot"].detected_text, "5146")
        self.assertEqual(by_id["missing-dot"].normalized_text, "51.46")
        self.assertEqual(by_id["missing-dot"].elevation, 51.46)
        self.assertLessEqual(by_id["missing-dot"].classification_confidence, 0.68)
        self.assertTrue(
            any("missing decimal glyph" in reason for reason in by_id["missing-dot"].reasons)
        )
        self.assertEqual(by_id["unrelated-id"].elevation, 44994.0)
        self.assertTrue(by_id["unrelated-id"].rejected)
        self.assertEqual(
            by_id["unrelated-id"].rejection_category,
            "OUTSIDE_PLAUSIBLE_RANGE",
        )

    def test_integer_fragments_and_competing_symbol_labels_are_not_capturable(self):
        project, _flow = project_and_workflow()
        shared_symbol = SymbolCandidate(
            id="oval",
            symbol_type="DESIGN_OVAL",
            bbox=Rect(40, 40, 60, 50),
            confidence=0.9,
            source_method=C.PDF_VECTOR,
        )
        candidates = [
            _text("integer-fragment", "27", x=44, y=42),
            _text("competing-a", "49.25", x=44, y=42),
            _text("competing-b", "49.75", x=46, y=42),
        ]
        by_id = {
            item.candidate_id: item
            for item in build_candidate_evidence(
                project,
                candidates,
                [shared_symbol],
            )
        }
        self.assertFalse(by_id["integer-fragment"].capturable)
        self.assertEqual(
            by_id["integer-fragment"].rejection_category,
            "AMBIGUOUS_NUMERIC_FRAGMENT",
        )
        self.assertFalse(by_id["competing-a"].capturable)
        self.assertFalse(by_id["competing-b"].capturable)
        self.assertEqual(
            by_id["competing-a"].rejection_category,
            "COMPETING_LABELS",
        )
        self.assertEqual(
            by_id["competing-b"].rejection_category,
            "COMPETING_LABELS",
        )

    def test_mode_matching_candidate_wins_within_snap_radius(self):
        index = SpatialCandidateIndex(
            [
                _evidence(
                    "existing",
                    x=50,
                    y=50,
                    point_type=C.EXISTING_GROUND,
                ),
                _evidence(
                    "design",
                    x=56,
                    y=50,
                    point_type=C.DESIGN_GRADE,
                ),
            ]
        )
        suggestion = ElevationUnderCursorService(index).suggest(
            PixelPoint(50, 50), capture_mode=C.DESIGN_GRADE
        )
        self.assertEqual(suggestion.evidence.candidate_id, "design")
        self.assertEqual(suggestion.snap_status, "SNAP MATCH")

    def test_nearby_strict_rejection_guards_against_wrong_capture(self):
        index = SpatialCandidateIndex(
            [
                _evidence(
                    "slope",
                    x=50,
                    y=50,
                    point_type=C.SLOPE_ANNOTATION,
                    rejected=True,
                ),
                _evidence(
                    "grade",
                    x=68,
                    y=50,
                    point_type=C.EXISTING_GROUND,
                ),
            ]
        )
        suggestion = ElevationUnderCursorService(index).suggest(
            PixelPoint(50, 50), capture_mode=C.EXISTING_GROUND
        )
        self.assertFalse(suggestion.can_capture)
        self.assertEqual(suggestion.evidence.candidate_id, "slope")
        self.assertIn("REJECTED", suggestion.snap_status)

    def test_soft_fragment_rejection_does_not_mask_valid_shared_symbol(self):
        index = SpatialCandidateIndex(
            [
                _evidence(
                    "fragment",
                    x=50,
                    y=50,
                    point_type=C.DESIGN_GRADE,
                    rejected=True,
                    rejection_category="AMBIGUOUS_NUMERIC_FRAGMENT",
                ),
                _evidence(
                    "valid",
                    x=50,
                    y=50,
                    point_type=C.DESIGN_GRADE,
                ),
            ]
        )
        suggestion = ElevationUnderCursorService(index).suggest(
            PixelPoint(50, 50), capture_mode=C.DESIGN_GRADE
        )
        self.assertTrue(suggestion.can_capture)
        self.assertEqual(suggestion.evidence.candidate_id, "valid")

    def test_alternative_offset_cycles_competing_mode_matches(self):
        index = SpatialCandidateIndex(
            [
                _evidence(
                    "nearest",
                    x=50,
                    y=50,
                    point_type=C.EXISTING_GROUND,
                ),
                _evidence(
                    "alternative",
                    x=54,
                    y=50,
                    point_type=C.EXISTING_GROUND,
                ),
            ]
        )
        suggestion = ElevationUnderCursorService(index).suggest(
            PixelPoint(50, 50),
            capture_mode=C.EXISTING_GROUND,
            alternative_offset=1,
        )
        self.assertEqual(suggestion.evidence.candidate_id, "alternative")
        self.assertIn("ALT 2/2", suggestion.snap_status)

    def test_capture_promotes_exactly_one_candidate_with_page_and_audit(self):
        project, flow = project_and_workflow()
        evidence = _evidence(
            "page3-existing",
            x=60,
            y=90,
            point_type=C.EXISTING_GROUND,
        )
        point = flow.capture_assisted_point(
            evidence,
            capture_mode=C.EXISTING_GROUND,
            click_pixel=PixelPoint(62, 91),
            snap_distance_px=2.24,
        )
        self.assertEqual(len(project.points), 1)
        self.assertEqual(point.page_index, 2)
        self.assertEqual(point.page_label, "3")
        self.assertEqual(point.capture_candidate_id, "page3-existing")
        self.assertEqual(point.capture_audit["method"], "CLICK")
        self.assertEqual(point.review_status, C.UNREVIEWED)
        with self.assertRaises(WorkflowError):
            flow.capture_assisted_point(
                evidence,
                capture_mode=C.EXISTING_GROUND,
                click_pixel=PixelPoint(60, 90),
                snap_distance_px=0,
            )

    def test_mode_override_is_explicit_and_requires_review(self):
        _project, flow = project_and_workflow()
        evidence = _evidence(
            "likely-existing",
            x=60,
            y=90,
            point_type=C.EXISTING_GROUND,
        )
        point = flow.capture_assisted_point(
            evidence,
            capture_mode=C.DESIGN_GRADE,
            click_pixel=PixelPoint(60, 90),
            snap_distance_px=0,
            capture_method="ENTER",
        )
        self.assertEqual(point.point_type, C.DESIGN_GRADE)
        self.assertEqual(point.capture_mode, C.DESIGN_GRADE)
        self.assertTrue(
            any("overrode likely class" in reason for reason in point.classification_reason)
        )
        self.assertEqual(point.review_status, C.UNREVIEWED)

    def test_large_index_lookup_stays_interactive(self):
        evidence = [
            _evidence(
                f"candidate-{index:05d}",
                x=float((index % 100) * 20),
                y=float((index // 100) * 20),
                point_type=(
                    C.DESIGN_GRADE if index % 2 else C.EXISTING_GROUND
                ),
            )
            for index in range(10_000)
        ]
        service = ElevationUnderCursorService(SpatialCandidateIndex(evidence))
        started = time.perf_counter()
        for index in range(500):
            service.suggest(
                PixelPoint(float(index % 100) * 20, float(index // 100) * 20),
                capture_mode=C.EXISTING_GROUND,
            )
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 1.0)


if __name__ == "__main__":
    unittest.main()
