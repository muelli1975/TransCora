from pathlib import Path
import os
import tempfile
import tkinter as tk
import unittest
from unittest.mock import patch

from transcora.core.model import Options
from transcora.gui.window import Window


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


if __name__ == '__main__':
    unittest.main()
