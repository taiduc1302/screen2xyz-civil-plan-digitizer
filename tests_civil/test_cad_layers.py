from __future__ import annotations

import os
import tempfile
import unittest

from screen2xyz_civil import cad_layers as cl

try:
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover - environment
    pymupdf = None


def build_fixture() -> bytes:
    """A four-page set: a layered plan sheet, a flat re-print, a scan, an empty page."""

    doc = pymupdf.open()
    # page 0: layered vector, drawing text as outlines (no real words)
    p = doc.new_page(width=400, height=300)
    curb = doc.add_ocg("DEMO-001 - DESIGN|P_Curb")
    shade = doc.add_ocg("Shading 245 (50%)")
    text = doc.add_ocg("P_Text")
    frame = doc.add_ocg("18-198 - XTB$0$Frame-Text")
    # one polyline object with three segments = an outline
    p.draw_polyline([(20, 20), (120, 20), (120, 80), (200, 80)], color=(0, 0, 0), oc=curb)
    # a Bezier on the curb layer - an arc stays an arc
    p.draw_bezier((200, 80), (230, 80), (250, 100), (250, 130), color=(0, 0, 0), oc=curb)
    # ten single hatch strokes and one multi-item outline on the shading layer
    for k in range(10):
        p.draw_line((30 + 8 * k, 150), (40 + 8 * k, 190), color=(0.5, 0.5, 0.5), oc=shade)
    p.draw_polyline([(30, 150), (120, 150), (120, 190), (30, 190), (30, 150)],
                    color=(0.5, 0.5, 0.5), oc=shade)
    for k in range(60):  # glyph-outline "text"
        p.draw_line((300, 20 + 4 * k), (330, 20 + 4 * k), color=(0, 0, 0), oc=text)
    p.draw_rect(pymupdf.Rect(5, 5, 395, 295), color=(0, 0, 1), oc=frame)
    p.insert_text((310, 280), "SHEET 04", fontsize=8)
    # page 1: flat vector, many objects, no layers
    p1 = doc.new_page(width=400, height=300)
    for k in range(80):
        p1.draw_line((10, 10 + 3 * k), (390, 10 + 3 * k), color=(0, 0, 0))
    # page 2: raster only
    p2 = doc.new_page(width=400, height=300)
    pix = pymupdf.Pixmap(pymupdf.csRGB, pymupdf.IRect(0, 0, 40, 30), False)
    pix.clear_with(200)
    p2.insert_image(pymupdf.Rect(0, 0, 400, 300), pixmap=pix)
    # page 3: empty
    doc.new_page(width=400, height=300)
    doc.set_metadata({"producer": "Microsoft: Print To PDF"})
    return doc.tobytes()


@unittest.skipIf(pymupdf is None, "PyMuPDF not installed")
class RegimeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp()
        cls.path = os.path.join(cls.tmp, "set.pdf")
        with open(cls.path, "wb") as fh:
            fh.write(build_fixture())
        cls.report = cl.document_regime(cls.path)

    def test_the_layered_sheet_is_seen_as_layered_with_outline_text(self):
        page = self.report["pages"][0]
        self.assertEqual(page["drawing_regime"], cl.LAYERED_VECTOR)
        self.assertEqual(page["text_regime"], cl.OUTLINE_TEXT)
        self.assertIn("TEXT_IS_DRAWN_AS_OUTLINES", {f["code"] for f in page["findings"]})
        self.assertIn("P_Text", page["layer_names"])

    def test_a_reprint_is_flat_vector_and_says_why(self):
        page = self.report["pages"][1]
        self.assertEqual(page["drawing_regime"], cl.FLAT_VECTOR)
        self.assertIn("REPRINT_LOST_LAYERS", {f["code"] for f in page["findings"]})

    def test_a_scan_is_raster(self):
        self.assertEqual(self.report["pages"][2]["drawing_regime"], cl.RASTER)

    def test_an_empty_page_is_empty(self):
        self.assertEqual(self.report["pages"][3]["drawing_regime"], cl.EMPTY)

    def test_the_set_verdict_is_the_richest_regime_present(self):
        self.assertEqual(self.report["verdict"], cl.LAYERED_VECTOR)
        self.assertEqual(self.report["optional_content_groups"], 4)

    def test_the_dictionary_separates_outline_objects_from_strokes(self):
        rows = {r["short"]: r for r in self.report["dictionary"]}
        self.assertEqual(rows["Shading 245 (50%)"]["stroke_objects"], 10)
        self.assertEqual(rows["Shading 245 (50%)"]["outline_objects"], 1)
        self.assertEqual(rows["Shading 245 (50%)"]["kind"], cl.KIND_HATCH)
        self.assertEqual(rows["P_Curb"]["hint"], "CURB")
        self.assertEqual(rows["P_Curb"]["status"], cl.PROPOSED)
        self.assertEqual(rows["P_Text"]["kind"], cl.KIND_TEXT)
        self.assertEqual(rows["18-198 - XTB$0$Frame-Text"]["kind"], cl.KIND_FRAME)


@unittest.skipIf(pymupdf is None, "PyMuPDF not installed")
class GeometryTests(unittest.TestCase):
    def setUp(self):
        self.doc = pymupdf.open("pdf", build_fixture())

    def tearDown(self):
        self.doc.close()

    def test_objects_come_back_in_the_raw_frame(self):
        objs = cl.objects_on_layer(self.doc, 0, "P_Curb", only="outline")
        self.assertEqual(len(objs), 1)
        pts = objs[0]["points_raw"]
        # drawn at top-left (20, 20) on a 300 pt page -> raw (20, 280)
        self.assertAlmostEqual(pts[0][0], 20.0, places=3)
        self.assertAlmostEqual(pts[0][1], 280.0, places=3)
        self.assertEqual(len(pts), 4)
        self.assertFalse(objs[0]["has_curve"])

    def test_the_raw_frame_matches_symbols(self):
        try:
            from screen2xyz_civil.symbols import _to_raw  # type: ignore
        except ImportError:
            self.skipTest("symbols._to_raw not present")
        page = self.doc[0]
        w, h = page.rect.width, page.rect.height
        for rot in (0, 180):
            for x, y in ((0.0, 0.0), (20.0, 20.0), (400.0, 300.0)):
                self.assertEqual(
                    cl._raw_point(x, y, h),
                    tuple(map(float, _to_raw(x, y, rotation=rot, width=w, height=h))),
                )

    def test_an_arc_is_reported_as_a_curve_not_flattened(self):
        objs = cl.objects_on_layer(self.doc, 0, "P_Curb", only="stroke")
        curves = [o for o in objs if o["has_curve"]]
        self.assertEqual(len(curves), 1)
        self.assertEqual(len(curves[0]["points_raw"]), 4)  # four Bezier control points

    def test_the_full_xref_name_and_the_short_name_both_match(self):
        a = cl.objects_on_layer(self.doc, 0, "DEMO-001 - DESIGN|P_Curb")
        b = cl.objects_on_layer(self.doc, 0, "P_Curb")
        self.assertEqual(len(a), len(b))
        self.assertEqual(len(a), 2)

    def test_hatch_strokes_and_the_outline_are_separable(self):
        self.assertEqual(len(cl.objects_on_layer(self.doc, 0, "Shading 245 (50%)", only="stroke")), 10)
        outline = cl.objects_on_layer(self.doc, 0, "Shading 245 (50%)", only="outline")
        self.assertEqual(len(outline), 1)
        self.assertEqual(len(outline[0]["points_raw"]), 5)

    def test_only_is_validated(self):
        with self.assertRaises(ValueError):
            cl.objects_on_layer(self.doc, 0, "P_Curb", only="both")


class NameConventionTests(unittest.TestCase):
    def test_civil_3d_house_style(self):
        self.assertEqual(cl.classify_layer_name("P_Pavement edge").hint, "EDGE_OF_PAVEMENT")
        self.assertEqual(cl.classify_layer_name("E_Ep").status, cl.EXISTING)
        self.assertEqual(cl.classify_layer_name("E_Ep").hint, "EDGE_OF_PAVEMENT")
        self.assertEqual(cl.classify_layer_name("P_Ditch bottom").hint, "DITCH")
        self.assertEqual(cl.classify_layer_name("E_Culv").hint, "CULVERT")
        self.assertEqual(cl.classify_layer_name("P_Sw").hint, "SIDEWALK")
        self.assertEqual(cl.classify_layer_name("RD-DW-PRO").hint, "DRIVEWAY")
        self.assertEqual(cl.classify_layer_name("RD-DW-PRO").status, cl.PROPOSED)

    def test_utility_suffix_convention(self):
        stm = cl.classify_layer_name("STM-MH-PRO")
        self.assertEqual((stm.status, stm.hint, stm.kind), (cl.PROPOSED, "STORM", cl.KIND_GEOMETRY))
        self.assertEqual(cl.classify_layer_name("STM-LIN-EXI-P").status, cl.EXISTING)
        self.assertEqual(cl.classify_layer_name("STM-TXT-PRO").kind, cl.KIND_TEXT)
        self.assertEqual(cl.classify_layer_name("STM-MHNO-PRO").kind, cl.KIND_TEXT)
        self.assertEqual(cl.classify_layer_name("HYD-SYM-EXI").hint, "HYDRANT")

    def test_national_cad_standard_style(self):
        n = cl.classify_layer_name("C-ROAD-CURB-N")
        self.assertEqual((n.status, n.hint), (cl.PROPOSED, "CURB"))
        self.assertEqual(cl.classify_layer_name("C-STRM-PIPE-E").status, cl.EXISTING)
        self.assertEqual(cl.classify_layer_name("C-PVMT-D").status, cl.DEMOLISH)

    def test_shading_layers_are_hatch_with_no_feature_of_their_own(self):
        s = cl.classify_layer_name("DEMO-001 - SITE 1 - DESIGN MASTER|Shading 241 (10%)")
        self.assertEqual(s.short, "Shading 241 (10%)")
        self.assertEqual(s.kind, cl.KIND_HATCH)
        self.assertIsNone(s.hint)
        self.assertEqual(cl.classify_layer_name("XSE_HATCH").hint, "CROSS_SECTION")

    def test_frame_and_layer_zero(self):
        self.assertEqual(cl.classify_layer_name("18-198 - XTB$0$TBK").kind, cl.KIND_FRAME)
        z = cl.classify_layer_name("0")
        self.assertEqual((z.status, z.kind, z.hint), (cl.UNKNOWN, cl.KIND_GEOMETRY, None))

    def test_hints_present_groups_by_feature(self):
        rows = [
            cl.DictionaryRow(cl.classify_layer_name("P_Curb"), 10, [3], 2, 8),
            cl.DictionaryRow(cl.classify_layer_name("E_Ep"), 5, [3], 1, 4),
            cl.DictionaryRow(cl.classify_layer_name("P_Pavement edge"), 5, [3], 1, 4),
            cl.DictionaryRow(cl.classify_layer_name("P_Text"), 99, [3], 0, 99),
        ]
        hints = cl.hints_present(rows)
        self.assertEqual(hints["CURB"], ["P_Curb"])
        self.assertEqual(hints["EDGE_OF_PAVEMENT"], ["E_Ep", "P_Pavement edge"])
        self.assertNotIn("TEXT", hints)


if __name__ == "__main__":
    unittest.main()
