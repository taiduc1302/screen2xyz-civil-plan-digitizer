import unittest
from screen2xyz_civil.archive_layers import aggregate
from screen2xyz_civil.cad_layers import classify_layer_name
from screen2xyz_civil.legend_symbols import rank_legend


class ArchiveDictionaryTests(unittest.TestCase):
    def test_duplicates_and_recurrence_do_not_promote_confidence(self):
        layer={'classification':classify_layer_name('P_Curb').as_dict(),'xref':7}
        a={'sha256':'a','source_id':'project1','consultant':'A','layers':[layer]}
        b={**a,'sha256':'b','source_id':'project2','consultant':'B'}
        row=aggregate([a,a,b])[0]
        self.assertEqual(len(row['sources']),2)
        self.assertEqual(row['consultants'],['A','B'])
        self.assertEqual(row['confidence'],'NAME_ONLY_UNVERIFIED')
        self.assertFalse(row['legend_confirmed'])

    def test_existing_and_proposed_are_not_merged(self):
        layers=[{'classification':classify_layer_name(n).as_dict(),'xref':i} for i,n in enumerate(('E_Curb','P_Curb'))]
        rows=aggregate([{'sha256':'a','source_id':'one','layers':layers}])
        self.assertEqual({r['status_hint'] for r in rows},{'EXISTING','PROPOSED'})


class LegendSymbolTests(unittest.TestCase):
    PLUS=[[0,1,0],[1,1,1],[0,1,0]]
    RING=[[1,1,1],[1,0,1],[1,1,1]]

    def test_padded_scaled_candidate_matches_own_legend(self):
        bigger=[[0]*10 for _ in range(10)]
        for y,row in enumerate(self.PLUS):
            for x,v in enumerate(row):
                for dy in (0,1):
                    for dx in (0,1):bigger[2+y*2+dy][2+x*2+dx]=v
        r=rank_legend(bigger,{'cross':self.PLUS,'ring':self.RING})
        self.assertEqual(r['label'],'cross')
        self.assertEqual(r['ranked'][0]['score'],1)
        self.assertFalse(r['quantity_approved'])

    def test_unknown_and_duplicate_labels_abstain(self):
        self.assertEqual(rank_legend([[0]],{'cross':self.PLUS})['status'],'UNKNOWN')
        self.assertEqual(rank_legend(self.PLUS,{'a':self.PLUS,'b':self.PLUS})['status'],'AMBIGUOUS')
        self.assertEqual(rank_legend([[1,1,1]],{'cross':self.PLUS})['status'],'UNKNOWN')

    def test_bad_masks_and_thresholds_refused(self):
        for mask in ([],[[1],[1,0]],[[255]]):
            with self.assertRaises(ValueError):rank_legend(mask,{})
        with self.assertRaises(ValueError):rank_legend(self.PLUS,{},min_score=float('nan'))
