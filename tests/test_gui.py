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
    def test_information_omits_inapplicable_stereo_note_but_keeps_written_metadata(self):
        from transcora.core.engine import Plan
        window = self.window
        window.add_paths([Path('clip_full_sbs.mp4')]); job = window.jobs[0]
        window.tree.selection_set(job.id)
        video = dict(width=3840, height=1080, index=0, codec_type='video',
                     codec_name='h264', avg_frame_rate='25/1')
        for language in ('de', 'en'):
            window.language = language
            for target in ('anaglyph', 'mono', 'half_sbs'):
                job.options = replace(Options(), target=target)
                output = Path('converted_'+target+'.mp4')
                job.plan = Plan(job.source, output, job.options, dict(video=video, streams=[video]),
                    'full_sbs', False, (1920,1080), 'yuv444p' if target=='anaglyph' else 'yuv420p',
                    '', 1, [], {}, 'Full-SBS · manuell gewählt')
                for status in ('ready', 'completed'):
                    job.status = status
                    job.detail = ('Gespeichert · '+job.plan.stereo_summary+'\nGespeichert: '+str(output)
                                  if status=='completed' else '')
                    window.apply_language(); window.show_job_details(job); self.root.update()
                    body = window.detail_text.get('1.0','end')
                    self.assertNotIn(window.t('3D-Kennzeichnung: Keine SBS/OU-Kennzeichnung'), body)
                    self.assertIn(str(output), body)
                    self.assertIn('1920', body)
                    if target == 'half_sbs':
                        self.assertIn('MP4-st3d', body)

    def test_completed_details_do_not_repeat_stereo_summary_and_output_path(self):
        from types import SimpleNamespace
        window = self.window
        window.add_paths([Path('clip_full_sbs.mp4')]); job = window.jobs[0]
        output = Path('completed_half_sbs.mp4')
        stereo = 'Half-SBS · MP4-Stereo-Kennzeichnung'
        job.plan = SimpleNamespace(summary=stereo+'\n'+str(output), warnings=[],
                                   review_warnings=[], output=output, layout='full_sbs', duration=1,
                                   info={'video': {'width':128, 'height':32, 'avg_frame_rate':'25/1'}})
        job.status = 'completed'
        job.detail = 'Gespeichert · '+stereo+'\nGespeichert: '+str(output)
        for language in ('de', 'en'):
            window.language = language; window.apply_language()
            window.show_job_details(job); self.root.update()
            body = window.detail_text.get('1.0','end')
            self.assertEqual(body.count(window.t(stereo)), 1)
            self.assertEqual(body.count(str(output)), 1)

    def test_after_batch_selection_fits_both_tabs_and_remains_available_while_busy(self):
        window = self.window
        for language in ('de', 'en'):
            window.language = language; window.apply_language()
            self.root.geometry('780x680')
            for tab, panel, combo in zip((window.video_tab, window.image_tab),
                    (window, window.images), window.batch_finish.combos):
                window.notebook.select(tab); self.root.update()
                row = combo.master
                self.assertLessEqual(row.winfo_rootx()+row.winfo_width(),
                                     self.root.winfo_rootx()+self.root.winfo_width())
                self.assertLessEqual(combo.winfo_rootx()+combo.winfo_width(),
                                     row.winfo_rootx()+row.winfo_width())
                self.assertLessEqual(row.winfo_rooty()+row.winfo_height(),
                                     panel.start_button.winfo_rooty())
                old_geometry = (row.winfo_width(), row.winfo_height(), panel.tree.winfo_height())
                combo.current(2); combo.event_generate('<<ComboboxSelected>>'); self.root.update()
                self.assertEqual(old_geometry, (row.winfo_width(), row.winfo_height(), panel.tree.winfo_height()))
                panel.set_busy(True)
                self.assertEqual(str(combo.cget('state')), 'readonly')
                panel.set_busy(False)

    def test_completed_video_and_image_batches_offer_action_but_errors_and_tests_do_not(self):
        from PIL import Image
        from transcora.core.images import ImageOptions
        window = self.window; tools = Toolchain.find()
        def wait_for_completion(panel):
            deadline = time.monotonic()+20
            while panel.busy and time.monotonic()<deadline:
                self.root.update(); time.sleep(.01)
            self.assertFalse(panel.busy, panel.status.get())
        with tempfile.TemporaryDirectory() as tmp, patch.object(window.batch_finish, 'completed', return_value=False) as completed:
            folder = Path(tmp)
            source = folder/'video_full_sbs.mp4'
            capture([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=128x32:r=25',
                     '-frames:v', '2', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', str(source)])
            window.defaults = replace(Options(), target='full_ou', container='mkv', video_size='original')
            window.output_var.set(str(folder/'video-out')); window.add_paths([source])
            window.check(False); wait_for_completion(window); completed.assert_not_called()
            window.check(True); wait_for_completion(window); completed.assert_called_once_with(True)
            completed.reset_mock()
            window.add_paths([folder/'missing_full_sbs.mp4'])
            window.check(True); wait_for_completion(window); completed.assert_called_once_with(False)
            completed.reset_mock()
            panel = window.images
            image = folder/'image_full_sbs.png'; Image.new('RGB', (64,16), 'red').save(image)
            panel.defaults = replace(ImageOptions(), metadata=False)
            panel.output.set(str(folder/'image-out')); panel.add_paths([image])
            panel.run(False); wait_for_completion(panel); completed.assert_not_called()
            panel.run(True); wait_for_completion(panel); completed.assert_called_once_with(True)
            completed.reset_mock()
            panel.add_paths([folder/'missing_full_sbs.png'])
            panel.run(True); wait_for_completion(panel); completed.assert_called_once_with(False)

    def test_new_stereo_inputs_fit_the_list_and_show_neutral_notices(self):
        from tkinter import font
        from transcora.core.model import Job
        from transcora.core.engine import plan_job
        from test_stereo_inputs import fixture
        window = self.window; tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = fixture(tools, folder, 'frame_sequential', '120')
            job = Job(source, Options(target='full_sbs', container='mkv', video_size='original'))
            job.plan = plan_job(tools, job, folder/'out', set())
            job.status = 'ready'; window.jobs.append(job); window.update_row(job)
            window.tree.selection_set(job.id); window.show_job_details(job)
            self.root.update()
            for language in ('de', 'en'):
                window.language = language; window.apply_language(); self.root.update()
                self.assertIn('Frame sequential', window.mappings['layout'].values())
                measured = font.Font(font=ttk.Style().lookup('Treeview', 'font')).measure('Frame sequential')
                self.assertGreaterEqual(window.tree.column('layout', 'width'), measured+16)
                self.assertEqual(window.attention.get(), '')
                self.assertNotIn('⚠', window.file_notes.get())

    def test_video_pause_preserves_completed_export_and_freezes_elapsed(self):
        import threading
        import shutil
        from transcora.gui.window import execute as actual_execute
        from transcora.core.journal import Journal
        tools = Toolchain.find(); window = self.window
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); sample = root / 'sample.mp4'
            capture([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=128x32:r=30',
                     '-frames:v', '1', '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
                     '-color_trc', 'bt709', '-color_primaries', 'bt709', '-color_range', 'tv', str(sample)])
            sources = []
            for n in range(2):
                source = root / f'clip{n}_full_sbs.mp4'; shutil.copy2(sample, source); sources.append(source)
            window.defaults = replace(Options(), target='full_ou', container='mkv', video_size='original')
            window.output_var.set(str(root / 'out')); window.add_paths(sources)
            entered, release = threading.Event(), threading.Event(); calls = []
            def export(tools, plan, *args):
                calls.append(plan.source)
                if len(calls) == 1:
                    entered.set()
                    if not release.wait(5): raise AssertionError('Test did not release current video')
                return actual_execute(tools, plan, *args)
            def wait_for(predicate):
                deadline = time.monotonic() + 15
                while not predicate() and time.monotonic() < deadline:
                    self.root.update(); time.sleep(.01)
                self.assertTrue(predicate(), window.status.get())
            with patch('transcora.gui.window.execute', side_effect=export):
                window.check(True)
                try:
                    wait_for(entered.is_set)
                    window.start_or_pause(); release.set()
                    wait_for(lambda: window.pause.paused and window.jobs[0].status == 'completed')
                    window.poll(); window.update_elapsed()
                    self.assertEqual(window.status.get(), 'Stapel pausiert')
                    self.assertEqual(window.start_text.get(), 'Fortsetzen')
                    self.assertEqual(len(Journal(root / 'out').read()['completed']), 1)
                    elapsed = window.elapsed_time.get()
                    with patch('transcora.gui.window.time.monotonic', return_value=time.monotonic() + 100):
                        window.update_elapsed()
                    self.assertEqual(window.elapsed_time.get(), elapsed)
                    self.assertLessEqual(window.start_button.winfo_rootx() + window.start_button.winfo_width(),
                                         self.root.winfo_rootx() + self.root.winfo_width())
                    window.start_or_pause(); wait_for(lambda: not window.busy)
                    self.assertEqual(len(calls), 2)
                    self.assertTrue(all(j.status == 'completed' for j in window.jobs))
                finally:
                    release.set(); window.cancel.set(); wait_for(lambda: not window.busy)

    def test_pause_finishes_the_current_image_then_resumes_or_aborts(self):
        import threading
        from PIL import Image
        from transcora.core.images import ImageOptions
        from transcora.gui.images_panel import execute_image as actual_execute
        from transcora.core.journal import Journal
        panel = self.window.images
        for abort in (False, True):
            with tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp).resolve(); sources = []
                for n in range(3):
                    source = root / f'pair{n}.mpo'
                    Image.new('RGB', (32, 24), 'red').save(source, format='MPO', save_all=True,
                                                        append_images=[Image.new('RGB', (32, 24), 'blue')])
                    sources.append(source)
                panel.jobs.clear(); panel.tree.delete(*panel.tree.get_children())
                panel.defaults = ImageOptions(task='mpo'); panel.output.set(str(root / 'out')); panel.add_paths(sources)
                entered, release = threading.Event(), threading.Event(); calls = []
                def execute_file(tools, plan, *args):
                    calls.append(plan.sources[0])
                    if len(calls) == 1:
                        entered.set()
                        if not release.wait(5): raise AssertionError('Test did not release current export')
                    return actual_execute(tools, plan, *args)
                def wait_for(predicate):
                    deadline = time.monotonic() + 8
                    while not predicate() and time.monotonic() < deadline:
                        self.root.update(); time.sleep(.01)
                    self.assertTrue(predicate(), panel.status.get())
                with patch('transcora.gui.images_panel.execute_image', side_effect=execute_file):
                    panel.run(True)
                    try:
                        wait_for(entered.is_set)
                        panel.start_or_pause()
                        self.assertEqual(panel.start_text.get(), self.window.t('Pause vorgemerkt'))
                        release.set(); wait_for(lambda: panel.pause.paused)
                        # Flush the completed-file and pause messages together.
                        panel.poll()
                        self.assertEqual([j.status for j in panel.jobs], ['completed', 'ready', 'ready'])
                        self.assertEqual(len(Journal(root / 'out').read()['completed']), 1)
                        self.assertEqual(panel.start_text.get(), self.window.t('Fortsetzen'))
                        panel.abort() if abort else panel.start_or_pause()
                        wait_for(lambda: not panel.busy)
                        self.assertEqual(len(calls), 1 if abort else 3)
                        self.assertEqual(panel.jobs[0].status, 'completed')
                    finally:
                        release.set(); panel.cancel.set()
                        wait_for(lambda: not panel.busy)

    def test_mono_half_image_choice_is_visible_only_for_mono_and_updates_name(self):
        window = self.window
        window.add_paths([Path('film_full_sbs.mp4')])
        window.variables['target'].set('Mono'); window.option_changed('target')
        self.root.update()
        self.assertTrue(window.option_frames['mono_eye'].winfo_ismapped())
        window.variables['mono_eye'].set('Rechtes Halbbild'); window.option_changed('mono_eye')
        self.assertEqual(window.jobs[0].options.mono_eye, 'right')
        self.assertIn('_mono_r', window.output_name.get())
        window.language = 'en'; window.apply_language()
        self.assertEqual(window.variables['mono_eye'].get(), 'Right half-image')
        window.variables['target'].set('Half-SBS'); window.option_changed('target')
        self.root.update()
        self.assertFalse(window.option_frames['mono_eye'].winfo_ismapped())

    def test_journal_write_error_does_not_turn_completed_image_export_into_failure(self):
        from PIL import Image
        from transcora.core.images import ImageOptions, mpo_jpegs
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp).resolve()
            source = folder / 'pair.mpo'
            Image.new('RGB', (32, 24), 'red').save(source, format='MPO', save_all=True,
                                                   append_images=[Image.new('RGB', (32, 24), 'blue')])
            panel = self.window.images
            panel.defaults = ImageOptions(task='mpo')
            panel.output.set(str(folder / 'out')); panel.add_paths([source])
            with patch('transcora.gui.images_panel.threading.Thread') as thread, \
                 patch('transcora.gui.images_panel.Journal.complete', side_effect=OSError('disk full')):
                thread.return_value.start.side_effect = lambda: thread.call_args.kwargs['target']()
                panel.run(True); panel.poll(); self.window.poll()
            job = panel.jobs[0]
            self.assertEqual(job.status, 'completed')
            self.assertIsNotNone(job.result)
            self.assertEqual(tuple(p.read_bytes() for p in job.result.outputs), mpo_jpegs(source))
            self.assertIn('Journal nicht gespeichert: 1', panel.status.get())
            self.assertIn('disk full', '\n'.join(self.window.log_lines))

    def test_colour_assumptions_and_other_review_messages_appear_only_once(self):
        from types import SimpleNamespace
        from transcora.core.engine import color_spec
        window = self.window
        window.add_paths([Path('colours_full_sbs.mp4')])
        job = window.jobs[0]
        _, messages = color_spec(dict(width=3840, height=1080, pix_fmt='yuv420p'), 'full_sbs')
        self.assertTrue(messages)
        action = 'Manuell gewähltes Layout/L/R weicht vom Dateinamen ab.'
        job.plan = SimpleNamespace(summary='Summary\n' + messages[0], warnings=messages + messages + [action],
                                   review_warnings=[action], layout='full_sbs', output=Path('test.mp4'), duration=1,
                                   info={'video': {'width': 3840, 'height': 1080, 'avg_frame_rate': '30/1'}})
        job.status = 'ready'
        # Additional details must not cause shared warnings to appear again.
        job.detail = 'Additional detail\n' + '\n'.join(messages)
        for language in ('de', 'en'):
            window.language = language; window.apply_language()
            window.selection_changed(); self.root.update()
            body = window.detail_text.get('1.0', 'end')
            for message in messages:
                self.assertEqual(body.count(window.t(message)), 1)
                index = window.detail_text.search(window.t(message), '1.0')
                self.assertNotIn('attention', window.detail_text.tag_names(index))
            self.assertEqual(body.count(window.t(action)), 1)
            self.assertIn('Additional detail', body)
            self.assertTrue(window.detail_text.tag_ranges('attention'))

    def test_delete_keeps_keyboard_selection_in_visible_order_on_both_tabs(self):
        for panel, suffix in ((self.window, '.mp4'), (self.window.images, '.png')):
            panel.add_paths([Path('C' + suffix), Path('A' + suffix), Path('B' + suffix)])
            panel.sorter.sort('file')
            rows = list(panel.tree.get_children())
            panel.tree.selection_set(rows[1]); panel.tree.focus(rows[1])
            panel.remove()
            self.assertEqual(panel.tree.selection(), (rows[2],))
            self.assertEqual(panel.tree.focus(), rows[2])
            panel.remove()
            self.assertEqual(panel.tree.selection(), (rows[0],))
            panel.remove()
            self.assertEqual(panel.tree.get_children(), ())
            self.assertEqual(panel.tree.selection(), ())

    def test_processing_column_sorts_numbers_and_completed_removal_preserves_files(self):
        from transcora.core.journal import Completion
        for panel, suffix in ((self.window, '.mp4'), (self.window.images, '.png')):
            panel.add_paths([Path(f'item{n}' + suffix) for n in range(3)])
            a, b, c = panel.jobs
            a.result = Completion((), 100, {}); a.status = 'completed'
            b.result = Completion((), 20, {}); b.status = 'completed'
            self.window.update_row(a) if panel is self.window else panel.refresh()
            self.window.update_row(b) if panel is self.window else panel.refresh()
            panel.sorter.sort('processing')
            self.assertEqual([j.id for j in panel.jobs], [b.id, a.id, c.id])
            self.assertEqual(panel.tree.set(a.id, 'processing'), '00:01:40')
            panel.remove_completed()
            self.assertEqual(panel.jobs, [c])
            self.assertEqual(str(panel.remove_completed_button.cget('state')), 'disabled')

    def test_completed_receipt_restores_after_removal_and_unchanged_entry_commits(self):
        from transcora.core.journal import Journal, request, NAME
        from transcora.core.model import Job
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve(); output = root / 'out'; output.mkdir()
            source = root / 'clip_full_sbs.mp4'; source.write_bytes(b'input')
            saved = output / 'clip_half_sbs.mp4'; saved.write_bytes(b'output')
            window = self.window
            window.output_var.set(str(output)); window.invalidate_all()
            Journal(output).complete(request(Job(source, replace(window.defaults)), 'video'), (saved,), 11.5)
            window.add_paths([source]); job = window.jobs[0]
            self.assertEqual(job.status, 'completed')
            self.assertEqual(window.tree.set(job.id, 'processing'), '00:00:11')
            window.selection_changed(); self.assertTrue(window.commit_entries())
            self.assertEqual(job.status, 'completed')
            window.remove_completed()
            self.assertTrue(saved.exists()); self.assertTrue((output / NAME).exists())
            window.add_paths([source]); self.assertEqual(window.jobs[0].status, 'completed')
            (output / NAME).unlink()
            with patch('transcora.gui.window.Toolchain.find', side_effect=OSError('test stop')):
                window.check(False)
                deadline = time.monotonic() + 5
                while window.busy and time.monotonic() < deadline:
                    self.root.update(); time.sleep(.01)
            self.assertEqual(window.jobs[0].status, 'queued')

    def test_new_column_and_completed_button_fit_standard_window_in_both_languages(self):
        window = self.window
        for language in ('de', 'en'):
            window.language = language; window.apply_language()
            for tab, panel in ((window.video_tab, window), (window.image_tab, window.images)):
                window.notebook.select(tab); self.root.update()
                self.assertLessEqual(sum(int(panel.tree.column(c, 'width')) for c in panel.tree['columns']), panel.tree.winfo_width())
                self.assertLess(panel.remove_completed_button.winfo_rootx(), panel.reset_button.winfo_rootx())
                self.assertLessEqual(panel.reset_button.winfo_rootx() + panel.reset_button.winfo_width(), self.root.winfo_rootx() + self.root.winfo_width())
                self.assertEqual(panel.tree.heading('processing', 'text'), 'Processing time' if language == 'en' else 'Bearbeitungszeit')

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
            from transcora.core.journal import Journal
            from transcora.core.images import ImageJob
            original_job = panel.jobs[-1]
            self.assertIsNotNone(original_job.result)
            restored = Journal(folder / 'out').lookup(ImageJob(original_job.source, replace(original_job.options)), 'image')
            self.assertEqual(restored.outputs, tuple(p.resolve() for p in outputs))
            self.assertIn('1 erfolgreich', panel.status.get())
            self.assertFalse(panel.busy)

    def test_bd_file_and_batch_estimates_survive_audio_and_mux_phases(self):
        from transcora.gui.remaining import RemainingTime
        window = self.window
        window.add_paths([Path('test_full_sbs.mp4')])
        job = window.jobs[0]
        job.options = replace(job.options, target='bd3d', container='iso')
        window.run_started = 10
        window.events.put(('batch', [100, 200]))
        window.events.put(('current', (job.source.name, 1, 2)))
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            window.poll()
        with patch('transcora.gui.window.time.monotonic', return_value=200):
            window.events.put(('progress', (job.id, 1, 2, {'percent': 37.5})))
            window.poll()
        self.assertIn('Restzeit: Datei ca.', window.elapsed.get())
        self.assertIn(' · Stapel ca.', window.elapsed.get())
        file_left,batch_left = window.remaining_time.remaining(200)
        self.assertGreater(batch_left,file_left)
        with patch('transcora.gui.window.time.monotonic', return_value=300):
            window.events.put(('phase', (job.id, 1, 2, 'BD-3D: Blu-ray-ISO erstellen')))
            window.poll()
        self.assertIn('Datei ca.',window.elapsed.get())
        self.assertNotIn('Schritt',window.elapsed.get())
        window.language='en';window.apply_language()
        self.assertIn('Remaining: file approx.',window.elapsed.get())
        self.assertIn(' · batch approx.',window.elapsed.get())

    def test_bd_modes_keep_bitrate_and_survive_language_list_and_target_changes(self):
        from transcora.core.model import BD_MODES
        window=self.window
        window.add_paths([Path('film_full_sbs.mp4')])
        job=window.jobs[0]
        window.tree.selection_set(job.id);window.selection_changed()
        window.variables['target'].set('BD-3D');window.option_changed('target')
        for mode,size in [('720p50',(1280,720)),('720p5994',(1280,720)),('1080p',(1920,1080))]:
            window.variables['bd_mode'].set(window.t(BD_MODES[mode]))
            window.combos['video_size'].event_generate('<<ComboboxSelected>>')
            self.root.update()
            self.assertEqual(job.options.bd_mode,mode)
            self.assertEqual(job.options.bd_bitrate_mbps,40)
            self.assertEqual(tuple(map(int,(window.variables[k].get() for k in ('video_width','video_height')))),size)
            self.assertEqual(Options.from_dict(job.serializable()['options']).bd_mode,mode)
            for language in ('en','de'):
                window.language=language;window.apply_language()
                self.assertEqual(window.variables['bd_mode'].get(),window.t(BD_MODES[mode]))
                self.assertEqual(str(window.combos['video_size'].cget('state')),'readonly')
        self.assertEqual(Options.from_dict({'target':'bd3d','container':'iso'}).bd_mode,'1080p')
        with self.assertRaises(ValueError):
            Options.from_dict({'bd_mode':'720p60'})

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

    def test_late_timing_bar_keeps_footer_and_list_inside_small_window(self):
        self.root.geometry('780x680');self.root.update()
        self.window.add_paths([Path('/one/current_full_sbs.mp4')])
        job=self.window.jobs[-1]
        self.window.tree.selection_set(job.id);self.window.selection_changed()
        self.window.variables['target'].set('BD-3D');self.window.option_changed('target')
        self.root.update()
        height=self.window.tree.winfo_height();detail=self.window.detail_text.winfo_height()
        self.window.elapsed_time.set('Vergangene Zeit: 02:34')
        self.window.elapsed.set('Restzeit: Datei ca. 05:12 · Stapel ca. 01:42:00');self.root.update()
        self.window.toggle_advanced();self.root.update()
        self.assertEqual(self.window.tree.winfo_height(),height)
        self.assertEqual(self.window.detail_text.winfo_height(),detail)
        self.assertLessEqual(self.window.start_button.winfo_rooty()+self.window.start_button.winfo_height(),
                             self.root.winfo_rooty()+self.root.winfo_height())

    def test_normal_settings_fit_and_bd_advanced_controls_stay_in_bounds(self):
        from transcora.core.model import TARGETS
        self.window.add_paths([Path('slideshow_full_sbs.mp4')])
        self.window.tree.selection_set(self.window.jobs[0].id)
        self.window.selection_changed()
        # The CI desktop can be shorter than a normal desktop. Test the client
        # area independently, then check the bounded small-window view too.
        # Tk's default maximum follows the physical desktop on Windows.
        self.root.maxsize(2000,2000)
        self.root.geometry('860x860'); self.root.update()
        self.assertEqual(self.root.winfo_height(),860)
        for language in ('de','en'):
            self.window.language=language; self.window.apply_language()
            for target in ('anaglyph','row_interleaved','bd3d'):
                self.window.variables['target'].set(self.window.t(TARGETS[target]))
                self.window.option_changed('target'); self.root.update()
                area=self.window.settings_area
                self.assertLessEqual(area.body.winfo_reqheight(),area.canvas.winfo_height())
                self.assertFalse(area.scroll.winfo_ismapped())
                self.assertGreaterEqual(self.window.tree.winfo_height(),140)
            self.assertFalse(self.window.combos['bd_bitrate_mbps'].winfo_ismapped())
            self.assertFalse(self.window.advanced_audio_button.winfo_ismapped())
            self.window.toggle_advanced(); self.root.update()
            self.assertTrue(self.window.combos['bd_bitrate_mbps'].winfo_ismapped())
            self.assertTrue(self.window.advanced_audio_button.winfo_ismapped())
            for key in ('codec','rate_mode','crf','bitrate_mbps'):
                self.assertFalse(self.window.combos[key].winfo_ismapped())
            self.root.geometry('780x680'); self.root.update()
            for widget in (self.window.combos['bd_bitrate_mbps'],self.window.advanced_audio_button):
                self.assertLessEqual(widget.winfo_rootx()+widget.winfo_width(),
                                     area.canvas.winfo_rootx()+area.canvas.winfo_width())
            self.window.close_advanced(); self.root.geometry('860x860'); self.root.update()

    def test_language_and_wheel_preserve_bd_bitrate_and_per_file_settings(self):
        from transcora.core.model import BD_BITRATES, TARGETS
        self.assertEqual(Options().bd_bitrate_mbps,40)
        self.window.add_paths([Path('one_full_sbs.mp4'),Path('two_full_sbs.mp4')])
        first,second=self.window.jobs
        first.options=replace(first.options,target='bd3d',container='iso',bd_bitrate_mbps=35)
        second.options=replace(second.options,target='bd3d',container='iso',bd_bitrate_mbps=40)
        self.window.tree.selection_set(first.id); self.window.selection_changed()
        self.window.toggle_advanced(); self.root.geometry('780x680'); self.root.update()
        for language in ('en','de','en'):
            self.window.language=language; self.window.apply_language(); self.root.update()
            self.assertEqual(self.window.variables['bd_bitrate_mbps'].get(),'35 Mbit/s')
            self.assertEqual(second.options.bd_bitrate_mbps,40)
            self.assertEqual(self.window.defaults.bd_bitrate_mbps,40)
            for value in BD_BITRATES:
                first.options=replace(first.options,bd_bitrate_mbps=value)
                self.window.selection_changed(); self.root.update()
                for delta in (120,-120):
                    self.window.combos['bd_bitrate_mbps'].event_generate('<MouseWheel>',delta=delta)
                    self.root.update()
                    self.assertEqual(first.options.bd_bitrate_mbps,value)
                    self.assertEqual(self.window.variables['bd_bitrate_mbps'].get(),f'{value} Mbit/s')
            first.options=replace(first.options,bd_bitrate_mbps=35)
        self.window.tree.selection_remove(first.id); self.window.selection_changed()
        self.window.variables['target'].set(self.window.t(TARGETS['bd3d']))
        self.window.option_changed('target')
        self.assertEqual(self.window.variables['bd_bitrate_mbps'].get(),'40 Mbit/s')
        self.window.add_paths([Path('new_full_sbs.mp4')])
        self.assertEqual(self.window.jobs[-1].options.bd_bitrate_mbps,40)
        with tempfile.TemporaryDirectory() as tmp, patch('transcora.gui.window.app_root',return_value=Path(tmp)):
            self.window.persist_settings()
            self.window.defaults=replace(self.window.defaults,bd_bitrate_mbps=20)
            self.window._load_settings()
            self.assertEqual(self.window.defaults.bd_bitrate_mbps,40)

    def test_dual_target_keeps_containers_and_preview_choices_separate(self):
        from types import SimpleNamespace
        window=self.window
        window.variables['target'].set(window.t('Dual · L/R-Spuren'))
        window.option_changed('target')
        self.assertEqual(window.defaults.target,'dual')
        self.assertEqual(window.defaults.container,'mp4')
        self.assertEqual(tuple(window.combos['container'].cget('values')),('MP4','MKV'))
        self.assertEqual(window.video_size_caption.get(),window.t('Ausgabegröße je Halbbild'))
        viewer=PreviewWindow(self.root,lambda seconds:None)
        window.controls.extend(viewer.controls())
        viewer.set_plan(SimpleNamespace(duration=1,options=window.defaults,
                        info={'video':{'avg_frame_rate':'25/1'}}))
        self.root.update()
        self.assertTrue(viewer.view_frame.winfo_ismapped())
        self.assertNotIn('BD-3D:', viewer.note.cget('text'))
        viewer.view_combo.current(1)
        self.assertEqual(viewer.preview_view,'cross')
        window.close_preview(viewer.dialog,viewer.time_entry,viewer.scale)
        self.assertFalse(any(widget==viewer.view_combo for widget,_ in window.controls))

    def test_suffix_popup_fits_player_names_without_widening_controls(self):
        from tkinter import font
        if self.root.tk.call('tk','windowingsystem')=='aqua':
            self.skipTest('Native macOS menus size themselves')
        window=self.window
        window.defaults=replace(window.defaults,target='half_sbs')
        window.refresh_controls();self.root.update()
        combo=window.combos['suffix'];before=combo.winfo_width()
        self.root.tk.call('ttk::combobox::Post',str(combo));self.root.update()
        try:
            popup=self.root.tk.call('ttk::combobox::PopdownWindow',str(combo))
            width=int(self.root.tk.call('wm','geometry',popup).split('x')[0])
            measured=max(font.Font(root=self.root,font='TkTextFont').measure(v) for v in combo.cget('values'))
            self.assertGreaterEqual(width,measured+36)
            self.assertEqual(combo.winfo_width(),before)
        finally:
            self.root.tk.call('ttk::combobox::Unpost',str(combo))

    def test_player_suffix_labels_are_menu_only_and_custom_text_stays_literal(self):
        window=self.window
        for language in ('de','en'):
            window.language=language; window.apply_language()
            window.variables['target'].set(window.t('Half-SBS')); window.option_changed('target')
            values=tuple(window.combos['suffix'].cget('values'))
            self.assertIn('-lrq (Bino/Stereoscopic Player)',values)
            self.assertIn('.3D.HSBS (Kodi)',values)
            self.assertFalse(any('HSBS-lrh' in v for v in values))
            window.variables['suffix'].set('-lrq (Bino/Stereoscopic Player)')
            window.option_changed('suffix')
            self.assertEqual(window.variables['suffix'].get(),'-lrq')
            self.assertEqual(window.defaults.suffix,'-lrq')
            self.assertTrue(window.output_name.get().endswith('-lrq.mp4'))
            window.variables['suffix'].set('_My own (label)')
            window.option_changed('suffix')
            self.assertEqual(window.defaults.suffix,'_My own (label)')

    def test_file_warnings_are_highlighted_and_follow_selection_and_language(self):
        from types import SimpleNamespace
        message='Full/Half-Layout nicht eindeutig erkennbar. Quelllayout für diese Datei auswählen.'
        self.window.add_paths([Path('unclear.mp4'),Path('good_full_sbs.mp4')])
        first,second=self.window.jobs
        first.status,first.detail='blocked',message
        self.window.tree.selection_set(first.id); self.window.selection_changed()
        for language in ('de','en'):
            self.window.language=language; self.window.apply_language(); self.root.update()
            text=self.window.detail_text
            self.assertTrue(text.get('1.0','end').startswith('⚠ '+self.window.t(message)))
            self.assertIn('attention',text.tag_names('1.0'))
            self.assertEqual(text.tag_cget('attention','foreground'),GOLD_LIGHT)
        self.window.tree.selection_set(second.id); self.window.selection_changed()
        self.assertEqual(self.window.attention.get(),'')
        second.plan=SimpleNamespace(summary='Summary',warnings=['Check your player'],review_warnings=['Check your player'],layout='full_sbs',
                                    info={'video':{'width':3840,'height':1080}},duration=10)
        self.window.events.put(('job',(second.id,'ready','Check your player',second.plan)))
        self.window.poll()
        self.assertTrue(self.window.detail_text.get('1.0','end').startswith('⚠ Check your player'))
        self.assertEqual(self.window.detail_text.get('1.0','end').count('Check your player'),1)

    def test_unclassified_notes_do_not_request_user_action(self):
        from types import SimpleNamespace
        self.window.add_paths([Path('good_full_sbs.mp4')])
        job=self.window.jobs[0]
        note='Untertitel werden nicht übernommen.'
        job.plan=SimpleNamespace(summary='Summary',warnings=[note],layout='full_sbs',output=Path('test.mp4'),
                                 info={'video':{'width':3840,'height':1080}},duration=10)
        job.status='ready'; job.detail=note
        for language in ('de','en'):
            self.window.language=language; self.window.apply_language()
            self.window.show_job_details(job); self.root.update()
            text=self.window.detail_text; body=text.get('1.0','end')
            self.assertIn(self.window.t(note),body)
            self.assertNotIn('⚠',body)
            self.assertFalse(text.tag_ranges('attention'))

    def test_english_check_log_translates_audio_labels_and_keeps_track_metadata(self):
        from types import SimpleNamespace
        from transcora.core.engine import Plan
        window=self.window
        window.language='en';window.language_var.set('English');window.apply_language()
        window.add_paths([Path('film_full_sbs.mp4')])
        job=window.jobs[0]
        video=dict(width=3840,height=1080,index=0,codec_name='h264',avg_frame_rate='30/1')
        audio=dict(index=1,codec_type='audio',codec_name='aac',channels=2,
                   tags={'language':'und','title':'Fertig · Wartet; Original'})
        plan=Plan(job.source,Path('C:/Output/film.mp4'),job.options,
                  dict(video=video,streams=[video,audio]),'full_sbs',False,(1920,1080),
                  'yuv420p','',60,[],{},'Full-SBS · manuell gewählt',[])
        with patch('transcora.gui.window.Toolchain.find',return_value=SimpleNamespace(inspect=lambda:{'version':'Fixture tools'})), \
             patch('transcora.gui.window.plan_job',return_value=plan), \
             patch('transcora.gui.window.threading.Thread') as thread:
            thread.return_value.start.side_effect=lambda:thread.call_args.kwargs['target']()
            window.check(False);window.poll()
        text='\n'.join(window.log_lines)
        self.assertIn('Audio: Track 1:',text)
        self.assertIn('2 channels',text)
        self.assertIn('und · Fertig · Wartet; Original',text)
        self.assertNotIn('Spur 1:',text)
        self.assertEqual(window.status.get(),'Check finished: 1 ready · 0 blocked.')

    def test_notes_are_distinct_from_review_warnings_and_selection_has_contrast(self):
        from types import SimpleNamespace
        from transcora.core.model import ANAGLYPH_PLAYER_NOTE, COMPATIBILITY_NOTE
        self.window.add_paths([Path('slideshow_full_sbs.mp4')])
        job=self.window.jobs[0]
        self.window.tree.selection_set(job.id)
        for language in ('de','en'):
            self.window.language=language
            for profile in ('quality','quality10','compatible'):
                note=COMPATIBILITY_NOTE if profile=='compatible' else ANAGLYPH_PLAYER_NOTE
                job.options=replace(job.options,target='anaglyph',profile=profile)
                job.plan=SimpleNamespace(summary='Summary',warnings=[note,note],
                    review_warnings=[] if profile=='compatible' else [note],layout='full_sbs',output=Path('slideshow.mkv'))
                job.status='ready';job.detail='\n'.join(job.plan.warnings)
                self.window.selection_changed(); self.root.update()
                text=self.window.detail_text; body=text.get('1.0','end')
                self.assertEqual(body.count(self.window.t(note)),1)
                self.assertEqual('⚠' in body,profile!='compatible')
                if profile=='quality10':self.assertIn(self.window.t('10 Bit: Feinere Abstufungen; kein HDR-Modus.'),body)
            info='29.970 → 23,976 fps: Ganze Stereobildpaare werden ausgelassen oder wiederholt. Laufzeit und Ton bleiben erhalten; Bewegungen können ungleichmäßiger werden. Keine Bewegungsinterpolation; Video wird nur einmal kodiert.'
            process='BD-3D: FFmpeg bereitet die Quelle vor, FRIM kodiert AVC/MVC und tsMuxeR erstellt die Ausgabe. Gewählter Ton wird als LPCM gespeichert.'
            job.options=replace(job.options,target='bd3d',container='iso')
            job.plan=SimpleNamespace(summary='Summary',warnings=[info,process],review_warnings=[],layout='full_sbs',output=Path('slideshow.iso'))
            job.detail='\n'.join(job.plan.warnings)
            self.window.selection_changed(); self.root.update()
            body=text.get('1.0','end')
            self.assertNotIn('⚠',body)
            self.assertIn(self.window.t(info),body);self.assertIn(self.window.t(process),body)
            self.assertFalse(text.tag_ranges('attention'))
        job.status='blocked';job.plan=None;job.detail='Quelllayout für diese Datei auswählen.'
        self.window.selection_changed(); self.root.update()
        text.tag_add('sel','1.0','1.end')
        self.assertEqual(text.tag_names()[-1],'sel')
        self.assertEqual(text.tag_cget('sel','foreground'),APP_BG)
        self.assertEqual(text.tag_cget('sel','background'),GOLD_LIGHT)

    def test_heading_clicks_sort_both_lists_preserve_selection_and_numeric_metadata(self):
        window=self.window
        window.add_paths([Path('Film10_full_sbs.mp4'),Path('Film2_full_sbs.mp4'),Path('Film1_full_sbs.mp4')])
        ten,two,one=window.jobs
        ten.source_fps='30000/1001';ten.source_duration=20
        two.source_fps='3/1';two.source_duration=3
        for job in window.jobs:window.update_row(job)
        window.tree.selection_set((ten.id,two.id));window.selection_changed();self.root.update()
        def click(panel,column):
            command=panel.tree.heading(column,'command')
            self.assertTrue(command)
            self.root.tk.call(command);self.root.update()
        self.assertEqual(window.tree.identify_region(20,10),'heading')
        window.tree.event_generate('<ButtonPress-1>',x=20,y=10)
        window.tree.event_generate('<ButtonRelease-1>',x=20,y=10)
        self.root.update()
        self.assertEqual(window.tree.get_children(),(one.id,two.id,ten.id))
        self.assertEqual([j.id for j in window.jobs],[one.id,two.id,ten.id])
        self.assertEqual(set(window.tree.selection()),{ten.id,two.id})
        click(window,'file');self.assertEqual(window.tree.get_children(),(ten.id,two.id,one.id))
        click(window,'fps');self.assertEqual(window.tree.get_children(),(two.id,ten.id,one.id))
        click(window,'fps');self.assertEqual(window.tree.get_children(),(ten.id,two.id,one.id))
        click(window,'duration');self.assertEqual(window.tree.get_children(),(two.id,ten.id,one.id))
        for language,label in [('en','Duration ▲'),('de','Dauer ▲')]:
            window.language=language;window.apply_language();self.root.update()
            self.assertEqual(window.tree.heading('duration','text'),label)
        window.set_busy(True);click(window,'file')
        self.assertEqual(window.tree.get_children(),(two.id,ten.id,one.id))
        window.set_busy(False)
        panel=window.images;window.notebook.select(window.image_tab)
        panel.add_paths([Path('Bild10_full_sbs.jpg'),Path('Bild2_full_sbs.jpg')])
        ten,two=panel.jobs;panel.tree.selection_set(ten.id);self.root.update()
        click(panel,'file');self.assertEqual(panel.tree.get_children(),(two.id,ten.id))
        self.assertEqual(panel.tree.selection(),(ten.id,))
        click(panel,'file');self.assertEqual(panel.tree.get_children(),(ten.id,two.id))
        for column in ('task','target','status'):self.assertTrue(panel.tree.heading(column,'command'))

    def test_real_folder_import_and_twenty_file_batch_with_shared_output_directory(self):
        import shutil
        from PIL import Image
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp, patch('transcora.gui.window.app_root',return_value=Path(tmp)):
            base=Path(tmp).resolve();folder=base/'videos';folder.mkdir()
            sample=base/'sample.mp4'
            capture([str(tools.ffmpeg),'-v','error','-f','lavfi','-i','testsrc2=s=128x32:r=30',
                     '-frames:v','1','-c:v','libx264','-pix_fmt','yuv420p','-colorspace','bt709',
                     '-color_trc','bt709','-color_primaries','bt709','-color_range','tv',str(sample)])
            for number in range(20):shutil.copy2(sample,folder/f'Diashow_{number+1}_full_sbs.MP4')
            window=self.window
            window.defaults=replace(Options(),target='full_ou',container='mkv',video_size='original')
            window.output_var.set(str(folder));window.recursive.set(True)
            def idle(timeout=90):
                deadline=time.monotonic()+timeout
                while window.busy and time.monotonic()<deadline:self.root.update();time.sleep(.01)
                self.assertFalse(window.busy,window.status.get())
            with patch('transcora.gui.window.filedialog.askdirectory',return_value=str(folder)):
                window.add_folder();idle(10)
            self.assertEqual(len(window.jobs),20)
            self.assertEqual(len(window.tree.get_children()),20)
            self.assertTrue(all(j.source_root==folder for j in window.jobs))
            window.check(True);idle()
            self.assertTrue(all(j.status=='completed' for j in window.jobs),[(j.source.name,j.status,j.detail) for j in window.jobs])
            self.assertEqual(len(list(folder.glob('*_full_ou.mkv'))),20)
            self.assertEqual(window.current_file.index,20)
            from transcora.core.journal import Journal
            self.assertEqual(len(Journal(folder).read()['completed']), 20)
            self.assertTrue(all(j.result and j.source_fps for j in window.jobs))
            sources = [j.source for j in window.jobs]
            window.remove_completed()
            window.add_paths(sources, folder)
            self.assertTrue(all(j.status == 'completed' and j.source_fps for j in window.jobs))
            with patch('transcora.gui.window.execute', side_effect=AssertionError('Completed files must not run again')):
                window.check(True)
            self.assertFalse(window.busy)
            self.assertEqual(len(list(folder.glob('*_full_ou.mkv'))), 20)
            # An output directory above the selected input must not hide it.
            child=base/'parent/child';child.mkdir(parents=True);shutil.copy2(sample,child/'child_full_sbs.mp4')
            window.output_var.set(str(child.parent))
            with patch('transcora.gui.window.filedialog.askdirectory',return_value=str(child)):
                window.add_folder();idle(10)
            self.assertEqual(len(window.jobs),21)
            # The corresponding image import supports shared input/output too.
            pictures=base/'pictures';pictures.mkdir();Image.new('RGB',(32,16)).save(pictures/'photo_full_sbs.png')
            panel=window.images;panel.output.set(str(pictures))
            with patch('transcora.gui.images_panel.filedialog.askdirectory',return_value=str(pictures)):
                panel.add_folder()
            self.assertEqual(len(panel.jobs),1)

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
        self.window.variables['target'].set('BD-3D')
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

    def test_batch_remaining_survives_mixed_settings_and_next_file(self):
        from transcora.gui.remaining import RemainingTime
        window = self.window
        window.run_started = 0
        window.remaining_time = RemainingTime([100, 200])
        with patch('transcora.gui.window.time.monotonic', return_value=0):
            window.remaining_time.start(1, 0)
        with patch('transcora.gui.window.time.monotonic', return_value=50):
            window.estimate_remaining(1, 2, 50)
        self.assertEqual(window.elapsed.get(), 'Restzeit: Datei ca. 00:50 · Stapel ca. 04:10')
        window.remaining_time.complete(100)
        window.events.put(('current', ('second.mp4', 2, 2)))
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            window.poll()
            window.update_elapsed()
        self.assertEqual(window.elapsed.get(), 'Restzeit: Datei ca. 03:20 · Stapel ca. 03:20')
        with patch('transcora.gui.window.time.monotonic', return_value=120):
            window.update_elapsed()
        self.assertIn('Stapel ca.', window.elapsed.get())
        window.set_busy(False)

    def test_remaining_estimate_uses_progress_and_freezes_after_finish(self):
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            self.window.run_started = 30
            self.window.set_busy(True)
            self.window.update_elapsed()
            self.assertEqual(self.window.elapsed.get(), 'Restzeit: Datei — · Stapel —')
            self.window.estimate_remaining(1, 1, 50)
            self.assertEqual(self.window.elapsed.get(), 'Restzeit: Datei ca. 01:10 · Stapel ca. 01:10')
            self.assertEqual(self.window.elapsed_time.get(), 'Vergangene Zeit: 01:10')
            self.window.abort()
            self.assertIsNotNone(self.window.run_started)
            self.window.set_busy(False)
        with patch('transcora.gui.window.time.monotonic', return_value=9999):
            self.window.update_elapsed()
        self.assertEqual(self.window.elapsed.get(), 'Restzeit: Datei — · Stapel —')
        self.assertEqual(self.window.elapsed_time.get(), 'Vergangene Zeit: 01:10')
        self.assertEqual(PreviewWindow.time_text(3661), '01:01:01')

    def test_bd_audio_options_remain_available_and_phase_replaces_stale_estimate(self):
        self.root.geometry('860x680')
        self.window.variables['target'].set('BD-3D')
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
        self.window.speed.set('Alte Geschwindigkeit')
        text = 'BD-3D: Blu-ray-ISO erstellen'
        self.window.events.put(('phase', ('job', 1, 1, text)))
        self.window.poll()
        self.assertEqual(self.window.status.get(), text)
        self.assertEqual(self.window.speed.get(), '')
        self.assertEqual(self.window.elapsed.get(), 'Restzeit: Datei — · Stapel —')
        self.assertEqual(str(self.window.progress.cget('mode')), 'indeterminate')
        self.window.events.put(('progress', ('job', 1, 1,
            {'percent': 94, 'seconds': 100, 'remaining_seconds': 120})))
        with patch('transcora.gui.window.time.monotonic', return_value=100):
            self.window.poll()
        self.assertEqual(self.window.elapsed.get(), 'Restzeit: Datei ca. 02:00 · Stapel ca. 02:00')
        self.assertEqual(str(self.window.progress.cget('mode')), 'determinate')
        self.window.set_busy(False)

    def test_log_has_dark_surfaces_and_scrollbar(self):
        self.window.log_lines=['alpha beta gamma']
        self.window.show_log()
        self.root.update()
        dialog = next(w for w in self.root.winfo_children() if isinstance(w, tk.Toplevel) and w.winfo_ismapped())
        self.assertEqual(dialog.cget('background'), APP_BG)
        frame = next(w for w in dialog.winfo_children() if isinstance(w, ttk.Frame))
        text = next(w for w in frame.winfo_children() if isinstance(w, tk.Text))
        self.assertEqual(text.cget('background'), PANEL_BG)
        self.assertEqual(text.cget('highlightthickness'), 0)
        self.assertTrue(text.cget('yscrollcommand'))
        text.event_generate('<ButtonPress-1>',x=text.bbox('1.0')[0]+1,y=text.bbox('1.0')[1]+3)
        text.event_generate('<B1-Motion>',x=text.bbox('1.5')[0]-1,y=text.bbox('1.5')[1]+3)
        text.event_generate('<ButtonRelease-1>',x=text.bbox('1.5')[0]-1,y=text.bbox('1.5')[1]+3)
        self.root.update()
        self.assertEqual(text.get('sel.first','sel.last'),'alpha')
        with patch.object(text.copy_menu,'tk_popup') as popup:
            text.event_generate('<Button-3>',x=10,y=10); self.root.update()
            popup.assert_called_once()
            self.assertEqual(text.copy_menu.entrycget(0,'state'),'normal')
            text.copy_menu.invoke(0)
        self.assertEqual(self.root.clipboard_get(),'alpha')
        self.assertEqual(text.get('1.0','end-1c'),'alpha beta gamma')
        self.assertEqual(str(text.cget('state')),'disabled')
        text.tag_remove('sel','1.0','end')
        with patch.object(text.copy_menu,'tk_popup'):
            text.event_generate('<Button-3>',x=10,y=10); self.root.update()
            self.assertEqual(text.copy_menu.entrycget(0,'state'),'disabled')
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

