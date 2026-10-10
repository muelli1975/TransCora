"""Still-frame controls with a timeline and an exact seconds field."""
from fractions import Fraction
import math
import tkinter as tk
from tkinter import ttk

from transcora.gui.native import dark_titlebar
from transcora.gui.slider import Timeline


class PreviewWindow:
    def __init__(self, parent, load_frame):
        self.load_frame = load_frame
        self.duration = 0.0
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Kontrollbild · vor der Kodierung")
        self.dialog.configure(background="#181818")
        self.dialog.after_idle(lambda: dark_titlebar(self.dialog))
        frame = ttk.Frame(self.dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        self.time_var = tk.StringVar(value="0")
        ttk.Label(frame, text="Zeitstelle (Sekunden)").grid(row=0, column=0, sticky="w")
        self.time_entry = ttk.Entry(frame, textvariable=self.time_var, width=12)
        self.time_entry.grid(row=0, column=1, padx=8)
        self.time_entry.bind("<Return>", lambda event: self.request())
        self.scale = Timeline(frame, from_=0, to=1, command=self.position_changed, state="disabled")
        self.scale.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.scale.bind("<ButtonRelease-1>", self.slider_released)
        self.scale.bind("<KeyRelease>", self.slider_released)
        self.position_label = ttk.Label(frame, text="Videodauer wird ermittelt …")
        self.position_label.grid(row=2, column=0, columnspan=3, sticky="w", pady=(2, 8))
        self.image_label = ttk.Label(frame, text="Kontrollbild wird berechnet …", background="#000000")
        self.image_label.grid(row=3, column=0, columnspan=3, pady=10)
        self.note = ttk.Label(frame, text="Gleiche Filterkette wie im Export · 8-Bit-Anzeige, ohne Videokompression",
                              wraplength=640)
        self.note.grid(row=4, column=0, columnspan=3, sticky="w")

    def controls(self):
        return [(self.time_entry, "normal"),
                (self.scale, "normal" if self.duration > 0 else "disabled")]

    @staticmethod
    def time_text(seconds):
        hours, rest = divmod(seconds, 3600)
        minutes, seconds = divmod(rest, 60)
        return f"{int(hours):02d}:{int(minutes):02d}:{seconds:06.3f}"

    def update_position_label(self, seconds):
        total = self.time_text(self.duration) if self.duration else "Dauer unbekannt"
        self.position_label.configure(text=f"{self.time_text(seconds)} / {total}")

    def position_changed(self, value):
        seconds = float(value)
        self.time_var.set(f"{seconds:.3f}")
        self.update_position_label(seconds)

    def slider_released(self, event):
        if event.type == tk.EventType.KeyRelease and event.keysym not in {
                "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"}:
            return
        if "disabled" not in self.scale.state():
            self.request()

    def request(self):
        entered = self.time_var.get()
        try:
            seconds = float(entered.replace(",", "."))
            if not math.isfinite(seconds) or seconds < 0 or (self.duration and seconds >= self.duration):
                raise ValueError
        except ValueError:
            self.note.configure(text="Zeitstelle liegt außerhalb des Videos oder ist ungültig.")
            return
        self.note.configure(text="Gleiche Filterkette wie im Export · 8-Bit-Anzeige, ohne Videokompression")
        self.scale.set(min(seconds, float(self.scale.cget("to"))))
        # Preserve exact entry values, including values beyond the slider's last frame.
        self.time_var.set(entered)
        self.update_position_label(seconds)
        self.load_frame(seconds)

    def set_plan(self, plan):
        self.duration = plan.duration
        try:
            frame_time = 1 / float(Fraction(plan.info["video"].get("avg_frame_rate", "0/0")))
            if not math.isfinite(frame_time) or frame_time <= 0:
                raise ValueError
        except (ValueError, ZeroDivisionError):
            frame_time = .04
        # Seeking to the container's end would return no frame.
        self.scale.configure(to=max(0, self.duration - frame_time))
        entered = self.time_var.get()
        seconds = float(entered.replace(",", "."))
        self.scale.set(min(seconds, float(self.scale.cget("to"))))
        self.time_var.set(entered)
        self.update_position_label(seconds)
