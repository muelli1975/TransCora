"""Full-resolution pixels with a fit display and scrollable one-to-one inspection."""
import tkinter as tk
from tkinter import ttk
from PIL import Image, ImageTk
from .theme import SECONDARY_BG, MUTED
from .localization import TextVar


class ImageView(ttk.Frame):
    def __init__(self, parent, localizer):
        super().__init__(parent)
        self.localizer = localizer
        self.images = []
        self.fit = tk.BooleanVar(value=True)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)
        bar = ttk.Frame(self); bar.grid(row=0, column=0, columnspan=2, sticky='ew', pady=(0, 5))
        ttk.Radiobutton(bar, text='An Fenster anpassen', variable=self.fit, value=True, command=self.render).pack(side='left')
        ttk.Radiobutton(bar, text='1:1 · Originalpixel', variable=self.fit, value=False, command=self.render).pack(side='left', padx=12)
        self.dimensions = TextVar(localizer)
        ttk.Label(bar, textvariable=self.dimensions, foreground=MUTED).pack(side='right')
        self.canvas = tk.Canvas(self, background=SECONDARY_BG, borderwidth=0, highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        y = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview); y.grid(row=1, column=1, sticky='ns')
        x = ttk.Scrollbar(self, orient='horizontal', command=self.canvas.xview); x.grid(row=2, column=0, sticky='ew')
        self.canvas.configure(xscrollcommand=x.set, yscrollcommand=y.set)
        self.canvas.bind('<Configure>', lambda event: self.render())
        self.canvas.bind('<ButtonPress-1>', lambda e: self.canvas.scan_mark(e.x, e.y))
        self.canvas.bind('<B1-Motion>', lambda e: self.canvas.scan_dragto(e.x, e.y, gain=1))
        localizer.apply()

    def set_images(self, images):
        self.images = [image.copy() for image in images]
        self.dimensions.set(' · '.join(f'{image.width} × {image.height} px' for image in images))
        self.render()

    def render(self):
        if not self.images: return
        available_w = max(1, self.canvas.winfo_width()); available_h = max(1, self.canvas.winfo_height())
        width = sum(image.width for image in self.images); height = max(image.height for image in self.images)
        ratio = min(1, available_w/width, available_h/height) if self.fit.get() else 1
        self.photos = []; self.canvas.delete('all'); x = 0
        for image in self.images:
            shown = image.resize((max(1, round(image.width*ratio)), max(1, round(image.height*ratio))), Image.Resampling.LANCZOS) if ratio != 1 else image
            photo = ImageTk.PhotoImage(shown); self.photos.append(photo)
            self.canvas.create_image(x, 0, image=photo, anchor='nw'); x += shown.width
        self.canvas.configure(scrollregion=(0, 0, x, max(1, round(height*ratio))))
