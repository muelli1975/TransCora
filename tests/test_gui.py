from pathlib import Path
from dataclasses import replace
import os
import json
import tempfile
import time
import tkinter as tk
import unittest
from unittest.mock import patch

from transcora.core.model import Options
from transcora.gui.window import Window
from transcora.core.engine import capture
from transcora.core.toolchain import Toolchain
from transcora.gui.preview_window import PreviewWindow
from transcora.gui.theme import APP_BG, PANEL_BG, DISABLED, GOLD_LIGHT
from tkinter import ttk


class GuiTests(unittest.TestCase):
    def test_image_extended_selection_and_changes_apply_to_all_selected(self):
        panel = self.window.images
        self.window.notebook.select(self.window.image_tab)
        panel.add_paths([Path('/photos/one_full_sbs.jpg'), Path('/photos/two_full_sbs.jpg'), Path('/photos/three_full_sbs.jpg')])
        self.root.update()
        def click(job, modifiers=0):
            x, y, width, height = panel.tree.bbox(job.id)
            panel.tree.event_generate('<ButtonPress-1>', x=x+12, y=y+height//2, state=modifiers)
            panel.tree.event_generate('<ButtonRelease-1>', x=x+12, y=y+height//2, state=modifiers)
            self.root.update()
        click(panel.jobs[0]); click(panel.jobs[2], 4)
        self.assertEqual(set(panel.tree.selection()), {panel.jobs[0].id, panel.jobs[2].id})
        click(panel.jobs[0]); click(panel.jobs[2], 1)
        self.assertEqual(len(panel.tree.selection()), 3)
        panel.tree.focus_force(); self.root.update()
        panel.tree.event_generate('<Control-a>'); self.root.update()
        self.assertEqual(len(panel.selected()), 3)
        panel.variables['target'].set('Full-OU'); panel.changed('target')
        self.assertTrue(all(job.options.target == 'full_ou' for job in panel.jobs))
        self.assertEqual(panel.defaults.target, 'keep')
        self.assertEqual(str(panel.preview_button.cget('state')), 'disabled')
        with patch('transcora.gui.images_panel.messagebox.showinfo') as info:
            panel.preview()
        info.assert_called_once()
        self.assertFalse(panel.busy)
        panel.tree.selection_set(panel.jobs[0].id); panel.selection_changed()
        self.assertEqual(str(panel.preview_button.cget('state')), 'normal')
        panel.variables['size_mode'].set('Benutzerdefiniert'); panel.changed('size_mode')
        panel.variables['size_edge'].set('kurze Seite'); panel.changed('size_edge')
        panel.variables['size_pixels'].set('600'); panel.changed('size_pixels')
        self.assertEqual(panel.jobs[0].options.size_pixels, 600)
        self.assertEqual(panel.jobs[1].options.size_mode, 'original')

    def test_language_switch_preserves_jobs_user_names_and_persists_language(self):
        self.window.add_paths([Path('/films/Wartet_full_sbs.mp4')])
        job = self.window.jobs[0]; job.status = 'ready'
        self.window.tree.selection_set(job.id); self.window.selection_changed()
        self.window.variables['suffix'].set('_Mein_Name'); self.window.option_changed('suffix')
        options = replace(job.options)
        with tempfile.TemporaryDirectory() as folder, patch('transcora.gui.window.app_root', return_value=Path(folder)):
            self.window.language_var.set('English'); self.window.language_changed(); self.root.update()
            saved = json.loads((Path(folder)/'settings.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['language'], 'en')
            self.assertEqual(job.options, options)
            self.assertEqual(self.window.notebook.tab(self.window.image_tab, 'text'), 'Images')
            self.assertEqual(self.window.tree.heading('file', 'text'), 'File')
            self.assertEqual(self.window.tree.item(job.id, 'values')[0], 'Wartet_full_sbs.mp4')
            self.assertIn('_Mein_Name', self.window.output_name.get())
            self.window.variables['target'].set('Change frame rate only'); self.window.option_changed('target')
            self.assertEqual(job.options.target, 'framerate')
            self.window.images.set_busy(True)
            self.assertTrue(all(str(widget.cget('state')) == 'disabled' for widget in self.window.language_controls))
            self.window.language_var.set('Deutsch'); self.window.language_changed()
            self.assertEqual(self.window.language, 'en')
            self.window.images.set_busy(False)
            self.window.language_var.set('Deutsch'); self.window.language_changed(); self.root.update()
            self.assertEqual(self.window.tree.heading('file', 'text'), 'Datei')
            self.assertEqual(self.window.notebook.tab(self.window.image_tab, 'text'), 'Bilder')
            self.assertEqual(job.options.target, 'framerate')
            self.window.language = 'en'; self.window._load_settings()
            self.assertEqual(self.window.language, 'de')

    def test_cross_view_gui_selects_mkv_and_image_preview_preserves_original_pixels(self):
        self.window.variables['target'].set('Kreuzblick · Full-SBS R/L')
        self.window.option_changed('target')
        self.assertEqual(self.window.defaults.container, 'mkv')
        self.assertEqual(self.window.variables['container'].get(), 'MKV')
        self.assertEqual(str(self.window.combos['container'].cget('state')), 'disabled')
        self.assertTrue(self.window.output_name.get().endswith('-rl.mkv'))
        from transcora.gui.image_view import ImageView
        from PIL import Image
        dialog = tk.Toplevel(self.root); dialog.geometry('600x400')
        viewer = ImageView(dialog, self.window.localizer); viewer.pack(fill='both', expand=True)
        source = Image.new('RGB', (2000, 1200), (20, 40, 60)); viewer.set_images([source])
        self.root.update()
        self.assertEqual(viewer.images[0].size, source.size)
        self.assertLess(viewer.photos[0].width(), source.width)
        viewer.fit.set(False); viewer.render(); self.root.update()
        self.assertEqual(viewer.photos[0].width(), source.width)
        self.assertEqual(viewer.photos[0].height(), source.height)
        self.assertEqual(viewer.canvas.cget('background'), '#181818')
        self.assertEqual(int(viewer.canvas.cget('highlightthickness')), 0)
        dialog.destroy()

    def test_images_tab_has_independent_selection_and_operation_guard(self):
        panel = self.window.images
        self.window.notebook.select(self.window.image_tab)
        panel.add_paths([Path('/photos/one_full_sbs.jpg'), Path('/photos/two.mpo')])
        self.assertEqual(len(panel.jobs), 2)
        self.assertEqual(len(self.window.jobs), 0)
        first, second = panel.jobs
        panel.tree.selection_set(first.id); panel.selection_changed()
        panel.variables['target'].set('Full-OU'); panel.changed('target')
        self.assertEqual(first.options.target, 'full_ou'); self.assertEqual(second.options.target, 'keep')
        panel.set_busy(True)
        self.assertEqual(self.window.notebook.tab(self.window.video_tab, 'state'), 'disabled')
        panel.set_busy(False)
        self.assertEqual(self.window.notebook.tab(self.window.video_tab, 'state'), 'normal')
        self.window.notebook.select(self.window.video_tab)
        self.window.set_busy(True)
        self.assertEqual(self.window.notebook.tab(self.window.image_tab, 'state'), 'disabled')
        self.window.set_busy(False)

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
            def descendants(widget):
                yield widget
                for child in widget.winfo_children():
                    yield from descendants(child)
            widgets = list(descendants(self.root))
            for callback in self.root.tk.call('after', 'info'):
                script = self.root.tk.splitlist(self.root.tk.call('after', 'info', callback))[0]
                owner = next((w for w in widgets if script in (w._tclCommands or [])), self.root)
                owner.after_cancel(callback)
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
        self.assertEqual(str(self.window.combos['suffix'].cget('state')), 'normal')
        self.assertEqual(self.window.variables['suffix'].get(), '_dubois_lcd')
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

    def test_suffix_preview_framerate_scope_and_selection_contrast(self):
        self.window.add_paths([Path('/one/Film_half_ou.mp4')])
        self.window.selection_changed()
        self.root.update()
        style = ttk.Style(self.root)
        self.assertEqual(style.lookup('Treeview', 'background', ('selected', '!focus')), GOLD_LIGHT)
        self.assertEqual(style.lookup('Treeview', 'foreground', ('selected', '!focus')), APP_BG)
        self.assertEqual(self.window.test_button.cget('style'), self.window.start_button.cget('style'))
        self.assertFalse(self.window.fps_frame.winfo_ismapped())
        self.window.variables['suffix'].set('_eigene_Endung')
        self.window.option_changed('suffix')
        self.assertIn('Film_eigene_Endung.mp4', self.window.output_name.get())
        self.window.variables['container'].set('MKV')
        self.window.option_changed('container')
        self.assertIn('Film_eigene_Endung.mkv', self.window.output_name.get())
        self.window.variables['swap'].set(True)
        self.window.option_changed('swap')
        self.window.variables['target'].set('Nur Framerate ändern')
        self.window.option_changed('target')
        self.root.update()
        self.assertTrue(self.window.fps_frame.winfo_ismapped())
        self.assertFalse(self.window.jobs[0].options.swap)
        self.assertFalse(self.window.variables['swap'].get())
        self.assertEqual(str(self.window.swap_control.cget('state')), 'disabled')
        self.assertIn('Film_30fps-tbh.mkv', self.window.output_name.get())
        self.window.variables['target_fps'].set('29,97')
        self.window.option_changed('target_fps')
        self.assertIn('Film_29.97fps-tbh.mkv', self.window.output_name.get())
        self.assertNotIn('-lrh', self.window.combos['suffix'].cget('values'))
        self.window.variables['target'].set('Half-SBS · 1080p')
        self.window.option_changed('target')
        self.root.update()
        self.assertFalse(self.window.fps_frame.winfo_ismapped())

    def test_rate_mode_keeps_values_and_does_not_shift_layout(self):
        self.window.toggle_advanced()
        self.root.update()
        crf = self.window.combos['crf']
        bitrate = self.window.combos['bitrate_mbps']
        self.assertTrue(crf.winfo_ismapped())
        self.assertFalse(bitrate.winfo_ismapped())
        location = (crf.winfo_rootx(), crf.winfo_rooty(), self.window.progress.winfo_rooty())
        self.window.variables['crf'].set('19,5')
        self.window.option_changed('crf')
        self.window.variables['rate_mode'].set('Zielbitrate (Durchschnitt)')
        self.window.option_changed('rate_mode')
        self.root.update()
        self.assertFalse(crf.winfo_ismapped())
        self.assertTrue(bitrate.winfo_ismapped())
        self.assertEqual(location, (bitrate.winfo_rootx(), bitrate.winfo_rooty(), self.window.progress.winfo_rooty()))
        self.window.variables['bitrate_mbps'].set('24')
        self.window.option_changed('bitrate_mbps')
        self.window.variables['rate_mode'].set('Qualität (CRF)')
        self.window.option_changed('rate_mode')
        self.root.update()
        self.assertEqual(self.window.defaults.crf, 19.5)
        self.assertEqual(self.window.defaults.bitrate_mbps, 24)
        self.assertTrue(crf.winfo_ismapped())

    def test_dark_disabled_controls_and_reset_scope(self):
        self.window.add_paths([Path('/one/A.mp4')])
        job = self.window.jobs[0]
        self.window.variables['target'].set('Anaglyph')
        self.window.option_changed('target')
        original = replace(job.options)
        self.window.output_var.set('/chosen/output')
        self.window.recursive.set(True)
        self.window.set_busy(True)
        style = ttk.Style(self.root)
        self.assertEqual(style.lookup('TCheckbutton', 'background', ('disabled', 'active')), APP_BG)
        self.assertEqual(style.lookup('TCombobox', 'foreground', ('readonly', 'disabled')), DISABLED)
        self.assertEqual(style.lookup('TCombobox', 'fieldbackground', ('readonly', 'disabled')), PANEL_BG)
        self.window.set_busy(False)
        self.window.reset_defaults()
        self.root.update()
        self.assertEqual(self.window.defaults, Options())
        self.assertEqual(job.options, original)
        self.assertEqual(self.window.output_var.get(), '/chosen/output')
        self.assertTrue(self.window.recursive.get())
        self.assertFalse(self.window.tree.selection())

    def test_saved_settings_and_legacy_settings_reset_source_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            old = {'schema_version': 1, 'defaults': dict(vars(Options(target='anaglyph', layout='full_sbs',
                    swap=True, method='rendepth2', rate_mode='abr', bitrate_mbps=24)), assume_bt709=True),
                    'output_folder': str(folder/'out'), 'input_folder': str(folder/'in'),
                    'custom_tools': '/unused/ffmpeg', 'mirror': False, 'recursive': True}
            (folder/'settings.json').write_text(json.dumps(old))
            with patch('transcora.gui.window.app_root', return_value=folder):
                self.window._load_settings()
                self.assertEqual(self.window.defaults.layout, 'auto')
                self.assertFalse(self.window.defaults.swap)
                self.assertEqual(self.window.defaults.method, 'rendepth2')
                self.assertEqual(self.window.defaults.bitrate_mbps, 24)
                self.assertTrue(self.window.recursive_value)
                self.window.output_var.set(str(folder/'out'))
                self.window.recursive.set(True)
                self.window.defaults = replace(self.window.defaults, swap=True, layout='half_ou')
                # Keep this test's root available for tearDown; inspect the real
                # persisted settings that finish_close writes.
                with patch.object(self.root, 'destroy'):
                    self.window.finish_close()
            saved = json.loads((folder/'settings.json').read_text())
            self.assertEqual(saved['schema_version'], 2)
            self.assertEqual(saved['defaults']['layout'], 'auto')
            self.assertFalse(saved['defaults']['swap'])
            self.assertEqual(saved['defaults']['method'], 'rendepth2')
            self.assertNotIn('custom_tools', saved)
            self.assertNotIn('mirror', saved)
            self.assertNotIn('geometry', saved)

    def test_folder_import_preserves_structure_and_excludes_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for name in ('A/same-lr.mp4', 'B/same-lr.mp4', 'output/finished.mp4'):
                source = folder/name
                source.parent.mkdir(parents=True, exist_ok=True)
                source.touch()
            self.window.recursive.set(True)
            self.window.output_var.set(str(folder/'output'))
            with patch('transcora.gui.window.filedialog.askdirectory', return_value=str(folder)):
                self.window.add_folder()
            deadline = time.monotonic()+10
            while self.window.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
            self.assertEqual(len(self.window.jobs), 2)
            self.assertEqual({job.source.parent.name for job in self.window.jobs}, {'A', 'B'})
            self.assertTrue(all(job.source_root == folder.resolve() for job in self.window.jobs))

    def test_presets_persist_scope_and_exclude_paths_and_title(self):
        from transcora.core.storage import load_presets
        self.window.add_paths([Path('/one/A-lr.mp4'), Path('/two/B-lr.mp4')])
        first, second = self.window.jobs
        self.window.tree.selection_set(first.id)
        self.window.selection_changed()
        self.window.variables['target'].set('BD-3D · 1080p')
        self.window.option_changed('target')
        self.window.variables['disc_title'].set('Mein Film')
        self.window.option_changed('disc_title')
        self.assertEqual(first.options.container, 'iso')
        self.assertEqual(first.options.disc_title, 'Mein Film')
        self.assertIsNone(self.window.defaults.disc_title)
        self.root.update()
        self.assertTrue(self.window.title_frame.winfo_ismapped())
        with tempfile.TemporaryDirectory() as tmp, patch('transcora.gui.window.app_root', return_value=Path(tmp)):
            self.window.store_preset('Blu-ray Qualität')
            data = json.loads((Path(tmp)/'user-presets.json').read_text(encoding='utf-8'))
            self.assertNotIn('disc_title', data['presets']['Blu-ray Qualität'])
            self.assertNotIn('source', data['presets']['Blu-ray Qualität'])
            self.window.presets = load_presets(Path(tmp)/'user-presets.json')
            self.window.tree.selection_set(second.id)
            self.window.apply_preset('Blu-ray Qualität')
            self.assertEqual(second.options.target, 'bd3d')
            self.assertIsNone(second.options.disc_title)
            self.assertEqual(first.options.disc_title, 'Mein Film')
            self.window.tree.selection_remove(second.id)
            self.window.apply_preset('Blu-ray Qualität')
            self.assertEqual(self.window.defaults.target, 'bd3d')
            self.window.delete_preset('Blu-ray Qualität')
            self.assertEqual(load_presets(Path(tmp)/'user-presets.json'), {})
        self.window.variables['target'].set('Anaglyph')
        self.window.option_changed('target')
        self.assertEqual(self.window.defaults.container, 'mp4')
        self.root.update()
        self.assertFalse(self.window.title_frame.winfo_ismapped())

    def test_remaining_estimate_uses_progress_and_freezes_after_finish(self):
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            self.window.run_started = 30
            self.window.set_busy(True)
            self.window.update_elapsed()
            self.assertEqual(self.window.elapsed.get(), 'Restzeit: —')
            self.window.estimate_remaining(1, 1, 50)
            self.assertEqual(self.window.elapsed.get(), 'Restzeit: ca. 01:10')
            self.assertEqual(self.window.elapsed_time.get(), 'Vergangene Zeit: 01:10')
            self.window.abort()
            self.assertIsNotNone(self.window.run_started)
            self.window.set_busy(False)
        with patch('transcora.gui.window.time.monotonic', return_value=9999):
            self.window.update_elapsed()
        self.assertEqual(self.window.elapsed.get(), 'Restzeit: —')
        self.assertEqual(self.window.elapsed_time.get(), 'Vergangene Zeit: 01:10')
        self.assertEqual(PreviewWindow.time_text(3661), '01:01:01')

    def test_bd_audio_options_remain_available_and_phase_replaces_stale_estimate(self):
        self.root.geometry('860x680')
        self.window.variables['target'].set('BD-3D · 1080p')
        self.window.option_changed('target')
        self.window.toggle_advanced()
        self.root.update()
        self.assertTrue(self.window.advanced.winfo_ismapped())
        self.assertGreaterEqual(self.window.tree.winfo_height(), 45)
        self.assertLessEqual(self.window.start_button.winfo_rooty()+self.window.start_button.winfo_height(),
                             self.root.winfo_rooty()+self.root.winfo_height())
        self.window.show_audio_options()
        self.root.update()
        self.assertTrue(self.window.audio_dialog.winfo_ismapped())
        self.assertEqual(str(self.window.combos['codec'].cget('state')), 'disabled')
        self.assertEqual(str(self.window.combos['audio_format'].cget('state')), 'disabled')
        self.assertEqual(self.window.variables['audio_format'].get(), 'LPCM · 24 Bit')
        self.assertEqual(str(self.window.combos['audio_tracks'].cget('state')), 'readonly')
        self.window.variables['audio_tracks'].set('Ausgewählte Spuren')
        self.window.option_changed('audio_tracks')
        self.assertEqual(str(self.window.combos['audio_selection'].cget('state')), 'normal')
        self.window.close_audio_options()
        self.assertFalse(self.window.audio_dialog.winfo_ismapped())
        self.window.run_started = time.monotonic()-30
        self.window.estimated_finish = time.monotonic()+100
        self.window.speed.set('Alte Geschwindigkeit')
        text = 'BD-3D: Fertige Ausgabe vollständig dekodieren und beide Halbbilder prüfen'
        self.window.events.put(('phase', ('job', 1, 1, text)))
        self.window.poll()
        self.assertEqual(self.window.status.get(), text)
        self.assertEqual(self.window.speed.get(), '')
        self.assertEqual(self.window.elapsed.get(), 'Restzeit: —')
        self.assertEqual(str(self.window.progress.cget('mode')), 'indeterminate')
        self.window.events.put(('progress', ('job', 1, 1,
            {'percent': 94, 'seconds': 100, 'remaining_seconds': 120})))
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            self.window.poll()
        self.assertEqual(self.window.elapsed.get(), 'Restzeit: ca. 02:00')
        self.assertEqual(str(self.window.progress.cget('mode')), 'determinate')
        self.window.set_busy(False)

    def test_log_has_dark_surfaces_and_scrollbar(self):
        self.window.show_log()
        self.root.update()
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_ismapped())
        self.assertEqual(dialog.cget('background'), APP_BG)
        frame = next(w for w in dialog.winfo_children() if isinstance(w, ttk.Frame))
        text = next(w for w in frame.winfo_children() if isinstance(w, tk.Text))
        self.assertEqual(text.cget('background'), PANEL_BG)
        self.assertEqual(text.cget('highlightthickness'), 0)
        self.assertTrue(text.cget('yscrollcommand'))
        dialog.destroy()
        self.window.set_busy(True)
        self.window.set_busy(False)

    def test_background_conversion_updates_real_job_list(self):
        try:
            tools = Toolchain.find()
        except ValueError:
            self.skipTest('FFmpeg fehlt')
        with tempfile.TemporaryDirectory() as tmp, patch('transcora.gui.window.app_root', return_value=Path(tmp)):
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
            self.assertTrue(list((folder/'logs').glob('*.log')))

    def test_preview_timeline_loads_selected_frame_and_keeps_exact_entry(self):
        try:
            tools = Toolchain.find()
        except ValueError:
            self.skipTest('FFmpeg fehlt')
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'timeline-lr.mkv'
            capture([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi', '-i',
                     'testsrc2=size=128x32:rate=25', '-frames:v', '50', '-c:v', 'ffv1',
                     '-colorspace', 'bt709', '-color_trc', 'bt709', '-color_primaries',
                     'bt709', '-color_range', 'tv', str(source)])
            self.window.defaults = replace(Options(), target='anaglyph')
            self.window.add_paths([source])
            self.window.output_var.set(str(Path(tmp)/'output'))
            self.window.tree.selection_set(self.window.jobs[0].id)
            viewers = []
            def make_viewer(*args):
                viewer = PreviewWindow(*args)
                viewers.append(viewer)
                return viewer
            with patch('transcora.gui.window.PreviewWindow', side_effect=make_viewer):
                self.window.show_preview()
            viewer = viewers[0]
            def wait_for_frame():
                deadline = time.monotonic()+20
                self.root.update()
                while self.window.busy and time.monotonic() < deadline:
                    self.root.update()
                    time.sleep(.01)
                self.assertFalse(self.window.busy, self.window.status.get())
            self.root.after(50, lambda: None)
            deadline = time.monotonic()+20
            while not hasattr(viewer.image_label, 'image') and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
            wait_for_frame()
            self.assertTrue(hasattr(viewer.image_label, 'image'), self.window.status.get())
            self.assertAlmostEqual(viewer.duration, 2)
            self.assertNotIn('disabled', viewer.scale.state())
            first = viewer.image_label.image.cget('data')
            viewer.scale.set(.8)
            viewer.scale.event_generate('<ButtonRelease-1>')
            wait_for_frame()
            self.assertEqual(viewer.time_var.get(), '00:00')
            self.assertAlmostEqual(viewer.position_seconds, .8, places=3)
            self.assertNotEqual(first, viewer.image_label.image.cget('data'))
            viewer.time_var.set('00:01,234567')
            viewer.request()
            wait_for_frame()
            self.assertEqual(viewer.time_var.get(), '00:01,234567')
            self.assertAlmostEqual(viewer.scale.get(), 1.234567)
            viewer.scale.set(float(viewer.scale.cget('to')))
            viewer.scale.event_generate('<ButtonRelease-1>')
            wait_for_frame()
            self.assertEqual(self.window.status.get(), 'Kontrollbild bereit.')
            viewer.time_var.set('00:02')
            viewer.request()
            self.assertFalse(self.window.busy)
            self.assertIn('außerhalb', viewer.note.cget('text'))
            self.window.close_preview(viewer.dialog, viewer.time_entry, viewer.scale)
            self.window.set_busy(True)
            self.window.set_busy(False)


if __name__ == '__main__':
    unittest.main()
