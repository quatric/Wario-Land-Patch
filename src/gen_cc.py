"""Build the Classic Controller feature: Vague Rant's Gecko codes, as ops."""
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, '..', 'tools'))
from layout import CC_BASE, CC_END
from ops import Feature, Hook

def parse(text):
    lines = [l.split()[:2] for l in text.splitlines() if l.strip() and not l.lstrip().startswith(('*', '$', '#'))]
    i, out = 0, []
    while i < len(lines):
        a, b = lines[i]
        kind, addr = int(a[:2], 16), 0x80000000 | (int(a[2:], 16) & 0x01FFFFFF)
        if kind == 0xC2:
            n = int(b, 16)
            ws = [int(x, 16) for ln in lines[i + 1:i + 1 + n] for x in ln]
            out.append(('C2', addr, ws))
            i += 1 + n
        else:
            raise ValueError('unsupported code line: %s %s' % (a, b))
    return out

def build(region, dol, mode='ba'):
    """mode: 'ba' (B/A Mode, default) or 'yb' (Y/B Mode)"""
    fn = f'{region}_{mode}.txt'
    text = open(os.path.join(HERE, 'cc', fn)).read()
    ops, cur = [], CC_BASE
    hook_notes = [
        'motion/shake: right stick -> tilt angle, button -> shake pulses',
        'pointer: right stick -> HOME Menu IR pointer',
        'read_kpad_stick: left stick -> digital D-pad directions',
        'read_kpad_button: Classic Controller buttons -> Wii Remote bits'
    ]
    parsed = parse(text)
    for idx, (kind, addr, body) in enumerate(parsed):
        orig = struct.unpack('>I', dol.read(addr, 4))[0]
        # In Gecko C2 code, body's last word is the displaced instruction (or zero/nop)
        note = hook_notes[idx] if idx < len(hook_notes) else ''
        # payload[:-1] is executed, payload[-1] placeholder becomes branch back to site+4
        ops.append(Hook(addr, orig, body, cur, note=note))
        cur += (len(body) * 4 + 15) & ~15
    if cur > CC_END:
        raise SystemExit(f'cc code overflows its window: 0x{cur:X} > 0x{CC_END:X}')
    mode_title = 'B/A Mode' if mode == 'ba' else 'Y/B Mode'
    feat_name = 'cc' if mode == 'ba' else 'cc_yb'
    return Feature(feat_name, f'Classic Controller ({mode_title})', region, ops)
