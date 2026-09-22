from __future__ import annotations

import unittest

import numpy as np

from screen2xyz_civil.fill_layers import (
    FillLayerError,
    RenderFrame,
    clip_polygon_x,
    close,
    dilate,
    erode,
    fill_holes,
    hatch_closing_radius,
    label_components,
    signed_area,
    simplify_closed,
    split_pinches,
    trace_loops,
    trace_regions,
)


class PinchTests(unittest.TestCase):
    def test_a_loop_that_revisits_a_vertex_is_cut_into_simple_loops(self):
        # Two unit squares touching at a corner, traced as one loop through
        # the shared corner (0,0) twice.
        loop = [(-1, -1), (0, -1), (0, 0), (1, 0), (1, 1), (0, 1), (0, 0), (-1, 0)]
        parts = split_pinches(loop)
        self.assertEqual(len(parts), 2)
        for part in parts:
            self.assertEqual(len(set(part)), len(part))  # simple
            self.assertAlmostEqual(abs(signed_area(part)), 1.0)

    def test_a_simple_loop_is_returned_unchanged(self):
        loop = [(0, 0), (3, 0), (3, 2), (0, 2)]
        self.assertEqual(split_pinches(loop), [loop])


class RegionChecksTests(unittest.TestCase):
    CX = 0.0881944444444444

    def _frame(self, h, w):
        return RenderFrame(dpi=90, rotation=0, page_width_pt=2384.0, page_height_pt=1684.0,
                           display_x0=0.0, display_y0=0.0, width_px=w, height_px=h)

    def test_a_region_touching_itself_at_a_corner_yields_two_healthy_polygons(self):
        # An outline through a pinch is refused by polygon_health as a
        # self-intersection; split, both lobes pass and nothing is lost.
        h, w = 40, 40
        mask = np.zeros((h, w), dtype=bool)
        mask[5:20, 5:20] = True
        mask[20:35, 20:35] = True
        rgb = np.full((h, w, 3), 255, dtype=np.uint8)
        rgb[mask] = (229, 229, 229)
        px_area = (72 / 90 * self.CX) ** 2
        _, regions = trace_regions(mask, mask, rgb, self._frame(h, w), px_area=px_area,
                                   min_area_m2=0.0, simplify_px=0.1, metres_per_point=self.CX)
        self.assertEqual(len(regions), 2)
        self.assertTrue(all(r.health_safe for r in regions))
        self.assertAlmostEqual(sum(r.area_m2_polygon for r in regions), 2 * 225 * px_area, places=6)

    def test_pattern_fractions_name_what_is_drawn_inside_a_region(self):
        h, w = 30, 30
        mask = np.zeros((h, w), dtype=bool)
        mask[5:25, 5:25] = True
        rgb = np.full((h, w, 3), 255, dtype=np.uint8)
        rgb[mask] = (229, 229, 229)
        rgb[10:12, 5:25] = (178, 178, 178)  # a full-depth hatch stroke across it
        px_area = (72 / 90 * self.CX) ** 2
        _, regions = trace_regions(mask, mask, rgb, self._frame(h, w), px_area=px_area,
                                   min_area_m2=0.0, simplify_px=0.1, metres_per_point=self.CX,
                                   patterns={"full_depth_asphalt_rr": (178, 178, 178), "widening_x_hatch": (127, 127, 127)})
        region = regions[0]
        self.assertAlmostEqual(region.pattern_fractions["full_depth_asphalt_rr"], 40 / 400, places=6)
        self.assertEqual(region.pattern_fractions["widening_x_hatch"], 0.0)
        self.assertEqual(region.dominant_pattern, "full_depth_asphalt_rr")


def _rect_mask(h, w, y0, y1, x0, x1):
    m = np.zeros((h, w), dtype=bool)
    m[y0:y1, x0:x1] = True
    return m


class MorphologyTests(unittest.TestCase):
    def test_dilate_grows_and_erode_shrinks_by_the_radius(self):
        m = _rect_mask(20, 20, 8, 12, 8, 12)
        self.assertEqual(int(dilate(m, 1).sum()), 6 * 6)
        self.assertEqual(int(erode(m, 1).sum()), 2 * 2)

    def test_closing_heals_a_one_pixel_seam_and_keeps_the_outline(self):
        # Two pattern cells with a one-pixel seam between them, as the tiling
        # pattern renders at 90 DPI.
        m = _rect_mask(20, 40, 5, 15, 2, 19) | _rect_mask(20, 40, 5, 15, 20, 38)
        healed = close(m, 2)
        self.assertTrue(healed[10, 19])
        self.assertEqual(int(healed.sum()), 10 * 36)  # 2..38 solid, nothing added outside

    def test_closing_does_not_bridge_a_wide_gap(self):
        m = _rect_mask(20, 60, 5, 15, 2, 20) | _rect_mask(20, 60, 5, 15, 40, 58)
        healed = close(m, 2)
        self.assertFalse(healed[10, 30])


class ComponentTests(unittest.TestCase):
    def test_diagonally_touching_pixels_are_separate_regions(self):
        m = np.zeros((4, 4), dtype=bool)
        m[1, 1] = True
        m[2, 2] = True
        labels, sizes = label_components(m)
        self.assertEqual(len(sizes) - 1, 2)

    def test_sizes_are_indexed_by_label(self):
        m = _rect_mask(10, 10, 1, 3, 1, 3) | _rect_mask(10, 10, 6, 9, 6, 9)
        labels, sizes = label_components(m)
        self.assertEqual(sorted(sizes[1:].tolist()), [4, 9])

    def test_small_enclosed_hole_is_filled_and_a_large_one_is_kept(self):
        m = _rect_mask(30, 30, 2, 28, 2, 28)
        m[10:12, 10:12] = False  # a 4 px label box
        m[15:25, 15:25] = False  # a 100 px real opening
        filled, n = fill_holes(m, 20)
        self.assertEqual(n, 4)
        self.assertTrue(filled[10, 10])
        self.assertFalse(filled[20, 20])

    def test_background_touching_the_border_is_never_a_hole(self):
        m = _rect_mask(10, 10, 0, 10, 0, 5)
        filled, n = fill_holes(m, 1000)
        self.assertEqual(n, 0)


class TraceTests(unittest.TestCase):
    def test_a_rectangle_traces_to_its_four_corners(self):
        m = _rect_mask(10, 10, 2, 5, 3, 7)
        loops = trace_loops(m)
        self.assertEqual(len(loops), 1)
        simplified = simplify_closed([(float(x), float(y)) for x, y in loops[0]], 0.1)
        self.assertEqual(len(simplified), 4)
        self.assertAlmostEqual(abs(signed_area(simplified)), 3 * 4)

    def test_a_region_with_a_hole_gives_two_loops_of_opposite_orientation(self):
        m = _rect_mask(12, 12, 1, 11, 1, 11)
        m[4:8, 4:8] = False
        loops = trace_loops(m)
        self.assertEqual(len(loops), 2)
        areas = sorted(signed_area(lp) for lp in loops)
        self.assertLess(areas[0], 0)
        self.assertGreater(areas[1], 0)
        self.assertAlmostEqual(abs(areas[0]), 16)
        self.assertAlmostEqual(abs(areas[1]), 100)

    def test_two_lobes_touching_at_a_corner_stay_two_loops(self):
        m = np.zeros((6, 6), dtype=bool)
        m[1:3, 1:3] = True
        m[3:5, 3:5] = True
        loops = trace_loops(m)
        self.assertEqual(len(loops), 2)
        for lp in loops:
            self.assertAlmostEqual(abs(signed_area(lp)), 4)

    def test_traced_area_equals_pixel_count(self):
        # An L shape: the loop must enclose exactly the set pixels.
        m = _rect_mask(10, 10, 1, 6, 1, 3) | _rect_mask(10, 10, 4, 6, 1, 8)
        loops = trace_loops(m)
        self.assertEqual(len(loops), 1)
        self.assertAlmostEqual(abs(signed_area(loops[0])), int(m.sum()))


class FrameTests(unittest.TestCase):
    def test_rotation_180_maps_display_pixels_to_the_raw_frame(self):
        # Sheet 05 PLAN viewport, raw (94,800)-(2234,1515), rendered at 90 DPI:
        # display clip x0 = 2384-2234 = 150. Pixel (0,0) is raw (2234, 800).
        frame = RenderFrame(dpi=90, rotation=180, page_width_pt=2384.0, page_height_pt=1684.0,
                            display_x0=150.0, display_y0=800.0, width_px=2676, height_px=894)
        self.assertEqual(frame.pixel_to_raw(0, 0), (2234.0, 800.0))
        x, y = frame.pixel_to_raw(90, 90)  # one inch in
        self.assertAlmostEqual(x, 2234.0 - 72.0)
        self.assertAlmostEqual(y, 800.0 + 72.0)

    def test_other_rotations_are_refused(self):
        frame = RenderFrame(dpi=90, rotation=90, page_width_pt=100, page_height_pt=100,
                            display_x0=0, display_y0=0, width_px=10, height_px=10)
        with self.assertRaises(FillLayerError):
            frame.pixel_to_raw(0, 0)


class ClipTests(unittest.TestCase):
    SQUARE = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
    # A U: two legs joined at the bottom. Cut through the mouth and it is two
    # pieces. Sutherland-Hodgman returned one ring bridging them along the
    # cut line - right area, self-touching boundary - found by the session
    # writing it to Revu on 2026-09-03.
    U = [(0.0, 0.0), (30.0, 0.0), (30.0, 20.0), (20.0, 20.0), (20.0, 5.0),
         (10.0, 5.0), (10.0, 20.0), (0.0, 20.0)]

    def _total(self, parts):
        return sum(abs(signed_area(p)) for p in parts)

    def test_clipping_to_a_band_keeps_the_band(self):
        parts = clip_polygon_x(self.SQUARE, 2.0, 5.0)
        self.assertEqual(len(parts), 1)
        self.assertAlmostEqual(self._total(parts), 30.0)

    def test_bounds_may_be_given_in_either_order(self):
        a = clip_polygon_x(self.SQUARE, 2.0, 5.0)
        b = clip_polygon_x(self.SQUARE, 5.0, 2.0)
        self.assertAlmostEqual(self._total(a), self._total(b))

    def test_a_band_outside_the_polygon_is_empty(self):
        self.assertEqual(clip_polygon_x(self.SQUARE, 20.0, 30.0), [])

    def test_a_polygon_wholly_inside_comes_back_whole(self):
        parts = clip_polygon_x(self.SQUARE, -5.0, 50.0)
        self.assertEqual(parts, [self.SQUARE])

    def test_a_concave_polygon_cut_across_its_mouth_gives_simple_pieces(self):
        # y-band is not what we clip on; clip the U in x through both legs:
        # x in [5, 25] cuts each leg and the bottom bar -> one ring (the bar
        # joins them). x in [5, 25] on the rotated U (legs along x) is the
        # real case, so rotate: swap axes.
        u_sideways = [(y, x) for x, y in self.U]  # legs now run along x, mouth at x=20
        parts = clip_polygon_x(u_sideways, 8.0, 25.0)
        self.assertEqual(len(parts), 2)
        for part in parts:
            self.assertGreaterEqual(len(part), 4)
            self.assertEqual(len(set(part)), len(part))  # simple ring
        # Area: two legs, each 10 wide (y) by (20-8)=12 long in x... legs are
        # y in [0,10] and [20,30], x from 5 to 20 clipped to [8, 20]: 2 * 10 * 12
        self.assertAlmostEqual(self._total(parts), 2 * 10.0 * 12.0)

    def test_each_piece_passes_the_repository_gate(self):
        from screen2xyz_civil.bluebeam_bridge import polygon_health
        u_sideways = [(y, x) for x, y in self.U]
        for part in clip_polygon_x(u_sideways, 8.0, 25.0):
            self.assertTrue(polygon_health(part)["safe_to_write"])


class HatchRadiusTests(unittest.TestCase):
    def test_radius_is_half_the_median_row_gap(self):
        # Vertical hatch lines every 16 px: row gap 16, radius 8.
        m = np.zeros((40, 160), dtype=bool)
        for x in range(0, 160, 16):
            m[:, x] = True
        self.assertEqual(hatch_closing_radius(m, sample_every=1), 8)

    def test_a_solid_has_no_gap_to_measure(self):
        with self.assertRaises(FillLayerError):
            hatch_closing_radius(np.ones((10, 50), dtype=bool), sample_every=1)


class AnalysisEdgeTests(unittest.TestCase):
    CX = 0.0881944444444444

    def _frame(self, h, w):
        return RenderFrame(dpi=90, rotation=0, page_width_pt=2384.0, page_height_pt=1684.0,
                           display_x0=0.0, display_y0=0.0, width_px=w, height_px=h)

    def _trace(self, mask):
        h, w = mask.shape
        rgb = np.full((h, w, 3), 255, dtype=np.uint8)
        rgb[mask] = (229, 229, 229)
        px = (72 / 90 * self.CX) ** 2
        _, regions = trace_regions(mask, mask, rgb, self._frame(h, w), px_area=px,
                                   min_area_m2=0.0, simplify_px=0.1, metres_per_point=self.CX)
        return regions[0]

    def test_a_region_inside_the_window_is_not_flagged(self):
        mask = np.zeros((30, 40), dtype=bool)
        mask[5:20, 5:20] = True
        region = self._trace(mask)
        self.assertEqual(region.touches_analysis_edge, [])

    def test_a_region_running_off_the_window_is_flagged(self):
        # An analysis box is not a feature boundary. A markup stopped at the
        # crop is short by however far the feature runs past it - 19 sq m on
        # one real item, because the analysis box ended at x 565.8 where the
        # drawing runs to 559.3.
        mask = np.zeros((30, 40), dtype=bool)
        mask[5:20, 20:] = True
        region = self._trace(mask)
        self.assertIn("right", region.touches_analysis_edge)
        codes = [f["code"] for f in region.findings]
        self.assertIn("REGION_TOUCHES_THE_ANALYSIS_EDGE", codes)

    def test_the_warning_names_every_edge_reached(self):
        mask = np.ones((30, 40), dtype=bool)
        region = self._trace(mask)
        self.assertEqual(set(region.touches_analysis_edge), {"top", "bottom", "left", "right"})

    def test_it_warns_rather_than_blocks(self):
        # The operator may have cropped deliberately; the point is that the
        # crop must be a decision, not an accident.
        mask = np.zeros((30, 40), dtype=bool)
        mask[5:20, 20:] = True
        finding = next(f for f in self._trace(mask).findings
                       if f["code"] == "REGION_TOUCHES_THE_ANALYSIS_EDGE")
        self.assertFalse(finding["blocking"])


if __name__ == "__main__":
    unittest.main()
