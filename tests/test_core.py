from dataclasses import replace
from pathlib import Path
import json
import re
import tempfile
import threading
import unittest
import struct
from types import SimpleNamespace
from unittest.mock import patch

from transcora.core.engine import Cancelled, color_spec, methods, publish_without_overwrite
from transcora.core.model import Job, Options, app_root, frame_rate
from transcora.core.naming import clean_stem, filename_layout, reserve_output
from transcora.core.storage import load_list, save_list
from transcora.core.toolchain import Toolchain
from transcora.core.mp4 import packed_stereo_boxes


class CoreTests(unittest.TestCase):
    def test_catalog_is_exactly_batch_without_cielab(self):
        batch = (app_root() / 'reference/AnaglyphBatch_DE.bat').read_text(encoding='utf-8-sig')
        blocks = re.findall(r'if "%~1"=="(\d+)" \((.*?)\n\)', batch, re.S)
        catalog = methods()
        expected = {}
        for number, block in blocks:
            values = dict(re.findall(r'set "([^=]+)=(.*?)"', block))
            if values.get('MATRIXMODE') != 'cielab':
                expected[values['MATRIXNAME']] = values
        self.assertEqual(len(catalog), 17)
        self.assertEqual(set(catalog), set(expected))
        for key, method in catalog.items():
            self.assertEqual(method['suffix'], key)
            self.assertEqual(method['pipeline_type'], expected[key]['MATRIXMODE'])
            if key != 'iaian7':
                self.assertEqual(method['left_matrix_ffmpeg'], expected[key]['MATRIX_LEFT'])
                self.assertEqual(method['right_matrix_ffmpeg'], expected[key]['MATRIX_RIGHT'])
                self.assertEqual(method['post_filter_ffmpeg'], expected[key]['POSTFIX'])

    def test_names_and_collisions_keep_method_at_end(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            reserved = set()
            for key, method in methods().items():
                options = Options(target='anaglyph', naming='players', profile='quality10', container='mkv')
                output = reserve_output(folder/'Film.3D.HSBS-lrh.mkv', folder, options, method['suffix'], reserved)
                self.assertEqual(output.name, f'Film_{key}.mkv')
                output.touch()
                again = reserve_output(folder/'Film-lr.mkv', folder, options, method['suffix'], reserved)
                self.assertEqual(again.name, f'Film_2_{key}.mkv')
            (folder/'CLIP_half_sbs.mp4').touch()
            output = reserve_output(folder/'Clip.mkv', folder, Options(), '', set())
            self.assertEqual(output.name, 'Clip_2_half_sbs.mp4')
            source = folder/'same.mp4'
            source.touch()
            output = reserve_output(source, folder, Options(naming='original'), '', set())
            self.assertEqual(output.name, 'same_2.mp4')

    def test_layout_hints_and_safe_windows_names(self):
        self.assertEqual(filename_layout('Film.3D.HSBS-lrh'), ('half_sbs', False))
        self.assertEqual(filename_layout('Film-rl'), ('full_sbs', True))
        self.assertEqual(filename_layout('Film.3D.HTAB-tbh'), ('half_ou', False))
        self.assertIsNone(filename_layout('Film_SBS_example'))
        with self.assertRaises(ValueError):
            filename_layout('Film.3D.HSBS-tbh')
        self.assertEqual(clean_stem('CON'), '_CON')
        self.assertEqual(clean_stem('My3Dmovie'), 'My3Dmovie')
        self.assertEqual(clean_stem('a/b:*?'), 'a_b')
        for layout in ('full_sbs', 'half_sbs', 'full_ou', 'half_ou'):
            self.assertEqual(filename_layout('Film_'+layout), (layout, False))

    def test_custom_suffix_and_exact_frame_rates(self):
        self.assertEqual(str(frame_rate('23,976')), '24000/1001')
        self.assertEqual(str(frame_rate('29.97')), '30000/1001')
        self.assertEqual(str(frame_rate('59,94')), '60000/1001')
        self.assertEqual(str(frame_rate('24')), '24')
        for value in ('nan', 'inf', '0', '241', '1/0', ''):
            with self.assertRaises(ValueError):
                frame_rate(value)
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            options = Options(target='anaglyph', suffix='_mein_test')
            output = reserve_output(folder/'Film-lr.mp4', folder, options, 'dubois_lcd', set())
            self.assertEqual(output.name, 'Film_mein_test.mp4')
            options.suffix = ''
            self.assertEqual(reserve_output(folder/'Film-lr.mp4', folder, options, '', set()).name, 'Film.mp4')
            for suffix in ('/bad', '\\bad', '..', 'space ', 'x'*81):
                with self.assertRaises(ValueError):
                    replace(options, suffix=suffix).validate()
            output = reserve_output(folder/'Film-tbh.mp4', folder, Options(target='framerate', layout='half_ou'), '', set())
            self.assertEqual(output.name, 'Film_30fps-tbh.mp4')
            self.assertEqual(filename_layout(output.stem), ('half_ou', False))
            output = reserve_output(folder/'Film_30fps-tbh.mp4', folder,
                Options(target='framerate', layout='half_ou', target_fps='24000/1001'), '', set())
            self.assertEqual(output.name, 'Film_23.976fps-tbh.mp4')

    def test_mp4_normalization_keeps_media_and_offsets_unchanged(self):
        def box(kind, content):
            return struct.pack('>I4s', len(content)+8, kind)+content
        st3d = box(b'st3d', b'\0\0\0\0\2')
        vexu = box(b'vexu', box(b'eyes', b'placeholder'))
        sample = box(b'avc1', bytes(78)+st3d+vexu)
        sample = box(b'stsd', bytes(4)+struct.pack('>I',1)+sample)
        for kind in (b'stbl', b'minf', b'mdia', b'trak', b'moov'):
            sample = box(kind, sample)
        media = box(b'mdat', b'unchanged media vexu eyes st3d')
        original = sample+media
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'packed.mp4'
            path.write_bytes(original)
            self.assertEqual(packed_stereo_boxes(path), [2])
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(packed_stereo_boxes(path, normalize=True), [2])
            expected = original.replace(vexu, vexu[:4]+b'free'+vexu[8:], 1)
            self.assertEqual(path.read_bytes(), expected)
            self.assertEqual(len(path.read_bytes()), len(original))
            path.write_bytes(struct.pack('>I4s', 500, b'moov'))
            with self.assertRaises(ValueError):
                packed_stereo_boxes(path)

    def test_lists_roundtrip_and_revalidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            job = Job(folder/'a.mp4', replace(Options(), target='anaglyph', method='rendepth2'), folder)
            job.status = 'completed'
            path = folder/'list.json'
            save_list(path, [job], folder/'output')
            jobs, output = load_list(path)
            self.assertEqual(jobs[0].options, job.options)
            self.assertEqual(jobs[0].source_root, folder)
            self.assertEqual(jobs[0].status, 'queued')
            self.assertIsNone(jobs[0].plan)
            self.assertEqual(output, folder/'output')
            data = json.loads(path.read_text())
            data['jobs'][0]['options']['crf'] = float('nan')
            path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):
                load_list(path)

    def test_color_assumptions_and_hdr_are_explicit(self):
        with self.assertRaisesRegex(ValueError, 'unvollständig'):
            color_spec({'pix_fmt': 'yuv420p', 'width': 720, 'height': 576})
        colors, warnings = color_spec({'pix_fmt': 'yuv420p', 'width': 1920, 'height': 1080})
        self.assertEqual(colors['transfer'], 'bt709')
        self.assertEqual(len(warnings), 4)
        with self.assertRaisesRegex(ValueError, 'HDR'):
            color_spec({'color_transfer': 'smpte2084'})
        with self.assertRaisesRegex(ValueError, 'HDR'):
            color_spec({'width': 3840, 'height': 2160, 'side_data_list': [
                {'side_data_type': 'Mastering display metadata'}]})
        with self.assertRaisesRegex(ValueError, 'Farbinterpretation'):
            color_spec({'width': 3840, 'height': 2160, 'color_primaries': 'bt2020'})
        with self.assertRaisesRegex(ValueError, 'unvollständig'):
            color_spec({'width': 1920, 'height': 1080, 'color_space': 'smpte170m'})

    def test_color_range_is_independent_and_existing_tags_win(self):
        tags = {'color_space': 'bt709', 'color_primaries': 'bt709', 'color_transfer': 'bt709'}
        colors, warnings = color_spec(dict(tags, pix_fmt='yuv420p', color_range='pc'))
        self.assertEqual(colors['range'], 'pc')
        self.assertFalse(warnings)
        for pix_fmt, expected in [('gbrp16le', 'pc'), ('yuvj420p', 'pc'), ('yuv420p10le', 'tv')]:
            with self.subTest(pix_fmt=pix_fmt):
                colors, warnings = color_spec(dict(tags, pix_fmt=pix_fmt))
                self.assertEqual(colors['range'], expected)
                self.assertEqual(len(warnings), 1)
        legacy = dict(tags, color_space='bt470bg', color_primaries='bt470bg', color_transfer='gamma28',
                      color_range='tv', pix_fmt='yuv420p')
        colors, warnings = color_spec(legacy)
        self.assertEqual(colors['matrix'], 'bt470bg')
        self.assertFalse(warnings)

    def test_old_lists_keep_choices_with_automatic_colour_handling(self):
        options = Options.from_dict({'target': 'anaglyph', 'method': 'rendepth2', 'container': 'mkv',
                                     'swap': True, 'layout': 'full_sbs', 'assume_bt709': False})
        self.assertEqual(options.container, 'mkv')
        self.assertTrue(options.swap)
        self.assertEqual(options.layout, 'full_sbs')
        self.assertNotIn('assume_bt709', vars(options))

    def test_tool_inspection_supports_ffmpeg_6_and_9_listing(self):
        names = ['zscale', 'colorchannelmixer', 'lutrgb', 'blend', 'crop', 'scale',
                 'pad', 'hstack', 'vstack', 'format', 'setsar', 'sidedata']
        for flags in ('TSC', 'TS'):
            def run(args, **kwargs):
                if '-filters' in args:
                    text = '\n'.join(f' {flags} {name:20} V->V filter' for name in names)
                elif '-encoders' in args:
                    text = ' V..... libx264\n V..... libx265'
                else:
                    text = 'FFmpeg version\nSupported pixel formats: yuv444p yuv444p10le yuv420p'
                return SimpleNamespace(returncode=0, stdout=text, stderr='')
            with self.subTest(flags=flags), patch('transcora.core.toolchain.subprocess.run', side_effect=run):
                self.assertTrue(Toolchain(Path('ffmpeg'), Path('ffprobe')).inspect()['h265'])

    def test_setts_help_detects_prescale_and_caches_the_probe(self):
        for text, expected in [('  -time_base <rational> output clock', ''),
                               ('  -prescale <boolean> ...VAS..B.. convert before evaluation', ':prescale=1')]:
            with self.subTest(help=text), patch('transcora.core.toolchain.subprocess.run',
                                               return_value=SimpleNamespace(stdout=text, stderr='')) as run:
                tools = Toolchain(Path('ffmpeg'), Path('ffprobe'))
                self.assertEqual(tools.setts_prescale, expected)
                self.assertEqual(tools.setts_prescale, expected)
                run.assert_called_once()

    def test_publication_never_overwrites_and_fat_fallback_cleans(self):
        with tempfile.TemporaryDirectory() as tmp:
            a, b = Path(tmp)/'part.mkv', Path(tmp)/'final.mkv'
            a.write_bytes(b'new')
            b.write_bytes(b'old')
            with self.assertRaises(ValueError):
                publish_without_overwrite(a, b, threading.Event())
            self.assertEqual(b.read_bytes(), b'old')
            b.unlink()
            with patch('transcora.core.engine.os.link', side_effect=OSError('no hardlinks')):
                publish_without_overwrite(a, b, threading.Event())
            self.assertEqual(b.read_bytes(), b'new')
            self.assertFalse(a.exists())
            a.write_bytes(b'new')
            cancel = threading.Event()
            cancel.set()
            with self.assertRaises(Cancelled):
                publish_without_overwrite(a, Path(tmp)/'cancelled.mkv', cancel)
            self.assertFalse((Path(tmp)/'cancelled.mkv').exists())


if __name__ == '__main__':
    unittest.main()
