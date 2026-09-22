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


@unittest.skipIf(pymupdf is None, "PyMuPDF not installed")
class ClipTests(unittest.TestCase):
    # A viewport clips its content at the match line; geometry beyond it is
    # in the file and never prints. On DEMO-001-06 a ditch-infill polygon
    # passed every numeric gate over blank paper that way.

    def make(self):
        doc = pymupdf.open()
        p = doc.new_page(width=400, height=300)
        ocg = doc.add_ocg("P_Veg")
        p.draw_line((0, 0), (1, 1), oc=ocg)  # creates the contents stream + OC wrapper
        xref = p.get_contents()[0]
        # clip 10..110 x 10..110 (PDF space): one line half inside, one fully
        # outside, one after the clip ends (unclipped)
        doc.update_stream(xref, (
            b"/OC /oc1 BDC q 10 10 100 100 re W n 0 0 m 50 50 l S 200 200 m 250 250 l S Q "
            b"300 20 m 350 20 l S EMC"
        ))
        return pymupdf.open("pdf", doc.tobytes())

    def test_objects_report_whether_a_clip_removes_them(self):
        d = self.make()
        objs = cl.objects_on_layer(d, 0, "P_Veg")
        if not objs:  # OC name binding may differ; fall back to all layers
            objs = cl.objects_on_layer(d, 0, "")
        self.assertEqual(len(objs), 3)
        objs.sort(key=lambda o: o["rect_raw"][0])
        inside, outside, free = objs
        self.assertFalse(inside["clipped"])
        self.assertLess(inside["visible_fraction"], 1.0)
        self.assertIsNotNone(inside["clip_raw"])
        self.assertTrue(outside["clipped"])
        self.assertEqual(outside["visible_fraction"], 0.0)
        self.assertFalse(free["clipped"])
        self.assertIsNone(free["clip_raw"])
        d.close()

    def test_the_renderer_says_what_prints(self):
        d = self.make()
        layer = "P_Veg" if cl.objects_on_layer(d, 0, "P_Veg") else ""
        objs = cl.printed_objects(d, 0, layer, cl.objects_on_layer(d, 0, layer))
        objs.sort(key=lambda o: o["rect_raw"][0])
        self.assertEqual([o["printed"] for o in objs], [True, False, True])
        d.close()

    def test_chains_drop_unprinted_objects_by_default(self):
        from screen2xyz_civil.layer_chains import chains_on_layer
        d = self.make()
        layer = "P_Veg" if cl.objects_on_layer(d, 0, "P_Veg") else ""
        r = chains_on_layer(d, 0, layer)
        self.assertEqual(r["clipped_dropped"], 1)
        self.assertEqual(r["fragments_used"], 2)
        r2 = chains_on_layer(d, 0, layer, only_visible=False)
        self.assertEqual(r2["clipped_dropped"], 0)
        self.assertEqual(r2["fragments_used"], 3)
        d.close()


@unittest.skipIf(pymupdf is None, "PyMuPDF not installed")
class PolygonClipTests(unittest.TestCase):
    # The plan viewport on DEMO-001-06 is a 15-segment polygon with a notch;
    # its scissor is only the bounding box, and a rectangle test called
    # 159 stipple objects on blank paper "visible".

    def test_a_notched_clip_is_tested_as_a_polygon_not_its_box(self):
        doc = pymupdf.open()
        p = doc.new_page(width=400, height=300)
        ocg = doc.add_ocg("P_Veg")
        p.draw_line((0, 0), (1, 1), oc=ocg)
        xref = p.get_contents()[0]
        # L-shaped clip: the square 0..200 x 0..200 minus the corner 100..200 x 100..200 (PDF space)
        clip = b"0 0 m 200 0 l 200 100 l 100 100 l 100 200 l 0 200 l h W n "
        body = (b"20 20 m 60 20 l S "        # inside the L
                b"150 150 m 190 150 l S "    # inside the box, in the notch -> not printed
                b"150 20 m 190 20 l S ")      # inside the L's lower arm
        doc.update_stream(xref, b"/OC /oc1 BDC q " + clip + body + b"Q EMC")
        d = pymupdf.open("pdf", doc.tobytes())
        objs = cl.objects_on_layer(d, 0, "P_Veg") or cl.objects_on_layer(d, 0, "")
        self.assertEqual(len(objs), 3)
        by_x = sorted(objs, key=lambda o: (o["rect_raw"][0], o["rect_raw"][1]))
        low_left, low_right, notch = by_x[0], [o for o in by_x[1:] if o["rect_raw"][1] < 100][0], [o for o in by_x[1:] if o["rect_raw"][1] > 100][0]
        self.assertFalse(low_left["clipped"])
        self.assertFalse(low_right["clipped"])
        self.assertTrue(notch["clipped"], "an object inside the scissor box but outside the clip polygon must be clipped")
        printed = {id(o): o["printed"] for o in cl.printed_objects(d, 0, "P_Veg" if cl.objects_on_layer(d, 0, "P_Veg") else "", objs)}
        self.assertFalse(notch["printed"])
        self.assertTrue(low_left["printed"] and low_right["printed"])
        d.close()
