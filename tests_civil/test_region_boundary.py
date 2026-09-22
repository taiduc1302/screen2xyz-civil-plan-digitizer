import unittest
try:
    import shapely
except ImportError:shapely=None
from screen2xyz_civil.region_boundary import enclosing_face


def line(points,layer='curb',basis='DRAWN_LINE'):
    return {'points_raw':points,'layer':layer,'boundary_from':basis}


@unittest.skipIf(shapely is None,'optional Shapely unavailable')
class RegionBoundaryTests(unittest.TestCase):
    def test_closed_face_names_each_source(self):
        lines=[line([(0,0),(10,0)],'curb'),line([(10,0),(10,10)],'wall'),
               line([(10,10),(0,10)],'toe'),line([(0,10),(0,0)],'edge')]
        r=enclosing_face((5,5),lines,metres_per_unit=.1)
        self.assertEqual(r['status'],'CLOSED_DRAWN_FACE_CANDIDATE')
        self.assertAlmostEqual(r['area_m2'],1)
        self.assertEqual({s['sources'][0]['layer'] for s in r['sides']},{'curb','wall','toe','edge'})

    def test_open_outline_never_silently_closes(self):
        r=enclosing_face((5,5),[line([(0,0),(10,0),(10,10),(0,10)])])
        self.assertEqual(r['status'],'NO_CLOSED_DRAWN_FACE')
        self.assertIsNone(r['area_m2'])

    def test_analysis_window_does_not_supply_missing_side(self):
        r=enclosing_face((5,5),[line([(0,0),(10,0),(10,10),(0,10)])],analysis_window=(0,0,10,10))
        self.assertIsNone(r['polygon_raw'])

    def test_intersections_are_noded_and_seed_selects_one_face(self):
        r=enclosing_face((2,5),[line([(0,0),(10,0),(10,10),(0,10),(0,0)]),line([(4,-2),(4,12)],'wall')])
        self.assertAlmostEqual(r['area_raw2'],40)
        self.assertEqual(r['arrangement']['faces'],2)

    def test_chain_bridge_is_not_declared_drawn(self):
        r=enclosing_face((5,5),[line([(0,0),(10,0),(10,10),(0,10)]),line([(0,10),(0,0)],basis='CHAIN_GAP_CANDIDATE')])
        self.assertEqual(r['status'],'UNSUPPORTED_CLOSURE')

    def test_seed_on_shared_boundary_refused(self):
        r=enclosing_face((0,5),[line([(0,0),(10,0),(10,10),(0,10),(0,0)])])
        self.assertEqual(r['status'],'SEED_ON_BOUNDARY')

    def test_inner_ring_is_preserved_and_subtracted(self):
        r=enclosing_face((1,1),[line([(0,0),(10,0),(10,10),(0,10),(0,0)]),line([(3,3),(7,3),(7,7),(3,7),(3,3)])])
        self.assertEqual(r['area_raw2'],84)
        self.assertEqual(len(r['holes_raw']),1)
