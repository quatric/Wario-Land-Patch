#!/usr/bin/env python3
"""Command-line tool to patch a .wbfs/.iso disc image in place.

    python3 tools/patch_disc.py "Wario Land Shake It.wbfs" --mode ba --cc --gc
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import disc
import features
import patcher


def main():
    ap = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    ap.add_argument('image', help='Path to .wbfs or .iso disc image')
    ap.add_argument('--mode', choices=['ba', 'yb'], default='ba',
                    help='Button mapping mode: ba (default, A=Jump, B=Attack) or yb (B=Jump, Y=Attack)')
    ap.add_argument('--cc', action='store_true', help='Enable Classic Controller support')
    ap.add_argument('--gc', action='store_true', help='Enable GameCube Controller support (port 1)')
    ap.add_argument('--cc-yb', action='store_true', help='Enable Classic Controller (Y/B Mode)')
    ap.add_argument('--gc-yb', action='store_true', help='Enable GameCube Controller (Y/B Mode)')
    a = ap.parse_args()

    explicit = [n for n in patcher.ORDER if getattr(a, n.replace('_', '-'), False) or getattr(a, n, False)]
    if explicit:
        which = explicit
    else:
        if a.cc and not a.gc:
            which = ['cc_yb' if a.mode == 'yb' else 'cc']
        elif a.gc and not a.cc:
            which = ['gc_yb' if a.mode == 'yb' else 'gc']
        else:
            # Default: enable both CC and GC for the chosen mode
            which = ['cc_yb', 'gc_yb'] if a.mode == 'yb' else ['cc', 'gc']

    ok = []
    disc.run_patch(a.image, print, lambda good, msg: ok.append(good), which)
    sys.exit(0 if ok and ok[0] else 1)


if __name__ == '__main__':
    main()
