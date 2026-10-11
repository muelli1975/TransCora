from __future__ import annotations

from dataclasses import asdict, replace
from pathlib import Path
import base64
import json
import os
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from transcora import __version__
from transcora.core.engine import Cancelled, execute, methods, plan_job, preview
from transcora.core.model import Job, LAYOUTS, PROFILES, TARGETS, Options, VIDEO_EXTENSIONS, app_root, FPS_CHOICES, COMPATIBILITY_NOTE
from transcora.core.naming import effective_suffix, suffix_choices, reserve_output, filename_layout, fps_suffix, default_disc_title
from transcora.core.storage import load_list, save_list, write_json, new_run_log, delete_run_logs, load_presets, save_presets, validate_preset_name
from transcora.core.toolchain import Toolchain
from transcora.gui.native import schedule_dark_titlebar
from transcora.gui.preview_window import PreviewWindow
from transcora.gui.theme import apply_theme, GOLD_LIGHT, MUTED, TEXT, PANEL_BG, APP_BG, SECONDARY_BG, BORDER


STATUS = {"queued": "Wartet", "checking": "Prüfung", "ready": "Bereit", "blocked": "Prüfen!",
          "running": "Läuft", "completed": "Fertig", "failed": "Fehler", "cancelled": "Abgebrochen"}


class Window:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.jobs: list[Job] = []
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.run_started = None
        self.estimate_weights = []
        self.estimated_finish = None
        self.estimate_updated = None
        self.closing = False
        self.updating = False
        self.controls = []
        self.log_lines = []
        self.catalog = methods()
        self.defaults = Options()
        self.input_folder = str(app_root())
        self.output_folder = str(app_root() / "output")
        self.recursive_value = False
        self._load_settings()
        self.last_output = str(Path(self.output_folder).expanduser().resolve())
        self.presets = {}
        try:
            self.presets = load_presets(app_root()/"user-presets.json")
        except (OSError, ValueError, TypeError) as error:
            self.log_lines.append("Voreinstellungen: " + str(error))
        self._style()
        self._build()
        schedule_dark_titlebar(root)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def _load_settings(self):
        try:
            data = json.loads((app_root() / "settings.json").read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") not in (1, 2):
                return
            defaults = Options.from_dict(data.get("defaults", {}))
            if defaults.method not in self.catalog:
                return
            self.defaults = replace(defaults, layout="auto", swap=False, disc_title=None)
            for key in ("input_folder", "output_folder"):
                if isinstance(data.get(key), str):
                    setattr(self, key, data[key])
            self.recursive_value = data.get("recursive") is True
        except (OSError, ValueError, TypeError):
            pass

    def _style(self):
        self.root.title(f"TransCora {__version__}")
        self.root.geometry("860x700")
        self.root.minsize(780, 680)
        self.root.option_add("*Font", ("Segoe UI", 9))
        try:
            self.root.iconbitmap(str(app_root() / "assets" / "transcora.ico"))
        except tk.TclError:
            pass
        apply_theme(self.root)

    def button(self, parent, text, command, **kwargs):
        button = ttk.Button(parent, text=text, command=command, **kwargs)
        self.controls.append((button, "normal"))
        return button

    def _build(self):
        outer = ttk.Frame(self.root, padding=12)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text="TransCora", foreground=GOLD_LIGHT, font=("Segoe UI", 15)).pack(side="left")
        ttk.Label(header, text="Lokale 3D-Video-Konvertierung", foreground=MUTED).pack(side="right")
        toolbar = ttk.Frame(outer)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for text, callback in (("Dateien hinzufügen", self.add_files), ("Ordner hinzufügen", self.add_folder),
                               ("Entfernen", self.remove), ("Liste laden", self.load), ("Liste speichern", self.save)):
            self.button(toolbar, text, callback).pack(side="left", padx=(0, 5))
        self.preset_button = ttk.Menubutton(toolbar, text="Voreinstellungen")
        self.preset_button.pack(side="right")
        self.controls.append((self.preset_button, "normal"))
        self.preset_menu = self.dark_menu(self.preset_button)
        self.preset_menu.configure(postcommand=self.refresh_preset_menu)
        self.preset_button.configure(menu=self.preset_menu)
        holder = ttk.Frame(outer)
        holder.grid(row=2, column=0, sticky="nsew")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(holder, columns=("file", "layout", "target", "status"), show="headings", height=6)
        for key, label, width in (("file", "Datei", 340), ("layout", "Quelle", 100),
                                  ("target", "Ziel", 165), ("status", "Status", 100)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=70, stretch=key == "file")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.selection_changed)
        self.selection_text = tk.StringVar(value="Einstellungen gelten für neu hinzugefügte Dateien.")
        ttk.Label(outer, textvariable=self.selection_text, foreground=MUTED).grid(row=3, column=0, sticky="w", pady=(5, 3))
        fields = ttk.Frame(outer)
        fields.grid(row=4, column=0, sticky="ew")
        for col in (0, 1, 2):
            fields.columnconfigure(col, weight=1, uniform="fields")
        self.variables = {}
        self.mappings = {"layout": LAYOUTS, "target": TARGETS, "profile": PROFILES,
                         "method": {k: m["label"] for k, m in self.catalog.items()},
                         "container": {"mkv": "MKV", "mp4": "MP4", "iso": "Blu-ray-ISO", "m2ts": "M2TS (AVC/MVC)"},
                         "codec": {"h264": "H.264", "h265": "H.265 / HEVC"},
                         "rate_mode": {"crf": "Qualität (CRF)", "abr": "Zielbitrate (Durchschnitt)"}}
        self.combos = {}
        self.option_frames = {}
        def combo(parent, row, col, key, label):
            frame = ttk.Frame(parent)
            self.option_frames[key] = frame
            frame.grid(row=row, column=col, sticky="ew", padx=(0, 8), pady=3)
            ttk.Label(frame, text=label).pack(anchor="w")
            var = tk.StringVar(value=self.mappings[key][getattr(self.defaults, key)])
            self.variables[key] = var
            widget = ttk.Combobox(frame, textvariable=var, values=list(self.mappings[key].values()), state="readonly", width=22)
            widget.pack(fill="x")
            widget.bind("<<ComboboxSelected>>", lambda event, k=key: self.option_changed(k))
            self.controls.append((widget, "readonly"))
            self.combos[key] = widget
        combo(fields, 0, 0, "layout", "Quelllayout")
        self.variables["swap"] = tk.BooleanVar(value=self.defaults.swap)
        swap = ttk.Checkbutton(fields, text="L/R tauschen", variable=self.variables["swap"], command=lambda: self.option_changed("swap"))
        swap.grid(row=0, column=1, sticky="sw", padx=(0, 8), pady=5)
        self.swap_control = swap
        self.controls.append((swap, "normal"))
        combo(fields, 0, 2, "target", "Ziel")
        combo(fields, 1, 0, "method", "Anaglyphenverfahren")
        combo(fields, 1, 1, "profile", "Anaglyph-Ausgabeprofil")
        combo(fields, 1, 2, "container", "Container")
        suffix_frame = ttk.Frame(fields)
        suffix_frame.grid(row=2, column=0, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(suffix_frame, text="Dateinamenszusatz · frei editierbar").pack(anchor="w")
        self.variables["suffix"] = tk.StringVar()
        suffix = ttk.Combobox(suffix_frame, textvariable=self.variables["suffix"], state="normal", width=22)
        suffix.pack(fill="x")
        for event in ("<<ComboboxSelected>>", "<FocusOut>", "<Return>", "<KeyRelease>"):
            suffix.bind(event, lambda e: self.option_changed("suffix"))
        self.combos["suffix"] = suffix
        self.controls.append((suffix, "normal"))
        self.title_frame = ttk.Frame(fields)
        self.title_frame.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(self.title_frame, text="Disc-Titel").pack(anchor="w")
        self.variables['disc_title'] = tk.StringVar()
        title_entry = ttk.Entry(self.title_frame, textvariable=self.variables['disc_title'])
        title_entry.pack(fill="x")
        for event in ('<FocusOut>', '<Return>'):
            title_entry.bind(event, lambda e: self.option_changed('disc_title'))
        self.controls.append((title_entry, 'normal'))
        self.fps_frame = ttk.Frame(fields)
        self.fps_frame.grid(row=2, column=1, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(self.fps_frame, text="Zielbildrate (fps) · Zahl oder Bruch").pack(anchor="w")
        self.variables["target_fps"] = tk.StringVar(value=self.defaults.target_fps)
        fps = ttk.Combobox(self.fps_frame, textvariable=self.variables["target_fps"], values=FPS_CHOICES, state="normal", width=22)
        fps.pack(fill="x")
        for event in ("<<ComboboxSelected>>", "<FocusOut>", "<Return>"):
            fps.bind(event, lambda e: self.option_changed("target_fps"))
        self.combos["target_fps"] = fps
        self.controls.append((fps, "normal"))
        folder_checks = ttk.Frame(fields)
        folder_checks.grid(row=2, column=2, sticky="sw", pady=4)
        self.recursive = tk.BooleanVar(value=self.recursive_value)
        check = ttk.Checkbutton(folder_checks, text="Unterordner mitverarbeiten", variable=self.recursive)
        check.pack(side="left", padx=(0, 10))
        self.controls.append((check, "normal"))
        self.output_name = tk.StringVar()
        ttk.Label(fields, textvariable=self.output_name, foreground=GOLD_LIGHT, wraplength=790).grid(
            row=3, column=0, columnspan=3, sticky="ew", pady=(3, 0))
        output = ttk.Frame(outer)
        output.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="Ausgabeordner").grid(row=0, column=0, padx=(0, 8))
        self.output_var = tk.StringVar(value=self.output_folder)
        entry = ttk.Entry(output, textvariable=self.output_var)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<FocusOut>", lambda event: self.invalidate_all())
        self.controls.append((entry, "normal"))
        self.button(output, "Wählen", self.choose_output).grid(row=0, column=2, padx=(8, 0))
        self.warning = tk.StringVar()
        ttk.Label(outer, textvariable=self.warning, foreground=GOLD_LIGHT, wraplength=800).grid(row=6, column=0, sticky="ew", pady=5)
        self.details = tk.StringVar(value="Dateien hinzufügen oder eine gespeicherte Liste laden.")
        detail_frame = ttk.Frame(outer)
        detail_frame.grid(row=7, column=0, sticky="ew")
        detail_frame.columnconfigure(0, weight=1)
        self.detail_text = tk.Text(detail_frame, height=4, width=1, wrap="word", background=APP_BG,
            foreground=MUTED, insertbackground=TEXT, selectbackground=GOLD_LIGHT, selectforeground=APP_BG,
            borderwidth=0, highlightthickness=0, state="disabled")
        self.detail_text.grid(row=0, column=0, sticky="ew")
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        def show_details(*args):
            self.detail_text.configure(state="normal")
            self.detail_text.delete("1.0", "end")
            self.detail_text.insert("1.0", self.details.get())
            self.detail_text.configure(state="disabled")
        self.details.trace_add("write", show_details)
        show_details()
        actions = ttk.Frame(outer)
        actions.grid(row=8, column=0, sticky="ew", pady=5)
        self.advanced_button = self.button(actions, "Erweitert ▸", self.toggle_advanced)
        self.advanced_button.pack(side="left")
        self.button(actions, "Kontrollbild", self.show_preview).pack(side="left", padx=5)
        ttk.Button(actions, text="Log", command=self.show_log).pack(side="left")
        self.advanced = ttk.Frame(outer)
        for col in (0, 1, 2):
            self.advanced.columnconfigure(col, weight=1, uniform="advanced")
        combo(self.advanced, 0, 0, "codec", "Videocodec")
        combo(self.advanced, 0, 1, "rate_mode", "Qualitätssteuerung")
        numeric = ttk.Frame(self.advanced)
        numeric.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=3)
        self.rate_fields = {}
        numeric.columnconfigure(0, weight=1)
        # Both alternatives occupy the same grid cell; switching does not grow
        # or move the advanced section, and retains both entered values.
        for key, label in (("crf", "CRF"), ("bitrate_mbps", "Bitrate (Mbit/s)")):
            rate_field = ttk.Frame(numeric)
            rate_field.grid(row=0, column=0, sticky="ew")
            self.rate_fields[key] = rate_field
            ttk.Label(rate_field, text=label).pack(anchor="w")
            var = tk.StringVar(value=str(getattr(self.defaults, key)))
            self.variables[key] = var
            number = ttk.Entry(rate_field, textvariable=var, width=8)
            number.pack(fill="x")
            number.bind("<FocusOut>", lambda event, k=key: self.option_changed(k))
            number.bind("<Return>", lambda event, k=key: self.option_changed(k))
            self.controls.append((number, "normal"))
            self.combos[key] = number
        self.button(self.advanced, "Standardeinstellungen", self.reset_defaults).grid(row=1, column=2, sticky="e", pady=5)
        self.status = tk.StringVar(value="Bereit")
        progress_info = ttk.Frame(outer)
        progress_info.grid(row=10, column=0, sticky="ew", pady=(6, 3))
        progress_info.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(progress_info, textvariable=self.status, wraplength=800)
        self.status_label.grid(row=0, column=0, sticky="w")
        self.elapsed = tk.StringVar(value="")
        self.elapsed_time = tk.StringVar(value="")
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.grid(row=11, column=0, sticky="ew")
        timing = ttk.Frame(outer)
        timing.grid(row=12, column=0, sticky="ew", pady=(3, 0))
        ttk.Label(timing, textvariable=self.elapsed_time, foreground=MUTED).pack(side='left')
        ttk.Label(timing, textvariable=self.elapsed, foreground=MUTED).pack(side='left', padx=(24, 0))
        footer = ttk.Frame(outer)
        footer.grid(row=13, column=0, sticky="ew", pady=(8, 0))
        self.speed = tk.StringVar(value="")
        ttk.Label(footer, textvariable=self.speed, foreground=MUTED).pack(side="left")
        self.abort_button = ttk.Button(footer, text="Abbrechen", command=self.abort, state="disabled", style="Danger.TButton")
        self.abort_button.pack(side="right")
        self.start_button = self.button(footer, "Start", lambda: self.check(True), style="Primary.TButton")
        self.start_button.pack(side="right", padx=5)
        self.test_button = self.button(footer, "Testen", lambda: self.check(False), style="Primary.TButton")
        self.test_button.pack(side="right")
        self.root.bind("<Control-o>", lambda event: self.add_files() if not self.busy else None)
        self.root.bind("<Delete>", lambda event: self.remove() if not self.busy and self.root.focus_get() == self.tree else None)
        self.root.bind("<Escape>", lambda event: self.abort() if self.busy else None)
        self.selection_changed()

    def dark_menu(self, parent):
        return tk.Menu(parent, tearoff=False, background=SECONDARY_BG, foreground=TEXT,
            activebackground=GOLD_LIGHT, activeforeground=APP_BG, borderwidth=1,
            relief='flat', activeborderwidth=0)

    def refresh_preset_menu(self):
        menu = self.preset_menu
        menu.delete(0, 'end')
        for child in menu.winfo_children():
            child.destroy()
        load = self.dark_menu(menu)
        delete = self.dark_menu(menu)
        for name in sorted(self.presets, key=str.casefold):
            load.add_command(label=name, command=lambda n=name: self.apply_preset(n))
            delete.add_command(label=name, command=lambda n=name: self.delete_preset(n))
        if not self.presets:
            load.add_command(label='Keine gespeicherten Voreinstellungen', state='disabled')
            delete.add_command(label='Keine gespeicherten Voreinstellungen', state='disabled')
        menu.add_cascade(label='Laden', menu=load)
        menu.add_command(label='Speichern unter …', command=self.preset_dialog)
        menu.add_cascade(label='Löschen', menu=delete)

    def store_preset(self, name):
        if self.busy:
            return
        name = validate_preset_name(name)
        selected = self.selected_jobs()
        options = selected[0].options if selected else self.defaults
        if any(replace(job.options, disc_title=None) != replace(options, disc_title=None) for job in selected):
            raise ValueError('Zum Speichern Dateien mit gleichen Einstellungen auswählen.')
        updated = dict(self.presets, **{name: replace(options, disc_title=None)})
        save_presets(app_root()/'user-presets.json', updated)
        self.presets = updated
        self.status.set('Voreinstellung gespeichert: ' + name)

    def preset_dialog(self):
        if self.busy:
            return
        dialog = tk.Toplevel(self.root, background=APP_BG)
        dialog.title('Voreinstellung speichern')
        dialog.transient(self.root)
        schedule_dark_titlebar(dialog)
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill='both', expand=True)
        ttk.Label(frame, text='Name der Voreinstellung').pack(anchor='w')
        name = tk.StringVar()
        entry = ttk.Entry(frame, textvariable=name, width=40)
        entry.pack(fill='x', pady=8)
        note = ttk.Label(frame, text='Ein vorhandener Name ersetzt die gespeicherte Voreinstellung.', wraplength=330)
        note.pack(anchor='w')
        def save(event=None):
            try:
                self.store_preset(name.get())
                dialog.destroy()
            except (OSError, ValueError) as error:
                note.configure(text=str(error))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(10, 0))
        ttk.Button(buttons, text='Abbrechen', command=dialog.destroy).pack(side='right')
        ttk.Button(buttons, text='Speichern', command=save, style='Primary.TButton').pack(side='right', padx=5)
        entry.bind('<Return>', save)
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        dialog.grab_set()
        entry.focus_set()

    def apply_preset(self, name):
        if self.busy:
            return
        options = self.presets[name]
        if options.method not in self.catalog:
            self.status.set('Anaglyphenverfahren der Voreinstellung ist nicht verfügbar.')
            return
        selected = self.selected_jobs()
        if selected:
            for job in selected:
                job.options = replace(options, disc_title=job.options.disc_title)
                job.plan = None
                job.status, job.detail = 'queued', 'Voreinstellung geladen; erneut prüfen.'
                self.update_row(job)
        else:
            self.defaults = replace(options, disc_title=None)
        self.selection_changed()
        self.status.set('Voreinstellung geladen: ' + name)

    def delete_preset(self, name):
        if self.busy:
            return
        try:
            updated = {n: o for n, o in self.presets.items() if n != name}
            save_presets(app_root()/'user-presets.json', updated)
            self.presets = updated
            self.status.set('Voreinstellung gelöscht: ' + name)
        except OSError as error:
            self.status.set('Voreinstellungen: ' + str(error))

    def selected_jobs(self):
        ids = set(self.tree.selection())
        return [job for job in self.jobs if job.id in ids]

    def reset_defaults(self):
        if self.busy:
            return
        self.defaults = Options()
        self.tree.selection_remove(*self.tree.selection())
        self.selection_changed()
        self.status.set("Standardeinstellungen für neue Dateien wiederhergestellt. Bestehende Jobs behalten ihre Einstellungen.")

    def update_row(self, job):
        layout = job.plan.layout if job.plan else job.options.layout
        values = (job.source.name, LAYOUTS.get(layout, "?"), TARGETS[job.options.target], STATUS[job.status])
        if self.tree.exists(job.id):
            self.tree.item(job.id, values=values)
        else:
            self.tree.insert("", "end", iid=job.id, values=values)

    def selection_changed(self, event=None):
        selected = self.selected_jobs()
        if not selected:
            self.selection_text.set("Einstellungen gelten für neu hinzugefügte Dateien.")
            self.updating = True
            for key, var in self.variables.items():
                value = getattr(self.defaults, key)
                if key == "disc_title":
                    value = value or ""
                if key == "suffix":
                    value = effective_suffix(self.defaults, self.catalog[self.defaults.method]["suffix"])
                    value = value or "Keiner"
                var.set(self.mappings[key][value] if key in self.mappings else value)
            self.updating = False
            self.last_suffix_display = self.variables['suffix'].get()
            self.last_title_display = self.variables['disc_title'].get()
            self.refresh_controls()
            return
        self.updating = True
        for key, var in self.variables.items():
            values = [getattr(job.options, key) for job in selected]
            if key == "disc_title":
                values = [job.options.disc_title or default_disc_title(job.source) for job in selected]
            if key == "suffix":
                values = [self.display_suffix(job) for job in selected]
            value = values[0]
            if key in self.mappings:
                var.set(self.mappings[key][value] if all(v == value for v in values) else "")
            else:
                var.set(value if all(v == value for v in values) else "")
        self.updating = False
        self.last_suffix_display = self.variables['suffix'].get()
        self.last_title_display = self.variables['disc_title'].get()
        self.selection_text.set(f"Einstellungen für {len(selected)} ausgewählte Datei(en). Leere Auswahlfelder bedeuten gemischte Werte.")
        job = selected[0]
        self.details.set((job.plan.summary if job.plan else str(job.source)) + "\n" + job.detail)
        self.refresh_controls()

    def option_changed(self, key):
        if self.busy or self.updating:
            return
        if key == "suffix" and self.variables[key].get() == self.last_suffix_display:
            return
        if key == 'disc_title' and self.variables[key].get() == self.last_title_display:
            return
        try:
            value = self.variables[key].get()
            if key == 'disc_title':
                value = value.strip() or None
            if key == "suffix":
                value = "" if value == "Keiner" else value
            if key in self.mappings:
                value = next(k for k, label in self.mappings[key].items() if label == value)
            elif key in {"crf", "bitrate_mbps"}:
                value = float(value.replace(",", "."))
            def changed(options, source=None):
                result = replace(options, **{key: value})
                if key == "target":
                    result.suffix = None
                    if value == 'bd3d':
                        result.container, result.codec = 'iso', 'h264'
                    elif options.target == 'bd3d':
                        result.container = 'mp4'
                    if value == "framerate":
                        result.swap = False
                if key == "suffix" and value == effective_suffix(replace(options, suffix=None), self.catalog[options.method]["suffix"], source):
                    result.suffix = None
                if key == "codec" and value == "h265":
                    result.container = "mkv"
                result.validate()
                return result
            candidates = self.selected_jobs()
            updates = [(job, changed(job.options, job.source)) for job in candidates]
            if key != 'disc_title':
                self.defaults = changed(self.defaults, candidates[0].source if candidates else None)
            for job, options in updates:
                job.options = options
                job.plan = None
                job.status, job.detail = "queued", "Einstellungen geändert; erneut prüfen."
                self.update_row(job)
            if key == "codec" and value == "h265":
                self.variables["container"].set("MKV")
            if key in {"target", "method", "target_fps", "layout", "disc_title", "container"}:
                self.selection_changed()
            self.last_suffix_display = self.variables['suffix'].get()
            self.status.set("Einstellungen übernommen. Vor dem Start wird erneut geprüft.")
            self.refresh_controls()
        except (ValueError, StopIteration) as error:
            self.status.set(str(error) or "Ungültige Eingabe.")
            if key in {"crf", "bitrate_mbps", "target_fps"}:
                selected = self.selected_jobs()
                options = selected[0].options if selected else self.defaults
                self.variables[key].set(str(getattr(options, key)))

    def refresh_controls(self):
        if self.busy:
            return
        selected = self.selected_jobs()
        options = selected[0].options if selected else self.defaults
        anaglyph = options.target == "anaglyph"
        framerate = options.target == "framerate"
        bd3d = options.target == 'bd3d'
        self.title_frame.grid() if bd3d and selected else self.title_frame.grid_remove()
        self.option_frames['method'].grid()
        self.option_frames['profile'].grid()
        self.combos['container'].configure(values=[self.mappings['container'][k] for k in
            (('iso', 'm2ts') if bd3d else ('mp4', 'mkv'))])
        self.advanced_button.configure(state='disabled' if bd3d else 'normal')
        if bd3d:
            self.advanced.grid_remove()
        self.swap_control.configure(state="disabled" if framerate else "normal")
        self.fps_frame.grid() if framerate else self.fps_frame.grid_remove()
        self.combos["method"].configure(state="readonly" if anaglyph else "disabled")
        self.combos["profile"].configure(state="readonly" if anaglyph else "disabled")
        self.combos["suffix"].configure(values=self.available_suffixes(options, selected[0] if selected else None))
        self.combos["container"].configure(state="disabled" if options.codec == "h265" else "readonly")
        self.combos["crf"].configure(state="normal" if options.rate_mode == "crf" else "disabled")
        self.combos["bitrate_mbps"].configure(state="normal" if options.rate_mode == "abr" else "disabled")
        active_field = "crf" if options.rate_mode == "crf" else "bitrate_mbps"
        for key, frame in self.rate_fields.items():
            frame.grid() if key == active_field else frame.grid_remove()
        text = ""
        if anaglyph:
            if options.profile == "compatible":
                text = COMPATIBILITY_NOTE
            else:
                text = "4:4:4: Nicht alle Player und Hardwaredecoder unterstützen dieses Format."
                if options.profile == "quality10":
                    text += " 10 Bit: Feinere Abstufungen; kein HDR-Modus."
        if framerate:
            text = "Layout, Auflösung und Augenreihenfolge bleiben erhalten. Video wird neu kodiert; Ton wird kopiert."
        if bd3d:
            text = "1080p · 23,976 fps · AVC/MVC · Hohe Qualität. Andere konstante Quellbildraten werden direkt angepasst."
            if options.container == 'm2ts':
                text += " M2TS enthält beide Halbbilder, jedoch keine Blu-ray-Disc-Struktur."
        if options.codec == "h265":
            text += " H.265: MKV, längere Rechenzeit und Zielplayer prüfen; CRF ist codecabhängig."
        if options.rate_mode == "abr" and not bd3d:
            text += " Zielbitrate = Videodurchschnitt, kein festes Dateigrößenlimit."
        self.warning.set(text)
        self.update_output_name()

    def display_suffix(self, job):
        options = job.options
        if job.plan and options.target == "framerate":
            options = replace(options, layout=job.plan.layout, swap=job.plan.swap)
        try:
            return effective_suffix(options, self.catalog[options.method]["suffix"], job.source) or "Keiner"
        except ValueError:
            return options.suffix or fps_suffix(options.target_fps)

    def available_suffixes(self, options, job=None):
        layout, swap = options.layout, False
        if job and options.target == "framerate":
            try:
                hint = filename_layout(job.source.stem)
                if layout == "auto" and hint:
                    layout, swap = hint
                if job.plan:
                    layout, swap = job.plan.layout, job.plan.swap
            except ValueError:
                pass
        choices = suffix_choices(options, self.catalog[options.method]["suffix"], layout, swap)
        if options.target == "framerate":
            current = self.display_suffix(job) if job else effective_suffix(options, "")
            if current and current != "Keiner" and current not in choices:
                choices.insert(0, current)
        return choices

    def update_output_name(self):
        selected = self.selected_jobs()
        if not selected:
            try:
                name = reserve_output(Path("Film.mp4"), self.output_path(), self.defaults,
                                      self.catalog[self.defaults.method]["suffix"], set()).name
                self.output_name.set("Beispiel-Ausgabename: " + name)
            except (ValueError, OSError):
                self.output_name.set("Ausgabename: Nach Auswahl einer Datei")
            return
        job = selected[0]
        try:
            reserved = set()
            for entry in self.jobs:
                if entry.plan:
                    path = entry.plan.output
                    reserved.add(str(path.resolve()).casefold())
                else:
                    options = entry.options
                    folder = self.output_path()
                    if entry.source_root:
                        folder /= entry.source.parent.relative_to(entry.source_root)
                    path = reserve_output(entry.source, folder, options, self.catalog[options.method]["suffix"], reserved)
                if entry is job:
                    self.output_name.set("Ausgabename: " + path.name)
                    break
        except (ValueError, OSError):
            self.output_name.set("Ausgabename: Quelllayout prüfen")

    def invalidate_all(self, force=False):
        if self.busy:
            return
        output = str(self.output_path())
        if output == self.last_output and not force:
            return
        self.last_output = output
        for job in self.jobs:
            if job.status != "completed":
                job.plan = None
                job.status, job.detail = "queued", "Ausgabeziel geändert; erneut prüfen."
                self.update_row(job)
        self.update_output_name()

    def add_paths(self, paths, source_root=None):
        existing = {os.path.normcase(str(job.source.resolve())) for job in self.jobs}
        added = []
        for path in paths:
            path = Path(path).resolve()
            key = os.path.normcase(str(path))
            if key in existing or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            job = Job(path, replace(self.defaults), source_root)
            self.jobs.append(job)
            existing.add(key)
            self.update_row(job)
            added.append(job.id)
        if added:
            self.tree.selection_set(added)
        self.status.set(f"{len(added)} hinzugefügt · {len(self.jobs)} Dateien insgesamt.")

    def add_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(title="Videos hinzufügen", initialdir=self.input_folder,
                 filetypes=[("Videos", " ".join("*" + e for e in sorted(VIDEO_EXTENSIONS))), ("Alle Dateien", "*.*")])
        if paths:
            self.input_folder = str(Path(paths[0]).parent)
            self.add_paths(paths)

    def add_folder(self):
        if self.busy:
            return
        value = filedialog.askdirectory(title="Videoordner hinzufügen", initialdir=self.input_folder)
        if not value:
            return
        folder = Path(value).resolve()
        output = self.output_path()
        recursive = self.recursive.get()
        self.input_folder = str(folder)
        def work():
            paths = []
            for path in folder.rglob("*") if recursive else folder.iterdir():
                if self.cancel.is_set():
                    raise Cancelled()
                if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                    resolved = path.resolve()
                    if resolved == output or output in resolved.parents:
                        continue
                    if folder not in resolved.parents:
                        continue
                    paths.append(resolved)
            self.events.put(("paths", (sorted(paths, key=lambda p: str(p).casefold()), folder)))
        self.background(work, "Ordner durchsuchen")

    def remove(self):
        if self.busy:
            return
        ids = set(self.tree.selection())
        self.jobs = [job for job in self.jobs if job.id not in ids]
        for id_ in ids:
            self.tree.delete(id_)
        self.status.set(f"{len(ids)} Listeneinträge entfernt; Quelldateien bleiben erhalten.")

    def load(self):
        if self.busy:
            return
        value = filedialog.askopenfilename(title="Jobliste laden", initialdir=self.input_folder, filetypes=[("TransCora-Jobliste", "*.json")])
        if not value:
            return
        try:
            jobs, output = load_list(Path(value))
            if any(job.options.method not in self.catalog for job in jobs):
                raise ValueError("Unbekanntes Anaglyphenverfahren in der Jobliste.")
            # Append lists; never erase the current list as a side effect of loading.
            existing = {os.path.normcase(str(job.source)) for job in self.jobs}
            for job in jobs:
                if os.path.normcase(str(job.source)) not in existing:
                    self.jobs.append(job)
                    existing.add(os.path.normcase(str(job.source)))
                    self.update_row(job)
            if output:
                self.output_var.set(str(output))
                self.invalidate_all()
            self.status.set("Jobliste ergänzt. Alle Quellen werden vor dem Start neu geprüft.")
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror("Jobliste", str(error), parent=self.root)

    def save(self):
        if self.busy:
            return
        value = filedialog.asksaveasfilename(title="Jobliste speichern", initialdir=self.input_folder, defaultextension=".json",
                                            filetypes=[("TransCora-Jobliste", "*.json")])
        if value:
            try:
                save_list(Path(value), self.jobs, self.output_path())
                self.status.set("Jobliste gespeichert; enthalten sind Pfade und Einstellungen, keine Videos.")
            except OSError as error:
                messagebox.showerror("Speichern", str(error), parent=self.root)

    def choose_output(self):
        value = filedialog.askdirectory(title="Ausgabeordner wählen", initialdir=self.output_var.get())
        if value:
            self.output_var.set(value)
            self.invalidate_all()

    def output_path(self):
        return Path(self.output_var.get().strip()).expanduser().resolve() if self.output_var.get().strip() else app_root() / "output"

    def toggle_advanced(self):
        if self.advanced.winfo_ismapped():
            self.advanced.grid_remove()
        else:
            self.advanced.grid(row=9, column=0, sticky="ew", pady=5)

    def set_busy(self, value):
        self.busy = value
        for widget, normal in self.controls:
            widget.configure(state="disabled" if value else normal)
        self.abort_button.configure(state="normal" if value else "disabled")
        if not value:
            self.update_elapsed()
            self.elapsed.set('Restzeit: —')
            self.run_started = None
            self.estimated_finish = None
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.refresh_controls()

    def update_elapsed(self):
        if self.run_started is None:
            return
        now = time.monotonic()
        self.elapsed_time.set('Vergangene Zeit: ' + PreviewWindow.time_text(max(0, now-self.run_started)))
        if self.estimated_finish is None or now-(self.estimate_updated or now) > 15:
            self.elapsed.set('Restzeit: Wird ermittelt …')
        else:
            remaining = max(1, self.estimated_finish-now)
            self.elapsed.set('Restzeit: ca. ' + PreviewWindow.time_text(remaining))

    def estimate_remaining(self, index, count, percent):
        if self.run_started is None or percent is None:
            return
        weights = self.estimate_weights if len(self.estimate_weights) == count else [1]*count
        fraction = (sum(weights[:index-1])+weights[index-1]*percent/100)/sum(weights)
        now = time.monotonic()
        elapsed = now-self.run_started
        if .01 <= fraction < 1 and elapsed >= 2:
            predicted = now+elapsed*(1-fraction)/fraction
            self.estimated_finish = predicted if self.estimated_finish is None else .25*predicted+.75*self.estimated_finish
            self.estimate_updated = now
        self.update_elapsed()

    def background(self, work, phase, track_time=False):
        if self.busy:
            return
        self.cancel.clear()
        if track_time:
            self.run_started = time.monotonic()
            self.estimated_finish = None
            self.estimate_updated = None
            self.estimate_weights = []
            self.update_elapsed()
        self.speed.set("")
        self.set_busy(True)
        self.status.set(phase)
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        def worker():
            try:
                work()
            except Cancelled:
                self.events.put(("notice", "Abgebrochen."))
            except Exception as error:
                self.events.put(("error", str(error)))
            finally:
                self.events.put(("done", None))
        threading.Thread(target=worker, daemon=True).start()

    def check(self, run):
        if self.busy:
            return
        self.option_changed("disc_title")
        if self.variables["disc_title"].get() != self.last_title_display:
            return
        self.option_changed("suffix")
        if self.variables['suffix'].get() != self.last_suffix_display:
            return
        candidates = [job for job in self.jobs if job.status != "completed"]
        if not candidates:
            self.status.set("Keine noch offenen Dateien in der Liste.")
            return
        output = self.output_path()
        log_path = None
        def work():
            nonlocal log_path
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=output):
                pass
            tools = Toolchain.find()
            capabilities = tools.inspect()
            self.events.put(("log", capabilities["version"]))
            reserved, ready = set(), []
            blocked = 0
            for index, job in enumerate(candidates, 1):
                if self.cancel.is_set():
                    raise Cancelled()
                self.events.put(("job", (job.id, "checking", "Technische Prüfung", None)))
                self.events.put(("notice", f"Testen: Datei {index} von {len(candidates)} · {job.source.name}"))
                try:
                    plan = plan_job(tools, job, output, reserved, self.cancel, capabilities)
                    ready.append((job, plan))
                    self.events.put(("job", (job.id, "ready", "\n".join(plan.warnings), plan)))
                    self.events.put(("log", plan.summary + "\n" + "\n".join(plan.warnings)))
                except Cancelled:
                    self.events.put(("job", (job.id, "cancelled", "Prüfung abgebrochen", None)))
                    raise
                except (ValueError, OSError) as error:
                    blocked += 1
                    self.events.put(("job", (job.id, "blocked", str(error), None)))
                    self.events.put(("log", job.source.name + ": " + str(error)))
            if not run:
                self.events.put(("notice", f"Test abgeschlossen: {len(ready)} bereit · {blocked} blockiert."))
                return
            self.events.put(("batch", [max(1, plan.duration) for _, plan in ready]))
            if ready:
                log_path = new_run_log(app_root())
            counts = {"completed": 0, "failed": 0, "cancelled": 0}
            for index, (job, plan) in enumerate(ready, 1):
                if self.cancel.is_set():
                    for remaining, _ in ready[index - 1:]:
                        self.events.put(("job", (remaining.id, "cancelled", "Nicht mehr gestartet", None)))
                        counts["cancelled"] += 1
                    break
                self.events.put(("job", (job.id, "running", "Verarbeitung", plan)))
                self.events.put(("notice", f"Datei {index} von {len(ready)} · {job.source.name}"))
                def emit(kind, payload):
                    self.events.put((kind, (job.id, index, len(ready), payload)))
                try:
                    execute(tools, plan, self.cancel, emit, log_path)
                    counts["completed"] += 1
                    self.events.put(("job", (job.id, "completed", "Ausgabe geprüft · " + plan.stereo_summary + "\nGespeichert: " + str(plan.output), plan)))
                except Cancelled:
                    counts["cancelled"] += 1
                    self.events.put(("job", (job.id, "cancelled", "Begonnene Ausgabe verworfen", plan)))
                except Exception as error:
                    counts["failed"] += 1
                    with log_path.open("a", encoding="utf-8") as log:
                        log.write(f"\nFehler: {job.source}\n{error}\n")
                    self.events.put(("job", (job.id, "failed", str(error), plan)))
                    self.events.put(("log", job.source.name + ": " + str(error)))
            summary = (f"{counts['completed']} erfolgreich · {counts['failed']} Fehler · {blocked} blockiert · "
                       f"{counts['cancelled']} abgebrochen. Log: {log_path or 'Kein Lauf gestartet'}")
            self.events.put(("notice", summary))
            self.events.put(("log", summary))
            if ready and not self.cancel.is_set():
                self.events.put(("sound", None))
        self.background(work, "Testen", track_time=run)

    def show_preview(self):
        selected = self.selected_jobs()
        if self.busy or len(selected) != 1:
            self.status.set("Für das Kontrollbild genau eine Datei auswählen.")
            return
        job = selected[0]
        def request(seconds):
            if self.busy:
                return
            output = self.output_path()
            def work():
                tools = Toolchain.find()
                plan = plan_job(tools, job, output, set(), self.cancel, tools.inspect())
                png = preview(tools, plan, self.cancel, seconds)
                self.events.put(("preview", (viewer, png, plan)))
                self.events.put(("notice", "Kontrollbild bereit."))
            self.background(work, "Kontrollbild berechnen")
        viewer = PreviewWindow(self.root, request)
        self.controls.extend(viewer.controls())
        viewer.dialog.protocol("WM_DELETE_WINDOW", lambda: self.close_preview(
            viewer.dialog, viewer.time_entry, viewer.scale))
        viewer.dialog.after(50, viewer.request)

    def close_preview(self, dialog, *widgets):
        self.controls = [(widget, state) for widget, state in self.controls if widget not in widgets]
        dialog.destroy()

    def show_log(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("TransCora · Log")
        dialog.configure(background=APP_BG)
        schedule_dark_titlebar(dialog)
        holder = ttk.Frame(dialog, padding=8)
        holder.pack(fill='both', expand=True)
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        text = tk.Text(holder, background=PANEL_BG, foreground=TEXT, wrap="word", width=90, height=25,
            borderwidth=0, highlightthickness=0, insertbackground=TEXT,
            selectbackground=GOLD_LIGHT, selectforeground=APP_BG)
        text.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(holder, orient='vertical', command=text.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        text.configure(yscrollcommand=scroll.set)
        text.insert("1.0", "\n\n".join(self.log_lines[-150:]) or "Noch keine technischen Meldungen.")
        text.configure(state="disabled")
        button = self.button(dialog, 'Logs löschen', lambda: self.clear_logs(text))
        button.pack(anchor='e', padx=8, pady=8)
        button.configure(state='disabled' if self.busy else 'normal')
        def forget(event):
            if event.widget == dialog:
                self.controls = [(w, state) for w, state in self.controls if w is not button]
        dialog.bind('<Destroy>', forget)

    def clear_logs(self, text=None):
        if self.busy:
            return
        try:
            count = delete_run_logs(app_root())
            self.log_lines.clear()
            self.status.set(f'{count} Laufprotokolle gelöscht.')
            if text is not None:
                text.configure(state='normal')
                text.delete('1.0', 'end')
                text.insert('1.0', 'Keine technischen Meldungen.')
                text.configure(state='disabled')
        except OSError as error:
            self.status.set(f'Logs löschen: {error}')

    def abort(self):
        if self.busy:
            self.cancel.set()
            self.abort_button.configure(state="disabled")
            self.status.set("Abbruch angefordert; laufenden Prozess beenden …")

    def poll(self):
        self.update_elapsed()
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "job":
                    id_, status, detail, plan = payload
                    job = next((job for job in self.jobs if job.id == id_), None)
                    if job:
                        job.status, job.detail, job.plan = status, detail, plan
                        self.update_row(job)
                        if id_ in self.tree.selection():
                            self.details.set((plan.summary + "\n" if plan else str(job.source) + "\n") + detail)
                elif kind in {"notice", "error"}:
                    self.status.set(payload)
                    if kind == "error":
                        self.log_lines.append(payload)
                elif kind == "log":
                    self.log_lines.append(payload)
                    self.log_lines = self.log_lines[-300:]
                elif kind == "paths":
                    self.add_paths(*payload)
                elif kind == "batch":
                    self.estimate_weights = payload
                elif kind == "progress":
                    _, index, count, value = payload
                    if value["percent"] is not None:
                        self.estimate_remaining(index, count, value["percent"])
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                        self.progress["value"] = ((index - 1) + value["percent"] / 100) / count * 100
                elif kind == "speed":
                    value = payload[3]
                    parts = []
                    if value["speed"] != "N/A":
                        parts.append("Geschwindigkeit " + value["speed"].replace("x", "×").replace(".", ","))
                    if value["fps"] not in (None, "N/A"):
                        parts.append(value["fps"].replace(".", ",") + " fps")
                    self.speed.set(" · ".join(parts))
                elif kind == "phase":
                    self.speed.set(payload[3])
                    self.progress.stop()
                    self.progress.configure(mode='indeterminate')
                    self.progress.start(15)
                    self.estimated_finish = None
                    self.update_elapsed()
                elif kind == "preview":
                    viewer, png, plan = payload
                    if viewer.dialog.winfo_exists():
                        viewer.set_plan(plan)
                        widgets = {viewer.time_entry, viewer.scale}
                        self.controls = [(widget, state) for widget, state in self.controls if widget not in widgets]
                        self.controls.extend(viewer.controls())
                        image = tk.PhotoImage(data=base64.b64encode(png))
                        viewer.image_label.configure(image=image, text="")
                        viewer.image_label.image = image
                elif kind == "sound":
                    if os.name == "nt":
                        import winsound
                        winsound.PlaySound(str(app_root() / "assets" / "ready.wav"), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)
                elif kind == "done":
                    self.set_busy(False)
                    if self.closing:
                        self.finish_close()
                        return
        except queue.Empty:
            pass
        self.root.after(100, self.poll)

    def close(self):
        if self.busy:
            if messagebox.askyesno("TransCora", "Laufende Arbeit abbrechen und TransCora schließen?", parent=self.root):
                self.closing = True
                self.abort()
        else:
            self.finish_close()

    def finish_close(self):
        try:
            write_json(app_root() / "settings.json", {"schema_version": 2,
                       "defaults": asdict(replace(self.defaults, layout="auto", swap=False, disc_title=None)),
                       "output_folder": str(self.output_path()), "input_folder": self.input_folder,
                       "recursive": self.recursive.get()})
        except OSError:
            # Read-only application folders must not prevent exit or conversion to a writable destination.
            messagebox.showwarning("Einstellungen", "Der Programmordner ist schreibgeschützt; Einstellungen konnten nicht gespeichert werden.", parent=self.root)
        self.root.destroy()
