from dataclasses import replace
from pathlib import Path
import json
import re
import tempfile
import threading
import unittest
from unittest.mock import patch

from transcora.core.engine import Cancelled, color_spec, methods, publish_without_overwrite
from transcora.core.model import Job, Options, app_root
from transcora.core.naming import clean_stem, filename_layout, reserve_output
from transcora.core.storage import load_list, save_list


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
            folder = Path(tmp)
            reserved = set()
            for key, method in methods().items():
                options = Options(target='anaglyph', naming='players', profile='quality10')
                output = reserve_output(folder/'Film.3D.HSBS-lrh.mkv', folder, options, method['suffix'], reserved)
                self.assertEqual(output.name, f'Film_{key}.mkv')
                output.touch()
                again = reserve_output(folder/'Film-lr.mkv', folder, options, method['suffix'], reserved)
                self.assertEqual(again.name, f'Film_2_{key}.mkv')
            (folder/'CLIP_half_sbs.mkv').touch()
            output = reserve_output(folder/'Clip.mkv', folder, Options(), '', set())
            self.assertEqual(output.name, 'Clip_2_half_sbs.mkv')
            source = folder/'same.mkv'
            source.touch()
            output = reserve_output(source, folder, Options(naming='original'), '', set())
            self.assertEqual(output.name, 'same_2.mkv')

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

    def test_lists_roundtrip_and_revalidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
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
            color_spec({'pix_fmt': 'yuv420p'}, False)
        colors, warnings = color_spec({'pix_fmt': 'yuv420p'}, True)
        self.assertEqual(colors['transfer'], 'bt709')
        self.assertEqual(len(warnings), 4)
        with self.assertRaisesRegex(ValueError, 'HDR'):
            color_spec({'color_transfer': 'smpte2084'}, True)

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
