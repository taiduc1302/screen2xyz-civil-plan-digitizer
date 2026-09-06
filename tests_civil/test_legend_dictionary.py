import unittest

from screen2xyz_civil.legend_dictionary import boxed_legends,pair_labels,appearance_signature,match_signatures


def word(text,box):return {'text':text,'rect_view':box}


def path(box,segments,colour=(120,120,120),layer=''):
    return {'rect_view':box,'segments':segments,'stroke':colour,'fill':None,'width':1,'layer':layer}


class LegendTests(unittest.TestCase):
    def test_smallest_enclosing_legend_not_page_frame(self):
        r=boxed_legends([word('LEGEND',[10,10,50,20])],[[0,0,100,150],[0,0,800,1000]],800000)
        self.assertEqual(r[0]['rect_view'],[0,0,100,150])

    def test_unboxed_heading_stays_unresolved(self):
        r=boxed_legends([word('LEGEND',[10,10,50,20])],[],800000)
        self.assertIsNone(r[0]['rect_view'])

    def test_wrapped_labels_and_adjacent_columns(self):
        swatches=[{'rect_view':[10,40,30,60]},{'rect_view':[200,40,220,60]}]
        words=[word('FULL DEPTH',[40,40,120,50]),word('REPLACEMENT',[40,53,140,63]),word('EXISTING',[230,40,300,50])]
        pairs,unpaired=pair_labels(words,swatches)
        self.assertEqual(pairs[0]['label'],'FULL DEPTH REPLACEMENT')
        self.assertEqual(pairs[1]['label'],'EXISTING')
        self.assertFalse(unpaired)

    def test_equal_label_association_is_not_chosen(self):
        pairs,_=pair_labels([word('PIPE',[40,40,60,50])],[{'rect_view':[10,40,30,50]},{'rect_view':[70,40,90,50]}])
        self.assertTrue(all(p['status']=='AMBIGUOUS_LABEL' for p in pairs))

    def test_duplicate_paths_do_not_change_signature(self):
        a=path([0,0,10,10],[[0,0,10,10]])
        self.assertEqual(appearance_signature([a]),appearance_signature([a,a]))

    def test_translation_preserves_angles_and_pitch(self):
        a=[path([0,0,10,10],[[0,0,10,10]]),path([0,5,10,15],[[0,5,10,15]])]
        b=[path([100,100,110,110],[[100,100,110,110]]),path([100,105,110,115],[[100,105,110,115]])]
        x,y=appearance_signature(a)[0],appearance_signature(b)[0]
        self.assertEqual(x['angles_deg'],y['angles_deg'])
        self.assertAlmostEqual(x['pitch_pt']['44'],y['pitch_pt']['44'],delta=.11)

    def test_same_colour_crosshatch_requires_both_angles(self):
        cross=appearance_signature([path([0,0,10,10],[[0,0,10,10],[0,10,10,0]])])
        single=appearance_signature([path([0,0,10,10],[[0,0,10,10]])])
        matches=match_signatures(cross,{'cross':cross,'single':single})
        self.assertEqual(matches[0]['layer'],'cross')
        self.assertGreater(matches[0]['score'],matches[1]['score'])

    def test_shared_background_does_not_identify_hatch_layer(self):
        hatch=appearance_signature([path([0,0,10,10],[[0,0,10,10]])])
        fill=path([0,0,10,10],[]);fill['fill']=(230,230,230)
        background=appearance_signature([fill])
        matches=match_signatures(hatch+background,{'hatch':hatch,'background':background})
        self.assertEqual([m['layer'] for m in matches],['hatch'])

    def test_flat_vector_has_no_invented_layer_name(self):
        sig=appearance_signature([path([0,0,10,10],[[0,0,10,10]])])
        self.assertIsNone(match_signatures(sig,{'':sig})[0]['layer'])

    def test_hidden_coloured_path_has_no_pixel_witness(self):
        try:
            from PIL import Image
            import numpy
        except ImportError:self.skipTest('optional image dependencies unavailable')
        from screen2xyz_civil.legend_dictionary import _visible
        image=Image.new('RGB',(100,100),'white')
        self.assertFalse(_visible([path([10,10,20,20],[[10,10,20,20]],(255,0,0))],image,1))
        image=Image.new('RGB',(500,500),'black')
        self.assertFalse(_visible([path([-100,-100,-90,-90],[[-100,-100,-90,-90]],(0,0,0))],image,1))

    def test_black_exact_geometry_is_retained(self):
        sig=appearance_signature([path([0,0,10,10],[[0,0,10,10]],(0,0,0))])
        self.assertEqual(match_signatures(sig,{'black':sig})[0]['score'],.8)

    def test_label_baseline_jitter_does_not_reverse_words(self):
        pairs,_=pair_labels([word('ROAD',[50,12,70,17]),word('WIDENING',[73,11,110,16])],[{'rect_view':[10,10,40,20]}])
        self.assertEqual(pairs[0]['label'],'ROAD WIDENING')

    def test_quad_rectangle_on_rotated_cover(self):
        try:import pymupdf as fitz
        except ImportError:self.skipTest('optional PyMuPDF unavailable')
        from screen2xyz_civil.legend_dictionary import _paths
        doc=fitz.open();page=doc.new_page(width=200,height=300)
        page.draw_quad(fitz.Quad((10,20),(90,20),(10,100),(90,100)))
        page.set_rotation(270)
        objects,boxes=_paths(page)
        self.assertEqual(len(boxes),1)
        self.assertEqual(boxes[0],[20,110,100,190])
        doc.close()
