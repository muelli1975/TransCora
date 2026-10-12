"""Heading sorting preserves selected jobs and uses numeric video metadata."""
from fractions import Fraction
import math
import re


class FileListSorter:
    def __init__(self, panel, labels):
        self.panel = panel
        self.tree = panel.tree
        self.labels = labels
        self.column = None
        self.descending = False
        owner = getattr(panel,'owner',panel)
        self.localizer = owner.localizer
        for column in labels:
            self.tree.heading(column,command=lambda key=column:self.sort(key))

    def busy(self):
        owner = getattr(self.panel,'owner',self.panel)
        return self.panel.busy or owner.busy or getattr(getattr(owner,'images',None),'busy',False)

    def key(self, job):
        if self.column == 'fps':
            try:
                return Fraction(job.source_fps)
            except (ValueError,TypeError,ZeroDivisionError):
                return None
        if self.column == 'duration':
            value = job.source_duration
            return value if value is not None and math.isfinite(value) else None
        value = self.tree.set(job.id,self.column)
        return tuple(int(part) if index%2 else part.casefold() for index,part in enumerate(re.split(r'(\d+)',value)))

    def sort(self, column):
        if self.busy():
            return
        self.descending = not self.descending if self.column == column else False
        self.column = column
        self.refresh()

    def refresh(self):
        if self.column is None or self.busy():
            return
        known, missing = [], []
        for job in self.panel.jobs:
            key = self.key(job)
            (missing if key is None else known).append((job,key))
        known.sort(key=lambda item:item[1],reverse=self.descending)
        self.panel.jobs[:] = [job for job,_ in known+missing]
        for index,job in enumerate(self.panel.jobs):
            self.tree.move(job.id,'',index)
        for column,label in self.labels.items():
            suffix = (' ▼' if self.descending else ' ▲') if column == self.column else ''
            self.localizer.heading(self.tree,column,label+suffix)
