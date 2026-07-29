"""Deterministic tests for the region-selection state machine and gating
math in ui/layout.py (no Tk, no worker - pure logic)."""

from __future__ import annotations

import unittest

from screen2xyz_m2.ui.layout import (REGION_CANCELLED, REGION_CONFIRMED,
                                     REGION_DRAGGING, REGION_NO_SELECTION,
                                     REGION_SELECTION_READY,
                                     region_confirm_allowed, region_drag_rect,
                                     region_on_cancel, region_on_confirm,
                                     region_on_press, region_on_redraw,
                                     region_on_release, region_stale)

MIN_PX = 8


class RegionStateTransitionTests(unittest.TestCase):
    def test_press_from_no_selection_enters_dragging(self):
        self.assertEqual(region_on_press(REGION_NO_SELECTION),
                         REGION_DRAGGING)

    def test_press_from_selection_ready_restarts_dragging(self):
        # Re-dragging after a prior ready selection discards it cleanly
        # rather than stacking a second Confirm control.
        self.assertEqual(region_on_press(REGION_SELECTION_READY),
                         REGION_DRAGGING)

    def test_release_with_meaningful_drag_is_selection_ready(self):
        self.assertEqual(region_on_release(40, 30, MIN_PX),
                         REGION_SELECTION_READY)

    def test_release_without_meaningful_drag_is_no_selection(self):
        # A simple click (near-zero movement) must never create a region.
        self.assertEqual(region_on_release(1, 1, MIN_PX),
                         REGION_NO_SELECTION)
        self.assertEqual(region_on_release(0, 0, MIN_PX),
                         REGION_NO_SELECTION)

    def test_release_exactly_at_minimum_is_ready(self):
        self.assertEqual(region_on_release(MIN_PX, MIN_PX, MIN_PX),
                         REGION_SELECTION_READY)

    def test_release_one_dimension_too_small_is_no_selection(self):
        self.assertEqual(region_on_release(MIN_PX, MIN_PX - 1, MIN_PX),
                         REGION_NO_SELECTION)

    def test_redraw_clears_to_no_selection(self):
        self.assertEqual(region_on_redraw(REGION_SELECTION_READY),
                         REGION_NO_SELECTION)

    def test_cancel_from_any_state_is_cancelled(self):
        for state in (REGION_NO_SELECTION, REGION_DRAGGING,
                     REGION_SELECTION_READY):
            self.assertEqual(region_on_cancel(state), REGION_CANCELLED)

    def test_confirm_only_from_selection_ready(self):
        self.assertEqual(region_on_confirm(REGION_SELECTION_READY),
                         REGION_CONFIRMED)

    def test_confirm_from_other_states_is_a_no_op(self):
        # Confirm must never fire from NO_SELECTION or mid-drag.
        self.assertEqual(region_on_confirm(REGION_NO_SELECTION),
                         REGION_NO_SELECTION)
        self.assertEqual(region_on_confirm(REGION_DRAGGING),
                         REGION_DRAGGING)


class RegionDragRectTests(unittest.TestCase):
    def test_drag_any_direction_normalizes(self):
        # Bottom-right to top-left drag must produce the same rect as the
        # opposite direction.
        forward = region_drag_rect(10, 10, 50, 40, 1, 1000, 1000)
        backward = region_drag_rect(50, 40, 10, 10, 1, 1000, 1000)
        self.assertEqual(forward, backward)
        self.assertEqual(forward, (10, 10, 40, 30))

    def test_scale_multiplies_canvas_coords_to_physical(self):
        # A 2x zoomed-out picker (scale=2) means 1 canvas px = 2 physical px.
        rect = region_drag_rect(10, 10, 30, 20, 2, 1000, 1000)
        self.assertEqual(rect, (20, 20, 40, 20))

    def test_zoom_preserves_original_physical_coordinates(self):
        # The same physical selection, dragged at two different zoom
        # levels, must resolve to the identical physical rect.
        native_w, native_h = 900, 600
        # At scale=1 the drag covers canvas [100,100]-[200,150].
        at_100pct = region_drag_rect(100, 100, 200, 150, 1, native_w,
                                     native_h)
        # At scale=2 the same physical area is half the canvas coordinates.
        at_50pct = region_drag_rect(50, 50, 100, 75, 2, native_w, native_h)
        self.assertEqual(at_100pct, at_50pct)

    def test_clamps_negative_start_to_bounds(self):
        rect = region_drag_rect(-50, -20, 30, 40, 1, 200, 200)
        x, y, w, h = rect
        self.assertGreaterEqual(x, 0)
        self.assertGreaterEqual(y, 0)

    def test_clamps_drag_beyond_bounds(self):
        rect = region_drag_rect(150, 150, 500, 500, 1, 200, 200)
        x, y, w, h = rect
        self.assertLessEqual(x + w, 200)
        self.assertLessEqual(y + h, 200)

    def test_out_of_bounds_drag_is_clamped_not_rejected(self):
        # A drag that starts or ends off-canvas must still produce a valid,
        # in-bounds rectangle rather than garbage coordinates.
        rect = region_drag_rect(-100, -100, 2000, 2000, 1, 300, 250)
        self.assertEqual(rect, (0, 0, 300, 250))


class RegionConfirmAllowedTests(unittest.TestCase):
    def test_allowed_when_every_condition_holds(self):
        self.assertTrue(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "CONTENT_DETECTED"))

    def test_too_small_blocks_confirm(self):
        self.assertFalse(region_confirm_allowed(
            10, 10, MIN_PX - 1, 40, 1000, 1000, MIN_PX, True,
            "CONTENT_DETECTED"))

    def test_out_of_bounds_blocks_confirm(self):
        self.assertFalse(region_confirm_allowed(
            980, 10, 50, 40, 1000, 1000, MIN_PX, True, "CONTENT_DETECTED"))
        self.assertFalse(region_confirm_allowed(
            -5, 10, 50, 40, 1000, 1000, MIN_PX, True, "CONTENT_DETECTED"))

    def test_no_crop_blocks_confirm(self):
        self.assertFalse(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, False, "CONTENT_DETECTED"))

    def test_blank_dark_crop_blocks_confirm(self):
        self.assertFalse(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "NEAR_UNIFORM_DARK"))

    def test_blank_light_crop_blocks_confirm(self):
        self.assertFalse(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "NEAR_UNIFORM_LIGHT"))

    def test_near_uniform_other_blocks_confirm_by_default(self):
        # Ambiguous (single flat non-black/white color) is blocked by
        # default - it might be a genuinely blank field, or a wrong region;
        # the owner must not be able to confirm it silently (§4).
        self.assertFalse(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "NEAR_UNIFORM_OTHER"))

    def test_near_uniform_other_allowed_with_explicit_override(self):
        self.assertTrue(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "NEAR_UNIFORM_OTHER",
            allow_near_uniform_other=True))

    def test_dark_and_light_never_allowed_even_with_override(self):
        # The override exists only for the ambiguous OTHER class - solid
        # black/white is never confirmable, override or not.
        self.assertFalse(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "NEAR_UNIFORM_DARK",
            allow_near_uniform_other=True))
        self.assertFalse(region_confirm_allowed(
            10, 10, 50, 40, 1000, 1000, MIN_PX, True, "NEAR_UNIFORM_LIGHT",
            allow_near_uniform_other=True))


class RegionStaleTests(unittest.TestCase):
    def test_unchanged_size_and_dpi_is_not_stale(self):
        self.assertFalse(region_stale(900, 320, 96, 900, 320, 96))

    def test_changed_width_is_stale(self):
        self.assertTrue(region_stale(900, 320, 96, 950, 320, 96))

    def test_changed_height_is_stale(self):
        self.assertTrue(region_stale(900, 320, 96, 900, 400, 96))

    def test_changed_dpi_is_stale(self):
        self.assertTrue(region_stale(900, 320, 96, 900, 320, 144))

    def test_unknown_dpi_on_either_side_does_not_false_positive(self):
        self.assertFalse(region_stale(900, 320, None, 900, 320, 144))
        self.assertFalse(region_stale(900, 320, 96, 900, 320, None))
