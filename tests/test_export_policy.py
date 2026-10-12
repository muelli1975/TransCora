"""User exports trust the tools; development checks do not gate publication."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import subprocess
import tempfile
import threading
import unittest

from transcora.core.bd3d_export import export
from transcora.core.engine import capture
from transcora.core.model import Options


class ExportPolicyTests(unittest.TestCase):
    def test_export_publishes_tool_output_without_extra_quality_gates(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder/'source.mkv'
            source.write_bytes(b'input')
            video = dict(index=0, width=1280, height=360, r_frame_rate='24/1', avg_frame_rate='24/1',
                         pix_fmt='yuv420p', color_space='bt709', color_transfer='bt709',
                         color_primaries='bt709', color_range='tv', start_time='7')
            stat = source.stat()
            plan = SimpleNamespace(source=source, output=folder/'movie.m2ts', layout='full_sbs', swap=False,
                options=Options(target='bd3d', container='m2ts'), duration=1,
                info=dict(video=video, streams=[], source_size=stat.st_size, source_mtime_ns=stat.st_mtime_ns))

            def encoded(tools, bd, plan, base, dependent, *args):
                base.write_bytes(b'avc')
                dependent.write_bytes(b'mvc')
                return 24, 7

            def mux(args, *rest, **kwargs):
                Path(args[-1]).write_bytes(b'muxed output')

            bd = SimpleNamespace(muxer='tsMuxeR', environment={})
            with patch('transcora.core.bd3d_export.BdTools.find', return_value=bd), \
                 patch('transcora.core.bd3d_export.encode', side_effect=encoded), \
                 patch('transcora.core.bd3d_export.tag_generated_stream', return_value=2), \
                 patch('transcora.core.bd3d_export.run', side_effect=mux), \
                 patch('transcora.core.bd3d_export.coded_fingerprint', side_effect=AssertionError('No hash gate')), \
                 patch('transcora.core.bd3d_export.verify_mux', side_effect=AssertionError('No validation gate')):
                export(SimpleNamespace(), plan, threading.Event(), lambda *a: None, folder/'log')
                self.assertEqual(plan.output.read_bytes(), b'muxed output')
                with self.assertRaises(ValueError):
                    export(SimpleNamespace(), plan, threading.Event(), lambda *a: None, folder/'log')
                self.assertEqual(plan.output.read_bytes(), b'muxed output')

    def test_analysis_can_finish_after_waiting_without_default_time_limit(self):
        process = MagicMock(returncode=0)
        process.poll.return_value = 0
        process.communicate.side_effect = [subprocess.TimeoutExpired('probe', .15), (b'valid metadata', b'')]
        with patch('transcora.core.engine.subprocess.Popen', return_value=process), \
             patch('transcora.core.engine.time.monotonic', side_effect=[0, 100000, 200000]):
            self.assertEqual(capture(['probe']), b'valid metadata')
        self.assertEqual(process.communicate.call_count, 2)
