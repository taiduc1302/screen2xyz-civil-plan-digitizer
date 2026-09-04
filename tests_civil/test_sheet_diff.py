from __future__ import annotations

import unittest

from screen2xyz_civil import sheet_diff as sd

try:
    import pymupdf  # type: ignore
except ImportError:  # pragma: no cover - environment
    pymupdf = None


def build_pair() -> bytes:
    """Page 0: base sheet. Page 1: the same sheet re-issued with one culvert
    moved, one storm structure added, a fence layer added, and the frame
    unchanged. Page 2: an unrelated cross-section sheet."""

    doc = pymupdf.open()
    ocg = {n: doc.add_ocg(n) for n in ("P_Culv", "STM-MH-PRO", "P_Fence", "Frame", "XSE_HATCH", "P_Pavement edge")}

    def base(page, culv_y, extra_mh=False, fence=False):
        page.draw_rect(pymupdf.Rect(5, 5, 395, 295), color=(0, 0, 1), oc=ocg["Frame"])
        for k in range(12):
            page.draw_line((20 + 10 * k, 200), (27 + 10 * k, 200), color=(0, 0, 0), oc=ocg["P_Pavement edge"])
        page.draw_line((100, culv_y), (160, culv_y), color=(0, 0, 0), oc=ocg["P_Culv"])
        page.draw_line((100, culv_y + 3.6), (160, culv_y + 3.6), color=(0, 0, 0), oc=ocg["P_Culv"])
        page.draw_circle((200, 100), 4, color=(0, 0, 0), oc=ocg["STM-MH-PRO"])
        if extra_mh:
            page.draw_circle((260, 100), 4, color=(0, 0, 0), oc=ocg["STM-MH-PRO"])
        if fence:
            for k in range(5):
                page.draw_line((300, 40 + 8 * k), (300, 46 + 8 * k), color=(0, 0, 0), oc=ocg["P_Fence"])

    base(doc.new_page(width=400, height=300), 150)
    base(doc.new_page(width=400, height=300), 170, extra_mh=True, fence=True)
    xs = doc.new_page(width=400, height=300)
    xs.draw_rect(pymupdf.Rect(5, 5, 395, 295), color=(0, 0, 1), oc=ocg["Frame"])
    for k in range(40):
        xs.draw_line((20, 20 + 6 * k), (380, 20 + 6 * k), color=(0.5, 0.5, 0.5), oc=ocg["XSE_HATCH"])
    return doc.tobytes()


@unittest.skipIf(pymupdf is None, "PyMuPDF not installed")
class MatchTests(unittest.TestCase):
    def setUp(self):
        self.doc = pymupdf.open("pdf", build_pair())

    def tearDown(self):
        self.doc.close()

    def test_the_revised_sheet_matches_its_base_page_not_the_cross_section(self):
        m = sd.match_revised_sheet(self.doc, 1, self.doc, candidates=[0, 2])
        self.assertEqual(m["base_page"], 0)
        self.assertEqual(m["runner_up"], 2)
        self.assertFalse(m["ambiguous"])
        self.assertGreater(m["similarity"], 0.7)

    def test_similarity_is_one_for_identical_tables_and_zero_for_disjoint(self):
        a = sd.layer_counts(self.doc, 0)
        self.assertAlmostEqual(sd.signature_similarity(a, a), 1.0)
        self.assertEqual(sd.signature_similarity(a, sd.layer_counts(self.doc, 2)) < 0.2, True)


@unittest.skipIf(pymupdf is None, "PyMuPDF not installed")
class DiffTests(unittest.TestCase):
    def setUp(self):
        self.doc = pymupdf.open("pdf", build_pair())
        self.diff = sd.diff_pages(self.doc, 0, self.doc, 1)

    def tearDown(self):
        self.doc.close()

    def rows(self):
        return {r["layer"]: r for r in self.diff["rows"]}

    def test_unchanged_layers_are_reported_unchanged(self):
        rows = self.rows()
        self.assertTrue(rows["Frame"]["unchanged"])
        self.assertTrue(rows["P_Pavement edge"]["unchanged"])
        self.assertEqual(rows["P_Pavement edge"]["common"], 12)

    def test_a_moved_culvert_is_removed_from_a_and_added_to_b(self):
        r = self.rows()["P_Culv"]
        self.assertEqual((len(r["only_in_a"]), len(r["only_in_b"])), (2, 2))
        # raw frame: drawn at y=150 on a 300 pt page -> raw y ~150; moved to 170 -> raw ~130
        self.assertAlmostEqual(r["changed_bbox_a"][1], 150 - 3.6, places=0)
        self.assertAlmostEqual(r["changed_bbox_b"][1], 130 - 3.6, places=0)

    def test_an_added_structure_shows_only_in_b(self):
        r = self.rows()["STM-MH-PRO"]
        self.assertEqual(len(r["only_in_a"]), 0)
        self.assertEqual(len(r["only_in_b"]), 1)
        self.assertEqual(r["common"], 1)

    def test_a_new_layer_shows_with_count_zero_in_a(self):
        r = self.rows()["P_Fence"]
        self.assertEqual((r["count_a"], r["count_b"]), (0, 5))

    def test_changed_layers_are_ranked_by_size_of_change(self):
        names = [r["layer"] for r in self.diff["changed"]]
        self.assertEqual(names[0], "P_Fence")
        self.assertEqual(set(names), {"P_Fence", "P_Culv", "STM-MH-PRO"})

    def test_layers_can_be_restricted(self):
        d = sd.diff_pages(self.doc, 0, self.doc, 1, layers=["P_Culv"])
        self.assertEqual([r["layer"] for r in d["rows"]], ["P_Culv"])

    def test_report_is_readable(self):
        text = sd.diff_report(self.diff)
        self.assertIn("P_Fence", text)
        self.assertIn("changed 3", text)


if __name__ == "__main__":
    unittest.main()
