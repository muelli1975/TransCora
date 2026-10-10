from __future__ import annotations

from dataclasses import asdict, replace
from datetime import datetime
from pathlib import Path
import base64
import json
import os
import queue
import tempfile
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from transcora import __version__
from transcora.core.engine import Cancelled, execute, methods, plan_job, preview
from transcora.core.model import Job, LAYOUTS, NAMING, PROFILES, TARGETS, Options, VIDEO_EXTENSIONS, app_root
from transcora.core.storage import load_list, save_list, write_json
from transcora.core.toolchain import Toolchain


STATUS = {"queued": "Wartet", "checking": "Prüfung", "ready": "Bereit", "blocked": "Prüfen!",
          "running": "Läuft", "completed": "Fertig", "failed": "Fehler", "cancelled": "Abgebrochen"}


class Window:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.jobs: list[Job] = []
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.closing = False
        self.updating = False
        self.controls = []
        self.log_lines = []
        self.catalog = methods()
        self.defaults = Options()
        self.custom_tools = ""
        self.input_folder = str(app_root())
        self.output_folder = str(app_root() / "output")
        self.recursive_value = False
        self.mirror_value = False
        self._load_settings()
        self.last_output = str(Path(self.output_folder).expanduser().resolve())
        self._style()
        self._build()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def _load_settings(self):
        try:
            data = json.loads((app_root() / "settings.json").read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") != 1:
                return
            defaults = Options.from_dict(data.get("defaults", {}))
            if defaults.method not in self.catalog:
                return
            self.defaults = defaults
            for key in ("input_folder", "output_folder", "custom_tools"):
                if isinstance(data.get(key), str):
                    setattr(self, key, data[key])
            self.recursive_value = data.get("recursive") is True
            self.mirror_value = data.get("mirror") is True
        except (OSError, ValueError, TypeError):
            pass

    def _style(self):
        self.root.title(f"TransCora {__version__}")
        self.root.geometry("860x650")
        self.root.minsize(780, 570)
        self.root.configure(background="#181818")
        self.root.option_add("*Font", ("Segoe UI", 9))
        try:
            self.root.iconbitmap(str(app_root() / "assets" / "transcora.ico"))
        except tk.TclError:
            pass
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", background="#181818", foreground="#e0e0e0", bordercolor="#333333")
        style.configure("TButton", background="#282828", foreground="#e0e0e0", padding=(9, 5))
        style.map("TButton", background=[("active", "#383838"), ("disabled", "#202020")],
                  foreground=[("disabled", "#777777")])
        style.configure("Primary.TButton", background="#9c7c38", foreground="#111111")
        style.map("Primary.TButton", background=[("active", "#c6a95e"), ("disabled", "#383020")],
                  foreground=[("disabled", "#777777")])
        style.configure("TCombobox", fieldbackground="#282828", background="#282828", arrowcolor="#c6a95e")
        style.map("TCombobox", fieldbackground=[("readonly", "#282828"), ("disabled", "#202020")],
                  foreground=[("readonly", "#e0e0e0"), ("disabled", "#777777")],
                  selectbackground=[("readonly", "#282828")], selectforeground=[("readonly", "#e0e0e0")])
        style.configure("TEntry", fieldbackground="#282828", foreground="#e0e0e0", insertcolor="#e0e0e0")
        style.configure("Treeview", background="#202020", fieldbackground="#202020", foreground="#e0e0e0", rowheight=25)
        style.map("Treeview", background=[("selected", "#4d4028")], foreground=[("selected", "#ffffff")])
        style.configure("Treeview.Heading", background="#282828", foreground="#c6a95e")
        style.configure("Horizontal.TProgressbar", background="#9c7c38", troughcolor="#333333")
        self.root.option_add("*TCombobox*Listbox.background", "#282828")
        self.root.option_add("*TCombobox*Listbox.foreground", "#e0e0e0")
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#4d4028")

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
        ttk.Label(header, text="TransCora", foreground="#c6a95e", font=("Segoe UI", 15)).pack(side="left")
        ttk.Label(header, text="Lokale 3D-Video-Konvertierung", foreground="#a8a8a8").pack(side="right")
        toolbar = ttk.Frame(outer)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 8))
        for text, callback in (("Dateien hinzufügen", self.add_files), ("Ordner hinzufügen", self.add_folder),
                               ("Entfernen", self.remove), ("Liste laden", self.load), ("Liste speichern", self.save)):
            self.button(toolbar, text, callback).pack(side="left", padx=(0, 5))
        holder = ttk.Frame(outer)
        holder.grid(row=2, column=0, sticky="nsew")
        holder.columnconfigure(0, weight=1)
        holder.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(holder, columns=("file", "layout", "target", "status"), show="headings", height=6)
        for key, label, width in (("file", "Datei", 340), ("layout", "Quelle", 100),
                                  ("target", "Ziel", 140), ("status", "Status", 100)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=70, stretch=key == "file")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.selection_changed)
        self.selection_text = tk.StringVar(value="Einstellungen gelten für neu hinzugefügte Dateien.")
        ttk.Label(outer, textvariable=self.selection_text, foreground="#a8a8a8").grid(row=3, column=0, sticky="w", pady=(5, 3))
        fields = ttk.Frame(outer)
        fields.grid(row=4, column=0, sticky="ew")
        for col in (0, 1, 2):
            fields.columnconfigure(col, weight=1, uniform="fields")
        self.variables = {}
        self.mappings = {"layout": LAYOUTS, "target": TARGETS, "profile": PROFILES, "naming": NAMING,
                         "method": {k: m["label"] for k, m in self.catalog.items()},
                         "container": {"mkv": "MKV", "mp4": "MP4"},
                         "codec": {"h264": "H.264", "h265": "H.265 / HEVC"},
                         "rate_mode": {"crf": "Qualität (CRF)", "abr": "Zielbitrate (Durchschnitt)"}}
        self.combos = {}
        def combo(parent, row, col, key, label):
            frame = ttk.Frame(parent)
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
        self.controls.append((swap, "normal"))
        combo(fields, 0, 2, "target", "Ziel")
        combo(fields, 1, 0, "method", "Anaglyphverfahren")
        combo(fields, 1, 1, "profile", "Anaglyph-Ausgabeprofil")
        combo(fields, 1, 2, "container", "Container")
        combo(fields, 2, 0, "naming", "Dateinamen · SBS/OU/Mono")
        folder_checks = ttk.Frame(fields)
        folder_checks.grid(row=2, column=1, columnspan=2, sticky="sw", pady=4)
        self.recursive = tk.BooleanVar(value=self.recursive_value)
        self.mirror = tk.BooleanVar(value=self.mirror_value)
        for label, var in (("Unterordner", self.recursive), ("Struktur spiegeln", self.mirror)):
            check = ttk.Checkbutton(folder_checks, text=label, variable=var)
            check.pack(side="left", padx=(0, 10))
            self.controls.append((check, "normal"))
        ttk.Label(folder_checks, text="beim Ordnerimport", foreground="#a8a8a8").pack(side="left")
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
        ttk.Label(outer, textvariable=self.warning, foreground="#d8c392", wraplength=800).grid(row=6, column=0, sticky="ew", pady=5)
        self.details = tk.StringVar(value="Dateien hinzufügen oder eine gespeicherte Liste laden.")
        ttk.Label(outer, textvariable=self.details, foreground="#a8a8a8", wraplength=800).grid(row=7, column=0, sticky="ew")
        actions = ttk.Frame(outer)
        actions.grid(row=8, column=0, sticky="ew", pady=5)
        self.button(actions, "Erweitert ▸", self.toggle_advanced).pack(side="left")
        self.button(actions, "Kontrollbild", self.show_preview).pack(side="left", padx=5)
        ttk.Button(actions, text="Log", command=self.show_log).pack(side="left")
        self.advanced = ttk.Frame(outer)
        for col in (0, 1, 2):
            self.advanced.columnconfigure(col, weight=1, uniform="advanced")
        combo(self.advanced, 0, 0, "codec", "Videocodec")
        combo(self.advanced, 0, 1, "rate_mode", "Qualitätssteuerung")
        numeric = ttk.Frame(self.advanced)
        numeric.grid(row=0, column=2, sticky="ew", padx=(0, 8), pady=3)
        for col, key, label in ((0, "crf", "CRF"), (1, "bitrate_mbps", "Mbit/s")):
            ttk.Label(numeric, text=label).grid(row=0, column=col, sticky="w")
            var = tk.StringVar(value=str(getattr(self.defaults, key)))
            self.variables[key] = var
            number = ttk.Entry(numeric, textvariable=var, width=8)
            number.grid(row=1, column=col, sticky="ew", padx=(0, 5))
            number.bind("<FocusOut>", lambda event, k=key: self.option_changed(k))
            number.bind("<Return>", lambda event, k=key: self.option_changed(k))
            self.controls.append((number, "normal"))
            self.combos[key] = number
            numeric.columnconfigure(col, weight=1)
        self.variables["assume_bt709"] = tk.BooleanVar(value=self.defaults.assume_bt709)
        assume = ttk.Checkbutton(self.advanced, text="Fehlende Farben: BT.709 SDR annehmen", variable=self.variables["assume_bt709"],
                                command=lambda: self.option_changed("assume_bt709"))
        assume.grid(row=1, column=0, columnspan=2, sticky="w", pady=5)
        self.controls.append((assume, "normal"))
        self.button(self.advanced, "FFmpeg-Ordner", self.choose_tools).grid(row=1, column=2, sticky="e")
        self.status = tk.StringVar(value="Bereit")
        self.status_label = ttk.Label(outer, textvariable=self.status, wraplength=800)
        self.status_label.grid(row=10, column=0, sticky="ew", pady=(6, 3))
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.grid(row=11, column=0, sticky="ew")
        footer = ttk.Frame(outer)
        footer.grid(row=12, column=0, sticky="ew", pady=(8, 0))
        self.speed = tk.StringVar(value="Timing erhalten · Audio kopieren")
        ttk.Label(footer, textvariable=self.speed, foreground="#a8a8a8").pack(side="left")
        self.abort_button = ttk.Button(footer, text="Abbrechen", command=self.abort, state="disabled")
        self.abort_button.pack(side="right")
        self.start_button = self.button(footer, "Starten", lambda: self.check(True), style="Primary.TButton")
        self.start_button.pack(side="right", padx=5)
        self.button(footer, "Prüfen", lambda: self.check(False)).pack(side="right")
        self.root.bind("<Control-o>", lambda event: self.add_files() if not self.busy else None)
        self.root.bind("<Delete>", lambda event: self.remove() if not self.busy and self.root.focus_get() == self.tree else None)
        self.root.bind("<Escape>", lambda event: self.abort() if self.busy else None)
        self.refresh_controls()

    def selected_jobs(self):
        ids = set(self.tree.selection())
        return [job for job in self.jobs if job.id in ids]

    def update_row(self, job):
        values = (job.source.name, LAYOUTS.get(job.options.layout, "?"), TARGETS[job.options.target], STATUS[job.status])
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
                var.set(self.mappings[key][value] if key in self.mappings else value)
            self.updating = False
            self.refresh_controls()
            return
        self.updating = True
        for key, var in self.variables.items():
            values = [getattr(job.options, key) for job in selected]
            value = values[0]
            if key in self.mappings:
                var.set(self.mappings[key][value] if all(v == value for v in values) else "")
            else:
                var.set(value)
        self.updating = False
        self.selection_text.set(f"Einstellungen für {len(selected)} ausgewählte Datei(en). Leere Auswahlfelder bedeuten gemischte Werte.")
        job = selected[0]
        self.details.set(job.plan.summary if job.plan else str(job.source) + "\n" + job.detail)
        self.refresh_controls()

    def option_changed(self, key):
        if self.busy or self.updating:
            return
        try:
            value = self.variables[key].get()
            if key in self.mappings:
                value = next(k for k, label in self.mappings[key].items() if label == value)
            elif key in {"crf", "bitrate_mbps"}:
                value = float(value.replace(",", "."))
            def changed(options):
                result = replace(options, **{key: value})
                if key == "codec" and value == "h265":
                    result.container = "mkv"
                result.validate()
                return result
            candidates = self.selected_jobs()
            updates = [(job, changed(job.options)) for job in candidates]
            self.defaults = changed(self.defaults)
            for job, options in updates:
                job.options = options
                job.plan = None
                job.status, job.detail = "queued", "Einstellungen geändert; erneut prüfen."
                self.update_row(job)
            if key == "codec" and value == "h265":
                self.variables["container"].set("MKV")
            self.status.set("Einstellungen übernommen. Vor dem Start wird erneut geprüft.")
            self.refresh_controls()
        except (ValueError, StopIteration) as error:
            self.status.set(str(error) or "Ungültige Eingabe.")
            if key in {"crf", "bitrate_mbps"}:
                selected = self.selected_jobs()
                options = selected[0].options if selected else self.defaults
                self.variables[key].set(str(getattr(options, key)))

    def refresh_controls(self):
        if self.busy:
            return
        selected = self.selected_jobs()
        options = selected[0].options if selected else self.defaults
        anaglyph = options.target == "anaglyph"
        self.combos["method"].configure(state="readonly" if anaglyph else "disabled")
        self.combos["profile"].configure(state="readonly" if anaglyph else "disabled")
        self.combos["naming"].configure(state="disabled" if anaglyph else "readonly")
        self.combos["container"].configure(state="disabled" if options.codec == "h265" else "readonly")
        self.combos["crf"].configure(state="normal" if options.rate_mode == "crf" else "disabled")
        self.combos["bitrate_mbps"].configure(state="normal" if options.rate_mode == "abr" else "disabled")
        text = ""
        if anaglyph:
            if options.profile == "compatible":
                text = "4:2:0: geringere Farbauflösung. Die Anaglyphenqualität kann darunter leiden."
            else:
                text = "4:4:4: Nicht alle Player und Hardwaredecoder unterstützen dieses Format."
                if options.profile == "quality10":
                    text += " 10 Bit: feinere Abstufungen; kein HDR-Modus."
            text += " Dateizusatz wie AnaglyphBatch: _" + self.catalog[options.method]["suffix"]
        if options.codec == "h265":
            text += " H.265: MKV, längere Rechenzeit und Zielplayer prüfen; CRF ist codecabhängig."
        if options.rate_mode == "abr":
            text += " Zielbitrate = Videodurchschnitt, kein festes Dateigrößenlimit."
        self.warning.set(text)

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
        recursive, mirror = self.recursive.get(), self.mirror.get()
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
                    if mirror and folder not in resolved.parents:
                        continue
                    paths.append(resolved)
            self.events.put(("paths", (sorted(paths, key=lambda p: str(p).casefold()), folder if mirror else None)))
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
                raise ValueError("Unbekanntes Anaglyphverfahren in der Jobliste.")
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

    def choose_tools(self):
        value = filedialog.askdirectory(title="Ordner mit ffmpeg und ffprobe", initialdir=self.custom_tools or str(app_root() / "tools"))
        if value:
            self.custom_tools = value
            self.invalidate_all(force=True)
            self.status.set("FFmpeg-Ordner gespeichert; wird beim nächsten Prüfen validiert.")

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
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.refresh_controls()

    def background(self, work, phase):
        if self.busy:
            return
        self.cancel.clear()
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
        candidates = [job for job in self.jobs if job.status != "completed"]
        if not candidates:
            self.status.set("Keine noch offenen Dateien in der Liste.")
            return
        output = self.output_path()
        custom = self.custom_tools
        log_path = output / "logs" / (datetime.now().strftime("%Y%m%d-%H%M%S") + ".log")
        def work():
            output.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryFile(dir=output):
                pass
            tools = Toolchain.find(custom)
            capabilities = tools.inspect()
            self.events.put(("log", capabilities["version"]))
            reserved, ready = set(), []
            blocked = 0
            for index, job in enumerate(candidates, 1):
                if self.cancel.is_set():
                    raise Cancelled()
                self.events.put(("job", (job.id, "checking", "Technische Prüfung", None)))
                self.events.put(("notice", f"Prüfen: Datei {index} von {len(candidates)} · {job.source.name}"))
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
                self.events.put(("notice", f"Vorprüfung: {len(ready)} bereit · {blocked} blockiert."))
                return
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
                    self.events.put(("job", (job.id, "completed", "Gespeichert: " + str(plan.output), plan)))
                except Cancelled:
                    counts["cancelled"] += 1
                    self.events.put(("job", (job.id, "cancelled", "Begonnene Ausgabe verworfen", plan)))
                except Exception as error:
                    counts["failed"] += 1
                    self.events.put(("job", (job.id, "failed", str(error), plan)))
                    self.events.put(("log", job.source.name + ": " + str(error)))
            summary = (f"{counts['completed']} erfolgreich · {counts['failed']} Fehler · {blocked} blockiert · "
                       f"{counts['cancelled']} abgebrochen. Log: {log_path}")
            self.events.put(("notice", summary))
            self.events.put(("log", summary))
            if ready and not self.cancel.is_set():
                self.events.put(("sound", None))
        self.background(work, "Vorabprüfung")

    def show_preview(self):
        selected = self.selected_jobs()
        if self.busy or len(selected) != 1:
            self.status.set("Für das Kontrollbild genau eine Datei auswählen.")
            return
        job = selected[0]
        dialog = tk.Toplevel(self.root)
        dialog.title("Kontrollbild · vor Encoding")
        dialog.configure(background="#181818")
        frame = ttk.Frame(dialog, padding=12)
        frame.pack(fill="both", expand=True)
        time_var = tk.StringVar(value="0")
        ttk.Label(frame, text="Zeitstelle (Sekunden)").grid(row=0, column=0, sticky="w")
        time_entry = ttk.Entry(frame, textvariable=time_var, width=10)
        time_entry.grid(row=0, column=1, padx=8)
        image_label = ttk.Label(frame, text="Kontrollbild laden")
        image_label.grid(row=1, column=0, columnspan=3, pady=10)
        note = ttk.Label(frame, text="Gleiche Filterkette wie im Export · 8-Bit-Anzeige, ohne Videokompression", wraplength=640)
        note.grid(row=2, column=0, columnspan=3, sticky="w")
        button = ttk.Button(frame, text="Laden")
        button.grid(row=0, column=2)
        self.controls.extend([(button, "normal"), (time_entry, "normal")])
        def request():
            if self.busy:
                return
            try:
                seconds = float(time_var.get().replace(",", "."))
            except ValueError:
                note.configure(text="Ungültige Zeitstelle.")
                return
            custom, output = self.custom_tools, self.output_path()
            def work():
                tools = Toolchain.find(custom)
                plan = plan_job(tools, job, output, set(), self.cancel, tools.inspect())
                png = preview(tools, plan, self.cancel, seconds)
                self.events.put(("preview", (dialog, image_label, png)))
                self.events.put(("notice", "Kontrollbild bereit."))
            self.background(work, "Kontrollbild berechnen")
        button.configure(command=request)
        dialog.protocol("WM_DELETE_WINDOW", lambda: self.close_preview(dialog, button, time_entry))
        dialog.after(50, request)

    def close_preview(self, dialog, *widgets):
        self.controls = [(widget, state) for widget, state in self.controls if widget not in widgets]
        dialog.destroy()

    def show_log(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("TransCora · Log")
        text = tk.Text(dialog, background="#202020", foreground="#e0e0e0", wrap="word", width=90, height=25)
        text.pack(fill="both", expand=True)
        text.insert("1.0", "\n\n".join(self.log_lines[-150:]) or "Noch keine technischen Meldungen.")
        text.configure(state="disabled")

    def abort(self):
        if self.busy:
            self.cancel.set()
            self.abort_button.configure(state="disabled")
            self.status.set("Abbruch angefordert; laufenden Prozess beenden …")

    def poll(self):
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
                elif kind == "progress":
                    _, index, count, value = payload
                    if value["percent"] is not None:
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                        self.progress["value"] = ((index - 1) + value["percent"] / 100) / count * 100
                elif kind == "speed":
                    self.speed.set("Geschwindigkeit " + payload[3] + " · Timing erhalten")
                elif kind == "phase":
                    self.speed.set(payload[3])
                elif kind == "preview":
                    dialog, label, png = payload
                    if dialog.winfo_exists():
                        image = tk.PhotoImage(data=base64.b64encode(png))
                        label.configure(image=image, text="")
                        label.image = image
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
            write_json(app_root() / "settings.json", {"schema_version": 1, "defaults": asdict(self.defaults),
                       "output_folder": str(self.output_path()), "input_folder": self.input_folder,
                       "custom_tools": self.custom_tools, "recursive": self.recursive.get(), "mirror": self.mirror.get()})
        except OSError:
            # Read-only application folders must not prevent exit or conversion to a writable destination.
            messagebox.showwarning("Einstellungen", "Der Programmordner ist schreibgeschützt; Einstellungen konnten nicht gespeichert werden.", parent=self.root)
        self.root.destroy()
