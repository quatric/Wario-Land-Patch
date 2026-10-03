"""Regression checks for modded disc identities without game data."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import disc
from disc_ids import match_disc_id
from regions import REGIONS


class DiscIdentityTests(unittest.TestCase):
    def test_supported_ids_and_mods(self):
        for key in REGIONS:
            if len(key) != 6:
                continue
            self.assertEqual(match_disc_id(key, REGIONS), key)
            self.assertEqual(match_disc_id(key[:4] + '99', REGIONS), key)
        self.assertIsNone(match_disc_id('ZZZZ99', REGIONS))
        self.assertIsNone(match_disc_id('R', REGIONS))

    def exercise(self, identity, version, mismatch=False):
        key = next(k for k in REGIONS if len(k) == 6)
        info = REGIONS[key]
        feature = disc.patcher.ORDER[0]
        with tempfile.TemporaryDirectory() as tmp:
            image = Path(tmp) / 'mod.iso'
            image.write_bytes(b'original mod image')
            commands = []
            def wit(cmd, **kwargs):
                commands.append(cmd)
                dest = Path(cmd[cmd.index('--dest') + 1])
                if cmd[1] == 'extract':
                    (dest / 'sys').mkdir(parents=True)
                    (dest / 'sys/boot.bin').write_bytes(identity.encode() + bytes([0, version]))
                    (dest / 'sys/main.dol').write_bytes(b'dol')
                elif cmd[1] == 'copy':
                    header = (Path(cmd[2]) / 'sys/boot.bin').read_bytes()
                    self.assertEqual(header[:6], identity.encode())
                    dest.write_bytes(b'patched mod image')
                return Mock(returncode=0, stdout='', stderr='')
            log, done = Mock(), Mock()
            with patch.object(disc, 'find_wit', return_value='wit'), \
                 patch.object(disc.subprocess, 'run', side_effect=wit), \
                 patch.object(disc, 'Dol'), \
                 patch.object(disc.patcher, 'status', return_value={feature: 'mismatch' if mismatch else 'clean'}), \
                 patch.object(disc.patcher, 'patch', return_value=['controller support']):
                disc.run_patch(str(image), log, done, which=[feature])
            success = done.call_args.args[0]
            if success:
                self.assertEqual(image.read_bytes(), b'patched mod image')
                self.assertEqual(Path(str(image) + '.bak').read_bytes(), b'original mod image')
            else:
                self.assertEqual(image.read_bytes(), b'original mod image')
                self.assertFalse(any(cmd[1] == 'copy' for cmd in commands))
            return success

    def test_modded_disc_flow(self):
        key = next(k for k in REGIONS if len(k) == 6)
        info = REGIONS[key]
        version = info.get('version', info.get('versions', [0])[0])
        self.assertTrue(self.exercise(key[:4] + '99', version))
        self.assertFalse(self.exercise('ZZZZ99', version))
        self.assertFalse(self.exercise(key[:4] + '99', version, mismatch=True))
        self.assertFalse(self.exercise(key[:4] + '99', 255))


if __name__ == '__main__':
    unittest.main()
