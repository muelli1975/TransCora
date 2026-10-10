"""Real FFmpeg exports, timing, cancellation and comparison with the original Batch."""
from dataclasses import replace
from pathlib import Path
import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import unittest

from transcora.core.engine import (Cancelled, build_graph, command, execute, methods, plan_job,
                                   preview, probe, capture)
from transcora.core.model import Job, Options, app_root
from transcora.core.toolchain import Toolchain


class FFmpegTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.tools = Toolchain.find()
        except ValueError:
            if os.environ.get('TRANSCORA_REQUIRE_FFMPEG'):
                raise
            raise unittest.SkipTest('FFmpeg/ffprobe fehlen')
        cls.capabilities = cls.tools.inspect()
        cls.temp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.temp.name)
        cls.source = cls.folder/'Test-lr.mkv'
        cls.ppm = cls.folder/'stereo.ppm'
        # Distinct eye colors and gradations reveal swaps and LUT/order differences.
        pixels = bytearray()
        for y in range(32):
            for x in range(128):
                if x < 64:
                    pixels.extend(((x*4) % 256, (y*8) % 256, (x*3+y*2) % 256))
                else:
                    pixels.extend(((x+y*4) % 256, (x*2+y) % 256, (x*3+y*5) % 256))
        cls.ppm.write_bytes(b'P6\n128 32\n255\n'+pixels)
        cls.run_ffmpeg('-loop', '1', '-framerate', '24000/1001', '-i', str(cls.ppm),
                       '-f', 'lavfi', '-i', 'sine=frequency=440:sample_rate=48000',
                       '-vf', 'setparams=colorspace=gbr:color_primaries=bt709:color_trc=iec61966-2-1:range=full',
                       '-frames:v', '6', '-t', '0.26', '-c:v', 'ffv1', '-pix_fmt', 'gbrp16le',
                       '-c:a', 'aac', '-colorspace', 'rgb', '-color_primaries', 'bt709',
                       '-color_trc', 'iec61966-2-1', '-color_range', 'pc', str(cls.source))
        # Set the known fixture interpretation on the frames themselves. FFmpeg
        # 9 may propagate unknown frame tags over output-only codec options.
        fixture = probe(cls.tools, cls.source)['video']
        expected = {'color_space': 'gbr', 'color_primaries': 'bt709',
                    'color_transfer': 'iec61966-2-1', 'color_range': 'pc'}
        if any(fixture.get(key) != value for key, value in expected.items()):
            raise AssertionError('Reference fixture colour tags were lost: '+json.dumps(fixture))

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    @classmethod
    def run_ffmpeg(cls, *args):
        return capture([str(cls.tools.ffmpeg), '-hide_banner', '-loglevel', 'error', '-nostdin',
                        '-filter_complex_threads', '1', '-threads', '1', *args], timeout=90)

    def plan(self, options=None, source=None):
        options = options or Options(target='anaglyph')
        return plan_job(self.tools, Job(source or self.source, options),
                        self.folder/'outputs', set(), capabilities=self.capabilities)

    def export(self, options):
        plan = self.plan(options)
        events = []
        execute(self.tools, plan, threading.Event(), lambda kind, value: events.append((kind, value)), self.folder/'run.log')
        self.assertTrue(plan.output.is_file())
        self.assertTrue(any(kind == 'progress' and value['percent'] == 100 for kind, value in events))
        self.assertFalse(list(plan.output.parent.glob('*.part.*')))
        return plan, probe(self.tools, plan.output)

    def test_all_17_anaglyph_exports(self):
        for key in methods():
            with self.subTest(method=key):
                plan, info = self.export(Options(target='anaglyph', method=key))
                self.assertEqual(info['video']['pix_fmt'], 'yuv444p')
                self.assertTrue(plan.output.stem.endswith('_'+key))

    def test_original_batch_pixel_consistency_all_17(self):
        batch = (app_root()/'reference/AnaglyphBatch_DE.bat').read_text(encoding='utf-8-sig')
        templates = dict(re.findall(r'if "%MATRIXMODE%"=="(\w+)" \(\s*set "VF=(.*?)"', batch))
        definitions = re.findall(r'if "%~1"=="\d+" \((.*?)\n\)', batch, re.S)
        definitions = {dict(re.findall(r'set "([^=]+)=(.*?)"', b)).get('MATRIXNAME'): dict(re.findall(r'set "([^=]+)=(.*?)"', b)) for b in definitions}
        video = probe(self.tools, self.source)['video']
        colors = {'matrix': 'gbr', 'primaries': 'bt709', 'transfer': 'iec61966-2-1', 'range': 'pc'}
        for key, method in methods().items():
            with self.subTest(method=key):
                reference = templates[method['pipeline_type']]
                for variable, value in {**definitions[key], 'SCALEPART': ''}.items():
                    reference = reference.replace('%'+variable+'%', value)
                self.assertNotIn('%', reference)
                graph, _, _ = build_graph(video, Options(target='anaglyph', method=key), 'full_sbs', False, colors, method)
                # Compare the sRGB composite before lossy YUV encoding against the Batch itself.
                graph = graph.split(';[composite]zscale=')[0]+';[composite]format=rgb24[v]'
                actual = self.run_ffmpeg('-i', str(self.source), '-filter_complex', graph, '-map', '[v]',
                                         '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1')
                expected = self.run_ffmpeg('-i', str(self.source), '-filter_complex', reference+'[ref]',
                                           '-map', '[ref]', '-frames:v', '1', '-f', 'rawvideo', '-pix_fmt', 'rgb24', 'pipe:1')
                self.assertEqual(len(actual), 64*32*3)
                self.assertEqual(actual, expected, 'Abweichung von der originalen Batch-Filterkette')

    def test_bitdepth_profiles_mp4_and_h265(self):
        for profile, container, codec, expected in [
            ('quality10', 'mkv', 'h264', 'yuv444p10le'),
            ('compatible', 'mp4', 'h264', 'yuv420p'),
            ('quality', 'mp4', 'h264', 'yuv444p'),
            ('quality10', 'mkv', 'h265', 'yuv444p10le'),
        ]:
            with self.subTest(profile=profile, codec=codec, container=container):
                if codec == 'h265' and not self.capabilities.get('h265'):
                    self.skipTest('Kein libx265')
                _, info = self.export(Options(target='anaglyph', profile=profile, container=container, codec=codec))
                self.assertEqual(info['video']['pix_fmt'], expected)
                self.assertEqual(len([s for s in info['streams'] if s['codec_type'] == 'audio']), 1)

    def test_layouts_geometry_order_and_preview(self):
        for target in ('half_sbs', 'half_ou', 'mono'):
            with self.subTest(target=target):
                plan, _ = self.export(Options(target=target, naming='players', crf=28))
                self.assertEqual(plan.size, (64, 32) if target == 'mono' else (1920, 1080))
        normal = self.plan(Options(target='mono'))
        swapped = self.plan(Options(target='mono', swap=True))
        a = preview(self.tools, normal, threading.Event())
        b = preview(self.tools, swapped, threading.Event())
        self.assertTrue(a.startswith(b'\x89PNG'))
        self.assertNotEqual(a, b)
        for layout, size in [('full_sbs',(64,32)), ('half_sbs',(128,32)), ('full_ou',(128,16)), ('half_ou',(128,32))]:
            plan = self.plan(Options(layout=layout, target='mono'))
            self.assertEqual(plan.size, size)
            self.assertTrue(preview(self.tools, plan, threading.Event()).startswith(b'\x89PNG'))

    def test_folder_outputs_and_filter_thread_equivalence(self):
        source = self.folder/'nested'/'album'/'same-lr.mkv'
        source.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(self.source, source)
        job = Job(source, Options(target='anaglyph'), self.folder/'nested')
        plan = plan_job(self.tools, job, self.folder/'mirrored', set(), capabilities=self.capabilities)
        self.assertEqual(plan.output.parent, self.folder/'mirrored'/'album')
        args = command(self.tools, plan, self.folder/'thread-output.mp4')
        self.assertNotIn('-filter_complex_threads', args)
        for method in ('dubois_lcd', 'iaian7', 'rendepth2'):
            graph = self.plan(Options(target='anaglyph', method=method)).graph
            hashes = []
            for threads in ('1', '0'):
                hashes.append(capture([str(self.tools.ffmpeg), '-v', 'error', '-nostdin',
                    '-filter_complex_threads', threads, '-i', str(self.source), '-filter_complex', graph,
                    '-map', '[v]', '-frames:v', '3', '-c:v', 'rawvideo', '-threads', '1',
                    '-f', 'framemd5', 'pipe:1'], timeout=30))
            self.assertEqual(hashes[0], hashes[1], method)

    def test_source_changes_and_cancel_leave_no_final_file(self):
        plan = self.plan(Options(target='half_sbs'))
        cancelled = threading.Event()
        cancelled.set()
        with self.assertRaises(Cancelled):
            execute(self.tools, plan, cancelled, lambda *args: None, self.folder/'cancel.log')
        self.assertFalse(plan.output.exists())
        # Cancellation during an actual FFmpeg process (slow 1080p export).
        timer = threading.Timer(.05, cancelled.set)
        cancelled.clear()
        timer.start()
        try:
            with self.assertRaises(Cancelled):
                execute(self.tools, plan, cancelled, lambda *args: None, self.folder/'cancel.log')
        finally:
            timer.cancel()
        self.assertFalse(plan.output.exists())
        self.assertFalse(list(plan.output.parent.glob('.*.part.*')))
        copy = self.folder/'changed-lr.mkv'
        shutil.copyfile(self.source, copy)
        plan = self.plan(source=copy)
        with copy.open('ab') as out:
            out.write(b'x')
        with self.assertRaisesRegex(ValueError, 'geändert'):
            execute(self.tools, plan, threading.Event(), lambda *args: None, self.folder/'changed.log')
        self.assertFalse(plan.output.exists())

    def test_vfr_timestamps_are_preserved(self):
        source = self.folder/'vfr-lr.mkv'
        self.run_ffmpeg('-loop', '1', '-framerate', '25', '-i', str(self.ppm), '-frames:v', '5',
                        '-vf', "settb=1/1000,setpts='N*N*40',setparams=colorspace=gbr:color_primaries=bt709:color_trc=iec61966-2-1:range=full", '-fps_mode', 'passthrough',
                        '-enc_time_base', '1/1000', '-c:v', 'ffv1', '-pix_fmt', 'gbrp16le',
                        '-colorspace', 'rgb', '-color_primaries', 'bt709', '-color_trc', 'iec61966-2-1',
                        '-color_range', 'pc', str(source))
        plan = self.plan(source=source)
        execute(self.tools, plan, threading.Event(), lambda *args: None, self.folder/'vfr.log')
        def times(path):
            data = json.loads(capture([str(self.tools.ffprobe), '-v', 'error', '-select_streams', 'v:0',
                                      '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time',
                                      '-of', 'json', str(path)]))
            return [float(f['best_effort_timestamp_time']) for f in data['frames']]
        before, after = times(source), times(plan.output)
        self.assertEqual(len(before), 5)
        self.assertEqual(len(before), len(after))
        for a, b in zip(before, after):
            self.assertAlmostEqual(a-before[0], b-after[0], delta=.0011)


if __name__ == '__main__':
    unittest.main()
