"""Read-only, redacted text audit of locally reachable Git history.

This is a limited pattern scan, not a secret-scanner replacement, media review,
licence clearance, or release authorization. Never prints matched content.
"""
from __future__ import annotations

import argparse
from collections import Counter
import io
import json
from pathlib import Path
import re
import subprocess

MAX_OBJECT_BYTES = 4 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
MAX_OBJECTS = 100_000
_TERMS = (('ty', 'bo'), ('bee', 'die'), ('black', 'bird'),
          ('port', ' ', 'kells'), ('mich', 'ael'), ('m', 'vu'), ('one', 'drive'))
RULES = {f'repository_term_{i}': re.compile(rb'\b' + re.escape(''.join(parts).encode()) + rb'\b', re.I)
         for i, parts in enumerate(_TERMS)}
RULES.update({
    'github_token_shape': re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
    'aws_access_key_shape': re.compile(rb'\bAKIA[A-Z0-9]{16}\b'),
    'private_key_header': re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
    'local_domain_email': re.compile(rb'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.local\b', re.I),
    'personal_home_path': re.compile(rb'(?:[A-Z]:[\\/]+Users[\\/]+|/(?:Users|home)/)[^\s\x00<>]+', re.I),
    'project_example_reference': re.compile(rb'\b' + b'King' + rb'[ _-]*' + b'Road' + rb'\b', re.I),
})


def detect(data: bytes) -> list[str]:
    return sorted(name for name, pattern in RULES.items() if pattern.search(data))


def git(root: Path, *args: str, data: bytes | None = None) -> bytes:
    result = subprocess.run(['git', '-C', str(root), *args], input=data,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=90, check=False)
    if result.returncode:
        raise RuntimeError('GIT_COMMAND_FAILED')
    return result.stdout


def audit(root: Path, max_object_bytes: int = MAX_OBJECT_BYTES) -> dict:
    if git(root, 'rev-parse', '--is-shallow-repository').strip() != b'false':
        raise RuntimeError('FULL_HISTORY_REQUIRED')
    entries = git(root, 'rev-list', '--objects', '--all').splitlines()
    ids = sorted(set(line.split(b' ', 1)[0] for line in entries))
    if not ids or len(ids) > MAX_OBJECTS:
        raise RuntimeError('OBJECT_COUNT_OUT_OF_BOUNDS')
    path_counts: Counter = Counter()
    for line in entries:
        if b' ' in line:
            path_counts.update(detect(line.split(b' ', 1)[1]))
    inventory = git(root, 'cat-file', '--batch-check=%(objectname) %(objecttype) %(objectsize)',
                    data=b'\n'.join(ids) + b'\n')
    chosen, skipped, total_bytes = [], 0, 0
    types: Counter = Counter()
    for line in inventory.splitlines():
        oid, kind, size_text = line.split()
        size = int(size_text)
        types[kind.decode('ascii')] += 1
        if size > max_object_bytes or total_bytes + size > MAX_TOTAL_BYTES:
            skipped += 1
            continue
        chosen.append(oid)
        total_bytes += size
    if not chosen:
        raise RuntimeError('NO_OBJECTS_SCANNED')
    stream = io.BytesIO(git(root, 'cat-file', '--batch', data=b'\n'.join(chosen) + b'\n'))
    counts: Counter = Counter()
    affected, binary_blobs = 0, 0
    for expected in chosen:
        oid, kind, size_text = stream.readline().split()
        size = int(size_text)
        body = stream.read(size)
        if oid != expected or len(body) != size or stream.read(1) != b'\n':
            raise RuntimeError('INVALID_OBJECT_STREAM')
        found = detect(body)
        counts.update(found)
        affected += bool(found)
        if kind == b'blob':
            try:
                body.decode('utf-8')
                binary_blobs += b'\x00' in body
            except UnicodeDecodeError:
                binary_blobs += 1
    refs = git(root, 'for-each-ref', '--format=%(refname)').splitlines()
    status = 'INCOMPLETE' if skipped else ('REVIEW_REQUIRED' if affected or path_counts else 'NO_PATTERN_MATCHES')
    return {
        'schema_version': 1,
        'scope': 'raw locally reachable Git objects and rev-list paths; not uncommitted files',
        'automated_text_scan': status,
        'head': git(root, 'rev-parse', 'HEAD').decode('ascii').strip(),
        'local_ref_count': len(refs),
        'object_counts': dict(sorted(types.items())),
        'objects_scanned': len(chosen), 'objects_skipped': skipped,
        'objects_with_matches': affected,
        'object_rule_counts': dict(sorted(counts.items())),
        'path_rule_counts': dict(sorted(path_counts.items())),
        'binary_blobs_requiring_separate_review': binary_blobs,
        'ready_for_public_release': False,
        'limitations': [
            'Pattern matches may be synthetic tests or legitimate notices; review before editing.',
            'Zero matches do not prove absence of sensitive data.',
            'Images, compressed media, archives, PDF streams and LFS contents are not decoded.',
            'Server-only refs, PR/issue text, caches, releases, Actions artifacts and forks are not covered.',
            'Authorship, licences, source rights and live application acceptance require separate review.',
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path, default=Path('.'))
    args = parser.parse_args()
    try:
        report = audit(args.repo)
    except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired):
        print(json.dumps({'automated_text_scan': 'INCOMPLETE', 'ready_for_public_release': False,
                          'error': 'Audit could not complete. Check Git availability, full history and resource limits.'}))
        return 2
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report['automated_text_scan'] == 'NO_PATTERN_MATCHES' else 1


if __name__ == '__main__':
    raise SystemExit(main())
