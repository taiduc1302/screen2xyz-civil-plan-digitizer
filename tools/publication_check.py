#!/usr/bin/env python3
"""Fail-closed scan of the public source snapshot, not GitHub cached history."""
from __future__ import annotations
import argparse, hashlib, json, re, subprocess, sys
from pathlib import Path

TERMS = tuple("".join(x) for x in (
    ("ty","bo"), ("bee","die"), ("black","bird"), ("port"," kells"),
    ("one","drive"), ("King","Road"), ("King ","Road"), ("king_","road"),
    ("Lef","euvre"), ("Hunt","ingdon"), ("Abbots","ford"),
    ("24-","047"), ("8293-","24"), ("1220-2026-","4266"),
))
POLICY = [re.compile(re.escape(x),re.I) for x in TERMS]
TOKEN = re.compile(r"(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{35,}|AKIA[A-Z0-9]{16})")
HOME = re.compile(r"(?i)(?:[a-z]:[\\/]+Users[\\/]+[a-z0-9]|/(?:home|Users)/[a-z0-9])")
KEY = re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")
EXCLUDED = {".git",".venv","__pycache__",".pytest_cache"}


def check(root: Path, *, git_tracked: bool=True) -> dict:
    root=root.resolve()
    if git_tracked:
        p=subprocess.run(["git","-C",str(root),"ls-files","-z"],capture_output=True,check=True)
        paths=[x.decode() for x in p.stdout.split(b"\0") if x]
    else:
        paths=[p.relative_to(root).as_posix() for p in root.rglob("*")
               if p.is_file() and not any(x in EXCLUDED for x in p.relative_to(root).parts)]
    allow=json.loads((root/"publication/binary_allowlist.json").read_text())
    findings=[];binary_count=0
    for rel in sorted(paths):
        path=root/rel
        if path.is_symlink() or Path(rel).is_absolute() or ".." in Path(rel).parts:
            findings.append({"rule":"unsafe_path"});continue
        if Path(rel).parts[0] in {"pilot","raw","private-validation"}:
            findings.append({"rule":"private_material"})
        if any(p.search(rel) for p in POLICY):findings.append({"rule":"project_path"})
        data=path.read_bytes()
        try:text=data.decode("utf-8");binary="\0" in text
        except UnicodeDecodeError:text="";binary=True
        if binary:
            binary_count+=1
            if allow.get(rel) != hashlib.sha256(data).hexdigest():
                findings.append({"rule":"unreviewed_binary"})
            continue
        if any(p.search(text) for p in POLICY):findings.append({"rule":"project_identifier"})
        if HOME.search(text):findings.append({"rule":"personal_home_path"})
        if TOKEN.search(text) or KEY.search(text):findings.append({"rule":"credential_shape"})
    return {"scope":"tracked source snapshot" if git_tracked else "unpacked source snapshot",
            "files_checked":len(paths),"binary_files_allowlisted":binary_count,
            "findings":findings,"result":"PASS" if not findings else "FAIL",
            "not_covered":["GitHub cached or server-only refs","external clones","native Revu acceptance"]}


def main():
    p=argparse.ArgumentParser();p.add_argument("--root",type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument("--unpacked",action="store_true");a=p.parse_args()
    try:r=check(a.root,git_tracked=not a.unpacked)
    except Exception as e:
        print(json.dumps({"result":"ERROR","error_type":type(e).__name__}));return 2
    print(json.dumps(r,indent=2));return 0 if r["result"]=="PASS" else 1

if __name__=="__main__":raise SystemExit(main())
