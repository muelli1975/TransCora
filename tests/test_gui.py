from pathlib import Path
from dataclasses import replace
import os
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from transcora.core.model import Options
from transcora.gui.window import Window
from transcora.core.engine import capture
from transcora.core.toolchain import Toolchain


class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            if os.environ.get('TRANSCORA_REQUIRE_GUI'):
                raise
            self.skipTest('Kein Display; unter Linux mit xvfb-run testen')
        with patch.object(Window, '_load_settings'):
            self.window = Window(self.root)
        self.root.update()

    def tearDown(self):
        if hasattr(self, 'root'):
            self.root.destroy()

    def test_file_list_selection_and_option_scope(self):
        self.window.add_paths([Path('/one/A.mp4'), Path('/two/B.mkv')])
        self.window.add_paths([Path('/one/A.mp4')])
        self.assertEqual(len(self.window.jobs), 2)
        first, second = self.window.jobs
        self.window.tree.selection_set(first.id)
        self.window.selection_changed()
        self.window.variables['target'].set('Anaglyph')
        self.window.option_changed('target')
        self.assertEqual(first.options.target, 'anaglyph')
        self.assertEqual(second.options.target, 'half_sbs')
        self.assertEqual(str(self.window.combos['naming'].cget('state')), 'disabled')
        self.window.tree.selection_remove(first.id)
        self.window.selection_changed()
        self.assertEqual(self.window.variables['target'].get(), 'Anaglyph')
        self.window.set_busy(True)
        self.assertEqual(str(self.window.start_button.cget('state')), 'disabled')
        self.window.set_busy(False)
        self.assertEqual(str(self.window.start_button.cget('state')), 'normal')

    def test_advanced_codec_and_output_invalidation(self):
        self.window.add_paths([Path('/one/A.mp4')])
        job = self.window.jobs[0]
        self.window.variables['codec'].set('H.265 / HEVC')
        self.window.option_changed('codec')
        self.assertEqual(job.options.container, 'mkv')
        self.assertEqual(str(self.window.combos['container'].cget('state')), 'disabled')
        job.status = 'ready'
        self.window.invalidate_all()
        self.assertEqual(job.status, 'ready')
        self.window.output_var.set(str(Path(tempfile.gettempdir())/'new-transcora-output'))
        self.window.invalidate_all()
        self.assertEqual(job.status, 'queued')
        self.window.toggle_advanced()
        self.root.update()
        self.assertTrue(self.window.advanced.winfo_ismapped())

    def test_background_conversion_updates_real_job_list(self):
        try:
            tools = Toolchain.find()
        except ValueError:
            self.skipTest('FFmpeg fehlt')
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            source = folder/'sample-lr.mkv'
            capture([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=128x32:rate=25',
                     '-frames:v', '3', '-c:v', 'ffv1', '-colorspace', 'bt709', '-color_trc', 'bt709',
                     '-color_primaries', 'bt709', '-color_range', 'tv', str(source)])
            self.window.defaults = replace(Options(), target='anaglyph')
            self.window.add_paths([source])
            self.window.output_var.set(str(folder/'output'))
            self.window.check(True)
            deadline = time.monotonic()+30
            while self.window.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
            self.assertFalse(self.window.busy, 'Worker did not finish')
            job = self.window.jobs[0]
            self.assertEqual(job.status, 'completed', self.window.status.get()+'\n'+job.detail)
            self.assertTrue(job.plan.output.is_file())
            self.assertTrue(list((folder/'output/logs').glob('*.log')))


if __name__ == '__main__':
    unittest.main()
