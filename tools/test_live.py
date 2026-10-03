#!/usr/bin/env python3
"""Automated live verification of controller input in Dolphin emulator."""
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from gdbmem import Gdb

DOLPHIN = '/Applications/Dolphin.app/Contents/MacOS/Dolphin'
U = '/tmp/wario_dolphin'
PORT = 2163
DOL_PATH = '/tmp/test_wario_fst/sys/main.dol'


def setup_profile():
    if os.path.exists(U):
        shutil.rmtree(U)
    os.makedirs(os.path.join(U, 'Config'), exist_ok=True)
    os.makedirs(os.path.join(U, 'Pipes'), exist_ok=True)

    with open(os.path.join(U, 'Config', 'Dolphin.ini'), 'w') as f:
        f.write(f"""[General]
GDBPort = {PORT}
[Core]
SIDevice0 = 6
CPUThread = False
EnableCheats = False
[DSP]
Backend = No Audio Output
[Interface]
ConfirmStop = False
[Input]
BackgroundInput = True
""")

    with open(os.path.join(U, 'Config', 'WiimoteNew.ini'), 'w') as f:
        f.write("""[Wiimote1]
Source = 0
[Wiimote2]
Source = 0
[Wiimote3]
Source = 0
[Wiimote4]
Source = 0
""")

    with open(os.path.join(U, 'Config', 'GCPadNew.ini'), 'w') as f:
        f.write("""[GCPad1]
Device = Pipe/0/gcpipe
Buttons/A = `Button A`
Buttons/B = `Button B`
Buttons/X = `Button X`
Buttons/Y = `Button Y`
Buttons/Z = `Button Z`
Buttons/Start = `Button START`
Main Stick/Up = `Axis MAIN Y +`
Main Stick/Down = `Axis MAIN Y -`
Main Stick/Left = `Axis MAIN X -`
Main Stick/Right = `Axis MAIN X +`
D-Pad/Up = `Button D_UP`
D-Pad/Down = `Button D_DOWN`
D-Pad/Left = `Button D_LEFT`
D-Pad/Right = `Button D_RIGHT`
""")

    pipe_path = os.path.join(U, 'Pipes', 'gcpipe')
    if not os.path.exists(pipe_path):
        os.mkfifo(pipe_path)
    return pipe_path


def main():
    if not os.path.exists(DOL_PATH):
        sys.exit(f'Error: {DOL_PATH} does not exist. Extract and patch a game first.')

    pipe_path = setup_profile()

    print('Launching Dolphin...')
    log = open('/tmp/wario_dolphin.log', 'w')
    p = subprocess.Popen([DOLPHIN, '-u', U, '-e', DOL_PATH, '-b', '-v', 'Null'],
                         stdout=log, stderr=log)

    g = None
    pipe = None
    try:
        print('Waiting for GDB stub on port %d...' % PORT)
        for _ in range(40):
            try:
                g = Gdb(port=PORT, timeout=10)
                break
            except Exception:
                time.sleep(0.5)
        if not g:
            raise RuntimeError('Could not connect to Dolphin GDB stub')
        print('Connected to Dolphin GDB stub.')

        # Wait for pipe to be available for writing
        for _ in range(30):
            try:
                pipe = os.open(pipe_path, os.O_WRONLY | os.O_NONBLOCK)
                break
            except OSError:
                time.sleep(0.5)
        if pipe is None:
            raise RuntimeError('Could not open GCPad pipe')
        print('Opened GCPad pipe.')

        g.cont()
        print('Game executing... waiting 8s for initialization...')
        time.sleep(8)

        def read_state(label):
            g.interrupt()
            g.drain(1.0)
            # Read STATE at 0x800041C0
            st_raw = g.read_mem(0x800041C0, 16)
            probe_tb, busy_tb, norep, ours, prev_btn = struct.unpack('>IIBBH', st_raw[:12])

            # Read KPAD struct channel 0 at 0x80603118
            kpad_raw = g.read_mem(0x80603118, 0x80)
            btn_hold, btn_down, btn_up = struct.unpack('>III', kpad_raw[0:12])
            dev_type, dev_err = kpad_raw[0x5C], kpad_raw[0x5D]
            cc_hold, cc_down, cc_up = struct.unpack('>III', kpad_raw[0x60:0x6C])

            print(f'[{label}] STATE: ours={ours}, prev_btn=0x{prev_btn:04X} | '
                  f'KPAD: dev={dev_type} (err={dev_err}) | '
                  f'CC hold=0x{cc_hold:04X} | Main hold=0x{btn_hold:04X}')
            g.cont()
            return {
                'ours': ours,
                'dev_type': dev_type,
                'cc_hold': cc_hold,
                'btn_hold': btn_hold,
            }

        # 1. Idle state
        s0 = read_state('IDLE')

        # 2. Press GC A
        print('\n--> Pressing GameCube A button...')
        os.write(pipe, b'PRESS A\n')
        time.sleep(2)
        s_a = read_state('PRESSED GC A')

        # 3. Release A, Press GC B
        print('\n--> Releasing A, Pressing GameCube B button...')
        os.write(pipe, b'RELEASE A\nPRESS B\n')
        time.sleep(2)
        s_b = read_state('PRESSED GC B')

        # 4. Release B, Press GC Start
        print('\n--> Releasing B, Pressing GameCube Start button...')
        os.write(pipe, b'RELEASE B\nPRESS START\n')
        time.sleep(2)
        s_start = read_state('PRESSED GC START')

        os.write(pipe, b'RELEASE START\n')

        # Verify findings
        print('\n=== Verification Summary ===')
        print(f"Hook active & synthesized: ours={s_a['ours']}")
        print(f"Classic Controller detected by game: dev_type={s_a['dev_type']} (expected 2)")
        print(f"GC A generated Classic A (0x0010): cc_hold=0x{s_a['cc_hold']:04X}")
        print(f"GC B generated Classic B (0x0040): cc_hold=0x{s_b['cc_hold']:04X}")
        print(f"GC Start generated Classic Plus (0x0400): cc_hold=0x{s_start['cc_hold']:04X}")

        success = (s_a['ours'] == 1 and
                   s_a['dev_type'] == 2 and
                   (s_a['cc_hold'] & 0x0010) == 0x0010 and
                   (s_b['cc_hold'] & 0x0040) == 0x0040 and
                   (s_start['cc_hold'] & 0x0400) == 0x0400)

        if success:
            print('\n>>> VERIFICATION SUCCESSFUL: GameCube controller input verified working end-to-end! <<<')
        else:
            print('\n>>> VERIFICATION FAILED: Controller input mismatch <<<')
            sys.exit(1)

    finally:
        if pipe:
            os.close(pipe)
        if g:
            g.interrupt()
            g.close()
        p.kill()
        p.wait()


if __name__ == '__main__':
    main()
