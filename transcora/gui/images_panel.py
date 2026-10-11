"""Independent still-image job list sharing the application's operation guard."""
from dataclasses import asdict, replace
from pathlib import Path
import json
import queue
import tempfile
import threading
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

from transcora.core.images import (ImageJob, ImageOptions, EXTENSIONS, TASKS, LAYOUTS, TARGETS, FORMATS,
    plans, execute_image, save_images, load_images, SIZES, SIZE_EDGES, image_methods)
from transcora.core.engine import Cancelled, methods
from transcora.core.model import app_root
from transcora.core.storage import write_json, new_run_log, validate_preset_name
from transcora.core.toolchain import Toolchain
from .theme import GOLD_LIGHT, MUTED, SECONDARY_BG, TEXT
from .native import schedule_dark_titlebar
from .localization import TextVar

STATUS = {'queued': 'Wartet', 'ready': 'Bereit', 'running': 'Läuft', 'completed': 'Fertig',
          'blocked': 'Prüfen!', 'failed': 'Fehler', 'cancelled': 'Abgebrochen'}


class ImagePanel:
    def __init__(self, parent, owner):
        self.owner = owner; self.root = owner.root; self.t = owner.t; self.jobs = []; self.controls = []
        self.events = queue.Queue(); self.cancel = threading.Event(); self.busy = False; self.updating = False
        self.defaults = ImageOptions(); self.presets = {}; self.input_folder = str(app_root())
        self.output = tk.StringVar(value=str(app_root()/'output')); self.recursive = tk.BooleanVar(value=False)
        try:
            data = json.loads((app_root()/'image-settings.json').read_text(encoding='utf-8'))
            self.defaults = ImageOptions.from_dict(data.get('defaults', {}))
            saved_output = data.get('output_folder', self.output.get())
            # Migrate only the old generated default, preserving custom folders.
            if Path(saved_output).resolve() == (app_root()/'output/images').resolve():
                saved_output = str(app_root()/'output')
            self.output.set(saved_output); self.input_folder = data.get('input_folder', self.input_folder)
            self.recursive.set(data.get('recursive') is True)
            self.presets = {k: ImageOptions.from_dict(v) for k, v in data.get('presets', {}).items()}
        except (ValueError, TypeError, OSError, AttributeError):
            pass
        box = ttk.Frame(parent, padding=10); box.pack(fill='both', expand=True)
        box.columnconfigure(0, weight=1); box.rowconfigure(2, weight=1)
        header = ttk.Frame(box); header.grid(row=0, column=0, sticky='ew', pady=(0, 4))
        ttk.Label(header, text='TransCora', foreground=GOLD_LIGHT, font=('Segoe UI', 15)).pack(side='left')
        owner.add_language_control(header)
        ttk.Label(header, text='Bilder und Halbbilder im Stapel verarbeiten', foreground=MUTED).pack(side='right', padx=12)
        toolbar = ttk.Frame(box); toolbar.grid(row=1, column=0, sticky='ew', pady=(0, 4))
        for title, callback in [('Dateien hinzufügen', self.add_files), ('Ordner hinzufügen', self.add_folder),
                                ('Entfernen', self.remove), ('Liste laden', self.load), ('Liste speichern', self.save)]:
            self.button(toolbar, title, callback).pack(side='left', padx=(0, 5))
        self.preset_button = ttk.Menubutton(toolbar, text='Voreinstellungen'); self.preset_button.pack(side='right')
        self.controls.append((self.preset_button, 'normal')); self.menu = owner.dark_menu(self.preset_button)
        self.menu.configure(postcommand=self.preset_menu); self.preset_button.configure(menu=self.menu)
        holder = ttk.Frame(box); holder.grid(row=2, column=0, sticky='nsew'); holder.rowconfigure(0, weight=1); holder.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(holder, columns=('file', 'task', 'target', 'status'), show='headings', height=8, selectmode='extended')
        for key, title, width in [('file', 'Datei', 300), ('task', 'Aufgabe', 155), ('target', 'Ziel', 140), ('status', 'Status', 95)]:
            self.tree.heading(key, text=title); self.tree.column(key, width=width, stretch=key == 'file', minwidth=70)
        self.tree.grid(row=0, column=0, sticky='nsew'); scroll = ttk.Scrollbar(holder, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns'); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewSelect>>', self.selection_changed)
        self.tree.bind('<Control-a>', self.select_all)
        self.tree.bind('<Control-A>', self.select_all)
        self.tree.bind('<Delete>', lambda event: self.remove() if not self.busy else None)
        self.scope = TextVar(owner.localizer, value='Einstellungen gelten für neu hinzugefügte Bilder.')
        ttk.Label(box, textvariable=self.scope, foreground=MUTED).grid(row=3, column=0, sticky='w', pady=(5, 3))
        fields = ttk.Frame(box); fields.grid(row=4, column=0, sticky='ew')
        for col in range(3): fields.columnconfigure(col, weight=1, uniform='image-fields')
        self.mappings = {'task': TASKS, 'layout': LAYOUTS, 'target': TARGETS, 'format': FORMATS,
                         'method': {k: v['label'] for k, v in image_methods().items()}, 'quality': {90: '90 · 4:4:4', 95: '95 · 4:4:4'}}
        self.variables = {}; self.combos = {}
        for row, keys in enumerate([('task', 'layout', 'target'), ('format', 'method', 'quality')]):
            for col, key in enumerate(keys):
                cell = ttk.Frame(fields); cell.grid(row=row, column=col, sticky='ew', padx=(0, 8), pady=3)
                label = {'task': 'Aufgabe', 'layout': 'Quelllayout', 'target': 'Ziel', 'format': 'Bildformat',
                         'method': 'Anaglyphenverfahren', 'quality': 'JPEG-Qualität'}[key]
                ttk.Label(cell, text=label).pack(anchor='w')
                var = tk.StringVar(value=self.t(self.mappings[key][getattr(self.defaults, key)])); self.variables[key] = var
                combo = ttk.Combobox(cell, textvariable=var, values=[self.t(v) for v in self.mappings[key].values()], state='readonly', width=22)
                combo.pack(fill='x'); combo.bind('<<ComboboxSelected>>', lambda e, k=key: self.changed(k))
                self.combos[key] = combo; self.controls.append((combo, 'readonly'))
        for col, key, label in [(0, 'swap', 'L/R tauschen'), (1, 'metadata', 'Metadaten übernehmen')]:
            var = tk.BooleanVar(value=getattr(self.defaults, key)); self.variables[key] = var
            check = ttk.Checkbutton(fields, text=label, variable=var, command=lambda k=key: self.changed(k))
            check.grid(row=2, column=col, sticky='w', pady=7); self.controls.append((check, 'normal'))
        size = ttk.Frame(fields); size.grid(row=2, column=2, sticky='ew', padx=(0, 8))
        ttk.Label(size, text='Größe').pack(anchor='w')
        self.mappings['size_mode'] = SIZES; self.mappings['size_edge'] = SIZE_EDGES
        self.variables['size_mode'] = tk.StringVar(value=self.t(SIZES[self.defaults.size_mode]))
        size_combo = ttk.Combobox(size, textvariable=self.variables['size_mode'], values=[self.t(v) for v in SIZES.values()], state='readonly')
        size_combo.pack(fill='x'); size_combo.bind('<<ComboboxSelected>>', lambda e: self.changed('size_mode'))
        self.combos['size_mode'] = size_combo; self.controls.append((size_combo, 'readonly'))
        self.custom_size = ttk.Frame(fields)
        self.custom_size.grid(row=3, column=0, columnspan=3, sticky='ew', pady=(2, 4))
        self.variables['size_edge'] = tk.StringVar(value=self.t(SIZE_EDGES[self.defaults.size_edge]))
        edge = ttk.Combobox(self.custom_size, textvariable=self.variables['size_edge'], values=[self.t(v) for v in SIZE_EDGES.values()], state='readonly', width=16)
        edge.pack(side='left'); edge.bind('<<ComboboxSelected>>', lambda e: self.changed('size_edge'))
        self.combos['size_edge'] = edge; self.controls.append((edge, 'readonly'))
        self.variables['size_pixels'] = tk.StringVar(value=str(self.defaults.size_pixels))
        entry = ttk.Entry(self.custom_size, textvariable=self.variables['size_pixels'], width=8)
        entry.pack(side='left', padx=6)
        for event in ('<FocusOut>', '<Return>'): entry.bind(event, lambda e: self.changed('size_pixels'))
        ttk.Label(self.custom_size, text='px').pack(side='left')
        self.controls.append((entry, 'normal')); self.size_entry = entry
        row = ttk.Frame(box); row.grid(row=5, column=0, sticky='ew', pady=8); row.columnconfigure(1, weight=1)
        ttk.Label(row, text='Ausgabeordner').grid(row=0, column=0, padx=(0, 8))
        entry = ttk.Entry(row, textvariable=self.output); entry.grid(row=0, column=1, sticky='ew'); self.controls.append((entry, 'normal'))
        self.button(row, '…', self.choose_output, width=4).grid(row=0, column=2, padx=(6, 0))
        check = ttk.Checkbutton(box, text='Unterordner mitverarbeiten und Struktur beibehalten', variable=self.recursive)
        check.grid(row=6, column=0, sticky='w'); self.controls.append((check, 'normal'))
        self.detail = TextVar(owner.localizer, value='MPO-Teilung erhält die komprimierten Bilddaten unverändert.')
        ttk.Label(box, textvariable=self.detail, foreground=MUTED, wraplength=740).grid(row=7, column=0, sticky='ew', pady=6)
        actions = ttk.Frame(box); actions.grid(row=8, column=0, sticky='ew')
        self.button(actions, 'Testen', lambda: self.run(False), style='Primary.TButton').pack(side='left')
        self.preview_button = self.button(actions, 'Kontrollbild', self.preview)
        self.preview_button.pack(side='left', padx=6)
        self.preview_dialog = None
        self.button(actions, 'Start', lambda: self.run(True), style='Primary.TButton').pack(side='left')
        self.abort_button = ttk.Button(actions, text='Abbrechen', command=self.abort, state='disabled', style='Danger.TButton'); self.abort_button.pack(side='left', padx=6)
        self.button(actions, 'Protokoll', owner.show_log).pack(side='right')
        self.button(actions, 'Details', self.show_details).pack(side='right', padx=6)
        self.progress = ttk.Progressbar(box, mode='determinate', maximum=100); self.progress.grid(row=9, column=0, sticky='ew', pady=(8, 3))
        self.status = TextVar(owner.localizer, value='Bereit.'); ttk.Label(box, textvariable=self.status).grid(row=10, column=0, sticky='w')

    def button(self, parent, text, command, **kwargs):
        widget = ttk.Button(parent, text=text, command=command, **kwargs); self.controls.append((widget, 'normal')); return widget

    def selected(self):
        ids = self.tree.selection(); return [j for j in self.jobs if j.id in ids]

    def select_all(self, event=None):
        if not self.busy and not self.owner.busy:
            self.tree.selection_set(self.tree.get_children())
            self.selection_changed()
        return 'break'

    def selection_changed(self, event=None):
        selection = self.selected(); opts = selection[0].options if selection else self.defaults
        self.updating = True
        for key, var in self.variables.items():
            value = getattr(opts, key)
            mixed = selection and any(getattr(job.options, key) != value for job in selection)
            if mixed and not isinstance(var, tk.BooleanVar):
                var.set('')
            else:
                var.set(self.t(self.mappings[key][value]) if key in self.mappings else value)
        self.updating = False
        self.scope.set(f'Einstellungen für {len(selection)} ausgewählte Datei(en). Leere Auswahlfelder bedeuten gemischte Werte.' if selection else
                       'Einstellungen gelten für neu hinzugefügte Bilder.')
        if selection: self.detail.set(selection[0].detail.replace('\n', ' · ')[:220])
        self.sensitivity()

    def changed(self, key):
        if self.busy or self.updating: return
        raw = self.variables[key].get()
        try:
            value = next(k for k, v in self.mappings[key].items() if self.t(v) == raw) if key in self.mappings else int(raw) if key == 'size_pixels' else raw
            selection = self.selected()
            for opts in [j.options for j in selection] if selection else [self.defaults]:
                replace(opts, **{key: value}, long_edge=0).validate()
            if not selection:
                self.defaults = replace(self.defaults, **{key: value}, long_edge=0)
            for job in selection:
                job.options = replace(job.options, **{key: value}, long_edge=0); job.status = 'queued'; job.detail = 'Einstellungen geändert; erneut testen.'
            self.refresh(); self.selection_changed()
        except (ValueError, StopIteration) as error:
            messagebox.showerror(self.t('Bildeinstellungen'), self.t(str(error)), parent=self.root); self.selection_changed()

    def sensitivity(self):
        opts = self.selected()[0].options if self.selected() else self.defaults
        self.preview_button.configure(state='normal' if not self.busy and not self.owner.busy and len(self.selected()) == 1 else 'disabled')
        self.custom_size.grid() if opts.task == 'convert' and opts.size_mode == 'custom' else self.custom_size.grid_remove()
        self.size_entry.configure(state='normal' if opts.task == 'convert' and not self.busy else 'disabled')
        for key, combo in self.combos.items():
            enabled = opts.task == 'convert' or key == 'task'
            if key == 'method': enabled = enabled and opts.target == 'anaglyph'
            if key == 'quality': enabled = enabled and opts.format == 'jpeg'
            combo.configure(state='readonly' if enabled and not self.busy else 'disabled')

    def refresh(self):
        for job in self.jobs:
            values = (job.source.name, self.t(TASKS[job.options.task]), self.t(TARGETS[job.options.target]), self.t(STATUS[job.status]))
            if self.tree.exists(job.id): self.tree.item(job.id, values=values)
            else: self.tree.insert('', 'end', iid=job.id, values=values)

    def add_paths(self, paths, source_root=None):
        if self.busy or self.owner.busy: return
        existing = {str(j.source.resolve()).casefold() for j in self.jobs}
        for item in paths:
            path = Path(item).expanduser().resolve(); key = str(path).casefold()
            if path.suffix.lower() in EXTENSIONS and key not in existing:
                self.jobs.append(ImageJob(path, replace(self.defaults), source_root)); existing.add(key)
        self.refresh()

    def add_files(self):
        if self.busy: return
        paths = filedialog.askopenfilenames(parent=self.root, title=self.t('Bilder hinzufügen'), initialdir=self.input_folder,
            filetypes=[(self.t('Bilder'), ' '.join('*'+s for s in sorted(EXTENSIONS))), (self.t('Alle Dateien'), '*.*')])
        if paths: self.input_folder = str(Path(paths[0]).parent); self.add_paths(paths)

    def add_folder(self):
        if self.busy: return
        value = filedialog.askdirectory(parent=self.root, initialdir=self.input_folder)
        if value:
            root = Path(value).resolve(); self.input_folder = value; output = Path(self.output.get()).expanduser().resolve()
            paths = root.rglob('*') if self.recursive.get() else root.iterdir()
            self.add_paths(sorted(p for p in paths if p.is_file() and not p.is_relative_to(output)), root)

    def choose_output(self):
        value = filedialog.askdirectory(parent=self.root, initialdir=self.output.get())
        if value: self.output.set(value)

    def remove(self):
        if self.busy: return
        selected = self.tree.selection(); self.jobs = [j for j in self.jobs if j.id not in selected]
        for id_ in selected: self.tree.delete(id_)
        self.selection_changed()

    def load(self):
        value = filedialog.askopenfilename(parent=self.root, filetypes=[(self.t('Bildliste'), '*.json')])
        if value:
            try:
                loaded = load_images(Path(value))
                existing = {str(job.source.resolve()).casefold() for job in self.jobs}
                for job in loaded:
                    key = str(job.source.resolve()).casefold()
                    if key not in existing:
                        self.jobs.append(job); existing.add(key)
                self.refresh(); self.selection_changed()
            except (ValueError, TypeError, OSError) as error: messagebox.showerror(self.t('Bildliste'), self.t(str(error)), parent=self.root)

    def save(self):
        value = filedialog.asksaveasfilename(parent=self.root, defaultextension='.json', filetypes=[(self.t('Bildliste'), '*.json')])
        if value:
            try: save_images(Path(value), self.jobs)
            except OSError as error: messagebox.showerror(self.t('Bildliste'), self.t(str(error)), parent=self.root)

    def preset_menu(self):
        self.menu.delete(0, 'end')
        for child in self.menu.winfo_children(): child.destroy()
        load, delete = self.owner.dark_menu(self.menu), self.owner.dark_menu(self.menu)
        for name in sorted(self.presets, key=str.casefold):
            load.add_command(label=name, command=lambda n=name: self.apply_preset(n))
            delete.add_command(label=name, command=lambda n=name: self.delete_preset(n))
        if not self.presets:
            for menu in (load, delete): menu.add_command(label=self.t('Keine gespeicherten Voreinstellungen'), state='disabled')
        self.menu.add_cascade(label=self.t('Laden'), menu=load)
        self.menu.add_command(label=self.t('Speichern unter …'), command=self.save_preset)
        self.menu.add_cascade(label=self.t('Löschen'), menu=delete)

    def apply_preset(self, name):
        if self.busy: return
        selected = self.selected()
        if not selected: self.defaults = replace(self.presets[name])
        for job in selected: job.options = replace(self.presets[name]); job.status = 'queued'; job.detail = 'Voreinstellung geändert.'
        self.refresh(); self.selection_changed()

    def save_preset(self):
        self.owner.preset_dialog(self.store_preset, 'Bildvoreinstellung')

    def store_preset(self, name):
        name = validate_preset_name(name)
        selected = self.selected()
        options = selected[0].options if selected else self.defaults
        if any(job.options != options for job in selected):
            raise ValueError('Zum Speichern Dateien mit gleichen Einstellungen auswählen.')
        previous = self.presets
        self.presets = dict(previous, **{name: replace(options)})
        try: self.persist()
        except OSError:
            self.presets = previous
            raise
        self.status.set('Voreinstellung gespeichert: '+name)

    def delete_preset(self, name):
        if self.busy or self.owner.busy: return
        previous = self.presets
        self.presets = {key: value for key, value in previous.items() if key != name}
        try:
            self.persist(); self.status.set('Voreinstellung gelöscht: '+name)
        except OSError as error:
            self.presets = previous; self.status.set(str(error))

    def persist(self):
        write_json(app_root()/'image-settings.json', {'defaults': asdict(self.defaults), 'presets': {k: asdict(v) for k, v in self.presets.items()},
            'output_folder': self.output.get(), 'input_folder': self.input_folder, 'recursive': self.recursive.get()})

    def show_details(self):
        selected = self.selected()
        if not selected: return
        dialog = tk.Toplevel(self.root); dialog.title('Bilddetails'); dialog.geometry('720x420'); schedule_dark_titlebar(dialog)
        text = tk.Text(dialog, wrap='word', background=SECONDARY_BG, foreground=TEXT, insertbackground=TEXT)
        scroll = ttk.Scrollbar(dialog, command=text.yview); scroll.pack(side='right', fill='y')
        text.pack(fill='both', expand=True); text.configure(yscrollcommand=scroll.set)
        self.owner.localizer.text(text, '\n\n'.join(str(j.source)+'\n'+j.detail for j in selected))
        self.owner.localizer.apply()

    def set_busy(self, value):
        self.busy = value
        self.owner.language_sensitivity()
        self.owner.notebook.tab(self.owner.video_tab, state='disabled' if value else 'normal')
        for widget, normal in self.controls: widget.configure(state='disabled' if value else normal)
        self.abort_button.configure(state='normal' if value else 'disabled'); self.sensitivity()

    def abort(self):
        if self.busy: self.cancel.set(); self.status.set('Abbruch angefordert …'); self.abort_button.configure(state='disabled')

    def run(self, convert):
        if self.busy or self.owner.busy or not self.jobs: return
        snapshot = [ImageJob(j.source, replace(j.options), j.source_root, j.id) for j in self.jobs if j.status != 'completed']
        if not snapshot: self.status.set('Alle Bilder sind bereits fertig.'); return
        output = Path(self.output.get()).expanduser().resolve()
        if not self.output.get().strip(): messagebox.showerror(self.t('Bilder'), self.t('Ausgabeordner auswählen.'), parent=self.root); return
        self.cancel.clear(); self.set_busy(True); self.progress['value'] = 0; self.status.set('Bildstapel prüfen …')
        def worker():
            try:
                tools = Toolchain.find(); prepared = plans(snapshot, output, self.cancel)
                for plan in prepared: self.events.put(('job', (plan.sources, 'ready', plan.summary)))
                if convert:
                    log = new_run_log(app_root()); self.owner.events.put(('log', 'Bildprotokoll: '+str(log)))
                    started = time.monotonic()
                    for number, plan in enumerate(prepared, 1):
                        if self.cancel.is_set(): raise Cancelled()
                        self.events.put(('job', (plan.sources, 'running', plan.summary)))
                        execute_image(tools, plan, self.cancel, lambda kind, data: self.events.put((kind, data)), log)
                        self.events.put(('job', (plan.sources, 'completed', plan.summary)))
                        left = (time.monotonic()-started)/number*(len(prepared)-number)
                        self.events.put(('progress', (number/len(prepared)*100, f'{number}/{len(prepared)} · Restzeit etwa {left:.0f} s')))
                    self.owner.events.put(('sound', None))
                self.events.put(('status', 'Bildstapel abgeschlossen.' if convert else 'Prüfung bestanden; bereit für Start.'))
            except Cancelled: self.events.put(('error', ('cancelled', 'Bildstapel abgebrochen.')))
            except Exception as error: self.events.put(('error', ('failed' if convert else 'blocked', str(error))))
            finally: self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def preview(self):
        if self.busy or self.owner.busy: return
        selected = self.selected()
        if len(selected) != 1:
            messagebox.showinfo(self.t('Kontrollbild'), self.t('Für das Kontrollbild genau eine Datei auswählen.'), parent=self.root)
            return
        job = selected[0]
        self.cancel.clear(); self.set_busy(True); self.status.set('Kontrollbild berechnen …')
        def worker():
            try:
                with tempfile.TemporaryDirectory(prefix='.transcora-preview-', dir=app_root()) as value:
                    folder = Path(value); opts = replace(job.options, metadata=False)
                    plan = plans([ImageJob(job.source, opts)], folder, self.cancel)[0]
                    execute_image(Toolchain.find(), plan, self.cancel, lambda *a: None, folder/'preview.log')
                    images = []
                    for file in plan.outputs:
                        with Image.open(file) as image:
                            image = ImageOps.exif_transpose(image); images.append(image.copy())
                    self.events.put(('preview', images))
            except Exception as error: self.events.put(('status', 'Kontrollbild: '+str(error)))
            finally: self.events.put(('done', None))
        from PIL import ImageOps
        threading.Thread(target=worker, daemon=True).start()

    def poll(self):
        try:
            while True:
                kind, data = self.events.get_nowait()
                if kind == 'job':
                    sources, status, detail = data
                    for job in self.jobs:
                        if job.source.resolve() in sources: job.status = status; job.detail = detail
                    self.refresh(); self.detail.set(detail.replace('\n', ' · ')[:220])
                elif kind == 'error':
                    status, detail = data; self.status.set(detail); self.owner.log_lines.append(detail)
                    for job in self.jobs:
                        if job.status in {'running', 'queued', 'ready'}: job.status = status; job.detail = detail
                    self.refresh()
                elif kind in {'status', 'phase'}: self.status.set(data)
                elif kind == 'progress': self.progress['value'] = data[0]; self.status.set(data[1])
                elif kind == 'preview':
                    from .image_view import ImageView
                    if self.preview_dialog is not None and self.preview_dialog.winfo_exists():
                        self.preview_dialog.destroy()
                    dialog = tk.Toplevel(self.root, background=SECONDARY_BG)
                    self.preview_dialog = dialog
                    dialog.title('Bildkontrolle · L/R-Reihenfolge und Details prüfen')
                    dialog.geometry('820x600'); dialog.minsize(500, 360); schedule_dark_titlebar(dialog)
                    viewer = ImageView(dialog, self.owner.localizer)
                    viewer.pack(fill='both', expand=True, padx=10, pady=10)
                    viewer.set_images(data)
                    ttk.Label(dialog, text='Gleiche Exportgröße und Kompression wie im Export.', foreground=MUTED).pack(anchor='w', padx=10, pady=(0, 10))
                    self.owner.localizer.apply()
                    self.status.set('Kontrollbild bereit.')
                elif kind == 'done':
                    self.set_busy(False)
                    if self.owner.closing: self.owner.finish_close(); return True
        except queue.Empty: pass
