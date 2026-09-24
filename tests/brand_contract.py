"""Visual-only contract captured before the brand-kit rollout (includes dirty Claude edits).

Run directly without a database: python tests/brand_contract.py.
Template attributes are compared as a multiset, so layout/classes can change but
existing fields, links, actions, IDs and validation attributes cannot disappear.
"""
import collections
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
BASELINE = Path(__file__).with_name('brand_contract.json')
ATTRS = re.compile(r'''\b(name|id|href|action|method|type|min|max|minlength|maxlength|pattern|target|rel|data-confirm|data-fee-warning)\s*=\s*("[^"]*"|'[^']*')''')


def signature(source):
    tags = re.findall(r'<(?:input|textarea|select|button|form|a)\b[^>]*>', source, re.S)
    result = collections.Counter()
    for tag in tags:
        attrs = sorted(ATTRS.findall(tag))
        flags = re.findall(r'\b(?:required|disabled|multiple|readonly)\b', tag)
        payload = [tag.split()[0], attrs, flags]
        result[json.dumps(payload, ensure_ascii=False)] += 1
    return dict(result)


def snapshot():
    return {p.name: signature(p.read_text(encoding='utf-8')) for p in sorted((ROOT/'app/templates').glob('*.html'))}


def verify():
    current = snapshot()
    baseline = json.loads(BASELINE.read_text(encoding='utf-8'))
    for name, expected in baseline.items():
        missing = collections.Counter(expected) - collections.Counter(current[name])
        assert not missing, f'Functional markup removed/changed in {name}: {missing}'
    print(f'Functional controls preserved across {len(baseline)} templates.')


if __name__ == '__main__':
    if '--snapshot' in sys.argv:
        print(json.dumps(snapshot(), ensure_ascii=True, indent=2))
    else:
        verify()
