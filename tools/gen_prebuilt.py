#!/usr/bin/env python3
"""Regenerate tools/prebuilt/*.json from src/ (needs devkitPPC and the retail DOLs).

    WARIO_DOLS=/path/with/RWLE01.dol,RWLP01.dol... python3 tools/gen_prebuilt.py
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, '..', 'src'))
from dol import Dol
from features import PREBUILT, dump
from regions import REGIONS
import gen_cc
import gen_gc


def dol_for(region):
    env = os.environ.get('WARIO_DOL_' + region)
    if env:
        return Dol(env)
    base = os.environ.get('WARIO_DOLS', '.')
    if base:
        p = os.path.join(base, region + '.dol')
        if os.path.exists(p):
            return Dol(p)
    sys.exit('set WARIO_DOLS=<dir with %s.dol> or WARIO_DOL_%s=<path>' % (region, region))


def main():
    os.makedirs(PREBUILT, exist_ok=True)
    usa_dol = dol_for('RWLE01')
    gen_gc.USA_DOL = usa_dol

    tasks = [
        ('cc', gen_cc.build, 'ba'),
        ('cc_yb', gen_cc.build, 'yb'),
        ('gc', gen_gc.build, 'ba'),
        ('gc_yb', gen_gc.build, 'yb'),
    ]

    for feat_name, builder, mode in tasks:
        for region in REGIONS:
            f = builder(region, dol_for(region), mode=mode)
            path = os.path.join(PREBUILT, f'{feat_name}_{region}.json')
            with open(path, 'w') as fh:
                json.dump(dump(f), fh, indent=1)
                fh.write('\n')
            print(f'{feat_name:6s} {region}  {len(f.ops)} ops -> {os.path.relpath(path)}')


if __name__ == '__main__':
    main()
