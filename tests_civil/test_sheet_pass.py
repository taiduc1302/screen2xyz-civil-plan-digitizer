from __future__ import annotations

import unittest

from screen2xyz_civil.sheet_pass import (
    BASELINE_TOLERANCE,
    KNOWN_LAYERS,
    MAX_PLAUSIBLE_GREY_LAYERS,
    MIN_LAYER_PIXELS,
    TITLE_BLOCK_BASELINE,
    LayerPresence,
    classify_grey_ramp,
    layers_above_baseline,
)


GREY_127 = (127, 127, 127)
GREY_83 = (83, 83, 83)
MILL_FILL = (229, 229, 229)
HATCH = (128, 128, 128)
PAPER = (255, 255, 255)
LINEWORK = (0, 0, 0)
UNKNOWN = (12, 34, 56)


class BaselineSeparationTests(unittest.TestCase):
    def test_title_block_furniture_is_not_reported_as_a_layer(self):
        # Grey-127 never drops below ~1 200 px on any sheet of the set purely
        # because of the title block. Before this check it read as a hatch
        # layer on all thirteen.
        rows = layers_above_baseline([(GREY_127, 1400)])
        self.assertEqual(len(rows), 1)
        self.assertFalse(rows[0].above_baseline)

    def test_the_same_colour_well_above_its_floor_is_a_layer(self):
        # Sheet 05 carries grey-127 at 23 983 - twenty times the floor.
        rows = layers_above_baseline([(GREY_127, 23983)])
        self.assertTrue(rows[0].above_baseline)

    def test_a_count_just_over_the_floor_is_not_enough(self):
        floor = TITLE_BLOCK_BASELINE[GREY_127]
        rows = layers_above_baseline([(GREY_127, int(floor * BASELINE_TOLERANCE))])
        self.assertFalse(rows[0].above_baseline)

    def test_a_colour_that_is_furniture_on_some_sheets_and_a_layer_on_others(self):
        # Grey-83 is logo on the roadworks sheets and a real layer on the two
        # storm sheets. One floor has to serve both.
        self.assertFalse(layers_above_baseline([(GREY_83, 3852)])[0].above_baseline)
        self.assertTrue(layers_above_baseline([(GREY_83, 61363)])[0].above_baseline)

    def test_a_colour_with_no_known_floor_still_has_to_clear_the_minimum(self):
        self.assertTrue(layers_above_baseline([(MILL_FILL, 288448)])[0].above_baseline)
        self.assertFalse(layers_above_baseline([(MILL_FILL, 40)])[0].above_baseline)

    def test_raster_speckle_below_the_minimum_is_not_a_layer(self):
        # The two storm sheets render 24 000+ distinct colours. Without this,
        # every one of the several hundred near-white ones reports as a layer.
        speckle = [((250, 250, 250), 89), ((245, 245, 245), 88), ((186, 186, 186), 64)]
        rows = layers_above_baseline(speckle)
        self.assertFalse(any(row.above_baseline for row in rows))

    def test_the_minimum_is_a_measurable_area_not_an_arbitrary_number(self):
        # 1 000 px at 90 DPI is ~5 sq m of ground at 1:250. Anything smaller
        # cannot be a fill worth measuring.
        self.assertEqual(MIN_LAYER_PIXELS, 1000)

    def test_known_layers_are_named_and_unknown_ones_are_not(self):
        rows = {row.colour: row for row in layers_above_baseline(
            [(MILL_FILL, 288448), (HATCH, 11352), (UNKNOWN, 9000)]
        )}
        self.assertIn("MILL AND OVERLAY", rows[MILL_FILL].name)
        self.assertIn("ROAD WIDENING", rows[HATCH].name)
        self.assertEqual(rows[UNKNOWN].name, "")

    def test_paper_and_linework_are_named_so_they_are_not_flagged_for_the_operator(self):
        # They are always present and never a fill. Reporting them as
        # unidentified layers on every sheet trains the operator to ignore the
        # flag that matters.
        self.assertTrue(KNOWN_LAYERS[PAPER])
        self.assertIn("not a fill layer", KNOWN_LAYERS[LINEWORK])

    def test_caller_may_supply_its_own_baseline_and_names(self):
        rows = layers_above_baseline(
            [((1, 2, 3), 100)],
            baseline={(1, 2, 3): 10},
            known={(1, 2, 3): "test layer"},
            min_count=0,
        )
        self.assertTrue(rows[0].above_baseline)
        self.assertEqual(rows[0].name, "test layer")

    def test_presence_row_serialises(self):
        row = LayerPresence(
            colour=MILL_FILL, count=10, baseline=0, above_baseline=True, name="x"
        )
        self.assertEqual(row.to_dict()["colour"], [229, 229, 229])


class KnownLayerTableTests(unittest.TestCase):
    def test_the_mill_overlay_fill_is_registered(self):
        # It was recorded NOT_PRESENT on Sheet 03 because the legend swatch is a
        # solid fill and the search was for a hatch. 978.81 sq m of a paid item.
        self.assertIn(MILL_FILL, KNOWN_LAYERS)

    def test_ditch_infill_is_registered_under_its_real_name(self):
        # Sheet 04's legend calls it DITCH INFILL. Reading only Sheet 03's
        # legend had it recorded as "landscape/sod".
        self.assertIn("DITCH INFILL", KNOWN_LAYERS[(0, 127, 0)])

    def test_every_known_colour_has_a_non_empty_meaning(self):
        for colour, name in KNOWN_LAYERS.items():
            self.assertTrue(name.strip(), colour)

    def test_the_unidentified_storm_layer_is_marked_as_unidentified(self):
        # Naming it something plausible would be worse than admitting it is
        # unknown - sheets 11/12 carry it at 16x floor and nobody has read
        # their legend yet.
        self.assertIn("unidentified", KNOWN_LAYERS[GREY_83])


class BaselineTableTests(unittest.TestCase):
    def test_every_baseline_colour_is_a_valid_rgb_triple(self):
        # The first version of this table was typed from a prose description of
        # the colours ("near-black", "green-Example Contractor", "cyan") and five of its seven
        # RGB values matched nothing on any page, so it suppressed nothing.
        for colour, count in TITLE_BLOCK_BASELINE.items():
            self.assertEqual(len(colour), 3, colour)
            self.assertTrue(all(0 <= channel <= 255 for channel in colour), colour)
            self.assertGreater(count, 0, colour)

    def test_the_two_dual_purpose_greys_carry_a_floor(self):
        # Both are furniture on some sheets and real layers on others; a
        # missing floor here is a false layer on all thirteen sheets.
        self.assertIn(GREY_127, TITLE_BLOCK_BASELINE)
        self.assertIn(GREY_83, TITLE_BLOCK_BASELINE)


def _row(colour, count, name=""):
    return LayerPresence(
        colour=colour, count=count, baseline=0, above_baseline=True, name=name
    )


class GreyRampTests(unittest.TestCase):
    def _ramp(self, n, start=190):
        # Kept clear of the greys this module names (83, 127, 128, 229) - a
        # census yields each colour once, so a ramp cannot also carry one.
        return [_row((v, v, v), 1200) for v in range(start, start + n)]

    def test_a_vector_sheet_keeps_its_few_unnamed_greys(self):
        # Sheet 04 carries grey-185, grey-178 and grey-153 above the floor.
        # Those are real fills nobody has looked up yet, not image noise.
        rows = [_row((185, 185, 185), 7598), _row((178, 178, 178), 6485),
                _row((153, 153, 153), 1152)]
        ramp, rasterised = classify_grey_ramp(rows)
        self.assertFalse(rasterised)
        self.assertEqual(ramp, [])

    def test_a_full_tonal_ramp_is_reclassified(self):
        # The storm sheets clear the floor with 39-40 distinct greys. No legend
        # has forty grey entries.
        ramp, rasterised = classify_grey_ramp(self._ramp(35))
        self.assertTrue(rasterised)
        self.assertEqual(len(ramp), 35)

    def test_the_limit_sits_between_the_measured_vector_and_raster_sheets(self):
        # Vector sheets of DEMO-001: 4-9 greys. Storm sheets: 39-40. Anywhere in
        # between separates them; drifting outside would break both cases.
        self.assertGreater(MAX_PLAUSIBLE_GREY_LAYERS, 9)
        self.assertLess(MAX_PLAUSIBLE_GREY_LAYERS, 39)

    def test_exactly_at_the_limit_is_not_yet_a_ramp(self):
        _, rasterised = classify_grey_ramp(self._ramp(MAX_PLAUSIBLE_GREY_LAYERS))
        self.assertFalse(rasterised)

    def test_named_layers_survive_on_a_rasterised_sheet(self):
        # Sheet 11's mill fill (401 536) and grey-83 (61 363) are an order clear
        # of the ramp and stay measurable; only the unnamed greys are noise.
        rows = self._ramp(30) + [
            _row((229, 229, 229), 401536, "40mm MILL AND OVERLAY (solid fill)"),
            _row((83, 83, 83), 61363, "unidentified grey-83 layer"),
        ]
        ramp, rasterised = classify_grey_ramp(rows)
        self.assertTrue(rasterised)
        self.assertNotIn((229, 229, 229), {row.colour for row in ramp})
        self.assertNotIn((83, 83, 83), {row.colour for row in ramp})

    def test_a_coloured_layer_is_never_ramp(self):
        rows = self._ramp(30) + [_row((221, 221, 109), 2912)]
        ramp, _ = classify_grey_ramp(rows)
        self.assertNotIn((221, 221, 109), {row.colour for row in ramp})


if __name__ == "__main__":
    unittest.main()
