from pathlib import Path
import tempfile
import unittest

from transcora.core.multiview import PairClock, demux_ts


class MultiviewSafetyTests(unittest.TestCase):
    def test_mismatched_or_missing_view_cannot_pass_pair_validation(self):
        clock = PairClock()
        clock.line('[showinfo@mv_right] n: 0 pts: 20 pts_time: 0.02')
        with self.assertRaises(ValueError):
            clock.line('[showinfo@mv_left] n: 0 pts: 21 pts_time: 0.021')
        clock = PairClock()
        clock.line('[showinfo@mv_left] n: 0 pts: 0 pts_time: 0')
        with self.assertRaises(ValueError):
            clock.finish()

    def test_demux_keeps_selected_payloads_and_rejects_loss_or_scrambling(self):
        def packet(pid, cc, payload, first=False, encrypted=False):
            padding = 183-len(payload)
            assert padding >= 0
            header = bytes([0x47, (pid>>8)|(0x40 if first else 0), pid&255,
                            0x30|cc|(0x80 if encrypted else 0)])
            adaptation = bytes([padding])+(b'\0'+b'\xff'*(padding-1) if padding else b'')
            return b'\0'*4+header+adaptation+payload
        pes = b'\0\0\1\xe0\0\0\x80\0\0'
        left, right = b'L'*210, b'R'*210
        stream = (packet(4113, 0, pes+left[:150], True)+packet(4114, 0, pes+right[:150], True)
                  +packet(4113, 1, left[150:])+packet(4114, 1, right[150:]))
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder/'source.m2ts'
            source.write_bytes(stream)
            paths = (folder/'left.264', folder/'right.mvc')
            demux_ts(source, (4113, 4114), paths, None)
            self.assertEqual(paths[0].read_bytes(), left)
            self.assertEqual(paths[1].read_bytes(), right)
            for bad in (stream[:384]+packet(4113, 2, left[150:])+stream[576:],
                        packet(4113, 0, pes+left[:150], True, True)+stream[192:]):
                for path in paths:
                    path.unlink()
                source.write_bytes(bad)
                with self.assertRaises(ValueError):
                    demux_ts(source, (4113, 4114), paths, None)
