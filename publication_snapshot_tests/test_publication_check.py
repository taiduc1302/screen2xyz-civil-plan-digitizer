from __future__ import annotations
import importlib.util,json,tempfile,unittest
from pathlib import Path
SPEC=importlib.util.spec_from_file_location("publication_check",Path(__file__).resolve().parents[1]/"tools/publication_check.py")
MOD=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(MOD)

class PublicSnapshotTests(unittest.TestCase):
    def run_check(self,rel,text):
        with tempfile.TemporaryDirectory() as t:
            r=Path(t);(r/"publication").mkdir();(r/"publication/binary_allowlist.json").write_text("{}")
            p=r/rel;p.parent.mkdir(parents=True,exist_ok=True)
            p.write_bytes(text if isinstance(text,bytes) else text.encode())
            return MOD.check(r,git_tracked=False)
    def test_synthetic_text_is_allowed(self):
        self.assertEqual(self.run_check("example.txt","Fictional geometry")['result'],'PASS')
    def test_private_input_folder_is_blocked(self):
        self.assertEqual(self.run_check("pilot/input.txt","test")['result'],'FAIL')
    def test_prohibited_company_is_blocked(self):
        self.assertEqual(self.run_check("example.txt",''.join(('ty','bo')))['result'],'FAIL')
    def test_prohibited_project_is_blocked(self):
        self.assertEqual(self.run_check("example.txt",''.join(('King ','Road')))['result'],'FAIL')
    def test_token_is_blocked_without_echo(self):
        token='gh'+'p_'+'x'*40;r=self.run_check("example.txt",token)
        self.assertEqual(r['result'],'FAIL');self.assertNotIn(token,json.dumps(r))
    def test_unreviewed_binary_is_blocked(self):
        self.assertEqual(self.run_check("example.bin",b"test\0bytes")['result'],'FAIL')
    def test_public_author_identity_is_preserved(self):
        self.assertEqual(self.run_check("NOTICE","Copyright 2026 taiduc1302")['result'],'PASS')
    def test_personal_home_is_blocked(self):
        value='C:'+chr(92)+'Users'+chr(92)+'sample'
        self.assertEqual(self.run_check("example.txt",value)['result'],'FAIL')
    def test_private_key_is_blocked(self):
        value='-----BEGIN '+'PRIVATE KEY'+'-----'
        self.assertEqual(self.run_check("example.txt",value)['result'],'FAIL')
