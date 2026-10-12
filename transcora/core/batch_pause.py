"""Pause only at a completed file boundary; the current encoder is untouched."""
import threading
import time


class BatchPause:
    def __init__(self):
        self.requested = threading.Event()
        self.wake = threading.Event()
        self.paused = False
        self.lock = threading.Lock()

    def reset(self):
        with self.lock:
            self.requested.clear()
            self.wake.clear()
            self.paused = False

    def toggle(self):
        with self.lock:
            if self.requested.is_set():
                self.requested.clear()
                self.wake.set()
            else:
                self.requested.set()
            return self.requested.is_set()

    def wait(self, cancel, notify):
        with self.lock:
            if not self.requested.is_set() or cancel.is_set():
                return 0.0
            self.paused = True
        started = time.monotonic()
        notify(True, started)
        while self.requested.is_set() and not cancel.is_set():
            self.wake.wait(.1)
            self.wake.clear()
        duration = max(0, time.monotonic() - started)
        with self.lock:
            self.paused = False
        notify(False, duration)
        return duration

    @property
    def caption(self):
        if self.paused:
            return 'Fortsetzen'
        return 'Pause vorgemerkt' if self.requested.is_set() else 'Nach Datei pausieren'
