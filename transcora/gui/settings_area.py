"""Shared compact settings and a viewport that preserves the job list and footer."""
import tkinter as tk
from tkinter import ttk, font
from .theme import APP_BG, GOLD_LIGHT, MUTED


class SettingsArea:
    def __init__(self, parent):
        self.frame = ttk.Frame(parent)
        self.frame.grid(row=4, column=0, sticky='ew', pady=(0, 8))
        self.frame.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(self.frame, height=240, width=1, background=APP_BG,
                                highlightthickness=0, borderwidth=0)
        self.canvas.grid(row=0, column=0, sticky='ew')
        self.scroll = ttk.Scrollbar(self.frame, command=self.canvas.yview)
        self.scroll.grid(row=0, column=1, sticky='ns')
        self.canvas.configure(yscrollcommand=self.scroll.set)
        self.body = ttk.Frame(self.canvas)
        self.window = self.canvas.create_window(0, 0, window=self.body, anchor='nw')
        self.body.columnconfigure(0, weight=1)
        self.canvas.bind('<Configure>', self.layout)
        self.body.bind('<Configure>', self.layout)
        self.parent = parent
        parent.rowconfigure(2, minsize=140)
        self.pending = False
        self.closed = False
        self.callback = None
        parent.bind('<Destroy>', self.destroy, add='+')
        parent.winfo_toplevel().bind('<Configure>', self.schedule, add='+')
        parent.bind('<Configure>', self.schedule, add='+')
        parent.bind('<Map>', self.schedule, add='+')
        parent.winfo_toplevel().bind('<MouseWheel>', self.wheel, add='+')
        parent.winfo_toplevel().bind('<FocusIn>', self.focus, add='+')
        self.schedule()

    def destroy(self,event):
        if event.widget is self.parent:
            self.closed=True
            if self.callback:
                self.parent.after_cancel(self.callback)

    def schedule(self, event=None):
        if self.closed or (event and event.widget not in (self.parent,self.parent.winfo_toplevel()) and getattr(event.widget,'master',None) is not self.parent):
            return
        if not self.pending:
            self.pending = True
            self.callback = self.parent.after_idle(self.fit)

    def fit(self):
        self.pending = False
        if self.closed or not self.parent.winfo_exists():
            return
        other = 20
        for widget in self.parent.grid_slaves():
            info = widget.grid_info()
            if int(info['row']) in (2, 4):
                continue
            value = info.get('pady', 0)
            pad = value if isinstance(value, tuple) else self.parent.tk.splitlist(str(value))
            other += widget.winfo_reqheight()+sum(int(v) for v in pad)*(2 if len(pad)==1 else 1)
        height = max(90, min(290, self.parent.winfo_height()-other-140-8))
        if abs(self.canvas.winfo_reqheight()-height)>1:
            self.canvas.configure(height=height)
        self.canvas.grid()
        self.layout()

    def layout(self, event=None):
        self.canvas.grid()
        self.canvas.itemconfigure(self.window, width=max(1, self.canvas.winfo_width()))
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        if self.body.winfo_reqheight()>self.canvas.winfo_height():
            self.scroll.grid()
        else:
            self.scroll.grid_remove()
            self.canvas.yview_moveto(0)

    def contains(self, widget):
        return str(widget).startswith(str(self.body)+'.')

    def wheel(self, event):
        widget = self.parent.winfo_containing(event.x_root, event.y_root)
        if widget and self.contains(widget) and self.body.winfo_reqheight()>self.canvas.winfo_height():
            self.canvas.yview_scroll(-1 if event.delta>0 else 1, 'units')
            return 'break'

    def focus(self, event):
        if self.contains(event.widget):
            top = event.widget.winfo_rooty()-self.body.winfo_rooty()
            visible = self.canvas.canvasy(0)
            height = self.canvas.winfo_height()
            end = top+event.widget.winfo_height()
            if top<visible or end>visible+height:
                self.canvas.yview_moveto(max(0, end-height)/max(1,self.body.winfo_reqheight()))

    def show_end(self, widget=None):
        self.parent.update_idletasks()
        self.layout()
        if widget:
            from types import SimpleNamespace
            self.focus(SimpleNamespace(widget=widget))
        else:
            self.canvas.yview_moveto(1)


def section(parent, row, title):
    outer = ttk.Frame(parent)
    outer.grid(row=row, column=0, sticky='ew', pady=(2, 6))
    outer.columnconfigure(1, weight=1)
    ttk.Label(outer, text=title, width=10, foreground=GOLD_LIGHT,
              font=('Segoe UI', 9, 'bold')).grid(row=0, column=0, sticky='nw', pady=(17,0))
    body = ttk.Frame(outer)
    body.grid(row=0, column=1, sticky='ew')
    for i in range(3):
        body.columnconfigure(i, weight=1, uniform='settings')
    return outer, body


class CurrentFile:
    """File identity survives phase updates; truncate by pixels, never expand layout."""
    def __init__(self, parent, localizer, row):
        self.localizer = localizer
        self.label = ttk.Label(parent, foreground=MUTED, width=1)
        self.label.grid(row=row, column=0, sticky='ew', pady=(3,0))
        self.name = ''
        self.index = self.count = 0
        self.label.bind('<Configure>', lambda event:self.render())

    def set(self, name='', index=0, count=0):
        self.name, self.index, self.count = str(name), index, count
        self.render()

    def render(self):
        if not self.name:
            self.label.configure(text='')
            return
        prefix = self.localizer.t('Datei')+f' {self.index}/{self.count} · '
        f = font.Font(root=self.label, font=ttk.Style(self.label).lookup('TLabel','font') or 'TkDefaultFont')
        space = max(0,self.label.winfo_width()-8-f.measure(prefix))
        name = self.name
        if f.measure(name)>space:
            lo, hi = 0, len(name)
            while lo<hi:
                n=(lo+hi+1)//2
                candidate=name[:(n+1)//2]+'…'+(name[-(n//2):] if n//2 else '')
                if f.measure(candidate)<=space:lo=n
                else:hi=n-1
            name=name[:(lo+1)//2]+'…'+(name[-(lo//2):] if lo//2 else '')
        self.label.configure(text=prefix+name)
