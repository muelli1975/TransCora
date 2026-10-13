"""Batch ETA from processed video duration and elapsed processing time."""
class RemainingTime:
    def __init__(self, items=()):
        self.items = list(items)  # Video durations in seconds.
        self.index = self.started = None
        self.measured_time = self.measured_duration = 0
        self.fraction = 0
        self.hint = None
        self.completed = False

    def start(self, index, now):
        if self.index == index:
            return
        self.index, self.started = index, now
        self.fraction = 0
        self.hint = None
        self.completed = False

    def progress(self, now, percent, remaining=None):
        if self.index is None or self.completed:
            return
        if remaining is not None:
            elapsed = max(0, now-self.started)
            self.hint = max(0, remaining)
            total = elapsed+self.hint
            self.fraction = elapsed/total if total > 0 else 1
        elif percent is not None and 0 < percent <= 100:
            self.fraction = max(self.fraction, percent/100)

    def complete(self, now, success=True):
        if self.index is None or self.completed:
            return
        if success:
            self.measured_time += max(0, now-self.started)
            self.measured_duration += self.items[self.index-1]
        self.completed = True

    def remaining(self, now):
        if self.index is None:
            return None, None
        duration = self.items[self.index-1]
        elapsed, processed = self.measured_time, self.measured_duration
        if not self.completed and self.fraction > 0:
            elapsed += max(0, now-self.started)
            processed += duration*self.fraction
        if elapsed > 0 and processed > 0:
            rate = elapsed/processed
        elif not self.completed and self.hint is not None:
            rate = self.hint/duration
        else:
            return None, None
        future = sum(self.items[self.index:])
        if self.completed:
            return None, round(future*rate, 6)
        file_left = duration*(1-self.fraction)*rate
        return round(file_left, 6), round(file_left+future*rate, 6)
