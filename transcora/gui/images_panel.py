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
from PIL import Image

from transcora.core.images import (ImageJob, ImageOptions, EXTENSIONS, TASKS, LAYOUTS, TARGETS, FORMATS,
    plans, execute_image, save_images, load_images, SIZES, SIZE_EDGES, image_methods)
from transcora.core.engine import Cancelled
from transcora.core.model import app_root, ROW_ORDERS
from transcora.core.storage import write_json, new_run_log, validate_preset_name
from transcora.core.toolchain import Toolchain
from transcora.core.journal import Journal, Completion, request, restore, processing_text
from .theme import checkbox, set_control_state, GOLD_LIGHT, MUTED, SECONDARY_BG, TEXT, APP_BG
from .native import schedule_dark_titlebar
from .localization import TextVar
from .settings_area import SettingsArea, section, CurrentFile
from .file_list import FileListSorter, remove_entries, completed_button

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
        self.tree = ttk.Treeview(holder, columns=('file', 'task', 'target', 'status', 'processing'), show='headings', height=8, selectmode='extended')
        for key, title, width in [('file', 'Datei', 260), ('task', 'Aufgabe', 155), ('target', 'Ziel', 185), ('status', 'Status', 80), ('processing', 'Bearbeitungszeit', 126)]:
            self.tree.heading(key, text=title); self.tree.column(key, width=width, stretch=key == 'file', minwidth=120 if key == 'file' else width)
        self.tree.grid(row=0, column=0, sticky='nsew'); scroll = ttk.Scrollbar(holder, command=self.tree.yview)
        scroll.grid(row=0, column=1, sticky='ns'); self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind('<<TreeviewSelect>>', self.selection_changed)
        self.sorter = FileListSorter(self,dict(file='Datei',task='Aufgabe',target='Ziel',status='Status',processing='Bearbeitungszeit'))
        self.tree.bind('<Control-a>', self.select_all)
        self.tree.bind('<Control-A>', self.select_all)
        if self.tree.tk.call('tk', 'windowingsystem') == 'aqua':
            self.tree.bind('<Command-a>', self.select_all)
            self.tree.bind('<Command-A>', self.select_all)
        self.tree.bind('<Delete>', lambda event: self.remove() if not self.busy else None)
        self.scope = TextVar(owner.localizer, value='Vorgaben für neue Dateien')
        scope = ttk.Frame(box); scope.grid(row=3,column=0,sticky='ew',pady=(6,4))
        ttk.Label(scope,textvariable=self.scope,foreground=MUTED).pack(side='left')
        self.reset_button = self.button(scope,'Standardeinstellungen',self.reset_defaults)
        self.reset_button.pack(side='right')
        self.remove_completed_button = self.button(scope, 'Fertige entfernen', self.remove_completed)
        self.remove_completed_button.pack(side='right', padx=(0, 6))
        completed_button(self)
        self.settings_area = SettingsArea(box)
        fields = self.settings_area.body
        _, source_fields = section(fields,0,'Quelle')
        _, output_fields = section(fields,1,'Ausgabe')
        _, format_fields = section(fields,2,'Format')
        self.advanced_section, advanced = section(fields,3,'Erweitert')
        self.advanced_section.grid_remove()
        self.settings_area.advanced = self.advanced_section
        _, save_fields = section(fields,4,'Speichern')
        self.option_frames = {}
        self.mappings = {'task': TASKS, 'layout': LAYOUTS, 'target': TARGETS, 'format': FORMATS,
                         'method': {k: v['label'] for k, v in image_methods().items()}, 'quality': {90: '90 · 4:4:4', 95: '95 · 4:4:4'}}
        self.variables = {}; self.combos = {}
        for row, keys in enumerate([('task', 'layout', 'target'), ('format', 'method', 'quality')]):
            for col, key in enumerate(keys):
                locations = {'task':(source_fields,0,2),'layout':(source_fields,0,0),
                             'target':(output_fields,0,0),'method':(output_fields,1,0),
                             'format':(format_fields,0,0),'quality':(format_fields,0,1)}
                parent,row,col = locations[key]
                cell = ttk.Frame(parent); self.option_frames[key] = cell
                cell.grid(row=row, column=col, sticky='ew', padx=(0, 8), pady=3)
                label = {'task': 'Aufgabe', 'layout': 'Quelllayout', 'target': 'Ziel', 'format': 'Dateiformat',
                         'method': 'Anaglyphenverfahren', 'quality': 'JPEG-Qualität'}[key]
                ttk.Label(cell, text=label).pack(anchor='w')
                var = tk.StringVar(value=self.t(self.mappings[key][getattr(self.defaults, key)])); self.variables[key] = var
                combo = ttk.Combobox(cell, textvariable=var, values=[self.t(v) for v in self.mappings[key].values()], state='readonly', width=22)
                combo.pack(fill='x'); combo.bind('<<ComboboxSelected>>', lambda e, k=key: self.changed(k))
                self.combos[key] = combo; self.controls.append((combo, 'readonly'))
        for col, key, label in [(0, 'swap', 'L/R tauschen'), (1, 'metadata', 'Metadaten übernehmen')]:
            var = tk.BooleanVar(value=getattr(self.defaults, key)); self.variables[key] = var
            check = checkbox(source_fields if key == 'swap' else advanced, text=label, variable=var, command=lambda k=key: self.changed(k))
            check.grid(row=0,column=1 if key=='swap' else 0,sticky='sw',pady=5); self.controls.append((check, 'normal'))
            self.combos[key] = check
        size = ttk.Frame(output_fields); size.grid(row=0, column=1, sticky='ew', padx=(0, 8))
        ttk.Label(size, text='Ausgabegröße').pack(anchor='w')
        self.mappings['size_mode'] = SIZES; self.mappings['size_edge'] = SIZE_EDGES
        self.variables['size_mode'] = tk.StringVar(value=self.t(SIZES[self.defaults.size_mode]))
        size_combo = ttk.Combobox(size, textvariable=self.variables['size_mode'], values=[self.t(v) for v in SIZES.values()], state='readonly')
        size_combo.pack(fill='x'); size_combo.bind('<<ComboboxSelected>>', lambda e: self.changed('size_mode'))
        self.combos['size_mode'] = size_combo; self.controls.append((size_combo, 'readonly'))
        self.dimensions = ttk.Frame(size); self.dimensions.pack(fill='x',pady=(4,0))
        self.dimension_values = [tk.StringVar(),tk.StringVar()]
        for i,var in enumerate(self.dimension_values):
            if i: ttk.Label(self.dimensions,text='×').pack(side='left',padx=4)
            ttk.Entry(self.dimensions,textvariable=var,width=7,state='disabled').pack(side='left')
        ttk.Label(self.dimensions,text='px').pack(side='left',padx=4)
        self.custom_size = ttk.Frame(size)
        self.custom_size.pack(fill='x', pady=(4, 0))
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
        self.screen_fields = ttk.Frame(size)
        self.mappings['row_first'] = ROW_ORDERS
        for key in ('screen_width','screen_height'):
            if key=='screen_height': ttk.Label(self.screen_fields,text='×').pack(side='left',padx=4)
            self.variables[key] = tk.StringVar(value=str(getattr(self.defaults,key)))
            entry = ttk.Entry(self.screen_fields,textvariable=self.variables[key],width=7)
            entry.pack(side='left'); self.combos[key]=entry; self.controls.append((entry,'normal'))
            for event in ('<FocusOut>','<Return>'):entry.bind(event,lambda e,k=key:self.changed(k))
        ttk.Label(self.screen_fields,text='px').pack(side='left',padx=4)
        self.row_frame = ttk.Frame(output_fields); self.row_frame.grid(row=1,column=0,sticky='ew',padx=(0,8))
        ttk.Label(self.row_frame,text='Erste Bildschirmzeile').pack(anchor='w')
        self.variables['row_first'] = tk.StringVar(value=self.t(ROW_ORDERS[self.defaults.row_first]))
        order = ttk.Combobox(self.row_frame,textvariable=self.variables['row_first'],values=[self.t(v) for v in ROW_ORDERS.values()],state='readonly')
        order.pack(fill='x'); order.bind('<<ComboboxSelected>>',lambda e:self.changed('row_first'))
        self.combos['row_first']=order; self.controls.append((order,'readonly'))
        row = ttk.Frame(save_fields); row.grid(row=0, column=0,columnspan=3, sticky='ew', pady=(0,8)); row.columnconfigure(1, weight=1)
        ttk.Label(row, text='Ausgabeordner').grid(row=0, column=0, padx=(0, 8))
        entry = ttk.Entry(row, textvariable=self.output); entry.grid(row=0, column=1, sticky='ew'); self.controls.append((entry, 'normal'))
        self.button(row, 'Auswählen', self.choose_output).grid(row=0, column=2, padx=(6, 0))
        check = checkbox(row, text='Unterordner mitverarbeiten', variable=self.recursive)
        check.grid(row=0,column=3,sticky='w',padx=(10,0)); self.controls.append((check, 'normal'))
        self.detail = TextVar(owner.localizer, value='Dateien hinzufügen oder eine gespeicherte Liste laden.')
        ttk.Label(save_fields,text='Dateinamenszusatz folgt dem gewählten Ziel.',foreground=MUTED).grid(row=1,column=0,columnspan=3,sticky='w')
        detail_frame = ttk.Frame(box,style='Bordered.TFrame',padding=1)
        detail_frame.grid(row=7,column=0,sticky='ew'); detail_frame.columnconfigure(0,weight=1)
        self.detail_text = tk.Text(detail_frame,height=4,width=1,wrap='word',background=APP_BG,foreground=MUTED,borderwidth=0,highlightthickness=0,padx=8,pady=6,state='disabled')
        self.detail_text.grid(row=0,column=0,sticky='ew')
        scroll = ttk.Scrollbar(detail_frame,command=self.detail_text.yview); scroll.grid(row=0,column=1,sticky='ns')
        self.detail_text.configure(yscrollcommand=scroll.set)
        def show_detail(*args):
            self.detail_text.configure(state='normal'); self.detail_text.delete('1.0','end')
            self.detail_text.insert('end',self.detail.get()); self.detail_text.configure(state='disabled')
        self.detail.trace_add('write',show_detail); show_detail()
        actions = ttk.Frame(box); actions.grid(row=13, column=0, sticky='ew',pady=(8,0))
        self.advanced_button = self.button(actions,'Erweitert ▸',self.toggle_advanced)
        self.advanced_button.pack(side='left')
        self.preview_button = self.button(actions, 'Kontrollbild', self.preview)
        self.preview_button.pack(side='left', padx=6)
        self.preview_dialog = None
        self.abort_button = ttk.Button(actions, text='Abbrechen', command=self.abort, state='disabled', style='Danger.TButton'); self.abort_button.pack(side='right', padx=6)
        self.button(actions, 'Start', lambda: self.run(True), style='Primary.TButton').pack(side='right',padx=5)
        self.button(actions, 'Testen', lambda: self.run(False), style='Primary.TButton').pack(side='right')
        self.button(actions, 'Log', owner.show_log).pack(side='left')
        self.button(actions, 'Details', self.show_details).pack(side='left', padx=6)
        self.progress = ttk.Progressbar(box, mode='determinate', maximum=100); self.progress.grid(row=11, column=0, sticky='ew', pady=(8, 3))
        self.status = TextVar(owner.localizer, value='Bereit.'); ttk.Label(box, textvariable=self.status).grid(row=10, column=0, sticky='ew')
        self.current_file = CurrentFile(box,owner.localizer,9)
        self.output.trace_add('write', self.output_changed)

    def restore_result(self, job):
        return restore(job, Path(self.output.get()).expanduser(), 'image', self.owner.journal_notice)

    def output_changed(self, *args):
        if self.busy or self.owner.busy:
            return
        for job in self.jobs:
            job.result = None
            job.status = 'queued'
            job.detail = 'Ausgabeziel geändert; erneut prüfen.'
            self.restore_result(job)
        self.refresh()
        self.selection_changed()

    def reset_defaults(self):
        if self.busy or self.owner.busy:return
        self.defaults=ImageOptions()
        self.tree.selection_remove(*self.tree.selection()); self.selection_changed()
        self.status.set('Standardeinstellungen für neue Dateien wiederhergestellt. Bestehende Jobs behalten ihre Einstellungen.')

    def toggle_advanced(self):
        if self.busy or self.owner.busy:return
        if self.advanced_section.winfo_ismapped():
            self.advanced_section.grid_remove(); self.advanced_button.configure(text='Erweitert ▸')
            self.settings_area.canvas.yview_moveto(0)
        else:
            self.advanced_section.grid(); self.advanced_button.configure(text='Erweitert ▾')
            self.settings_area.show_end(self.combos["metadata"])

    def refresh_dimensions(self):
        from transcora.core.images import ImagePlan, image_graph
        from transcora.core.naming import filename_layout
        values=[]
        for job in self.selected():
            try:
                with Image.open(job.source) as image:
                    size=image.size[::-1] if image.getexif().get(274,1) in (5,6,7,8) else image.size
                    mpo=image.format=='MPO'
                opts=job.options
                if opts.task=='mpo':out=size
                else:
                    hint=filename_layout(job.source.stem)
                    layout='full_sbs' if mpo else (hint[0] if opts.layout=='auto' and hint else opts.layout)
                    if layout=='auto':layout='full_sbs' if job.source.suffix.lower() in {'.jps','.pns'} else 'mono'
                    packed=(size[0]*2,size[1]) if mpo else size
                    plan=ImagePlan((job.source,),(),opts,layout,opts.swap,packed,(),())
                    _,out=image_graph(plan)
                    if opts.target=='split':out=(out[0]//2,out[1])
                values.append(out)
            except (ValueError,OSError,KeyError):values.append(None)
        for i,var in enumerate(self.dimension_values):
            numbers=[v[i] if v else None for v in values]
            var.set(str(numbers[0]) if numbers and numbers[0] is not None and len(set(numbers))==1 else '')

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
        self.scope.set((f'Für {len(selection)} ausgewählte Datei(en)' + (' · Gemischte Werte' if any(any(getattr(j.options,k)!=getattr(selection[0].options,k) for j in selection[1:]) for k in self.variables) else '')) if selection else
                       'Vorgaben für neue Dateien')
        if selection: self.detail.set(selection[0].detail.replace('\n', ' · ')[:220])
        self.sensitivity()

    def changed(self, key):
        if self.busy or self.updating: return
        raw = self.variables[key].get()
        try:
            value = next(k for k, v in self.mappings[key].items() if self.t(v) == raw) if key in self.mappings else int(raw) if key in {'size_pixels', 'screen_width', 'screen_height'} else raw
            selection = self.selected()
            def updated(opts):
                changes = {key: value, 'long_edge': 0}
                if key == 'target' and value == 'row_interleaved':
                    changes['format'] = 'png'
                return replace(opts, **changes)
            for opts in [j.options for j in selection] if selection else [self.defaults]:
                updated(opts).validate()
            if not selection:
                self.defaults = updated(self.defaults)
            for job in selection:
                options = updated(job.options)
                if options == job.options:
                    continue
                job.options = options; job.status = 'queued'; job.detail = 'Einstellungen geändert; erneut testen.'
                job.result = None
                self.restore_result(job)
            self.refresh(); self.selection_changed()
        except (ValueError, StopIteration) as error:
            if key in {'size_pixels', 'screen_width', 'screen_height'}:
                self.status.set(str(error))
                (self.size_entry if key == 'size_pixels' else self.combos[key]).focus_set()
                return
            messagebox.showerror(self.t('Bildeinstellungen'), self.t(str(error)), parent=self.root); self.selection_changed()

    def commit_entries(self):
        pending = {key: self.variables[key].get() for key in ('size_pixels', 'screen_width', 'screen_height')}
        for key, widget in [('size_pixels', self.size_entry), ('screen_width', self.combos['screen_width']),
                            ('screen_height', self.combos['screen_height'])]:
            if str(widget.cget('state')) == 'disabled': continue
            raw = pending[key]
            selection = self.selected()
            values = [getattr(j.options, key) for j in selection] if selection else [getattr(self.defaults, key)]
            if not raw and len(set(values)) > 1: continue
            try:
                value = int(raw)
                for job in selection or [None]:
                    replace(job.options if job else self.defaults, **{key: value}).validate()
            except ValueError as error:
                self.status.set(str(error))
                widget.focus_set()
                return False
            if any(v != value for v in values):
                self.variables[key].set(raw)
                self.changed(key)
        return True

    def sensitivity(self):
        opts = self.selected()[0].options if self.selected() else self.defaults
        rows = opts.task == 'convert' and opts.target == 'row_interleaved'
        self.screen_fields.pack(fill='x',pady=(4,0)) if rows else self.screen_fields.pack_forget()
        self.dimensions.pack_forget() if rows else self.dimensions.pack(fill='x',pady=(4,0))
        self.row_frame.grid() if rows else self.row_frame.grid_remove()
        self.option_frames['method'].grid() if opts.task=='convert' and opts.target=='anaglyph' else self.option_frames['method'].grid_remove()
        self.option_frames['quality'].grid() if opts.format=='jpeg' and opts.task=='convert' else self.option_frames['quality'].grid_remove()
        self.preview_button.configure(state='normal' if not self.busy and not self.owner.busy and len(self.selected()) == 1 else 'disabled')
        completed_button(self)
        self.custom_size.pack(fill='x', pady=(4, 0)) if opts.task == 'convert' and opts.size_mode == 'custom' and not rows else self.custom_size.pack_forget()
        self.size_entry.configure(state='normal' if opts.task == 'convert' and opts.size_mode == 'custom' and not rows and not self.busy else 'disabled')
        for key, combo in self.combos.items():
            enabled = opts.task == 'convert' or key == 'task'
            if key == 'method': enabled = enabled and opts.target == 'anaglyph'
            if key == 'quality': enabled = enabled and opts.format == 'jpeg'
            if key == 'row_first': enabled = rows
            if key in {'screen_width', 'screen_height'}: enabled = rows
            if key in {'size_mode', 'size_edge'}: enabled = enabled and not rows
            set_control_state(combo, ('normal' if key in {'swap', 'metadata', 'screen_width', 'screen_height'} else 'readonly') if enabled and not self.busy else 'disabled')
        if rows or opts.task=='mpo':
            self.variables['size_mode'].set(self.t('Monitorauflösung' if rows else 'Original'))
        self.refresh_dimensions()
        self.settings_area.layout()
        if rows:
            self.detail.set('Polfilter: Exakte Monitorauflösung, Vollbild ohne Skalierung. PNG erhält die Farbzeilen verlustfrei.')
        elif not self.selected():
            self.detail.set('MPO-Teilung erhält die komprimierten Bilddaten unverändert.' if opts.task == 'mpo' else
                            'Dateien hinzufügen oder eine gespeicherte Liste laden.')

    def refresh(self):
        for job in self.jobs:
            values = (job.source.name, self.t(TASKS[job.options.task]), self.t(TARGETS[job.options.target]), self.t(STATUS[job.status]), processing_text(job.result))
            if self.tree.exists(job.id): self.tree.item(job.id, values=values)
            else: self.tree.insert('', 'end', iid=job.id, values=values)
        self.sorter.refresh()
        completed_button(self)

    def add_paths(self, paths, source_root=None):
        if self.busy or self.owner.busy: return
        existing = {str(j.source.resolve()).casefold() for j in self.jobs}
        for item in paths:
            path = Path(item).expanduser().resolve(); key = str(path).casefold()
            if path.suffix.lower() in EXTENSIONS and key not in existing:
                job = ImageJob(path, replace(self.defaults), source_root)
                self.restore_result(job)
                self.jobs.append(job); existing.add(key)
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
            excluded_output = output if output != root and output.is_relative_to(root) else None
            paths = root.rglob('*') if self.recursive.get() else root.iterdir()
            self.add_paths(sorted(p for p in paths if p.is_file() and (excluded_output is None or not p.is_relative_to(excluded_output))), root)

    def choose_output(self):
        value = filedialog.askdirectory(parent=self.root, initialdir=self.output.get())
        if value: self.output.set(value)

    def remove(self):
        if self.sorter.busy(): return
        remove_entries(self, self.tree.selection())

    def remove_completed(self):
        if self.sorter.busy(): return
        remove_entries(self, [j.id for j in self.jobs if j.status == 'completed'])

    def load(self):
        value = filedialog.askopenfilename(parent=self.root, filetypes=[(self.t('Bildliste'), '*.json')])
        if value:
            try:
                loaded = load_images(Path(value))
                existing = {str(job.source.resolve()).casefold() for job in self.jobs}
                for job in loaded:
                    key = str(job.source.resolve()).casefold()
                    if key not in existing:
                        self.restore_result(job)
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
        for job in selected:
            job.options = replace(self.presets[name]); job.status = 'queued'; job.detail = 'Voreinstellung geändert.'
            job.result = None
            self.restore_result(job)
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
        for widget, normal in self.controls: set_control_state(widget, 'disabled' if value else normal)
        self.abort_button.configure(state='normal' if value else 'disabled'); self.sensitivity()
        if not value:self.sorter.refresh()

    def abort(self):
        if self.busy: self.cancel.set(); self.status.set('Abbruch angefordert …'); self.abort_button.configure(state='disabled')

    def run(self, convert):
        if self.busy or self.owner.busy or not self.jobs: return
        if not self.commit_entries(): return
        for job in self.jobs:
            self.restore_result(job)
        self.refresh()
        snapshot = [ImageJob(j.source, replace(j.options), j.source_root, j.id) for j in self.jobs if j.status != 'completed']
        if not snapshot: self.status.set('Alle Bilder sind bereits fertig.'); return
        output = Path(self.output.get()).expanduser().resolve()
        if not self.output.get().strip(): messagebox.showerror(self.t('Bilder'), self.t('Ausgabeordner auswählen.'), parent=self.root); return
        self.cancel.clear(); self.set_busy(True); self.progress['value'] = 0; self.status.set('Bildstapel prüfen …')
        def worker():
            try:
                prepared = []; reserved = set(); receipts = {}; blocked = failed = completed = journal_failures = 0
                for job in snapshot:
                    if self.cancel.is_set(): raise Cancelled()
                    try:
                        try:
                            receipts[job.source.resolve()] = request(job, 'image') if convert else None
                        except (OSError, ValueError):
                            receipts[job.source.resolve()] = None
                        plan = plans([job], output, self.cancel, reserved=reserved)[0]
                    except Cancelled:
                        raise
                    except Exception as error:
                        blocked += 1
                        self.events.put(('job', ((job.source.resolve(),), 'blocked', str(error))))
                        self.owner.events.put(('log', job.source.name+': '+str(error)))
                        continue
                    prepared.append(plan)
                    self.events.put(('job', (plan.sources, 'ready', plan.summary)))
                if convert and prepared:
                    log = new_run_log(app_root()); self.owner.events.put(('log', 'Bildprotokoll: '+str(log)))
                    started = time.monotonic(); tools = None
                    for number, plan in enumerate(prepared, 1):
                        if self.cancel.is_set(): raise Cancelled()
                        self.events.put(('current',(plan.sources[0].name,number,len(prepared))))
                        self.events.put(('job', (plan.sources, 'running', plan.summary)))
                        try:
                            file_started = time.monotonic()
                            if plan.options.task != 'mpo' and tools is None:
                                tools = Toolchain.find()
                            execute_image(tools, plan, self.cancel, lambda kind, data: self.events.put((kind, data)), log)
                        except Cancelled:
                            raise
                        except Exception as error:
                            failed += 1
                            self.events.put(('job', (plan.sources, 'failed', str(error))))
                            self.owner.events.put(('log', plan.sources[0].name+': '+str(error)))
                        else:
                            elapsed = max(0, time.monotonic() - file_started)
                            completion = Completion(plan.outputs, elapsed, {})
                            try:
                                if receipts[plan.sources[0]] is None:
                                    raise ValueError('Quelldaten für den Journalnachweis fehlen.')
                                completion = Journal(output).complete(receipts[plan.sources[0]], plan.outputs, elapsed,
                                    effective={'options': asdict(plan.options), 'layout': plan.layout, 'swap': plan.swap, 'size': plan.size},
                                    tools={'image': 'Pillow ' + Image.__version__})
                            except (OSError, ValueError) as error:
                                journal_failures += 1
                                self.owner.events.put(('log', 'Journal nicht gespeichert: ' + str(error)))
                                self.events.put(('status', 'Ausgabe fertig; Journal nicht gespeichert.'))
                            self.events.put(('result', (plan.sources, completion)))
                            completed += 1
                            self.events.put(('job', (plan.sources, 'completed', plan.summary)))
                        left = (time.monotonic()-started)/number*(len(prepared)-number)
                        self.events.put(('progress', (number/len(prepared)*100, f'{number}/{len(prepared)} · Restzeit etwa {left:.0f} s')))
                    if completed: self.owner.events.put(('sound', None))
                summary = (f'Bildstapel abgeschlossen: {completed} erfolgreich · {failed} Fehler · {blocked} blockiert.'
                           if convert else f'Bildprüfung abgeschlossen: {len(prepared)} bereit · {blocked} blockiert.')
                if journal_failures:
                    summary += ' · ' + self.t('Journal nicht gespeichert: ') + str(journal_failures)
                self.events.put(('status', summary))
            except Cancelled: self.events.put(('error', ('cancelled', 'Bildstapel abgebrochen.')))
            except Exception as error: self.events.put(('error', ('failed' if convert else 'blocked', str(error))))
            finally: self.events.put(('done', None))
        threading.Thread(target=worker, daemon=True).start()

    def preview(self):
        if self.busy or self.owner.busy: return
        if not self.commit_entries(): return
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
                elif kind == 'result':
                    sources, completion = data
                    for job in self.jobs:
                        if job.source.resolve() in sources:
                            job.result = completion
                elif kind == 'error':
                    status, detail = data; self.status.set(detail); self.owner.log_lines.append(detail)
                    for job in self.jobs:
                        if job.status in {'running', 'queued', 'ready'}: job.status = status; job.detail = detail
                    self.refresh()
                elif kind == 'current': self.current_file.set(*data)
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
