import hashlib
import json
from pathlib import Path
import tempfile
import unittest
try:
    import pymupdf as fitz
    import pypdf
except ImportError:fitz=None
from screen2xyz_civil.markup_migrate import migrate,intersects


class WindowTests(unittest.TestCase):
    def test_touching_window_is_flagged(self):
        self.assertTrue(intersects([0,0,10,10],[10,5,20,20]))
        self.assertFalse(intersects([0,0,10,10],[11,5,20,20]))


@unittest.skipIf(fitz is None,'optional PDF operator dependencies unavailable')
class MigrationTests(unittest.TestCase):
    def fixture(self,root,subject='test',revised_width=200):
        base=root/'base.pdf';rev=root/'rev.pdf'
        d=fitz.open();p=d.new_page(width=200,height=300)
        p.draw_rect((0,0,200,300),fill=(0,1,0),color=None)
        a=p.add_polygon_annot([(20,20),(80,20),(80,80),(20,80)])
        a.set_info(subject=subject);a.update();d.save(base);d.close()
        d=fitz.open();p=d.new_page(width=revised_width,height=300)
        p.draw_rect((0,0,revised_width,300),fill=(0,0,1),color=None);d.save(rev);d.close()
        return base,rev

    def test_replaced_content_and_preserved_vertices_independent_renderer(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root);out=root/'out.pdf'
            before=hashlib.sha256(base.read_bytes()).hexdigest()
            report=migrate(base,rev,{0:0},output_pdf=out,change_windows={0:[[0,200,100,300]]})
            with fitz.open(base) as a,fitz.open(out) as b:
                pa,pb=a[0],b[0];aa=next(pa.annots());bb=next(pb.annots())
                self.assertEqual(aa.vertices,bb.vertices)
                self.assertEqual(b[0].get_pixmap(annots=False).pixel(150,150),(0,0,255))
                self.assertIn('AI_PROPOSED',bb.info['subject'])
            self.assertEqual(before,hashlib.sha256(base.read_bytes()).hexdigest())
            self.assertEqual(report['pages'][0]['annotations'][0]['status'],'REVIEW_CHANGED_WINDOW')

    def test_protected_subject_preserved(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root,'DRAWN_BY_ESTIMATOR keep')
            out=root/'out.pdf';migrate(base,rev,{0:0},output_pdf=out,change_windows={0:[]})
            with fitz.open(out) as d:self.assertEqual(next(d[0].annots()).info['subject'],'DRAWN_BY_ESTIMATOR keep')

    def test_existing_output_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            with self.assertRaises(FileExistsError):migrate(base,rev,{0:0},output_pdf=base,change_windows={})

    def test_wrong_page_size_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root,revised_width=201)
            with self.assertRaises(ValueError):migrate(base,rev,{0:0},output_pdf=root/'out.pdf',change_windows={})

    def test_missing_diff_is_review_not_unchanged(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            r=migrate(base,rev,{0:0},output_pdf=root/'out.pdf',change_windows={})
            self.assertEqual(r['pages'][0]['annotations'][0]['status'],'REVIEW_CHANGED_WINDOW')

    def test_retained_sidecar_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            (root/'out.migration.json').write_text('retained')
            with self.assertRaises(FileExistsError):migrate(base,rev,{0:0},output_pdf=root/'out.pdf',change_windows={})
            self.assertFalse((root/'out.pdf').exists())

    def test_negative_page_and_invalid_window_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            for mapping,windows in [({-1:0},{}),({0:0},{0:[[0,0,float('nan'),1]]})]:
                with self.assertRaises(ValueError):migrate(base,rev,mapping,output_pdf=root/'out.pdf',change_windows=windows)

    def test_visible_revision_annotation_refused(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            d=fitz.open(rev);p=d[0];p.add_text_annot((50,50),'revision note');other=root/'rev_note.pdf';d.save(other);d.close()
            with self.assertRaisesRegex(ValueError,'revised page'):migrate(base,other,{0:0},output_pdf=root/'out.pdf',change_windows={})

    def test_userunit_mismatch_refused(self):
        from pypdf.generic import NameObject,NumberObject
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            w=pypdf.PdfWriter(clone_from=rev);w.pages[0][NameObject('/UserUnit')]=NumberObject(2)
            other=root/'scaled.pdf';w.write(other)
            with self.assertRaisesRegex(ValueError,'UserUnit'):migrate(base,other,{0:0},output_pdf=root/'out.pdf',change_windows={})

    def test_measure_dictionary_survives_independent_pdf_read(self):
        from pypdf.generic import NameObject,TextStringObject,DictionaryObject
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);base,rev=self.fixture(root)
            w=pypdf.PdfWriter(clone_from=base)
            a=w.pages[0]['/Annots'][0].get_object()
            a[NameObject('/Measure')]=DictionaryObject({NameObject('/Type'):NameObject('/Measure'),NameObject('/R'):TextStringObject('1 in = 20 ft')})
            measured=root/'measured.pdf';w.write(measured)
            out=root/'out.pdf';migrate(measured,rev,{0:0},output_pdf=out,change_windows={0:[]})
            with fitz.open(out) as d:
                p=d[0];a=next(p.annots())
                self.assertIn('1 in = 20 ft',d.xref_get_key(a.xref,'Measure')[1])
