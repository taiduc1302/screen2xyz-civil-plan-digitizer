"""Independent coordinate anchors and fail-closed table evidence tests."""
import hashlib
import tempfile
import unittest
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    fitz = None
from PIL import Image
from screen2xyz_civil.detection import Rect
from screen2xyz_civil.ocr import OcrLine, OcrResult, OcrWord
from screen2xyz_civil.sheet_text import read_words, cells_from_grid, vector_grid


class PixelAnchor:
    def extract(self, image, **kwargs):
        with Image.open(image) as im:
            mask = im.convert('RGB').point(lambda x: x)
            hits = [(x,y) for y in range(im.height) for x in range(im.width)
                    if (lambda p:p[0]>200 and p[1]<50 and p[2]<50)(mask.getpixel((x,y)))]
        xs,ys=zip(*hits)
        w=OcrWord('ANCHOR',Rect(min(xs),min(ys),max(xs)+1,max(ys)+1))
        return OcrResult('SUCCESS','ANCHOR','pixel-test','en-US',0,(OcrLine('ANCHOR',(w,)),))


class SheetTextTests(unittest.TestCase):
    @unittest.skipIf(fitz is None, 'optional PyMuPDF operator dependency unavailable')
    def test_render_pixel_anchor_maps_to_native_box_at_all_rotations(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            for rotation in [0,90,180,270]:
                with self.subTest(rotation=rotation):
                    doc=fitz.open(); p=doc.new_page(width=200,height=300)
                    p.draw_rect(fitz.Rect(40,60,80,90),fill=(1,0,0),color=None)
                    p.set_rotation(rotation); src=td/f'{rotation}.pdf'; doc.save(src); doc.close()
                    before=hashlib.sha256(src.read_bytes()).hexdigest()
                    result=read_words(src,0,(30.3,200.4,90.8,250.2),out_png=td/f'anchor{rotation}.png',dpi=144,adapter=PixelAnchor())
                    for actual,expected in zip(result['words'][0]['rect_raw'],[40,210,80,240]):
                        self.assertAlmostEqual(actual,expected,delta=.6)
                    self.assertEqual(before,hashlib.sha256(src.read_bytes()).hexdigest())

    @unittest.skipIf(fitz is None, 'optional PyMuPDF operator dependency unavailable')
    def test_nonzero_media_origin_all_rotations(self):
        with tempfile.TemporaryDirectory() as td:
            td=Path(td)
            for rot in [0,90,180,270]:
                with self.subTest(rotation=rot):
                    d=fitz.open();p=d.new_page(width=200,height=300)
                    p.set_mediabox(fitz.Rect(10,20,210,320))
                    p.draw_rect(fitz.Rect(40,60,80,90),fill=(1,0,0),color=None)
                    p.set_rotation(rot);src=td/f'{rot}.pdf';d.save(src);d.close()
                    r=read_words(src,0,(40,220,100,270),out_png=td/f'{rot}.png',dpi=144,adapter=PixelAnchor())
                    for actual,expected in zip(r['words'][0]['rect_raw'],[50,230,90,260]):
                        self.assertAlmostEqual(actual,expected,delta=.6)

    @unittest.skipIf(fitz is None, 'optional PyMuPDF operator dependency unavailable')
    def test_existing_render_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            target=Path(td)/'retained.png';target.write_bytes(b'evidence')
            with self.assertRaises(FileExistsError):
                read_words('unused.pdf',0,None,out_png=target)
            self.assertEqual(target.read_bytes(),b'evidence')

    @unittest.skipIf(fitz is None, 'optional PyMuPDF operator dependency unavailable')
    def test_missing_layer_does_not_read_full_sheet(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.pdf'; doc=fitz.open(); doc.new_page(); doc.save(p); doc.close()
            with self.assertRaisesRegex(ValueError,'layer not found'):
                read_words(p,0,None,out_png=Path(td)/'x.png',layers=['absent'],adapter=PixelAnchor())

    @unittest.skipIf(fitz is None, 'optional PyMuPDF operator dependency unavailable')
    def test_invalid_window_is_refused(self):
        with tempfile.TemporaryDirectory() as td:
            p=Path(td)/'test.pdf'; doc=fitz.open(); doc.new_page(); doc.save(p); doc.close()
            for w in [(0,0,0,1),(0,float('nan'),1,2),(10000,10000,11000,11000)]:
                with self.subTest(window=w), self.assertRaises(ValueError):
                    read_words(p,0,w,out_png=Path(td)/'x.png',adapter=PixelAnchor())

    def test_spatial_rows_split_tokens_missing_and_duplicates_preserved(self):
        words=[{'text':t,'rect_view':b,'rect_raw':b} for t,b in [
            ('18.60',[21,21,29,25]),('1+',[1,2,5,7]),('185.74',[6,1,18,6]),('18.60',[21,1,29,5])]]
        rows=cells_from_grid(words,[0,20,40],[0,20,40])
        self.assertEqual(rows[0][0]['text'],'1+ 185.74')
        self.assertEqual(rows[0][1]['numeric_value'],18.60)
        self.assertEqual(rows[1][1]['numeric_value'],18.60)
        self.assertIn('EMPTY_CELL',rows[1][0]['flags'])

    def test_crossing_word_is_flagged_and_grid_must_be_ordered(self):
        r=cells_from_grid([{'text':'450','rect_view':[8,1,19,8]}],[0,10,20],[0,10])
        self.assertIn('WORD_CROSSES_GRID',r[0][1]['flags'])
        with self.assertRaises(ValueError):
            cells_from_grid([],[0,0,2],[0,10])

    def test_stacked_flow_values_keep_vertical_order(self):
        words=[{'text':t,'rect_view':b} for t,b in [
            ('0.210',[1,12,12,18]),('0.138',[2,2,12,8])]]
        cell=cells_from_grid(words,[0,20],[0,20])[0][0]
        self.assertEqual(cell['text'],'0.138\n0.210')
        self.assertIsNone(cell['numeric_value'])

    @unittest.skipIf(fitz is None, 'optional PyMuPDF operator dependency unavailable')
    def test_segmented_table_rules_recovered_without_text_strokes(self):
        with tempfile.TemporaryDirectory() as td:
            src=Path(td)/'grid.pdf'; doc=fitz.open(); p=doc.new_page(width=200,height=200)
            for y in [20,40,60]:
                for x in [20,60]: p.draw_line((x,y),(x+40,y))
            for x in [20,60,100]:
                for y in [20,40]: p.draw_line((x,y),(x,y+20))
            p.insert_text((30,35),'ABC',fontsize=8); doc.save(src); doc.close()
            g=vector_grid(src,0,(19,19,101,61))
            self.assertEqual(g['x_edges'],[20,60,100])
            self.assertEqual(g['y_edges'],[20,40,60])
