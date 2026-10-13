import threading
import time
import unittest
from transcora.core.batch_pause import BatchPause


class PauseTests(unittest.TestCase):
    def test_request_can_be_withdrawn_before_the_file_boundary(self):
        pause = BatchPause()
        self.assertTrue(pause.toggle())
        self.assertFalse(pause.toggle())
        self.assertEqual(pause.wait(threading.Event(), lambda *args: self.fail('Unexpected pause')), 0)

    def test_resume_and_cancel_release_the_waiting_worker(self):
        for abort in (False, True):
            pause = BatchPause(); cancel = threading.Event(); entered = threading.Event(); events = []
            pause.toggle()
            def notify(paused, value):
                events.append((paused, value))
                if paused: entered.set()
            worker = threading.Thread(target=lambda: pause.wait(cancel, notify))
            worker.start()
            try:
                self.assertTrue(entered.wait(2))
                self.assertTrue(pause.paused)
                self.assertEqual(pause.caption, 'Fortsetzen')
                cancel.set() if abort else pause.toggle()
                worker.join(2)
                self.assertFalse(worker.is_alive())
                self.assertEqual([p for p, _ in events], [True, False])
                self.assertGreaterEqual(events[1][1], 0)
            finally:
                cancel.set(); worker.join(2)

