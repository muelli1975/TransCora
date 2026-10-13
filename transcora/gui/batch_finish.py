"""Optional session-only action after a completely successful batch."""
import math
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import ttk, messagebox

from .localization import TextVar
from .native import schedule_dark_titlebar
from .theme import APP_BG


CHOICES = ('Nichts tun', 'TransCora beenden', 'Computer herunterfahren')


def shutdown_command():
    if sys.platform == 'win32':
        # The countdown belongs to TransCora. A Windows timeout above zero
        # implies forced application closing, so request zero without /f.
        return [str(os.path.join(os.environ.get('SystemRoot', r'C:\Windows'),
                                 'System32', 'shutdown.exe')), '/s', '/t', '0']
    if sys.platform == 'darwin':
        return ['/usr/bin/osascript', '-e', 'tell application "System Events" to shut down']
    if sys.platform.startswith('linux'):
        return ['systemctl', 'poweroff']
    raise OSError('Herunterfahren wird auf diesem Betriebssystem nicht unterstützt.')


def request_shutdown():
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if sys.platform == 'win32' else {}
    result = subprocess.run(shutdown_command(), capture_output=True, text=True,
                            errors='replace', timeout=15, **options)
    if result.returncode:
        raise OSError((result.stderr or result.stdout).strip() or
                      'Das Betriebssystem hat das Herunterfahren abgelehnt.')


class BatchFinish:
    def __init__(self, owner):
        self.owner = owner
        self.choice = TextVar(owner.localizer, CHOICES[0])
        self.combos = []
        self.dialog = None
        self.timer = None
        self.deadline = 0
        self.requesting = False

    def add_controls(self, parent, row):
        frame = ttk.Frame(parent)
        frame.grid(row=row, column=0, sticky='ew', pady=(6, 0))
        ttk.Label(frame, text='Nach dem Stapel').pack(side='left', padx=(0, 8))
        combo = ttk.Combobox(frame, textvariable=self.choice, state='readonly', width=26,
                             values=[self.owner.t(text) for text in CHOICES])
        combo.pack(side='left')
        combo.bind('<<ComboboxSelected>>', self.selected)
        self.combos.append(combo)
        return frame

    def selected(self, event):
        index = event.widget.current()
        self.choice.set(CHOICES[index] if 0 <= index < len(CHOICES) else CHOICES[0])

    def render(self):
        for combo in self.combos:
            combo.configure(values=[self.owner.t(text) for text in CHOICES])

    def completed(self, success):
        if not success or self.owner.closing or self.owner.busy or self.owner.images.busy:
            return False
        action = self.choice.source
        if action == CHOICES[0]:
            return False
        self.choice.set(CHOICES[0])
        if action == CHOICES[1]:
            if self.owner.save_session():
                self.owner.root.destroy()
                return True
        elif action == CHOICES[2]:
            self.countdown()
        return False

    def countdown(self):
        dialog = self.dialog = tk.Toplevel(self.owner.root, background=APP_BG)
        dialog.title(self.owner.t('Computer herunterfahren'))
        dialog.transient(self.owner.root)
        dialog.resizable(False, False)
        schedule_dark_titlebar(dialog)
        body = ttk.Frame(dialog, padding=16)
        body.pack(fill='both', expand=True)
        self.note = ttk.Label(body, wraplength=380)
        self.note.pack(anchor='w', pady=(0, 12))
        self.cancel_button = ttk.Button(body, text=self.owner.t('Abbrechen'), command=self.cancel)
        self.cancel_button.pack(anchor='e')
        dialog.protocol('WM_DELETE_WINDOW', self.cancel)
        dialog.bind('<Escape>', lambda event: self.cancel())
        dialog.grab_set()
        self.cancel_button.focus_set()
        self.deadline = time.monotonic() + 30
        self.tick()

    def tick(self):
        self.timer = None
        if self.dialog is None:
            return
        remaining = max(0, math.ceil(self.deadline - time.monotonic()))
        if remaining:
            self.note.configure(text=self.owner.t(
                'Stapel erfolgreich abgeschlossen. Computer wird in {0} Sekunden heruntergefahren.').format(remaining))
            self.timer = self.owner.root.after(250, self.tick)
        else:
            self.perform_shutdown()

    def cancel(self):
        if self.requesting:
            return
        if self.timer is not None:
            self.owner.root.after_cancel(self.timer)
            self.timer = None
        if self.dialog is not None:
            self.dialog.grab_release()
            self.dialog.destroy()
            self.dialog = None

    def perform_shutdown(self):
        if not self.owner.save_session():
            self.cancel()
            return
        self.requesting = True
        self.cancel_button.configure(state='disabled')
        self.note.configure(text=self.owner.t('Herunterfahren angefordert …'))
        def worker():
            error = None
            try:
                request_shutdown()
            except (OSError, subprocess.SubprocessError) as failure:
                error = str(failure)
            self.owner.events.put(('shutdown-result', error))
        threading.Thread(target=worker, daemon=True).start()

    def shutdown_result(self, error):
        self.requesting = False
        if error is None:
            self.owner.root.destroy()
            return True
        self.cancel()
        messagebox.showerror(self.owner.t('Computer herunterfahren'),
                             self.owner.t('Herunterfahren nicht möglich: {0}').format(error),
                             parent=self.owner.root)
        return False
