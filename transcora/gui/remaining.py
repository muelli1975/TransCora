"""Elapsed-work estimates; no extra media scans or stored machine benchmarks."""
class RemainingTime:
    def __init__(self, items=()):
        # (duration, comparable export settings, has a separate MVC encode stage)
        self.items = list(items)
        self.history = {}
        self.index = None
        self.started = self.phase_started = self.updated = None
        self.finish = self.encode_elapsed = None
        self.finishing = False

    def start(self, index, now):
        if self.index == index:
            return
        self.index, self.started, self.phase_started = index, now, now
        self.finish = self.encode_elapsed = self.updated = None
        self.finishing = False

    def phase(self, now):
        self.phase_started = now

    def progress(self, now, percent, phase_percent=None, remaining=None):
        if self.index is None:
            return
        weight, kind, bd = self.items[self.index-1]
        elapsed = now-self.started
        if remaining is not None:
            predicted = now+max(0, remaining)
        elif bd:
            if self.finishing or phase_percent is None or not .01 <= phase_percent/100 < 1:
                return
            phase_elapsed = now-self.phase_started
            if phase_elapsed < 2:
                return
            encoding = phase_elapsed/(phase_percent/100)
            samples = self.history.get(kind, ())
            overhead = (sum(s[1] for s in samples)/sum(s[2] for s in samples)*weight
                        if samples else encoding*30/70)
            predicted = now+encoding-phase_elapsed+overhead
        else:
            fraction = percent/100
            if elapsed < 2 or not .01 <= fraction < 1:
                return
            predicted = self.started+elapsed/fraction
        self.finish = predicted if self.finish is None else .25*predicted+.75*self.finish
        self.updated = now

    def end_encoding(self, now):
        if self.index is None:
            return
        self.encode_elapsed = now-self.started
        self.finishing = True

    def complete(self, now, success=True):
        if self.index is None:
            return
        weight, kind, bd = self.items[self.index-1]
        total = now-self.started
        if success and total > 0:
            overhead = max(0, total-self.encode_elapsed) if bd and self.encode_elapsed is not None else 0
            self.history.setdefault(kind, []).append((total, overhead, weight))
        self.finish = None

    def remaining(self, now):
        if self.index is None or self.finish is None or self.finish <= now:
            return None, None
        # Encoder updates should be live; a stall is not a reliable countdown.
        if not self.finishing and self.updated is not None and now-self.updated > 15:
            return None, None
        file_left = self.finish-now
        weight, current_kind, _ = self.items[self.index-1]
        current_rate = (self.finish-self.started)/weight
        batch_left = file_left
        for future_weight, kind, _ in self.items[self.index:]:
            samples = self.history.get(kind, ())
            rate = (sum(s[0] for s in samples)/sum(s[2] for s in samples)
                    if samples else current_rate if kind == current_kind else None)
            if rate is None:
                return file_left, None
            batch_left += future_weight*rate
        return file_left, batch_left
