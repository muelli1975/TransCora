"""A single round handle on a continuous timeline, with keyboard support."""
import tkinter as tk
from .theme import APP_BG, BORDER, GOLD, GOLD_LIGHT, DISABLED


class Timeline(tk.Canvas):
    def __init__(self, parent, *, from_=0, to=1, command=None, state="normal"):
        super().__init__(parent, height=28, width=400, background=APP_BG,
                         highlightthickness=1, highlightbackground=APP_BG,
                         highlightcolor=GOLD, takefocus=True, borderwidth=0)
        self.minimum, self.maximum = float(from_), float(to)
        self.value, self.callback, self.enabled = self.minimum, command, state != "disabled"
        self.bind("<Configure>", lambda e: self.draw())
        self.bind("<Button-1>", self.move_pointer)
        self.bind("<B1-Motion>", self.move_pointer)
        self.bind("<KeyPress>", self.move_key)

    def configure(self, cnf=None, **kwargs):
        if "to" in kwargs:
            self.maximum = float(kwargs.pop("to"))
        if "state" in kwargs:
            self.enabled = kwargs.pop("state") != "disabled"
        result = super().configure(cnf, **kwargs)
        if hasattr(self, "value"):
            self.value = min(self.maximum, max(self.minimum, self.value))
            self.draw()
        return result

    config = configure

    def cget(self, key):
        if key == "to":
            return self.maximum
        if key == "state":
            return "normal" if self.enabled else "disabled"
        return super().cget(key)

    def state(self):
        return () if self.enabled else ("disabled",)

    def get(self):
        return self.value

    def set(self, value):
        self.value = min(self.maximum, max(self.minimum, float(value)))
        self.draw()
        if self.callback:
            self.callback(self.value)

    def draw(self):
        self.delete("all")
        left, right, y = 10, max(10, self.winfo_width() - 10), 14
        ratio = (self.value-self.minimum) / (self.maximum-self.minimum) if self.maximum > self.minimum else 0
        x = left + ratio * (right-left)
        self.create_line(left, y, right, y, fill=BORDER, width=4, capstyle="round")
        self.create_line(left, y, x, y, fill=GOLD if self.enabled else DISABLED, width=4, capstyle="round")
        self.create_oval(x-7, y-7, x+7, y+7, fill=GOLD_LIGHT if self.enabled else DISABLED, outline="")

    def move_pointer(self, event):
        if self.enabled:
            self.focus_set()
            ratio = (event.x-10) / max(1, self.winfo_width()-20)
            self.set(self.minimum + ratio*(self.maximum-self.minimum))

    def move_key(self, event):
        if not self.enabled:
            return
        step = max(.04, (self.maximum-self.minimum)/1000)
        if event.keysym in {"Left", "Down", "Right", "Up", "Prior", "Next", "Home", "End"}:
            value = {"Left": self.value-step, "Down": self.value-step, "Right": self.value+step,
                     "Up": self.value+step, "Prior": self.value+10*step, "Next": self.value-10*step,
                     "Home": self.minimum, "End": self.maximum}[event.keysym]
            self.set(value)
            return "break"
