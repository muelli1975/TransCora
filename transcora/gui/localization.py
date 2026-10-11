"""Keep German source text separately from translated widget presentation."""
import tkinter as tk
from tkinter import ttk
import weakref
import customtkinter as ctk
from transcora.i18n import translate


class TextVar(tk.StringVar):
    def __init__(self, localizer, value=''):
        self.localizer = localizer
        self.source = str(value)
        super().__init__(master=localizer.root, value=localizer.t(value))
        localizer.variables[id(self)] = self

    def set(self, value):
        self.source = str(value)
        super().set(self.localizer.t(value))

    def render(self):
        value = self.localizer.t(self.source)
        if self.get() != value:
            super().set(value)


class Localizer:
    def __init__(self, root, owner):
        self.root, self.owner = root, owner
        self.variables = weakref.WeakValueDictionary()
        self.sources = weakref.WeakKeyDictionary()
        self.bodies = weakref.WeakKeyDictionary()

    def t(self, text):
        return translate(text, self.owner.language)

    def text(self, widget, source):
        self.bodies[widget] = source
        widget.configure(state='normal')
        widget.delete('1.0', 'end')
        widget.insert('1.0', self.t(source))
        widget.configure(state='disabled')

    def apply(self):
        for var in list(self.variables.values()):
            var.render()
        def render(widget):
            saved = self.sources.setdefault(widget, {})
            def option(key, current, setter):
                source, previous = saved.get(key, (current, None))
                if current != previous:
                    source = current
                value = self.t(source)
                if value != current:
                    setter(value)
                saved[key] = (source, value)
            if isinstance(widget, ctk.CTkCheckBox):
                option('text', str(widget.cget('text')), lambda value: widget.configure(text=value))
            elif isinstance(widget, (ttk.Label, ttk.Button, ttk.Checkbutton, ttk.Radiobutton, ttk.Menubutton, ttk.LabelFrame)):
                if not ('textvariable' in widget.keys() and widget.cget('textvariable')):
                    option('text', str(widget.cget('text')), lambda value: widget.configure(text=value))
            if isinstance(widget, tk.Toplevel):
                from .theme import APP_BG
                widget.configure(background=APP_BG)
                option('title', widget.title(), widget.title)
            if isinstance(widget, ttk.Notebook):
                for tab in widget.tabs():
                    option('tab'+tab, widget.tab(tab, 'text'), lambda value, tab=tab: widget.tab(tab, text=value))
            if isinstance(widget, ttk.Treeview):
                for column in widget.cget('columns'):
                    option('heading'+column, widget.heading(column, 'text'), lambda value, column=column: widget.heading(column, text=value))
            for child in widget.winfo_children():
                render(child)
        render(self.root)
        for widget, source in list(self.bodies.items()):
            if widget.winfo_exists() and widget.get('1.0', 'end-1c') != self.t(source):
                self.text(widget, source)
