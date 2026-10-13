import os
import queue
import time
import tkinter as tk
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from transcora.gui.batch_finish import BatchFinish, CHOICES, request_shutdown, shutdown_command
from transcora.gui.localization import Localizer


class ShutdownCommandTests(unittest.TestCase):
    def test_native_requests_do_not_force_other_applications_to_close(self):
        for platform, expected in (
            ('win32', ['/s', '/t', '0']),
            ('linux', ['systemctl', 'poweroff']),
            ('darwin', ['/usr/bin/osascript', '-e', 'tell application "System Events" to shut down']),
        ):
            with self.subTest(platform=platform), patch('transcora.gui.batch_finish.sys.platform', platform):
                command = shutdown_command()
                self.assertEqual(command[1:] if platform == 'win32' else command, expected)
                self.assertNotIn('/f', command)
                self.assertNotIn('--force', command)

    def test_rejected_shutdown_is_reported_without_a_fallback(self):
        with patch('transcora.gui.batch_finish.subprocess.run', return_value=SimpleNamespace(
                returncode=1, stderr='Permission denied', stdout='')) as run:
            with self.assertRaisesRegex(OSError, 'Permission denied'):
                request_shutdown()
            self.assertEqual(run.call_count, 1)


class FinishTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError:
            if os.environ.get('TRANSCORA_REQUIRE_GUI'):
                raise
            self.skipTest('No display')
        self.owner = SimpleNamespace(root=self.root, language='de', closing=False, busy=False,
            images=SimpleNamespace(busy=False), events=queue.Queue(), save_session=Mock(return_value=True))
        self.owner.localizer = Localizer(self.root, self.owner)
        self.owner.t = self.owner.localizer.t
        self.finish = BatchFinish(self.owner)
        self.shutdown = patch('transcora.gui.batch_finish.request_shutdown').start()
        self.addCleanup(patch.stopall)

    def tearDown(self):
        if hasattr(self, 'root'):
            for timer in self.root.tk.call('after', 'info'):
                self.root.after_cancel(timer)
            self.root.destroy()

    def test_default_and_shared_selection_translate_without_persistence(self):
        self.finish.add_controls(self.root, 0)
        self.finish.add_controls(self.root, 1)
        self.assertEqual(self.finish.choice.source, CHOICES[0])
        combo = self.finish.combos[0]
        combo.current(2)
        self.finish.selected(SimpleNamespace(widget=combo))
        self.assertEqual(self.finish.combos[1].get(), CHOICES[2])
        self.owner.language = 'en'
        self.owner.localizer.apply(); self.finish.render()
        self.assertEqual(combo.get(), 'Shut down computer')
        self.assertEqual(combo.current(), 2)
        self.assertEqual(BatchFinish(self.owner).choice.source, CHOICES[0])

    def test_error_abort_and_other_active_work_do_not_start_actions(self):
        self.finish.choice.set(CHOICES[2])
        for attribute in ('closing', 'busy'):
            setattr(self.owner, attribute, True)
            self.assertFalse(self.finish.completed(True))
            setattr(self.owner, attribute, False)
        self.owner.images.busy = True
        self.assertFalse(self.finish.completed(True))
        self.owner.images.busy = False
        self.assertFalse(self.finish.completed(False))
        self.assertIsNone(self.finish.dialog)
        self.shutdown.assert_not_called()

    def test_close_saves_before_exiting_and_stays_open_if_save_fails(self):
        self.finish.choice.set(CHOICES[1])
        self.owner.save_session.return_value = False
        with patch.object(self.root, 'destroy') as destroy:
            self.assertFalse(self.finish.completed(True)); destroy.assert_not_called()
            self.finish.choice.set(CHOICES[1]); self.owner.save_session.return_value = True
            self.assertTrue(self.finish.completed(True)); destroy.assert_called_once()
        self.assertEqual(self.finish.choice.source, CHOICES[0])
        self.shutdown.assert_not_called()

    def test_shutdown_has_thirty_second_countdown_and_can_be_cancelled(self):
        self.finish.choice.set(CHOICES[2])
        before = time.monotonic()
        self.assertFalse(self.finish.completed(True))
        self.assertGreaterEqual(self.finish.deadline, before + 30)
        self.assertIn('30 Sekunden', self.finish.note.cget('text'))
        self.assertEqual(self.finish.choice.source, CHOICES[0])
        self.finish.cancel()
        self.assertIsNone(self.finish.dialog); self.assertIsNone(self.finish.timer)
        self.shutdown.assert_not_called(); self.owner.save_session.assert_not_called()

    def test_countdown_does_not_shutdown_if_settings_cannot_be_saved(self):
        self.finish.countdown(); self.finish.cancel()
        self.finish.countdown(); self.owner.save_session.return_value = False
        self.finish.deadline = time.monotonic() - 1
        self.finish.tick()
        self.shutdown.assert_not_called(); self.assertIsNone(self.finish.dialog)

    def test_shutdown_runs_only_after_deadline_and_returns_error_to_gui(self):
        self.shutdown.side_effect = OSError('Denied')
        self.finish.countdown(); self.finish.deadline = time.monotonic() - 1
        self.finish.tick()
        kind, error = self.owner.events.get(timeout=3)
        self.assertEqual(kind, 'shutdown-result'); self.assertEqual(error, 'Denied')
        self.owner.save_session.assert_called_once(); self.shutdown.assert_called_once()
        with patch('transcora.gui.batch_finish.messagebox.showerror') as showerror:
            self.assertFalse(self.finish.shutdown_result(error)); showerror.assert_called_once()
        self.assertIsNone(self.finish.dialog)

    def test_successful_native_request_closes_application(self):
        with patch.object(self.root, 'destroy') as destroy:
            self.assertTrue(self.finish.shutdown_result(None)); destroy.assert_called_once()
