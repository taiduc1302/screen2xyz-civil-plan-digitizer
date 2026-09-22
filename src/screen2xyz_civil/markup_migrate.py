"""Copy-on-write replacement of revised sheet content, preserving annotations.

Uses pypdf object cloning, including annotation appearance/measurement data;
does not redraw measurements or alter source PDFs. An external manifest flags
change-window intersections. The output is always a proposal working copy.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path


def intersects(a,b):
    return not (a[2]<b[0] or b[2]<a[0] or a[3]<b[1] or b[3]<a[1])


def _hash(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def migrate(base_pdf,revised_pdf,page_map,*,output_pdf,change_windows):
    """Replace page drawing dictionaries; preserve annotation raw geometry.

    page_map maps zero-based base page -> revised page. Equal page boxes and
    rotations are mandatory. change_windows maps base page -> raw rectangles.
    An absent window list is UNKNOWN and flags every annotation on that page.
    This migrates the saved PDF only; unsaved host/session state is unavailable.
    """
    from pypdf import PdfReader,PdfWriter
    from pypdf.generic import NameObject,TextStringObject,ArrayObject,DictionaryObject
    source=Path(base_pdf).resolve();revision=Path(revised_pdf).resolve();target=Path(output_pdf).resolve()
    if target.exists():raise FileExistsError(target)
    if target.with_suffix('.migration.json').exists():raise FileExistsError(target.with_suffix('.migration.json'))
    if target in (source,revision):raise ValueError('source PDFs are immutable')
    before={str(p):_hash(p) for p in (source,revision)}
    base=PdfReader(source);rev=PdfReader(revision);writer=PdfWriter(clone_from=base)
    for reader in (base,rev):
        oc=reader.trailer['/Root'].get('/OCProperties')
        if oc:
            oc=oc.get_object();config=oc.get('/D',{})
            if str(config.get('/BaseState','/ON'))!='/ON' or any(config.get(k) for k in ('/AS','/RBGroups','/Locked')):
                raise ValueError('unsupported optional-content configuration')
    for old_index,new_index in page_map.items():
        if not isinstance(old_index,int) or not isinstance(new_index,int) or not 0<=old_index<len(base.pages) or not 0<=new_index<len(rev.pages):
            raise ValueError('page indices must be nonnegative and within source documents')
        for window in change_windows.get(old_index) or []:
            if len(window)!=4 or not all(math.isfinite(v) for v in window) or window[0]>window[2] or window[1]>window[3]:
                raise ValueError('finite ordered raw change rectangle required')
    report={'status':'AI_PROPOSED','source_sha256':before,'output':str(target),
            'saved_pdf_only':True,'pages':[],'render_checked':False,
            'signature_status':'UNSIGNED_DERIVATIVE: rewriting invalidates original digital signatures; source PDFs remain authoritative'}
    for old_index,new_index in page_map.items():
        old=writer.pages[old_index];new=rev.pages[new_index]
        for name in ('mediabox','cropbox'):
            if tuple(getattr(old,name))!=tuple(getattr(new,name)):raise ValueError(f'page {old_index}: {name} mismatch')
        if old.rotation!=new.rotation:raise ValueError('page rotation mismatch; raw migration refused')
        if old.get('/UserUnit',1)!=new.get('/UserUnit',1):raise ValueError('UserUnit mismatch')
        omitted=[]
        for reference in new.get('/Annots',[]):
            annot=reference.get_object();r=[float(v) for v in annot.get('/Rect',[])]
            if len(r)==4 and (r[0]==r[2] or r[1]==r[3]) and annot.get('/FT')=='/Sig':
                omitted.append({'type':'ZERO_AREA_SIGNATURE_WIDGET','field':str(annot.get('/T',''))})
            else:raise ValueError('revised page has visible or unsupported annotations; preserve them explicitly before migration')
        # Keep page identity (/Parent, /Annots) so all annotation /P references
        # continue to refer to this page. Clone every revised drawing dependency.
        for key in ('/Contents','/Resources','/Group','/Metadata','/Thumb','/VP','/PieceInfo'):
            if key in old:del old[key]
            if key in new:old[NameObject(key)]=new.raw_get(key).clone(writer)
        windows=change_windows.get(old_index)
        rows=[]
        for reference in old.get('/Annots',[]):
            annot=reference.get_object();rect=[float(v) for v in annot.get('/Rect',[])]
            subject=str(annot.get('/Subj',''));identifier=str(annot.get('/NM',''))
            changed=windows is None or len(rect)!=4 or any(intersects(rect,w) for w in windows)
            state='REVIEW_CHANGED_WINDOW' if changed else 'UNCHANGED_WINDOW_CANDIDATE'
            protected=any(term in subject.casefold() for term in ('drawn_by_estimator','corrected by estimator'))
            # Keep protected content byte-for-byte at annotation-dictionary
            # level. Its migration/review status is in this manifest only.
            if not protected:
                annot[NameObject('/Subj')]=TextStringObject(f'AI_PROPOSED | {state} | {subject}')
            rows.append({'id':identifier,'subtype':str(annot.get('/Subtype','')),'rect_raw':rect,
                         'original_subject':subject,'protected':protected,'status':state})
        report['pages'].append({'base_page_index':old_index,'revised_page_index':new_index,
                                'omitted_revision_annotations':omitted,
                                'annotations':rows,'count':len(rows),'change_window_count':None if windows is None else len(windows)})
    # Revised content may reference new OCGs. Preserve both sets' OCG objects;
    # merge default ON/OFF lists without renaming the groups used by resources.
    rev_oc=rev.trailer['/Root'].get('/OCProperties')
    if rev_oc:
        imported=rev_oc.get_object().clone(writer)
        existing=writer.root_object.get('/OCProperties')
        if existing:
            existing=existing.get_object()
            for key in ('/OCGs',):
                existing.setdefault(NameObject(key),ArrayObject()).extend(imported.get(key,[]))
            config=existing.setdefault(NameObject('/D'),DictionaryObject())
            for key in ('/ON','/OFF','/Order'):
                config.setdefault(NameObject(key),ArrayObject()).extend(imported.get('/D',{}).get(key,[]))
        else:writer.root_object[NameObject('/OCProperties')]=imported
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('xb') as out:writer.write(out)
    for p,digest in before.items():
        if _hash(p)!=digest:raise RuntimeError('source changed during migration')
    report['output_sha256']=_hash(target)
    target.with_suffix('.migration.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    return report
