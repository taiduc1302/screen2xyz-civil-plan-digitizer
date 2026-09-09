import math
import unittest
from screen2xyz_civil.pattern_edge import lattice_report, PatternEdgeError
from tests_civil import test_pattern_edge
from screen2xyz_civil import cad_layers as cl
try:
    import pymupdf
except ImportError:
    pymupdf = None


class RotatedLatticeTests(unittest.TestCase):
    def test_independently_known_axes_preserve_verdict(self):
        base = lattice_report(test_pattern_edge.LatticeTests.HULL, pitch_pt=5.1)
        for degrees in (17, 37, 89, 143, 270):
            angle = math.radians(degrees)
            ring = [(x*math.cos(angle)-y*math.sin(angle)+500,
                     x*math.sin(angle)+y*math.cos(angle)-300) for x,y in test_pattern_edge.LatticeTests.HULL]
            result = lattice_report(ring, pitch_pt=5.1, grid_angle_deg=degrees)
            self.assertEqual(result['on_lattice_edges'], base['on_lattice_edges'])
            self.assertTrue(result['on_lattice'])

    def test_nonfinite_inputs_refused(self):
        for kw in ({'pitch_pt':float('nan')}, {'pitch_pt':5.1,'grid_angle_deg':float('inf')}):
            with self.assertRaises(PatternEdgeError): lattice_report([], **kw)


@unittest.skipIf(pymupdf is None, 'PyMuPDF not installed')
class CurvedClipTests(unittest.TestCase):
    def test_curve_against_independent_renderer(self):
        doc = pymupdf.open()
        page = doc.new_page(width=120, height=120)
        layer = doc.add_ocg('P_Test')
        page.draw_line((0,0),(1,1),oc=layer)
        # Cubic arch rises only to y=85, while its controls reach y=110.
        doc.update_stream(page.get_contents()[0], b'/OC /oc1 BDC q 10 10 m 10 110 110 110 110 10 c h W n 0 0 0 rg 0 0 120 120 re f Q EMC')
        with pymupdf.open('pdf',doc.tobytes()) as source:
            clip = next(d for d in source[0].get_drawings(extended=True) if d['type']=='clip')
            poly = cl._clip_polygon(clip['items'])
            pix = source[0].get_pixmap(colorspace=pymupdf.csGRAY)
            # get_drawings is top-left; y=25 is above the arch but inside
            # the old control hull. y=36 is just inside the true curve.
            for x,y in ((60,25),(60,36),(60,80),(15,100)):
                self.assertEqual(cl._point_in_polygon(x,y,poly), pix.pixel(x,y)[0]<128, (x,y))
            self.assertGreater(len(poly), 10)
        doc.close()

    def test_disjoint_rings_and_mixed_paths_refused(self):
        p=pymupdf.Point
        for items in ([('l',p(0,0),p(10,0)),('l',p(20,20),p(30,30))],
                      [('re',pymupdf.Rect(0,0,10,10),1),('l',p(0,0),p(1,1))]):
            with self.assertRaises(ValueError): cl._clip_polygon(items)

    def test_quad_is_not_its_axis_aligned_box(self):
        q=pymupdf.Quad((5,0),(10,5),(0,5),(5,10))
        poly=cl._clip_polygon([('qu',q)])
        self.assertTrue(cl._point_in_polygon(5,5,poly))
        self.assertFalse(cl._point_in_polygon(1,1,poly))
