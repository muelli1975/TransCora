"""Stereo tools' shared Nachtgold palette and ttk widget states."""
from tkinter import ttk

APP_BG = "#111111"
SECONDARY_BG = "#181818"
PANEL_BG = "#202020"
HOVER_BG = "#282828"
BORDER = "#333333"
TEXT = "#f2f2f2"
MUTED = "#b8b8b8"
DISABLED = "#727272"
GOLD = "#9c7c38"
GOLD_LIGHT = "#c6a95e"
DANGER = "#7f3939"
DANGER_HOVER = "#944545"


def apply_theme(root):
    root.configure(background=APP_BG)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=APP_BG, foreground=TEXT, bordercolor=BORDER,
                    darkcolor=BORDER, lightcolor=BORDER)
    # Match the Stereo-Tools segmented selector: dark inactive segments,
    # gold selection and the existing light-gold selected hover state.
    style.configure("TNotebook", background=APP_BG, borderwidth=0, tabmargins=(10, 4, 10, 0))
    style.configure("TNotebook.Tab", background=SECONDARY_BG, foreground=TEXT,
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    padding=(18, 4), focuscolor=GOLD_LIGHT)
    tab_colors = [("disabled", SECONDARY_BG), ("selected", "active", GOLD_LIGHT),
                  ("selected", GOLD), ("active", HOVER_BG)]
    style.map("TNotebook.Tab", background=tab_colors,
              foreground=[("disabled", DISABLED), ("selected", APP_BG)],
              lightcolor=[("selected", GOLD), ("!selected", BORDER)],
              darkcolor=[("selected", GOLD), ("!selected", BORDER)])
    style.configure("TButton", background=SECONDARY_BG, foreground=TEXT,
                    bordercolor=BORDER, padding=(9, 5), focusthickness=1, focuscolor=GOLD_LIGHT)
    style.map("TButton", background=[("disabled", SECONDARY_BG), ("active", HOVER_BG)],
              foreground=[("disabled", DISABLED)], bordercolor=[("disabled", BORDER), ("active", BORDER)])
    style.configure("Primary.TButton", background=SECONDARY_BG, foreground=GOLD_LIGHT,
                    bordercolor=GOLD, darkcolor=GOLD, lightcolor=GOLD)
    style.map("Primary.TButton", background=[("disabled", SECONDARY_BG), ("active", GOLD_LIGHT)],
              foreground=[("disabled", DISABLED), ("active", APP_BG)],
              bordercolor=[("disabled", BORDER), ("active", GOLD_LIGHT)],
              darkcolor=[("disabled", BORDER), ("active", GOLD_LIGHT)],
              lightcolor=[("disabled", BORDER), ("active", GOLD_LIGHT)])
    style.configure("Danger.TButton", background=SECONDARY_BG, foreground=TEXT,
                    bordercolor=DANGER, darkcolor=DANGER, lightcolor=DANGER)
    style.map("Danger.TButton", background=[("disabled", SECONDARY_BG), ("active", DANGER_HOVER)],
              foreground=[("disabled", DISABLED)], bordercolor=[("disabled", BORDER), ("active", DANGER_HOVER)],
              darkcolor=[("disabled", BORDER), ("active", DANGER_HOVER)],
              lightcolor=[("disabled", BORDER), ("active", DANGER_HOVER)])
    style.configure("TMenubutton", background=SECONDARY_BG, foreground=TEXT,
                    bordercolor=BORDER, padding=(9, 5), arrowcolor=GOLD_LIGHT)
    style.map("TMenubutton", background=[("active", HOVER_BG)], foreground=[("disabled", DISABLED)])
    style.configure("TCheckbutton", background=APP_BG, foreground=TEXT,
                    indicatorbackground=SECONDARY_BG, indicatorforeground=TEXT)
    style.map("TCheckbutton", background=[("disabled", APP_BG), ("active", APP_BG)],
              foreground=[("disabled", DISABLED)],
              indicatorbackground=[("disabled", "selected", DISABLED), ("disabled", SECONDARY_BG),
                                   ("selected", GOLD), ("active", HOVER_BG)])
    style.configure("TRadiobutton", background=APP_BG, foreground=TEXT,
                    indicatorbackground=SECONDARY_BG, indicatorforeground=TEXT)
    style.map("TRadiobutton", background=[("active", APP_BG)],
              foreground=[("disabled", DISABLED)],
              indicatorbackground=[("selected", GOLD), ("active", HOVER_BG)])
    style.configure("TCombobox", fieldbackground=PANEL_BG, background=HOVER_BG, arrowcolor=GOLD_LIGHT)
    style.map("TCombobox", fieldbackground=[("disabled", PANEL_BG), ("readonly", PANEL_BG)],
              foreground=[("disabled", DISABLED), ("readonly", TEXT)],
              arrowcolor=[("disabled", DISABLED)], background=[("disabled", HOVER_BG), ("active", BORDER)],
              selectbackground=[("disabled", PANEL_BG), ("readonly", PANEL_BG)],
              selectforeground=[("disabled", DISABLED), ("readonly", TEXT)])
    style.configure("TEntry", fieldbackground=SECONDARY_BG, foreground=TEXT, insertcolor=TEXT)
    style.map("TEntry", fieldbackground=[("disabled", SECONDARY_BG)], foreground=[("disabled", DISABLED)])
    style.configure("Bordered.TFrame", background=APP_BG, borderwidth=1, relief="solid",
                    bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
    style.configure("Treeview", background=PANEL_BG, fieldbackground=PANEL_BG, foreground=TEXT, rowheight=25)
    style.map("Treeview", background=[("selected", GOLD_LIGHT)], foreground=[("selected", APP_BG)])
    style.configure("Treeview.Heading", background=PANEL_BG, foreground=GOLD_LIGHT)
    style.map("Treeview.Heading", background=[("active", HOVER_BG)])
    style.configure("Horizontal.TProgressbar", background=GOLD, troughcolor=BORDER)
    style.configure("Horizontal.TScale", background=SECONDARY_BG, troughcolor=BORDER)
    style.map("Horizontal.TScale", background=[("disabled", DISABLED), ("active", GOLD_LIGHT), ("!disabled", GOLD_LIGHT)])
    style.configure("TScrollbar", background=BORDER, troughcolor=SECONDARY_BG, arrowcolor=MUTED)
    style.map("TScrollbar", background=[("active", HOVER_BG)])
    root.option_add("*TCombobox*Listbox.background", SECONDARY_BG)
    root.option_add("*TCombobox*Listbox.foreground", TEXT)
    root.option_add("*TCombobox*Listbox.selectBackground", HOVER_BG)
    root.option_add("*TCombobox*Listbox.selectForeground", TEXT)
    return style
