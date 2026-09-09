"""Read-only cross-set OCG name evidence; recurrence is not feature approval."""
from dataclasses import asdict
from pathlib import Path
import hashlib
from .cad_layers import classify_layer_name, _import_pymupdf


def inventory_pdf(path, *, source_id, consultant=None):
    path = Path(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    with _import_pymupdf().open(str(path)) as doc:
        layers = []
        for xref, info in (doc.get_ocgs() or {}).items():
            name = info.get('name', '')
            classification = asdict(classify_layer_name(name))
            layers.append({'xref':xref, 'name':name, 'default_on':info.get('on'),
                           'classification':classification,
                           'confidence':'NAME_ONLY_UNVERIFIED' if classification['hint'] else 'UNCLASSIFIED',
                           'legend_confirmed':False})
        return {'path':str(path), 'sha256':digest, 'source_id':source_id,
                'consultant':consultant, 'consultant_basis':'SUPPLIED' if consultant else 'UNKNOWN',
                'pages':doc.page_count, 'producer':doc.metadata.get('producer'), 'layers':layers}


def aggregate(records):
    """Deduplicate byte-identical PDFs; preserve incompatible status hints."""
    seen=set(); groups={}
    for record in records:
        if record['sha256'] in seen: continue
        seen.add(record['sha256'])
        for layer in record['layers']:
            c=layer['classification']; key=(c['short'],c['hint'],c['status'])
            row=groups.setdefault(key, {'short':c['short'], 'feature_hint':c['hint'],
                'status_hint':c['status'], 'confidence':'NAME_ONLY_UNVERIFIED' if c['hint'] else 'UNCLASSIFIED',
                'sources':[], 'consultants':[], 'legend_confirmed':False})
            ref={'source_id':record['source_id'],'sha256':record['sha256'],'xref':layer['xref']}
            if ref not in row['sources']: row['sources'].append(ref)
            if record.get('consultant') and record['consultant'] not in row['consultants']:
                row['consultants'].append(record['consultant'])
    return sorted(groups.values(),key=lambda r:(r['short'],r['status_hint']))
