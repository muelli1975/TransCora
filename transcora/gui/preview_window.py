"""Still-frame controls with one editable clock and a timeline."""
from fractions import Fraction
import math
import tkinter as tk
from tkinter import ttk

from transcora.gui.native import schedule_dark_titlebar
from transcora.gui.slider import Timeline
from transcora.gui.image_view import ImageView


class PreviewWindow:
    def __init__(self, parent, load_frame):
        self.load_frame = load_frame
        self.duration = 0.0
        self.localizer = parent.localizer
        self.t = self.localizer.t
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Kontrollbild · vor der Kodierung")
        self.dialog.configure(background="#181818")
        self.dialog.geometry("820x600")
        self.dialog.minsize(500, 400)
        schedule_dark_titlebar(self.dialog)
        frame = ttk.Frame(self.dialog, padding=12)
        frame.pack(fill="both", expand=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(3, weight=1)
        self.time_var = tk.StringVar(value="00:00")
        self.position_seconds = 0.0
        self.displayed_time = "00:00"
        ttk.Label(frame, text="Zeitposition").grid(row=0, column=0, sticky="w")
        self.time_entry = ttk.Entry(frame, textvariable=self.time_var, width=16)
        self.time_entry.grid(row=0, column=1, padx=8)
        self.time_entry.bind("<Return>", lambda event: self.request())
        self.scale = Timeline(frame, from_=0, to=1, command=self.position_changed, state="disabled")
        self.scale.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self.scale.bind("<ButtonRelease-1>", self.slider_released)
        self.scale.bind("<KeyRelease>", self.slider_released)
        self.position_label = ttk.Label(frame, text="Videodauer wird ermittelt …")
        self.position_label.grid(row=0, column=2, sticky="w")
        self.image_view = ImageView(frame, self.localizer)
        self.image_view.grid(row=3, column=0, columnspan=3, pady=10, sticky="nsew")
        self.image_label = self.image_view.canvas
        self.note = ttk.Label(frame, text="Gleiche Filterkette wie im Export · 8-Bit-Anzeige, ohne Videokompression",
                              wraplength=640)
        self.note.grid(row=4, column=0, columnspan=3, sticky="w")

    def controls(self):
        return [(self.time_entry, "normal"),
                (self.scale, "normal" if self.duration > 0 else "disabled")]

    @staticmethod
    def time_text(seconds):
        # One clock display; fractions retain the slider's precise position.
        whole = int(seconds)
        hours, rest = divmod(whole, 3600)
        minutes, secs = divmod(rest, 60)
        clock = f"{minutes:02d}:{secs:02d}"
        return f"{hours:02d}:" + clock if hours else clock

    @staticmethod
    def parse_time(value):
        parts = value.replace(",", ".").split(":")
        if len(parts) not in (2, 3) or any(not p for p in parts):
            raise ValueError
        if any(not p.isdigit() for p in parts[:-1]):
            raise ValueError
        seconds = float(parts[-1])
        if not math.isfinite(seconds) or not 0 <= seconds < 60:
            raise ValueError
        if len(parts) == 3 and int(parts[1]) >= 60:
            raise ValueError
        return seconds + int(parts[-2])*60 + (int(parts[0])*3600 if len(parts) == 3 else 0)

    def update_position_label(self, seconds):
        self.position_label.configure(text="/ " + (self.time_text(self.duration) if self.duration else self.t("Dauer unbekannt")))

    def position_changed(self, value):
        self.position_seconds = float(value)
        self.displayed_time = self.time_text(self.position_seconds)
        self.time_var.set(self.displayed_time)
        self.update_position_label(self.position_seconds)

    def slider_released(self, event):
        if event.type == tk.EventType.KeyRelease and event.keysym not in {
                "Left", "Right", "Up", "Down", "Home", "End", "Prior", "Next"}:
            return
        if "disabled" not in self.scale.state():
            self.request()

    def request(self):
        entered = self.time_var.get()
        try:
            seconds = self.position_seconds if entered == self.displayed_time else self.parse_time(entered)
            if not math.isfinite(seconds) or seconds < 0 or (self.duration and seconds >= self.duration):
                raise ValueError
        except ValueError:
            self.note.configure(text="Zeitstelle liegt außerhalb des Videos oder ist ungültig.")
            return
        self.note.configure(text="Gleiche Filterkette wie im Export · 8-Bit-Anzeige, ohne Videokompression")
        self.scale.set(min(seconds, float(self.scale.cget("to"))))
        # Preserve exact entry values, including values beyond the slider's last frame.
        self.time_var.set(entered)
        self.displayed_time = entered
        self.position_seconds = seconds
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
        seconds = self.position_seconds if entered == self.displayed_time else self.parse_time(entered)
        self.scale.set(min(seconds, float(self.scale.cget("to"))))
        self.time_var.set(entered)
        self.displayed_time = entered
        self.position_seconds = seconds
        self.update_position_label(seconds)
