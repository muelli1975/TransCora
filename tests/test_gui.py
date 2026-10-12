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
    def test_duration_and_source_fps_survive_option_changes_and_rows_have_exact_size(self):
        from types import SimpleNamespace
        self.window.add_paths([Path('Film_full_sbs.mp4')])
        job = self.window.jobs[0]
        job.plan = SimpleNamespace(layout='full_sbs',info={'video':{'avg_frame_rate':'60000/1001'}},duration=3723.4)
        self.window.update_row(job)
        self.assertEqual(self.window.tree.set(job.id,'duration'),'01:02:03')
        self.assertEqual(self.window.tree.set(job.id,'fps'),'59.94')
        job.plan = None
        self.window.variables['target'].set('Zeilenverschachtelt (Polfilter)')
        self.window.option_changed('target')
        self.root.update()
        self.assertTrue(self.window.screen_fields.winfo_ismapped())
        self.assertEqual(self.window.tree.set(job.id,'duration'),'01:02:03')
        self.window.variables['screen_width'].set('2560'); self.window.option_changed('screen_width')
        self.window.variables['screen_height'].set('1440'); self.window.option_changed('screen_height')
        self.assertEqual((job.options.screen_width,job.options.screen_height),(2560,1440))
        self.assertEqual(str(self.window.combos['target_fps'].cget('state')),'disabled')
        self.window.variables['fps_mode'].set('Zielbildrate wählen'); self.window.option_changed('fps_mode')
        self.assertEqual(str(self.window.combos['target_fps'].cget('state')),'normal')
        panel=self.window.images
        panel.variables['target'].set('Zeilenverschachtelt (Polfilter)'); panel.changed('target')
        self.assertEqual(panel.defaults.format,'png')
        panel.variables['screen_width'].set('2560'); panel.changed('screen_width')
        panel.variables['screen_height'].set('1440'); panel.changed('screen_height')
        panel.variables['row_first'].set('Rechtes Auge in erster Zeile'); panel.changed('row_first')
        self.assertEqual((panel.defaults.screen_width,panel.defaults.screen_height,panel.defaults.row_first),(2560,1440,'right'))

    def test_image_batch_continues_after_bad_source_and_export_failure(self):
        from PIL import Image
        from transcora.core.images import ImageOptions, mpo_jpegs
        from transcora.gui.images_panel import execute_image as actual_execute
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            bad = folder/'bad.jpg'; bad.write_bytes(b'not an image')
            sources = [folder/'a/stereo.mpo', folder/'b/stereo.mpo']
            for source in sources:
                source.parent.mkdir()
                Image.new('RGB', (32, 24), 'red').save(source, format='MPO', save_all=True,
                                                     append_images=[Image.new('RGB', (32, 24), 'blue')])
            panel = self.window.images
            panel.add_paths([bad, *sources])
            for job in panel.jobs: job.options = ImageOptions(task='mpo')
            panel.output.set(str(folder/'out'))
            def export(tools, plan, *args):
                if plan.sources[0] == sources[0].resolve():
                    raise OSError('One export failed')
                return actual_execute(tools, plan, *args)
            with patch('transcora.gui.images_panel.threading.Thread') as thread, \
                 patch('transcora.gui.images_panel.Toolchain.find', side_effect=AssertionError('MPO needs no FFmpeg')), \
                 patch('transcora.gui.images_panel.execute_image', side_effect=export), \
                 patch('transcora.gui.images_panel.new_run_log', return_value=folder/'run.log'):
                thread.return_value.start.side_effect = lambda: thread.call_args.kwargs['target']()
                panel.run(False); panel.poll()
                self.assertEqual([job.status for job in panel.jobs], ['blocked', 'ready', 'ready'])
                panel.run(True); panel.poll()
            self.assertEqual([job.status for job in panel.jobs], ['blocked', 'failed', 'completed'])
            expected = mpo_jpegs(sources[1])
            outputs = (folder/'out/stereo_2_l.jpg', folder/'out/stereo_2_r.jpg')
            self.assertEqual(tuple(path.read_bytes() for path in outputs), expected)
            self.assertIn('1 erfolgreich', panel.status.get())
            self.assertFalse(panel.busy)

    def test_bd_remaining_time_is_per_phase_and_resets_between_steps(self):
        window = self.window
        window.add_paths([Path('test_full_sbs.mp4')])
        job = window.jobs[0]
        job.options = replace(job.options, target='bd3d', container='iso')
        window.run_started = 10
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            window.events.put(('phase', (job.id, 1, 2, 'BD-3D: Beide Halbbilder in hoher Qualität kodieren')))
            window.poll()
        with patch('transcora.gui.window.time.monotonic', return_value=200):
            window.events.put(('progress', (job.id, 1, 2, {'percent': 18, 'phase_percent': 20,
                                                       'remaining_scope': 'phase'})))
            window.poll()
        self.assertEqual(window.estimated_finish, 600)
        self.assertEqual(window.remaining_scope, 'phase')
        self.assertIn('aktueller Schritt', window.elapsed.get())
        with patch('transcora.gui.window.time.monotonic', return_value=300):
            window.events.put(('phase', (job.id, 1, 2, 'BD-3D: Blu-ray-ISO erstellen')))
            window.events.put(('progress', (job.id, 1, 2, {'percent': 90})))
            window.poll()
        self.assertIsNone(window.estimated_finish)
        with patch('transcora.gui.window.time.monotonic', return_value=400):
            window.events.put(('progress', (job.id, 1, 2, {'percent': 95, 'remaining_seconds': 30,
                                                       'remaining_scope': 'phase'})))
            window.poll()
        self.assertEqual(window.estimated_finish, 430)

    def test_image_extended_selection_and_changes_apply_to_all_selected(self):
        panel = self.window.images
        self.window.notebook.select(self.window.image_tab)
        panel.add_paths([Path('/photos/one_full_sbs.jpg'), Path('/photos/two_full_sbs.jpg'), Path('/photos/three_full_sbs.jpg')])
        self.root.update()
        def click(job, modifiers=0):
            x, y, width, height = panel.tree.bbox(job.id)
            if self.root.tk.call('tk', 'windowingsystem') == 'aqua' and modifiers == 4:
                panel.tree.event_generate('<Command-ButtonPress-1>', x=x+12, y=y+height//2)
                panel.tree.event_generate('<Command-ButtonRelease-1>', x=x+12, y=y+height//2)
            else:
                panel.tree.event_generate('<ButtonPress-1>', x=x+12, y=y+height//2, state=modifiers)
                panel.tree.event_generate('<ButtonRelease-1>', x=x+12, y=y+height//2, state=modifiers)
            self.root.update()
        click(panel.jobs[0]); click(panel.jobs[2], 4)
        self.assertEqual(set(panel.tree.selection()), {panel.jobs[0].id, panel.jobs[2].id})
        click(panel.jobs[0]); click(panel.jobs[2], 1)
        self.assertEqual(len(panel.tree.selection()), 3)
        panel.tree.focus_force(); self.root.update()
        panel.tree.event_generate('<Command-a>' if self.root.tk.call('tk', 'windowingsystem') == 'aqua' else '<Control-a>'); self.root.update()
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
            self.window.variables['target'].set('Keep layout'); self.window.option_changed('target')
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

    def test_cross_view_gui_keeps_mp4_and_image_preview_preserves_original_pixels(self):
        self.window.variables['target'].set('Kreuzblick · Full-SBS R/L')
        self.window.option_changed('target')
        self.assertEqual(self.window.defaults.container, 'mp4')
        self.assertEqual(self.window.variables['container'].get(), 'MP4')
        self.assertEqual(str(self.window.combos['container'].cget('state')), 'readonly')
        self.assertTrue(self.window.output_name.get().endswith('-rl.mp4'))
        self.window.variables['container'].set('MKV')
        self.window.option_changed('container')
        self.assertEqual(self.window.defaults.container, 'mkv')
        self.assertTrue(self.window.output_name.get().endswith('-rl.mkv'))
        self.window.variables['video_size'].set('Benutzerdefiniert')
        self.window.option_changed('video_size')
        self.root.update()
        self.assertFalse(self.window.advanced.winfo_ismapped())
        self.assertTrue(self.window.video_dimensions.winfo_ismapped())
        self.assertEqual(self.window.video_size_caption.get(), 'Ausgabegröße')
        self.window.variables['video_width'].set('1920'); self.window.option_changed('video_width')
        self.window.variables['video_height'].set('540'); self.window.option_changed('video_height')
        self.assertEqual((self.window.defaults.video_width, self.window.defaults.video_height), (1920,540))
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

    def test_inline_dimensions_dialog_and_tabs_keep_main_layout(self):
        from tkinter import ttk
        self.root.geometry('780x680')
        self.root.update()
        height = self.window.tree.winfo_height()
        detail = self.window.detail_text.winfo_height()
        self.assertGreaterEqual(height, 135)
        self.assertGreaterEqual(int(self.window.detail_text.cget('padx')), 6)
        self.window.toggle_advanced()
        self.root.update()
        self.assertEqual(self.window.tree.winfo_height(), height)
        self.assertEqual(self.window.detail_text.winfo_height(), detail)
        self.window.close_advanced()
        self.window.variables['video_size'].set(self.window.t('Benutzerdefiniert'))
        self.window.option_changed('video_size')
        self.root.update()
        self.assertFalse(self.window.advanced_section.winfo_ismapped())
        self.assertEqual(self.window.tree.winfo_height(), height)
        self.assertEqual(self.window.video_dimensions.master, self.window.option_frames['video_size'])
        self.window.variables['video_width'].set('2560')
        self.window.variables['video_height'].set('1440')
        self.assertTrue(self.window.commit_entries())
        self.assertEqual(self.window.defaults.video_width, 2560)
        self.assertEqual(self.window.defaults.video_height, 1440)
        self.window.variables['video_width'].set('2559')
        self.assertFalse(self.window.commit_entries())
        self.assertEqual(self.window.variables['video_width'].get(), '2559')
        self.assertEqual(self.window.defaults.video_width, 2560)
        self.window.variables['video_width'].set('2560')
        self.window.variables['video_size'].set(self.window.t('Automatisch'))
        self.window.option_changed('video_size')
        self.assertEqual(self.window.variables['video_width'].get(), '1920')
        self.assertEqual(str(self.window.combos['video_width'].cget('state')), 'disabled')
        style = ttk.Style()
        self.assertEqual(style.lookup('TNotebook.Tab', 'padding', ('selected',)),
                         style.lookup('TNotebook.Tab', 'padding', ('!selected',)))

    def test_polarised_target_has_fixed_eight_bit_and_no_profile_selector(self):
        from transcora.core.model import BD_BITRATES
        self.assertEqual(BD_BITRATES, (20, 25, 30, 35, 40))
        self.assertEqual(Options.from_dict({'target': 'row_interleaved', 'profile': 'quality10'}).profile, 'quality')
        self.window.variables['profile'].set(self.window.t('Hohe Farbtiefe · 10 Bit / 4:4:4'))
        self.window.option_changed('profile')
        self.window.variables['target'].set(self.window.t('Zeilenverschachtelt (Polfilter)'))
        self.window.option_changed('target')
        self.root.update()
        self.assertEqual(self.window.defaults.profile, 'quality')
        self.assertFalse(self.window.option_frames['profile'].winfo_ismapped())
        self.assertFalse(self.window.option_frames['method'].winfo_ismapped())
        self.assertTrue(self.window.screen_fields.winfo_ismapped())

    def test_dimension_focus_change_preserves_pending_height_and_invalid_edits_block_save(self):
        self.window.variables['video_size'].set('Benutzerdefiniert')
        self.window.option_changed('video_size')
        self.window.variables['video_width'].set('2560')
        self.window.variables['video_height'].set('1440')
        self.window.option_changed('video_width')
        self.assertEqual(self.window.variables['video_height'].get(), '1440')
        self.assertTrue(self.window.commit_entries())
        self.assertEqual(self.window.defaults.video_height, 1440)
        self.window.variables['video_width'].set('2559')
        with patch('transcora.gui.window.filedialog.asksaveasfilename') as dialog:
            self.window.save()
            dialog.assert_not_called()

    def test_shared_checkbox_widget_label_and_disabled_toggle(self):
        import customtkinter as ctk
        check = self.window.recursive_control
        self.assertIsInstance(check, ctk.CTkCheckBox)
        self.assertEqual(check.cget('checkbox_width'), 24)
        self.assertEqual(check.cget('corner_radius'), 4)
        self.assertEqual(check.cget('text'), 'Unterordner mitverarbeiten')
        self.assertEqual(self.window.profile_caption.get(), 'Anaglyph-Ausgabeprofil')
        before = self.window.recursive.get()
        check.toggle()
        self.assertNotEqual(self.window.recursive.get(), before)
        self.window.language = 'en'
        self.window.apply_language()
        self.assertEqual(check.cget('text'), 'Include subfolders')
        self.window.language = 'de'
        self.window.apply_language()
        self.assertEqual(check.cget('text'), 'Unterordner mitverarbeiten')
        check.configure(state='disabled')
        check.toggle()
        self.assertNotEqual(self.window.recursive.get(), before)

    def test_displayed_original_dimensions_follow_checked_source_and_mixed_values(self):
        from types import SimpleNamespace
        self.window.add_paths([Path('A_full_sbs.mp4'), Path('B_full_sbs.mp4')])
        a, b = self.window.jobs
        for job, size in [(a, (3840, 1080)), (b, (2560, 720))]:
            job.plan = SimpleNamespace(layout='full_sbs', duration=1,
                info={'video': {'width': size[0], 'height': size[1], 'avg_frame_rate': '25/1'}})
            self.window.update_row(job)
            job.options = replace(job.options, target='anaglyph', video_size='original')
            job.plan = None
        self.window.tree.selection_set(a.id)
        self.window.selection_changed()
        self.assertEqual((self.window.variables['video_width'].get(), self.window.variables['video_height'].get()), ('1920', '1080'))
        self.window.tree.selection_set(a.id, b.id)
        self.window.selection_changed()
        self.assertEqual(self.window.variables['video_width'].get(), '')
        self.assertEqual(self.window.variables['video_height'].get(), '')

    def test_actual_image_preview_and_pending_custom_edge(self):
        from PIL import Image
        panel = self.window.images
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp)/'test_full_sbs.png'
            Image.new('RGB', (64, 24), 'red').save(source)
            panel.add_paths([source])
            panel.tree.selection_set(panel.jobs[0].id)
            panel.selection_changed()
            panel.variables['size_mode'].set(self.window.t('Benutzerdefiniert'))
            panel.changed('size_mode')
            panel.variables['size_pixels'].set('100')
            panel.preview()
            deadline = time.monotonic()+20
            while panel.busy and time.monotonic() < deadline:
                self.root.update()
                time.sleep(.01)
            self.assertFalse(panel.busy, panel.status.get())
            self.assertEqual(panel.jobs[0].options.size_pixels, 100)
            self.assertIsNotNone(panel.preview_dialog, panel.status.get())
            panel.preview_dialog.destroy()

    def test_settings_viewport_and_current_file_preserve_footer_in_small_windows(self):
        from tkinter import font
        for tab,panel in [(self.window.video_tab,self.window),(self.window.image_tab,self.window.images)]:
            self.window.notebook.select(tab)
            for geometry in ('780x680','1100x850'):
                self.root.geometry(geometry); self.root.update()
                self.assertTrue(panel.combos['layout'].winfo_ismapped())
                height=panel.tree.winfo_height(); detail=panel.detail_text.winfo_height()
                panel.toggle_advanced(); self.root.update()
                self.assertGreaterEqual(panel.tree.winfo_height(),135)
                self.assertEqual(panel.tree.winfo_height(),height)
                self.assertEqual(panel.detail_text.winfo_height(),detail)
                self.assertTrue(panel.reset_button.winfo_ismapped())
                panel.current_file.set('Beginning_'+'long_filename_'*70+'ending.mp4',7,20)
                self.root.update()
                text=panel.current_file.label.cget('text')
                self.assertIn('…',text); self.assertTrue(text.endswith('ending.mp4'))
                self.assertIn('7/20',text)
                face=font.Font(root=self.root,font=ttk.Style().lookup('TLabel','font') or 'TkDefaultFont')
                self.assertLessEqual(face.measure(text),panel.current_file.label.winfo_width())
                self.assertLess(panel.current_file.label.winfo_rooty(),panel.progress.winfo_rooty())
                panel.toggle_advanced();self.root.update()
        job_path=Path('/one/current_full_sbs.mp4');self.window.add_paths([job_path])
        job=self.window.jobs[-1]
        self.window.events.put(('current',(job_path.name,1,20)))
        self.window.events.put(('phase',(job.id,1,20,'BD-3D: M2TS erstellen')))
        self.window.poll()
        self.assertEqual(self.window.current_file.name,job_path.name)

    def test_shared_output_buttons_and_photo_dimensions(self):
        from PIL import Image
        from transcora.core.images import ImageOptions
        panel=self.window.images
        self.window.notebook.select(self.window.image_tab)
        with tempfile.TemporaryDirectory() as tmp:
            source=Path(tmp)/'sample_full_sbs.png'
            Image.new('RGB',(400,150)).save(source)
            panel.add_paths([source]); job=panel.jobs[-1]
            job.options=ImageOptions(layout='full_sbs',target='anaglyph',metadata=False)
            panel.tree.selection_set(job.id);panel.selection_changed();self.root.update()
            self.assertEqual([v.get() for v in panel.dimension_values],['200','150'])
            panel.reset_defaults()
            self.assertEqual(job.options.target,'anaglyph')
            self.assertEqual(panel.defaults.target,'keep')
        for panel in (self.window,panel):
            buttons=[widget for widget,_ in panel.controls if isinstance(widget,ttk.Button) and widget.cget('text')=='Auswählen']
            self.assertEqual(len(buttons),1)

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
            for callback in self.root.tk.call('after', 'info'):
                self.root.tk.call('after', 'cancel', callback)
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
        self.assertEqual(self.window.variables['target'].get(), 'Half-SBS')
        self.window.add_paths([Path('/three/C.mp4')])
        self.assertEqual(self.window.jobs[-1].options.target, 'half_sbs')
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
        self.assertTrue(self.window.fps_frame.winfo_ismapped())
        self.window.variables['suffix'].set('_eigene_Endung')
        self.window.option_changed('suffix')
        self.assertIn('Film_eigene_Endung.mp4', self.window.output_name.get())
        self.window.variables['container'].set('MKV')
        self.window.option_changed('container')
        self.assertIn('Film_eigene_Endung.mkv', self.window.output_name.get())
        self.window.variables['swap'].set(True)
        self.window.option_changed('swap')
        self.window.variables['target'].set('Layout beibehalten')
        self.window.option_changed('target')
        self.root.update()
        self.assertTrue(self.window.fps_frame.winfo_ismapped())
        self.assertFalse(self.window.jobs[0].options.swap)
        self.assertFalse(self.window.variables['swap'].get())
        self.assertEqual(str(self.window.swap_control.cget('state')), 'disabled')
        self.window.variables['fps_mode'].set('Zielbildrate wählen')
        self.window.option_changed('fps_mode')
        self.assertIn('Film_30fps-tbh.mkv', self.window.output_name.get())
        self.window.variables['target_fps'].set('29,97')
        self.window.option_changed('target_fps')
        self.assertIn('Film_29.97fps-tbh.mkv', self.window.output_name.get())
        self.assertNotIn('-lrh', self.window.combos['suffix'].cget('values'))
        self.window.variables['target'].set('Half-SBS')
        self.window.option_changed('target')
        self.root.update()
        self.assertTrue(self.window.fps_frame.winfo_ismapped())

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
        self.assertEqual(self.window.recursive_control.cget('fg_color'), DISABLED)
        style = ttk.Style(self.root)
        self.assertEqual(style.lookup('TCheckbutton', 'background', ('disabled', 'active')), APP_BG)
        self.assertEqual(style.lookup('TCombobox', 'foreground', ('readonly', 'disabled')), DISABLED)
        self.assertEqual(style.lookup('TCombobox', 'fieldbackground', ('readonly', 'disabled')), PANEL_BG)
        self.window.set_busy(False)
        from transcora.gui.theme import GOLD
        self.assertEqual(self.window.recursive_control.cget('fg_color'), GOLD)
        self.window.images.set_busy(True)
        self.assertEqual(self.window.images.combos['metadata'].cget('fg_color'), DISABLED)
        self.window.images.set_busy(False)
        self.assertEqual(self.window.images.combos['metadata'].cget('fg_color'), GOLD)
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
