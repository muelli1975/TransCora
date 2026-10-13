from __future__ import annotations
from .remaining import RemainingTime

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
from transcora.i18n import LANGUAGES
from transcora.gui.localization import Localizer, TextVar
from transcora.gui.settings_area import SettingsArea, section, CurrentFile
from transcora.gui.file_list import FileListSorter, remove_entries, completed_button
from transcora.core.journal import Journal, Completion, JournalError, request, restore, processing_text
from transcora.core.batch_pause import BatchPause
from transcora.core.engine import Cancelled, execute, methods, plan_job, preview
from transcora.core.model import Job, LAYOUTS, PROFILES, TARGETS, Options, VIDEO_EXTENSIONS, app_root, FPS_CHOICES, FPS_MODES, COMPATIBILITY_NOTE, ANAGLYPH_PLAYER_NOTE, AUDIO_FORMATS, AUDIO_TRACKS, AUDIO_CHANNELS, VIDEO_SIZES, BD_BITRATES, BD_MODES, ROW_ORDERS
from transcora.core.naming import effective_suffix, suffix_choices, reserve_output, filename_layout, fps_suffix, default_disc_title
from transcora.core.storage import load_list, save_list, write_json, new_run_log, delete_run_logs, load_presets, save_presets, validate_preset_name
from transcora.core.toolchain import Toolchain
from transcora.gui.native import schedule_dark_titlebar
from transcora.gui.preview_window import PreviewWindow
from transcora.gui.theme import checkbox, set_control_state, apply_theme, GOLD_LIGHT, MUTED, TEXT, PANEL_BG, APP_BG, SECONDARY_BG


STATUS = {"queued": "Wartet", "checking": "Prüfung", "ready": "Bereit", "blocked": "Prüfen!",
          "running": "Läuft", "completed": "Fertig", "failed": "Fehler", "cancelled": "Abgebrochen"}


class Window:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.jobs: list[Job] = []
        self.source_geometry = {}
        self.events = queue.Queue()
        self.cancel = threading.Event()
        self.busy = False
        self.processing = False
        self.pause = BatchPause()
        self.pause_started = None
        self.run_started = None
        self.estimate_weights = []
        self.remaining_time = RemainingTime()
        self.closing = False
        self.updating = False
        self.controls = []
        self.log_lines = []
        self.journal_messages = set()
        self.catalog = methods()
        self.defaults = Options()
        self.language = 'de'
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
        self.localizer = Localizer(root, self)
        root.localizer = self.localizer
        self.t = self.localizer.t
        self._style()
        self._build()
        self.apply_language()
        self.root.update_idletasks()
        # The initial size should fit ordinary settings plus a useful file list.
        # On shorter screens the bounded settings viewport remains scrollable.
        extra = max(0, self.settings_area.normal_height()-self.settings_area.canvas.winfo_height())
        screen_limit = max(680,self.root.winfo_screenheight()-80)
        height = min(screen_limit,max(860,self.root.winfo_height()+extra+max(0,180-self.tree.winfo_height())))
        self.root.geometry(f'860x{height}')
        root.after_idle(self.settings_area.layout)
        root.after_idle(self.images.settings_area.layout)
        schedule_dark_titlebar(root)
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)

    def add_language_control(self, parent):
        combo = ttk.Combobox(parent, textvariable=self.language_var,
                             values=list(LANGUAGES.values()), state='readonly', width=10)
        combo.pack(side='right')
        combo.bind('<<ComboboxSelected>>', self.language_changed)
        self.language_controls.append(combo)

    def language_changed(self, event=None):
        if self.busy or self.images.busy:
            self.language_var.set(LANGUAGES[self.language])
            return
        self.language = next(key for key, label in LANGUAGES.items() if label == self.language_var.get())
        self.apply_language()
        try:
            self.persist_settings()
        except OSError:
            self.status.set('Der Programmordner ist schreibgeschützt; Einstellungen konnten nicht gespeichert werden.')

    def apply_language(self):
        for panel in (self, self.images):
            for key, mapping in panel.mappings.items():
                if key in panel.combos:
                    panel.combos[key].configure(values=[self.t(value) for value in mapping.values()])
        for job in self.jobs:
            self.update_row(job)
        self.selection_changed()
        self.images.refresh(); self.images.selection_changed()
        self.combos['target_fps'].configure(values=[value.replace(',', '.') if self.language == 'en' else value for value in FPS_CHOICES])
        self.localizer.apply()

    def persist_settings(self):
        write_json(app_root() / 'settings.json', {'schema_version': 2,
                   'defaults': asdict(replace(self.defaults, layout='auto', swap=False, disc_title=None)),
                   'output_folder': str(self.output_path()), 'input_folder': self.input_folder,
                   'recursive': self.recursive.get(), 'language': self.language})

    def language_sensitivity(self):
        for widget in self.language_controls:
            widget.configure(state='disabled' if self.busy or self.images.busy else 'readonly')

    def _load_settings(self):
        try:
            data = json.loads((app_root() / "settings.json").read_text(encoding="utf-8"))
            if not isinstance(data, dict) or data.get("schema_version") not in (1, 2):
                return
            self.language = data.get('language', 'de') if data.get('language') in LANGUAGES else 'de'
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
        self.root.geometry("860x760")
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
        self.notebook = ttk.Notebook(self.root)
        self.notebook.bind('<<NotebookTabChanged>>',self.tab_changed)
        self.notebook.pack(fill='both', expand=True)
        self.video_tab = ttk.Frame(self.notebook)
        self.image_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.video_tab, text='Videos')
        self.notebook.add(self.image_tab, text='Bilder')
        outer = ttk.Frame(self.video_tab, padding=10)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)
        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(header, text="TransCora", foreground=GOLD_LIGHT, font=("Segoe UI", 15)).pack(side="left")
        self.language_var = tk.StringVar(value=LANGUAGES[self.language])
        self.language_controls = []
        self.add_language_control(header)
        ttk.Label(header, text="Lokale 3D-Video-Konvertierung", foreground=MUTED).pack(side="right", padx=12)
        toolbar = ttk.Frame(outer)
        toolbar.grid(row=1, column=0, sticky="ew", pady=(0, 4))
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
        self.tree = ttk.Treeview(holder, columns=("file", "layout", "fps", "duration", "target", "status", "processing"), show="headings", height=6, selectmode="extended")
        from tkinter import font
        table_font = font.Font(font=ttk.Style().lookup('Treeview', 'font'))
        source_width = max(100, *(table_font.measure(label)+16 for label in
                                 ('Frame sequential', 'Zeilenverschachtelt', 'Row interleaved', 'MVC / Blu-ray 3D')))
        file_width = max(120, 290-source_width)
        for key, label, width in (("file", "Datei", file_width), ("layout", "Quelle", source_width), ("fps", "fps", 55),
                                  ("duration", "Dauer", 70), ("target", "Ziel", 185), ("status", "Status", 80),
                                  ("processing", "Bearbeitungszeit", 126)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=120 if key == "file" else width, stretch=key == "file")
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(holder, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.bind("<<TreeviewSelect>>", self.selection_changed)
        self.sorter = FileListSorter(self,dict(file='Datei',layout='Quelle',fps='fps',duration='Dauer',target='Ziel',status='Status',processing='Bearbeitungszeit'))
        self.tree.bind('<Control-a>', self.select_all)
        self.tree.bind('<Control-A>', self.select_all)
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
            self.tree.bind('<Command-a>', self.select_all)
            self.tree.bind('<Command-A>', self.select_all)
        self.selection_text = TextVar(self.localizer, value="Vorgaben für neue Dateien")
        scope = ttk.Frame(outer)
        scope.grid(row=3,column=0,sticky='ew',pady=(6,4))
        ttk.Label(scope,textvariable=self.selection_text,foreground=MUTED).pack(side='left')
        self.reset_button = self.button(scope,'Standardeinstellungen',self.reset_defaults)
        self.reset_button.pack(side='right')
        self.remove_completed_button = self.button(scope, 'Fertige entfernen', self.remove_completed)
        self.remove_completed_button.pack(side='right', padx=(0, 6))
        completed_button(self)
        self.settings_area = SettingsArea(outer)
        fields = self.settings_area.body
        _, source_fields = section(fields,0,'Quelle')
        _, output_fields = section(fields,1,'Ausgabe')
        _, format_fields = section(fields,2,'Format')
        self.advanced_section, self.advanced = section(fields,3,'Erweitert')
        self.advanced_section.grid_remove()
        self.settings_area.advanced = self.advanced_section
        _, save_fields = section(fields,4,'Speichern')
        self.variables = {}
        self.mappings = {"layout": LAYOUTS, "target": TARGETS, "profile": PROFILES,
                         'mono_eye': {'left': 'Linkes Halbbild', 'right': 'Rechtes Halbbild'},
                         "method": {k: m["label"] for k, m in self.catalog.items()},
                         "container": {"mkv": "MKV", "mp4": "MP4", "iso": "Blu-ray-ISO", "m2ts": "M2TS (AVC/MVC)"},
                         "codec": {"h264": "H.264", "h265": "H.265 / HEVC"},
                         "rate_mode": {"crf": "Qualität (CRF)", "abr": "Zielbitrate (Durchschnitt)"},
                         'video_size': dict(VIDEO_SIZES, default='Automatisch'), 'bd_bitrate_mbps': {n: str(n)+' Mbit/s' for n in BD_BITRATES},
                         'row_first': ROW_ORDERS, 'bd_mode': BD_MODES,
                         'fps_mode': FPS_MODES,
                         'audio_format': AUDIO_FORMATS, 'audio_tracks': AUDIO_TRACKS, 'audio_channels': AUDIO_CHANNELS}
        self.combos = {}
        self.option_frames = {}
        def combo(parent, row, col, key, label):
            routes = {'layout':(source_fields,0,0),'target':(output_fields,0,0),
                      'video_size':(output_fields,0,1),'method':(output_fields,1,0),
                      'profile':(output_fields,1,1),'row_first':(output_fields,1,0),
                      'mono_eye':(output_fields,1,0),
                      'container':(format_fields,0,0)}
            parent,row,col = routes.get(key,(parent,row,col))
            frame = ttk.Frame(parent)
            self.option_frames[key] = frame
            frame.grid(row=row, column=col, sticky="ew", padx=(0, 8), pady=3)
            if key == 'video_size':
                self.video_size_caption = TextVar(self.localizer, value=label)
                ttk.Label(frame, textvariable=self.video_size_caption).pack(anchor='w')
            elif key == 'profile':
                self.profile_caption = TextVar(self.localizer, value=label)
                ttk.Label(frame, textvariable=self.profile_caption).pack(anchor='w')
            else:
                ttk.Label(frame, text=label).pack(anchor="w")
            var = tk.StringVar(value=self.t(self.mappings[key][getattr(self.defaults, key)]))
            self.variables[key] = var
            widget = ttk.Combobox(frame, textvariable=var, values=[self.t(v) for v in self.mappings[key].values()], state="readonly", width=1)
            widget.pack(fill="x")
            widget.bind("<<ComboboxSelected>>", lambda event, k=key: self.option_changed(k))
            self.controls.append((widget, "readonly"))
            self.combos[key] = widget
        combo(fields, 0, 0, "layout", "Quelllayout")
        self.variables["swap"] = tk.BooleanVar(value=self.defaults.swap)
        swap = checkbox(source_fields, text="L/R tauschen", variable=self.variables["swap"], command=lambda: self.option_changed("swap"))
        swap.grid(row=0, column=1, sticky="sw", padx=(0, 8), pady=5)
        self.swap_control = swap
        self.controls.append((swap, "normal"))
        combo(fields, 0, 2, "target", "Ziel")
        combo(fields, 1, 0, 'mono_eye', 'Halbbild')
        combo(fields, 1, 0, "method", "Anaglyphenverfahren")
        combo(fields, 1, 1, "profile", "Anaglyph-Ausgabeprofil")
        combo(fields, 1, 2, "container", "Dateiformat")
        suffix_frame = ttk.Frame(save_fields)
        suffix_frame.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(suffix_frame, text="Dateinamenszusatz · frei editierbar").pack(anchor="w")
        self.variables["suffix"] = tk.StringVar()
        suffix = ttk.Combobox(suffix_frame, textvariable=self.variables["suffix"], state="normal", width=22)
        suffix.pack(fill="x")
        for event in ("<<ComboboxSelected>>", "<FocusOut>", "<Return>", "<KeyRelease>"):
            suffix.bind(event, lambda e: self.option_changed("suffix"))
        self.combos["suffix"] = suffix
        self.controls.append((suffix, "normal"))
        self.title_frame = ttk.Frame(output_fields)
        self.title_frame.grid(row=1, column=0, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(self.title_frame, text="Disc-Titel").pack(anchor="w")
        self.variables['disc_title'] = tk.StringVar()
        title_entry = ttk.Entry(self.title_frame, textvariable=self.variables['disc_title'])
        title_entry.pack(fill="x")
        for event in ('<FocusOut>', '<Return>'):
            title_entry.bind(event, lambda e: self.option_changed('disc_title'))
        self.controls.append((title_entry, 'normal'))
        self.fps_frame = ttk.Frame(format_fields)
        self.fps_frame.grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=3)
        ttk.Label(self.fps_frame, text="Bildrate (fps)").pack(anchor="w")
        fps_controls = ttk.Frame(self.fps_frame)
        fps_controls.pack(fill='x')
        self.variables['fps_mode'] = tk.StringVar(value=self.t(FPS_MODES[self.defaults.fps_mode]))
        fps_mode = ttk.Combobox(fps_controls, textvariable=self.variables['fps_mode'], values=[self.t(v) for v in FPS_MODES.values()], state='readonly', width=1)
        fps_mode.pack(side='left', fill='x', expand=True, padx=(0, 4))
        fps_mode.bind('<<ComboboxSelected>>', lambda e: self.option_changed('fps_mode'))
        self.combos['fps_mode'] = fps_mode
        self.controls.append((fps_mode, 'readonly'))
        self.variables["target_fps"] = tk.StringVar(value=self.defaults.target_fps)
        fps = ttk.Combobox(fps_controls, textvariable=self.variables["target_fps"], values=FPS_CHOICES, state="normal", width=8)
        fps.pack(side='left')
        for event in ("<<ComboboxSelected>>", "<FocusOut>", "<Return>"):
            fps.bind(event, lambda e: self.option_changed("target_fps"))
        self.combos["target_fps"] = fps
        self.controls.append((fps, "normal"))
        combo(fields, 2, 1, "video_size", "Ausgabegröße")
        self.variables['bd_mode'] = tk.StringVar(value=self.t(BD_MODES[self.defaults.bd_mode]))
        self.combos['video_size'].bind('<<ComboboxSelected>>', lambda e: self.option_changed(
            'bd_mode' if (self.selected_jobs()[0].options if self.selected_jobs() else self.defaults).target == 'bd3d' else 'video_size'))
        self.output_name = TextVar(self.localizer, )
        output_example = ttk.Label(save_fields, textvariable=self.output_name, foreground=GOLD_LIGHT, width=1)
        output_example.grid(row=1, column=1, columnspan=2, sticky="ew", pady=(3, 0))
        output_example.bind('<Configure>',lambda e:output_example.configure(wraplength=max(1,e.width)))
        output = ttk.Frame(save_fields)
        output.grid(row=0, column=0, columnspan=3, sticky="ew", pady=(0, 8))
        output.columnconfigure(1, weight=1)
        ttk.Label(output, text="Ausgabeordner").grid(row=0, column=0, padx=(0, 8))
        self.output_var = tk.StringVar(value=self.output_folder)
        entry = ttk.Entry(output, textvariable=self.output_var)
        entry.grid(row=0, column=1, sticky="ew")
        entry.bind("<FocusOut>", lambda event: self.invalidate_all())
        self.controls.append((entry, "normal"))
        self.button(output, "Auswählen", self.choose_output).grid(row=0, column=2, padx=(8, 0))
        folder_checks = ttk.Frame(output)
        folder_checks.grid(row=0, column=3, sticky="w", padx=(10, 0))
        self.recursive = tk.BooleanVar(value=self.recursive_value)
        check = checkbox(folder_checks, text="Unterordner mitverarbeiten", variable=self.recursive)
        self.recursive_control = check
        check.pack(side="left", padx=(0, 10))
        self.controls.append((check, "normal"))
        self.warning = TextVar(self.localizer, )
        self.attention = TextVar(self.localizer, )
        self.option_attention = TextVar(self.localizer, )
        self.file_notes = TextVar(self.localizer, )

        self.details = TextVar(self.localizer, value="Dateien hinzufügen oder eine gespeicherte Liste laden.")
        detail_frame = ttk.Frame(outer, style="Bordered.TFrame", padding=1)
        detail_frame.grid(row=7, column=0, sticky="ew")
        detail_frame.columnconfigure(0, weight=1)
        self.detail_text = tk.Text(detail_frame, height=4, width=1, wrap="word", background=APP_BG,
            foreground=MUTED, insertbackground=TEXT, selectbackground=GOLD_LIGHT, selectforeground=APP_BG,
            inactiveselectbackground=GOLD_LIGHT, exportselection=False,
            borderwidth=0, highlightthickness=0, padx=8, pady=6, state="disabled")
        self.detail_text.grid(row=0, column=0, sticky="ew")
        detail_scroll = ttk.Scrollbar(detail_frame, orient="vertical", command=self.detail_text.yview)
        detail_scroll.grid(row=0, column=1, sticky="ns")
        self.detail_text.configure(yscrollcommand=detail_scroll.set)
        def show_details(*args):
            if getattr(self, 'updating_details', False):
                return
            self.detail_text.configure(state="normal")
            self.detail_text.delete("1.0", "end")
            seen = set()
            def insert(source, attention=False):
                for line in source.splitlines():
                    translated = self.t(line).strip()
                    identity = translated.removeprefix('⚠').strip()
                    if identity and identity not in seen:
                        seen.add(identity)
                        self.detail_text.insert('end', ('⚠ ' if attention else '') + identity + '\n',
                                                ('attention',) if attention else ())
            insert(self.attention.source, True)
            represented = self.attention.source.splitlines()+self.file_notes.source.splitlines()
            if self.option_attention.source and self.option_attention.source not in represented:
                insert(self.option_attention.source, True)
            insert(self.file_notes.source)
            # File warnings already explain these options. Keep only additional
            # option notes (such as the 10-bit explanation) below them.
            notes = self.warning.source
            for shown in represented:
                if shown:
                    notes = notes.replace(shown, '')
            if notes.strip():
                insert(notes.strip())
            insert(self.details.source)
            self.detail_text.configure(state="disabled")
        self.render_details = show_details
        self.detail_text.tag_configure('attention', foreground=GOLD_LIGHT, font=('Segoe UI',9,'bold'))
        self.detail_text.tag_raise('sel')
        self.attention.trace_add('write', show_details)
        self.option_attention.trace_add('write',show_details)
        self.file_notes.trace_add('write',show_details)
        self.warning.trace_add('write', show_details)
        self.details.trace_add("write", show_details)
        show_details()
        actions = ttk.Frame(outer)
        actions.grid(row=13, column=0, sticky="ew", pady=(8, 0))
        self.advanced_button = self.button(actions, "Erweitert ▸", self.toggle_advanced)
        self.advanced_button.pack(side="left")
        self.button(actions, "Kontrollbild", self.show_preview).pack(side="left", padx=5)
        ttk.Button(actions, text="Log", command=self.show_log).pack(side="left")
        combo(self.advanced, 0, 0, "codec", "Videocodec")
        combo(self.advanced, 0, 1, "rate_mode", "Qualitätssteuerung")
        numeric = ttk.Frame(self.advanced)
        self.numeric_fields = numeric
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
        self.bd_video = ttk.Frame(self.advanced)
        self.bd_video.grid(row=0,column=0,columnspan=3,sticky='ew',pady=3)
        self.bd_video.columnconfigure(1,weight=1)
        ttk.Label(self.bd_video,text='Video',width=9).grid(row=0,column=0,sticky='w')
        combo(self.bd_video, 0, 1, "bd_bitrate_mbps", "Bitrate")
        self.combos['bd_bitrate_mbps'].configure(width=12)
        self.option_frames['bd_bitrate_mbps'].grid_configure(sticky='w')
        self.rate_fields["bd_bitrate_mbps"] = self.option_frames["bd_bitrate_mbps"]
        self.video_dimensions = ttk.Frame(self.option_frames['video_size'])
        self.video_dimensions.pack(fill='x', pady=(4, 0))
        for key in ('video_width', 'video_height'):
            if key == 'video_height':
                ttk.Label(self.video_dimensions, text='×').pack(side='left', padx=4)
            var = tk.StringVar(value=str(getattr(self.defaults, key)))
            self.variables[key] = var
            entry = ttk.Entry(self.video_dimensions, textvariable=var, width=7)
            entry.pack(side='left', fill='x', expand=True)
            for event in ('<FocusOut>', '<Return>'):
                entry.bind(event, lambda e, k=key: self.option_changed(k))
            self.combos[key] = entry
            self.controls.append((entry, 'normal'))
        ttk.Label(self.video_dimensions, text='px').pack(side='left', padx=(4, 0))
        self.screen_fields = ttk.Frame(self.option_frames["video_size"])
        self.screen_fields.pack(fill='x',pady=(4,0))
        screen_values = ttk.Frame(self.screen_fields)
        screen_values.pack(fill='x')
        for key in ('screen_width', 'screen_height'):
            if key == 'screen_height':
                ttk.Label(screen_values, text='×').pack(side='left', padx=5)
            self.variables[key] = tk.StringVar(value=str(getattr(self.defaults, key)))
            entry = ttk.Entry(screen_values, textvariable=self.variables[key], width=8)
            entry.pack(side='left', fill='x', expand=True)
            for event in ('<FocusOut>', '<Return>'):
                entry.bind(event, lambda e, k=key: self.option_changed(k))
            self.combos[key] = entry
            self.controls.append((entry, 'normal'))
        combo(fields, 1, 0, 'row_first', 'Erste Bildschirmzeile')
        self.audio_row = ttk.Frame(self.advanced)
        self.audio_row.grid(row=1,column=0,columnspan=3,sticky='ew',pady=(6,3))
        self.audio_row.columnconfigure(2,weight=1)
        ttk.Label(self.audio_row,text='Audio',width=9).grid(row=0,column=0,sticky='w')
        self.advanced_audio_button = self.button(self.audio_row, 'Tonoptionen …', self.show_audio_options)
        self.advanced_audio_button.grid(row=0,column=1,sticky='w',padx=(0,8))
        self.audio_summary = TextVar(self.localizer, )
        audio_summary = ttk.Label(self.audio_row,textvariable=self.audio_summary,foreground=MUTED,width=1)
        audio_summary.grid(row=0,column=2,sticky='ew')
        audio_summary.bind('<Configure>',lambda e:audio_summary.configure(wraplength=max(1,e.width)))
        self.format_audio_button = self.button(format_fields,'Tonoptionen …',self.show_audio_options)
        self.format_audio_button.grid(row=0,column=2,sticky='sw',padx=(0,8),pady=3)
        # Keep the main window usable at its minimum height. Audio controls live
        # in a reusable dialog so their values and state follow the same selection.
        self.audio_dialog = tk.Toplevel(self.root, background=APP_BG)
        self.audio_dialog.withdraw()
        self.audio_dialog.title('Tonoptionen')
        self.audio_dialog.transient(self.root)
        self.audio_dialog.resizable(False, False)
        self.audio_dialog.protocol('WM_DELETE_WINDOW', self.close_audio_options)
        self.audio_dialog.bind('<Escape>', lambda e: self.close_audio_options())
        schedule_dark_titlebar(self.audio_dialog)
        audio_fields = ttk.Frame(self.audio_dialog, padding=12)
        audio_fields.pack(fill='both', expand=True)
        for col in (0, 1, 2):
            audio_fields.columnconfigure(col, weight=1, uniform='audio')
        combo(audio_fields, 0, 0, 'audio_format', 'Tonformat')
        combo(audio_fields, 0, 1, 'audio_tracks', 'Tonspuren')
        combo(audio_fields, 0, 2, 'audio_channels', 'Tonkanäle')
        selection = ttk.Frame(audio_fields)
        selection.grid(row=1, column=0, sticky='ew', padx=(0, 8), pady=3)
        ttk.Label(selection, text='Spurnummern · z. B. 1, 3 oder 2-4').pack(anchor='w')
        self.variables['audio_selection'] = tk.StringVar(value=self.defaults.audio_selection)
        audio_selection = ttk.Entry(selection, textvariable=self.variables['audio_selection'])
        audio_selection.pack(fill='x')
        for event in ('<FocusOut>', '<Return>'):
            audio_selection.bind(event, lambda e: self.option_changed('audio_selection'))
        self.controls.append((audio_selection, 'normal'))
        self.combos['audio_selection'] = audio_selection
        self.audio_note = TextVar(self.localizer, )
        ttk.Label(audio_fields, textvariable=self.audio_note, foreground=MUTED, wraplength=360).grid(
            row=1, column=1, columnspan=2, sticky='w', pady=3)
        ttk.Label(audio_fields, text='Einstellungen werden sofort übernommen.', foreground=MUTED).grid(
            row=2, column=0, columnspan=2, sticky='w', pady=(12, 0))
        ttk.Button(audio_fields, text='Schließen', command=self.close_audio_options).grid(
            row=2, column=2, sticky='e', pady=(12, 0))
        self.status = TextVar(self.localizer, value="Bereit")
        progress_info = ttk.Frame(outer)
        progress_info.grid(row=10, column=0, sticky="ew", pady=(6, 3))
        progress_info.columnconfigure(0, weight=1)
        self.status_label = ttk.Label(progress_info, textvariable=self.status, wraplength=800)
        self.status_label.grid(row=0, column=0, sticky="w")
        self.elapsed = TextVar(self.localizer, value="")
        self.elapsed_time = TextVar(self.localizer, value="")
        self.current_file = CurrentFile(outer,self.localizer,9)
        self.progress = ttk.Progressbar(outer, mode="determinate", maximum=100)
        self.progress.grid(row=11, column=0, sticky="ew")
        timing = ttk.Frame(outer)
        timing.grid(row=12, column=0, sticky="ew", pady=(3, 0))
        ttk.Label(timing, textvariable=self.elapsed_time, foreground=MUTED).pack(side='left')
        ttk.Label(timing, textvariable=self.elapsed, foreground=MUTED).pack(side='left', padx=(24, 0))
        footer = actions
        self.speed = TextVar(self.localizer, value="")
        ttk.Label(timing, textvariable=self.speed, foreground=MUTED).pack(side="right")
        def timing_visibility(*args):
            timing.grid() if self.elapsed.get() or self.elapsed_time.get() or self.speed.get() else timing.grid_remove()
            self.settings_area.schedule()
        for var in (self.elapsed, self.elapsed_time, self.speed):
            var.trace_add('write', timing_visibility)
        timing_visibility()
        self.abort_button = ttk.Button(footer, text="Abbrechen", command=self.abort, state="disabled", style="Danger.TButton")
        self.abort_button.pack(side="right")
        self.start_text = TextVar(self.localizer, 'Start')
        self.start_button = self.button(footer, "Start", self.start_or_pause, style="Primary.TButton", textvariable=self.start_text)
        self.start_button.pack(side="right", padx=5)
        self.test_button = self.button(footer, "Testen", lambda: self.check(False), style="Primary.TButton")
        self.test_button.pack(side="right")
        from .images_panel import ImagePanel
        self.images = ImagePanel(self.image_tab, self)
        self.root.bind("<Control-o>", lambda event: (self.images.add_files() if self.notebook.select() == str(self.image_tab)
            else self.add_files()) if not self.busy and not self.images.busy else None)
        self.root.bind("<Delete>", lambda event: self.remove() if not self.busy and self.root.focus_get() == self.tree else None)
        if self.root.tk.call('tk', 'windowingsystem') == 'aqua':
            self.root.tk.call('bind', str(self.root), '<Command-o>', self.root.bind('<Control-o>'))
        self.root.bind("<Escape>", lambda event: self.images.abort() if self.images.busy else self.abort() if self.busy else None)
        self.selection_changed()

    def tab_changed(self,event=None):
        if not hasattr(self,'images'):return
        panel=self.images if self.notebook.select()==str(self.image_tab) else self
        panel.settings_area.fit()
        self.root.after(10,panel.settings_area.layout)

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
            load.add_command(label=self.t('Keine gespeicherten Voreinstellungen'), state='disabled')
            delete.add_command(label=self.t('Keine gespeicherten Voreinstellungen'), state='disabled')
        menu.add_cascade(label=self.t('Laden'), menu=load)
        menu.add_command(label=self.t('Speichern unter …'), command=self.preset_dialog)
        menu.add_cascade(label=self.t('Löschen'), menu=delete)

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

    def preset_dialog(self, store=None, title='Voreinstellung speichern'):
        if self.busy or self.images.busy:
            return
        if not (self.images.commit_entries() if store else self.commit_entries()):
            return
        store = store or self.store_preset
        dialog = tk.Toplevel(self.root, background=APP_BG)
        dialog.title(title)
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
                store(name.get())
                dialog.destroy()
            except (OSError, ValueError) as error:
                note.configure(text=str(error))
        buttons = ttk.Frame(frame)
        buttons.pack(fill='x', pady=(10, 0))
        ttk.Button(buttons, text='Abbrechen', command=dialog.destroy).pack(side='right')
        ttk.Button(buttons, text='Speichern', command=save, style='Primary.TButton').pack(side='right', padx=5)
        entry.bind('<Return>', save)
        dialog.bind('<Escape>', lambda e: dialog.destroy())
        self.localizer.apply()
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
                job.result = None
                self.restore_result(job)
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

    def select_all(self, event=None):
        if not self.busy and not self.images.busy:
            self.tree.selection_set(self.tree.get_children())
            self.selection_changed()
        return 'break'

    def reset_defaults(self):
        if self.busy:
            return
        self.defaults = Options()
        self.tree.selection_remove(*self.tree.selection())
        self.selection_changed()
        self.status.set("Standardeinstellungen für neue Dateien wiederhergestellt. Bestehende Jobs behalten ihre Einstellungen.")

    def update_row(self, job):
        layout = job.plan.layout if job.plan else job.options.layout
        if not job.plan and job.result:
            layout = job.result.record.get('effective', {}).get('layout', layout)
        if job.plan:
            job.source_fps = job.plan.info["video"].get("avg_frame_rate")
            job.source_duration = job.plan.duration or None
            video = job.plan.info['video']
            if video.get('width') and video.get('height'):
                self.source_geometry[job.id] = (video['width'], video['height'], job.plan.layout)
        rate = job.source_fps
        try:
            from fractions import Fraction
            fps = f"{float(Fraction(rate)):.3f}".rstrip("0").rstrip(".")
        except (ValueError, ZeroDivisionError, TypeError):
            fps = "—"
        if job.source_duration is None:
            duration = "-"
        else:
            seconds = int(job.source_duration + .5)
            duration = f"{seconds//3600:02}:{seconds//60%60:02}:{seconds%60:02}"
        values = (job.source.name, self.t(LAYOUTS.get(layout, "?")), fps, duration,
                  self.t(('BD-3D · ' + self.t(BD_MODES[job.options.bd_mode]) if job.options.target == 'bd3d' else
                          'Mono · ' + self.t(self.mappings['mono_eye'][job.options.mono_eye]) if job.options.target == 'mono' else TARGETS[job.options.target])),
                  self.t(STATUS[job.status]), processing_text(job.result))
        if self.tree.exists(job.id):
            self.tree.item(job.id, values=values)
        else:
            self.tree.insert("", "end", iid=job.id, values=values)
        completed_button(self)

    def journal_notice(self, message):
        if message not in self.journal_messages:
            self.journal_messages.add(message)
            self.log_lines.append(message)
            self.status.set(message)

    def restore_result(self, job):
        completion = restore(job, self.output_path(), 'video', self.journal_notice)
        if completion:
            geometry = completion.record.get('effective', {}).get('source_geometry')
            if (isinstance(geometry, list) and len(geometry) == 3
                    and all(isinstance(n, int) and n > 0 for n in geometry[:2]) and geometry[2] in LAYOUTS):
                self.source_geometry[job.id] = tuple(geometry)
        return completion

    def selection_changed(self, event=None):
        selected = self.selected_jobs()
        if not selected:
            self.attention.set('')
            self.file_notes.set('')
            self.details.set("Dateien hinzufügen oder eine gespeicherte Liste laden.")
            self.selection_text.set("Vorgaben für neue Dateien")
            self.updating = True
            for key, var in self.variables.items():
                value = getattr(self.defaults, key)
                if key == "disc_title":
                    value = value or ""
                if key == "suffix":
                    value = effective_suffix(self.defaults, self.catalog[self.defaults.method]["suffix"])
                    value = value or "Keiner"
                var.set(self.t(self.mappings[key][value]) if key in self.mappings else self.t(value) if key == "suffix" and value == "Keiner" else value)
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
                var.set(self.t(self.mappings[key][value]) if all(v == value for v in values) else "")
            else:
                var.set(self.t(value) if key == "suffix" and value == "Keiner" else value if all(v == value for v in values) else "")
        self.updating = False
        self.last_suffix_display = self.variables['suffix'].get()
        self.last_title_display = self.variables['disc_title'].get()
        self.selection_text.set(f"Für {len(selected)} ausgewählte Datei(en)" + (" · Gemischte Werte" if any(any(getattr(j.options,k)!=getattr(selected[0].options,k) for j in selected[1:]) for k in self.variables) else ""))
        job = selected[0]
        self.show_job_details(job)
        self.refresh_controls()

    def show_job_details(self, job):
        warnings = list(dict.fromkeys(getattr(job.plan,'warnings',()))) if job.plan else []
        review = list(dict.fromkeys(getattr(job.plan,'review_warnings',()))) if job.plan else []
        attention = job.detail if job.status in {'blocked','failed'} else '\n'.join(review)
        summary = (job.plan.summary_text(self.t) if hasattr(job.plan,'summary_text') else job.plan.summary) if job.plan else str(job.source)
        extra = job.detail if job.status not in {'blocked','failed'} and job.detail != '\n'.join(getattr(job.plan,'warnings',())) else ''
        self.updating_details = True
        try:
            self.attention.set(attention)
            self.file_notes.set('\n'.join(note for note in warnings if note not in review))
            self.details.set(summary+('\n'+extra if extra else ''))
        finally:
            self.updating_details = False
        self.render_details()

    def option_changed(self, key):
        if self.busy or self.updating:
            return
        if key in {'video_width', 'video_height', 'screen_width', 'screen_height', 'crf', 'bitrate_mbps', 'target_fps'}:
            if str(self.combos[key].cget('state')) == 'disabled':
                return True
        if key == 'audio_selection':
            selected = self.selected_jobs()
            options = [job.options for job in selected] if selected else [self.defaults]
            if all(o.audio_selection == self.variables[key].get() for o in options):
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
                value = "" if value == self.t("Keiner") else value
            if key in self.mappings:
                value = next(k for k, label in self.mappings[key].items() if self.t(label) == value)
            elif key in {"video_width", "video_height", 'screen_width', 'screen_height'}:
                value = int(value)
            elif key in {"crf", "bitrate_mbps"}:
                value = float(value.replace(",", "."))
            selected = self.selected_jobs()
            current = [j.options for j in selected] if selected else [self.defaults]
            if all(getattr(o, key) == value for o in current):
                return True
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
                    if value == 'row_interleaved':
                        result.profile = 'quality'
                if key == "suffix" and value == effective_suffix(replace(options, suffix=None), self.catalog[options.method]["suffix"], source):
                    result.suffix = None
                if key == "codec" and value == "h265":
                    result.container = "mkv"
                if key == 'audio_channels' and value == 'stereo' and options.target != 'bd3d':
                    result.audio_format = 'aac'
                result.validate()
                return result
            candidates = self.selected_jobs()
            updates = [(job, changed(job.options, job.source)) for job in candidates]
            if key != 'disc_title' and not candidates:
                self.defaults = changed(self.defaults, candidates[0].source if candidates else None)
            for job, options in updates:
                if job.options == options:
                    continue
                job.options = options
                job.plan = None
                job.result = None
                job.status, job.detail = "queued", "Einstellungen geändert; erneut prüfen."
                self.restore_result(job)
                self.update_row(job)
            if key == "codec" and value == "h265":
                self.variables["container"].set("MKV")
            if key in {"target", "method", "target_fps", "layout", "disc_title", "container", 'audio_channels', "video_size", 'bd_mode', 'row_first', 'fps_mode', 'mono_eye'}:
                self.selection_changed()
            self.last_suffix_display = self.variables['suffix'].get()
            self.status.set("Einstellungen übernommen. Vor dem Start wird erneut geprüft.")
            self.refresh_controls()
            return True
        except (ValueError, StopIteration) as error:
            self.status.set(str(error) or "Ungültige Eingabe.")
            if key in {"crf", "bitrate_mbps", "target_fps", 'audio_selection', "video_width", "video_height", 'screen_width', 'screen_height'}:
                self.combos[key].focus_set()
            return False

    def refresh_controls(self):
        if self.busy:
            return
        selected = self.selected_jobs()
        options = selected[0].options if selected else self.defaults
        anaglyph = options.target == "anaglyph"
        framerate = options.target == "framerate"
        bd3d = options.target == 'bd3d'
        rows = options.target == 'row_interleaved'
        self.screen_fields.pack(fill='x',pady=(4,0)) if rows else self.screen_fields.pack_forget()
        self.combos['row_first'].configure(state='readonly' if rows else 'disabled')
        for key in ('screen_width', 'screen_height'):
            self.combos[key].configure(state='normal' if rows else 'disabled')
        self.title_frame.grid() if bd3d and selected else self.title_frame.grid_remove()
        self.option_frames['method'].grid() if anaglyph else self.option_frames['method'].grid_remove()
        self.option_frames['row_first'].grid() if rows else self.option_frames['row_first'].grid_remove()
        self.option_frames['mono_eye'].grid() if options.target == 'mono' else self.option_frames['mono_eye'].grid_remove()
        self.option_frames['profile'].grid() if anaglyph else self.option_frames['profile'].grid_remove()
        self.combos['container'].configure(values=[self.t(self.mappings['container'][k]) for k in
            (('iso', 'm2ts') if bd3d else ('mp4', 'mkv'))])
        self.advanced_button.configure(state='normal')
        set_control_state(self.swap_control, "disabled" if framerate else "normal")
        self.fps_frame.grid_remove() if bd3d else self.fps_frame.grid()
        self.combos['fps_mode'].configure(state='disabled' if bd3d else 'readonly')
        self.combos['target_fps'].configure(state='normal' if not bd3d and options.fps_mode == 'custom' else 'disabled')
        self.option_frames['video_size'].grid()
        self.combos['video_size'].configure(
            textvariable=self.variables['bd_mode' if bd3d else 'video_size'],
            values=[self.t(v) for v in (BD_MODES if bd3d else self.mappings['video_size']).values()],
            state='disabled' if framerate or rows else 'readonly')
        if framerate or rows:
            self.variables['video_size'].set(self.t('Monitorauflösung' if rows else 'Original'))
        self.video_dimensions.pack_forget() if rows else self.video_dimensions.pack(fill='x',pady=(4,0))
        custom_size = not bd3d and not framerate and not rows and options.video_size == "custom"
        self.video_size_caption.set('Ausgabegröße je Halbbild' if bd3d else 'Ausgabegröße')
        for key in ('video_width', 'video_height'):
            self.combos[key].configure(state='normal' if custom_size else 'disabled')
        self.refresh_dimensions()
        self.combos["bd_bitrate_mbps"].configure(state="readonly" if bd3d else "disabled")
        self.combos["method"].configure(state="readonly" if anaglyph else "disabled")
        self.combos["profile"].configure(state="readonly" if anaglyph else "disabled",
            values=[self.t(value) for value in PROFILES.values()])
        self.combos["suffix"].configure(values=[self.t(v) for v in self.available_suffixes(options, selected[0] if selected else None)])
        self.combos["container"].configure(state="disabled" if options.codec == "h265" else "readonly")
        self.combos['codec'].configure(state='disabled' if bd3d else 'readonly')
        self.combos['rate_mode'].configure(state='disabled' if bd3d else 'readonly')
        for key in ('codec','rate_mode'):
            self.option_frames[key].grid_remove() if bd3d else self.option_frames[key].grid()
        self.numeric_fields.grid_remove() if bd3d else self.numeric_fields.grid()
        self.bd_video.grid() if bd3d else self.bd_video.grid_remove()
        self.audio_row.grid() if bd3d else self.audio_row.grid_remove()
        self.format_audio_button.grid_remove() if bd3d else self.format_audio_button.grid()
        self.combos["crf"].configure(state="normal" if options.rate_mode == "crf" and not bd3d else "disabled")
        self.combos["bitrate_mbps"].configure(state="normal" if options.rate_mode == "abr" and not bd3d else "disabled")
        no_audio = options.audio_tracks == 'none'
        self.combos['audio_format'].configure(state='disabled' if bd3d or no_audio or options.audio_channels == 'stereo' else 'readonly')
        formats = ['LPCM · 24 Bit' if o.target == 'bd3d' else AUDIO_FORMATS[
            'aac' if o.audio_channels == 'stereo' else o.audio_format] for o in
            ([j.options for j in selected] if selected else [options])]
        self.variables['audio_format'].set(self.t(formats[0]) if len(set(formats)) == 1 else '')
        self.combos['audio_channels'].configure(state='disabled' if no_audio else 'readonly')
        self.combos['audio_selection'].configure(state='normal' if options.audio_tracks == 'selected' else 'disabled')
        self.audio_note.set('BD-3D: LPCM mit 48 kHz und 24 Bit.' if bd3d else (
            'AAC wird neu kodiert. Stereo mischt vorhandene Kanäle zusammen.' if options.audio_format == 'aac' or options.audio_channels == 'stereo'
            else 'Originalton wird kopiert. Blu-ray-LPCM wird in MKV verlustfrei als FLAC gespeichert.'))
        self.audio_summary.set('Ohne Ton' if no_audio else
            self.t(formats[0])+' · '+self.t(AUDIO_TRACKS[options.audio_tracks])+' · '+self.t(AUDIO_CHANNELS[options.audio_channels]))
        active_field = "bd_bitrate_mbps" if bd3d else "crf" if options.rate_mode == "crf" else "bitrate_mbps"
        for key, frame in self.rate_fields.items():
            frame.grid() if key == active_field else frame.grid_remove()
        text = ""
        review_text = ''
        if anaglyph:
            if options.profile == "compatible":
                text = COMPATIBILITY_NOTE
            else:
                review_text = ANAGLYPH_PLAYER_NOTE
                if options.profile == "quality10":
                    text += " 10 Bit: Feinere Abstufungen; kein HDR-Modus."
        if framerate:
            text = "Layout, Auflösung und Halbbildreihenfolge bleiben erhalten. Video wird neu kodiert; Ton gemäß Tonoptionen."
        if bd3d:
            text = self.t(BD_MODES[options.bd_mode]) + self.t(" · AVC/MVC · Hohe Qualität.")
            if options.container == 'm2ts':
                text += " M2TS enthält beide Halbbilder, jedoch keine Blu-ray-Disc-Struktur."
        if options.target == "cross_sbs":
            text = "Kreuzblick: Full-SBS mit rechtem Halbbild zuerst."
        if rows:
            text = 'Polfilter: Vollbild ohne Skalierung. 4:4:4 erhält getrennte Farbzeilen; 4:2:0 würde die Farben beider Augen vermischen.'
        if options.codec == "h265":
            text += " H.265: MKV, längere Rechenzeit und Zielplayer prüfen; CRF ist codecabhängig."
        if options.rate_mode == "abr" and not bd3d:
            text += " Zielbitrate = Videodurchschnitt, kein festes Dateigrößenlimit."
        self.option_attention.set(review_text)
        self.warning.set(text)
        self.update_output_name()
        self.settings_area.layout()

    def display_suffix(self, job):
        options = job.options
        if job.plan and options.target == "framerate":
            options = replace(options, layout=job.plan.layout, swap=job.plan.swap)
        try:
            return effective_suffix(options, self.catalog[options.method]["suffix"], job.source) or self.t("Keiner")
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
            job.plan = None
            job.result = None
            job.status, job.detail = "queued", "Ausgabeziel geändert; erneut prüfen."
            self.restore_result(job)
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
            self.restore_result(job)
            self.jobs.append(job)
            existing.add(key)
            self.update_row(job)
            added.append(job.id)
        if added:
            self.tree.selection_set(added)
        self.sorter.refresh()
        self.status.set(f"{len(added)} hinzugefügt · {len(self.jobs)} Dateien insgesamt.")

    def add_files(self):
        if self.busy:
            return
        paths = filedialog.askopenfilenames(title=self.t("Videos hinzufügen"), initialdir=self.input_folder,
                 filetypes=[(self.t("Videos"), " ".join("*" + e for e in sorted(VIDEO_EXTENSIONS))), (self.t("Alle Dateien"), "*.*")])
        if paths:
            self.input_folder = str(Path(paths[0]).parent)
            self.add_paths(paths)

    def add_folder(self):
        if self.busy:
            return
        value = filedialog.askdirectory(title=self.t("Videoordner hinzufügen"), initialdir=self.input_folder)
        if not value:
            return
        folder = Path(value).resolve()
        output = self.output_path()
        excluded_output = output if output != folder and output.is_relative_to(folder) else None
        recursive = self.recursive.get()
        self.input_folder = str(folder)
        def work():
            paths = []
            for path in folder.rglob("*") if recursive else folder.iterdir():
                if self.cancel.is_set():
                    raise Cancelled()
                if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                    resolved = path.resolve()
                    if excluded_output is not None and resolved.is_relative_to(excluded_output):
                        continue
                    if folder not in resolved.parents:
                        continue
                    paths.append(resolved)
            self.events.put(("paths", (sorted(paths, key=lambda p: str(p).casefold()), folder)))
        self.background(work, "Ordner durchsuchen")

    def remove(self):
        if self.sorter.busy():
            return
        count = remove_entries(self, self.tree.selection())
        self.status.set(f"{count} Listeneinträge entfernt; Quelldateien bleiben erhalten.")

    def remove_completed(self):
        if self.sorter.busy():
            return
        count = remove_entries(self, [j.id for j in self.jobs if j.status == 'completed'])
        self.status.set(f"{count} Listeneinträge entfernt; Quelldateien bleiben erhalten.")

    def load(self):
        if self.busy:
            return
        value = filedialog.askopenfilename(title=self.t("Jobliste laden"), initialdir=self.input_folder, filetypes=[(self.t("TransCora-Jobliste"), "*.json")])
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
                    self.restore_result(job)
                    self.update_row(job)
            if output:
                self.output_var.set(str(output))
                self.invalidate_all()
            self.status.set("Jobliste ergänzt. Alle Quellen werden vor dem Start neu geprüft.")
            self.sorter.refresh()
        except (OSError, ValueError, TypeError) as error:
            messagebox.showerror(self.t("Jobliste"), self.t(str(error)), parent=self.root)

    def save(self):
        if self.busy:
            return
        if not self.commit_entries():
            return
        value = filedialog.asksaveasfilename(title=self.t("Jobliste speichern"), initialdir=self.input_folder, defaultextension=".json",
                                            filetypes=[(self.t("TransCora-Jobliste"), "*.json")])
        if value:
            try:
                save_list(Path(value), self.jobs, self.output_path())
                self.status.set("Jobliste gespeichert; enthalten sind Pfade und Einstellungen, keine Videos.")
            except OSError as error:
                messagebox.showerror(self.t("Speichern"), self.t(str(error)), parent=self.root)

    def choose_output(self):
        value = filedialog.askdirectory(title=self.t("Ausgabeordner wählen"), initialdir=self.output_var.get())
        if value:
            self.output_var.set(value)
            self.invalidate_all()

    def output_path(self):
        return Path(self.output_var.get().strip()).expanduser().resolve() if self.output_var.get().strip() else app_root() / "output"

    def toggle_advanced(self):
        if self.busy:
            return
        if self.advanced_section.winfo_ismapped():
            self.close_advanced()
            return
        if not self.commit_entries():
            return
        self.refresh_controls()
        self.advanced_section.grid()
        self.advanced_button.configure(text='Erweitert ▾')
        self.settings_area.show_end(self.advanced)

    def close_advanced(self):
        if not self.commit_entries(('crf', 'bitrate_mbps')):
            return
        self.advanced_section.grid_remove()
        self.advanced_button.configure(text='Erweitert ▸')
        self.settings_area.canvas.yview_moveto(0)

    def selected_options(self):
        selected = self.selected_jobs()
        return selected[0].options if selected else self.defaults

    def commit_entries(self, keys=None):
        # Buttons do not reliably take focus in Tk; commit editable entries
        # explicitly before running, saving, or opening another dialog.
        keys = keys or ('video_width', 'video_height', 'screen_width', 'screen_height',
                        'target_fps', 'crf', 'bitrate_mbps', 'audio_selection')
        pending = {key: self.variables[key].get() for key in keys}
        for key in keys:
            if str(self.combos[key].cget('state')) == 'disabled':
                continue
            raw = pending[key]
            selected = self.selected_jobs()
            if not raw and selected and len({str(getattr(j.options, key)) for j in selected}) > 1:
                continue
            self.variables[key].set(raw)
            if self.option_changed(key) is False:
                return False
        return True

    def refresh_dimensions(self):
        from transcora.core.video import output_dimensions
        selected = self.selected_jobs()
        # Selection changes already populate custom values. Do not overwrite
        # a second dimension still being edited when the first loses focus.
        if all(o.video_size == 'custom' and o.target not in {'bd3d','row_interleaved','framerate'} for o in ([j.options for j in selected] or [self.defaults])):
            return
        values = []
        for job in selected or [None]:
            opts = job.options if job else self.defaults
            if opts.target == 'bd3d':
                from transcora.core.bd3d import output_mode
                values.append(output_mode(opts.bd_mode)[:2]); continue
            if opts.video_size == 'custom':
                size = opts.video_width, opts.video_height
            elif opts.video_size in {'1080p', '2160p'} or (opts.video_size == 'default' and opts.target.startswith('half_')):
                if opts.target.startswith('half_') or opts.target == 'cross_sbs':
                    h = 2160 if opts.video_size == '2160p' else 1080
                    size = (h*16//9 * (2 if opts.target == 'cross_sbs' else 1), h)
                else:
                    size = None
            else:
                size = None
            source = self.source_geometry.get(job.id) if job else None
            if source and opts.video_size != 'custom':
                w, h, layout = source
                layout = opts.layout if opts.layout in {'full_sbs', 'half_sbs', 'full_ou', 'half_ou'} else layout
                ew, eh = (w, h) if layout == 'frame_sequential' else ((w//2, h) if layout.endswith('sbs') else (w, h//2))
                ew *= 2 if layout == 'half_sbs' else 1
                eh *= 2 if layout in {'half_ou', 'row_interleaved'} else 1
                size = output_dimensions(opts, ew, eh)
                if opts.target in {'full_sbs', 'cross_sbs'}: size = size[0]*2, size[1]
                elif opts.target == 'full_ou': size = size[0], size[1]*2
            values.append(size)
        for i, key in enumerate(('video_width', 'video_height')):
            numbers = [v[i] if v else None for v in values]
            self.variables[key].set(str(numbers[0]) if numbers[0] is not None and all(n == numbers[0] for n in numbers) else '')

    def show_audio_options(self):
        if self.busy:
            return
        if not self.commit_entries():
            return
        self.refresh_controls()
        self.audio_dialog.geometry(f'+{self.root.winfo_rootx()+30}+{self.root.winfo_rooty()+100}')
        self.audio_dialog.deiconify()
        self.audio_dialog.lift()
        self.audio_dialog.grab_set()
        self.combos['audio_tracks'].focus_set()

    def close_audio_options(self):
        if self.option_changed('audio_selection') is False:
            return
        self.audio_dialog.grab_release()
        self.audio_dialog.withdraw()

    def set_busy(self, value):
        self.busy = value
        self.language_sensitivity()
        self.notebook.tab(self.image_tab, state='disabled' if value else 'normal')
        for widget, normal in self.controls:
            set_control_state(widget, "disabled" if value else normal)
        self.abort_button.configure(state="normal" if value else "disabled")
        completed_button(self)
        if not value:
            self.processing = False
        self.update_start_button()
        if not value:
            self.update_elapsed()
            self.elapsed.set('Restzeit: Datei — · Stapel —')
            self.run_started = None
            self.progress.stop()
            self.progress.configure(mode="determinate")
            self.refresh_controls()
            self.sorter.refresh()

    def update_elapsed(self):
        if self.run_started is None:
            return
        now = self.pause_started if self.pause_started is not None else time.monotonic()
        self.elapsed_time.set('Vergangene Zeit: ' + PreviewWindow.time_text(max(0, now-self.run_started)))
        file_left, batch_left = self.remaining_time.remaining(now)
        def label(value):
            return self.t('ca. ') + PreviewWindow.time_text(value) if value is not None else '—'
        self.elapsed.set(f'Restzeit: Datei {label(file_left)} · Stapel {label(batch_left)}')

    def estimate_remaining(self, index, count, percent, phase_percent=None, remaining=None):
        if self.run_started is None:
            return
        now = time.monotonic()
        if not self.remaining_time.items:
            weights = self.estimate_weights if len(self.estimate_weights) == count else [1]*count
            self.remaining_time = RemainingTime([(w, 'video', False) for w in weights])
        self.remaining_time.start(index, self.run_started if self.remaining_time.index is None else now)
        self.remaining_time.progress(now, percent, phase_percent, remaining)
        self.update_elapsed()

    def background(self, work, phase, track_time=False):
        if self.busy:
            return
        self.cancel.clear()
        self.processing = track_time
        self.pause.reset()
        self.pause_started = None
        if track_time:
            self.run_started = time.monotonic()
            self.estimate_weights = []
            self.remaining_time = RemainingTime()
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
        if not self.commit_entries():
            return
        self.option_changed("disc_title")
        if self.variables["disc_title"].get() != self.last_title_display:
            return
        self.option_changed("suffix")
        if self.variables['suffix'].get() != self.last_suffix_display:
            return
        self.option_changed('audio_selection')
        for job in self.jobs:
            self.restore_result(job)
            self.update_row(job)
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
            self.events.put(('notice', 'Testen: Mitgelieferte Videowerkzeuge prüfen'))
            capabilities = tools.inspect()
            self.events.put(("log", capabilities["version"]))
            reserved, ready, receipts = set(), [], {}
            blocked = 0
            for index, job in enumerate(candidates, 1):
                if self.cancel.is_set():
                    raise Cancelled()
                self.events.put(("current", (job.source.name,index,len(candidates))))
                self.events.put(("job", (job.id, "checking", "Technische Prüfung", None)))
                self.events.put(("notice", f"Testen: Datei {index} von {len(candidates)}"))
                try:
                    try:
                        receipts[job.id] = request(job, 'video') if run else None
                    except (OSError, ValueError):
                        receipts[job.id] = None
                    def phase(text):
                        self.events.put(('phase', (job.id, index, len(candidates), text)))
                    plan = plan_job(tools, job, output, reserved, self.cancel, capabilities, phase=phase)
                    ready.append((job, plan))
                    self.events.put(("job", (job.id, "ready", "\n".join(plan.warnings), plan)))
                    self.events.put(("log", plan.summary_text(self.t) + "\n" + "\n".join(plan.warnings)))
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
            self.events.put(("batch", [(max(1, plan.duration),
                (plan.options.target, plan.options.codec, plan.options.profile, plan.size,
                 plan.options.bd_mode if plan.options.target == 'bd3d' else plan.options.target_fps if plan.options.fps_mode == 'custom' else plan.info['video'].get('avg_frame_rate')),
                plan.options.target == 'bd3d') for _, plan in ready]))
            if ready:
                log_path = new_run_log(app_root())
            counts = {"completed": 0, "failed": 0, "cancelled": 0}
            journal_failures = 0
            for index, (job, plan) in enumerate(ready, 1):
                if self.cancel.is_set():
                    for remaining, _ in ready[index - 1:]:
                        self.events.put(("job", (remaining.id, "cancelled", "Nicht mehr gestartet", None)))
                        counts["cancelled"] += 1
                    break
                self.events.put(("current", (job.source.name,index,len(ready))))
                self.events.put(("job", (job.id, "running", "Verarbeitung", plan)))
                self.events.put(("notice", f"Datei {index} von {len(ready)}"))
                def emit(kind, payload):
                    self.events.put((kind, (job.id, index, len(ready), payload)))
                try:
                    started = time.monotonic()
                    execute(tools, plan, self.cancel, emit, log_path)
                    elapsed = max(0, time.monotonic() - started)
                    completion = Completion((plan.output,), elapsed, {})
                    try:
                        if receipts[job.id] is None:
                            raise JournalError('Quelldaten für den Journalnachweis fehlen.')
                        completion = Journal(output).complete(receipts[job.id], (plan.output,), elapsed,
                            effective={'options': asdict(plan.options), 'layout': plan.layout, 'swap': plan.swap, 'size': plan.size,
                                       'source_fps': plan.info['video'].get('avg_frame_rate'), 'source_duration': plan.duration,
                                       'source_geometry': [plan.info['video']['width'], plan.info['video']['height'], plan.layout]},
                            tools={'video': capabilities['version']})
                    except (OSError, ValueError) as error:
                        journal_failures += 1
                        self.events.put(('log', 'Journal nicht gespeichert: ' + str(error)))
                        self.events.put(('notice', 'Ausgabe fertig; Journal nicht gespeichert.'))
                    self.events.put(('result', (job.id, completion)))
                    counts["completed"] += 1
                    self.events.put(("job", (job.id, "completed", "Gespeichert · " + plan.stereo_summary + "\nGespeichert: " + str(plan.output), plan)))
                except Cancelled:
                    counts["cancelled"] += 1
                    self.events.put(("job", (job.id, "cancelled", "Begonnene Ausgabe verworfen", plan)))
                except Exception as error:
                    counts["failed"] += 1
                    with log_path.open("a", encoding="utf-8") as log:
                        log.write(f"\nFehler: {job.source}\n{error}\n")
                    self.events.put(("job", (job.id, "failed", str(error), plan)))
                    self.events.put(("log", job.source.name + ": " + str(error)))
                if index < len(ready):
                    self.pause.wait(self.cancel, lambda paused, value: self.events.put(('pause', (paused, value, index, len(ready)))))
            summary = (f"{counts['completed']} erfolgreich · {counts['failed']} Fehler · {blocked} blockiert · "
                       f"{counts['cancelled']} abgebrochen. Log: {log_path or self.t('Kein Lauf gestartet')}")
            if journal_failures:
                summary += ' · ' + self.t('Journal nicht gespeichert: ') + str(journal_failures)
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
        if not self.commit_entries():
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

    def update_start_button(self):
        self.start_text.set(self.pause.caption if self.busy and self.processing else 'Start')
        self.start_button.configure(state='normal' if not self.busy or self.processing else 'disabled')

    def start_or_pause(self):
        if self.busy and self.processing:
            self.pause.toggle()
            self.update_start_button()
        elif not self.busy:
            self.check(True)

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
            selectbackground=GOLD_LIGHT, selectforeground=APP_BG, exportselection=False,
            inactiveselectbackground=GOLD_LIGHT)
        text.grid(row=0, column=0, sticky='nsew')
        scroll = ttk.Scrollbar(holder, orient='vertical', command=text.yview)
        scroll.grid(row=0, column=1, sticky='ns')
        text.configure(yscrollcommand=scroll.set)
        self.localizer.text(text, "\n\n".join(self.log_lines[-150:]) or "Noch keine technischen Meldungen.")
        menu = self.dark_menu(text)
        text.copy_menu = menu
        def copy_selected(event=None):
            if text.tag_ranges('sel'):
                text.clipboard_clear()
                text.clipboard_append(text.get('sel.first','sel.last'))
            return 'break'
        menu.add_command(label=self.t('Kopieren'), command=copy_selected)
        def popup(event):
            menu.entryconfigure(0,label=self.t('Kopieren'),
                                state='normal' if text.tag_ranges('sel') else 'disabled')
            try:
                menu.tk_popup(event.x_root,event.y_root)
            finally:
                menu.grab_release()
            return 'break'
        text.bind('<Button-1>',lambda e:text.focus_set(),add='+')
        text.bind('<Button-3>',popup)
        if self.root.tk.call('tk','windowingsystem')=='aqua':
            text.bind('<Button-2>',popup)
            text.bind('<Control-Button-1>',popup)
        text.bind('<<Copy>>',copy_selected)
        def select_all(event=None):
            text.tag_add('sel','1.0','end-1c')
            return 'break'
        text.bind('<Control-a>',select_all)
        text.bind('<Control-A>',select_all)
        if self.root.tk.call('tk','windowingsystem')=='aqua':
            text.bind('<Command-a>',select_all)
        button = self.button(dialog, 'Logs löschen', lambda: self.clear_logs(text))
        button.pack(anchor='e', padx=8, pady=8)
        button.configure(state='disabled' if self.busy else 'normal')
        def forget(event):
            if event.widget == dialog:
                self.controls = [(w, state) for w, state in self.controls if w is not button]
        dialog.bind('<Destroy>', forget)
        self.localizer.apply()

    def clear_logs(self, text=None):
        if self.busy:
            return
        try:
            count = delete_run_logs(app_root())
            self.log_lines.clear()
            self.status.set(f'{count} Laufprotokolle gelöscht.')
            if text is not None:
                self.localizer.text(text, 'Keine technischen Meldungen.')
        except OSError as error:
            self.status.set(f'Logs löschen: {error}')

    def abort(self):
        if self.busy:
            self.cancel.set()
            self.abort_button.configure(state="disabled")
            self.status.set("Abbruch angefordert; laufenden Prozess beenden …")

    def poll(self):
        if self.images.poll():
            return
        self.update_elapsed()
        try:
            while True:
                kind, payload = self.events.get_nowait()
                if kind == "current":
                    self.current_file.set(*payload)
                    if self.remaining_time.items:
                        self.remaining_time.start(payload[1], time.monotonic())
                elif kind == "job":
                    id_, status, detail, plan = payload
                    job = next((job for job in self.jobs if job.id == id_), None)
                    if self.remaining_time.items and status in {'completed','failed','cancelled'} and job and job.status == 'running':
                        self.remaining_time.complete(time.monotonic(), status == 'completed')
                    if job:
                        job.status, job.detail, job.plan = status, detail, plan
                        self.update_row(job)
                        if id_ in self.tree.selection():
                            self.refresh_dimensions()
                            self.show_job_details(job)
                elif kind == 'result':
                    job = next((j for j in self.jobs if j.id == payload[0]), None)
                    if job:
                        job.result = payload[1]
                elif kind == 'pause':
                    paused, value, index, count = payload
                    if paused:
                        self.pause_started = value
                        self.status.set('Stapel pausiert')
                        self.progress.stop()
                        self.progress.configure(mode='determinate')
                        self.progress['value'] = index / count * 100
                    else:
                        if self.run_started is not None:
                            self.run_started += value
                        self.pause_started = None
                    self.update_start_button()
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
                    self.remaining_time = RemainingTime(payload)
                    self.estimate_weights = [item[0] for item in payload]
                elif kind == "progress":
                    _, index, count, value = payload
                    if value["percent"] is not None:
                        self.estimate_remaining(index, count, value['percent'],
                            value.get('phase_percent'), value.get('remaining_seconds'))
                        self.progress.stop()
                        self.progress.configure(mode="determinate")
                        self.progress["value"] = ((index - 1) + value["percent"] / 100) / count * 100
                elif kind == 'estimate':
                    if payload[3].get('encoding_complete'):
                        self.remaining_time.end_encoding(time.monotonic())
                        self.update_elapsed()
                elif kind == "speed":
                    value = payload[3]
                    parts = []
                    if value["speed"] != "N/A":
                        numeric = value["speed"].replace("x", "×")
                        parts.append("Geschwindigkeit " + (numeric.replace(".", ",") if self.language == 'de' else numeric))
                    if value["fps"] not in (None, "N/A"):
                        parts.append((value["fps"].replace(".", ",") if self.language == 'de' else value["fps"]) + " fps")
                    self.speed.set(" · ".join(parts))
                elif kind == "phase":
                    self.status.set(payload[3])
                    self.log_lines.append(payload[3])
                    self.speed.set('')
                    self.progress.stop()
                    self.progress.configure(mode='indeterminate')
                    self.progress.start(15)
                    self.remaining_time.phase(time.monotonic())
                    self.update_elapsed()
                elif kind == "preview":
                    viewer, png, plan = payload
                    if viewer.dialog.winfo_exists():
                        viewer.set_plan(plan)
                        widgets = {viewer.time_entry, viewer.scale}
                        self.controls = [(widget, state) for widget, state in self.controls if widget not in widgets]
                        self.controls.extend(viewer.controls())
                        image = tk.PhotoImage(master=viewer.dialog, data=base64.b64encode(png))
                        from PIL import Image
                        import io
                        viewer.image_view.set_images([Image.open(io.BytesIO(png))])
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
        self.localizer.apply()
        self.current_file.render()
        self.images.current_file.render()
        self.root.after(100, self.poll)

    def close(self):
        if self.busy or self.images.busy:
            if messagebox.askyesno(self.t("TransCora"), self.t("Laufende Arbeit abbrechen und TransCora schließen?"), parent=self.root):
                self.closing = True
                self.abort()
                self.images.abort()
        else:
            self.finish_close()

    def finish_close(self):
        try:
            self.images.persist()
            write_json(app_root() / "settings.json", {"schema_version": 2,
                       "defaults": asdict(replace(self.defaults, layout="auto", swap=False, disc_title=None)),
                       "output_folder": str(self.output_path()), "input_folder": self.input_folder,
                       "recursive": self.recursive.get(), "language": self.language})
        except OSError:
            # Read-only application folders must not prevent exit or conversion to a writable destination.
            messagebox.showwarning(self.t("Einstellungen"), self.t("Der Programmordner ist schreibgeschützt; Einstellungen konnten nicht gespeichert werden."), parent=self.root)
        self.root.destroy()
