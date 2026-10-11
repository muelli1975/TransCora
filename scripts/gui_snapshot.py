"""CI-only Windows snapshots of the actual Tk application for visual review."""
from pathlib import Path
import ctypes
import sys
import tkinter as tk
import time
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.gui.window import Window
from transcora.core.model import Job, Options
from transcora.gui.preview_window import PreviewWindow

OUT = ROOT/'output/gui-check'
OUT.mkdir(parents=True, exist_ok=True)
# The CI desktop is only 720 pixels high; keep its taskbar off the captures.
taskbar = ctypes.windll.user32.FindWindowW('Shell_TrayWnd', None)
ctypes.windll.user32.ShowWindow(taskbar, 0)
root = tk.Tk()
window = Window(root)
root.geometry('860x680+20+0')
root.lift()
root.update()


def snap(widget, name):
    widget.lift()
    for _ in range(5):
        widget.update()
        time.sleep(.1)
    # Client surfaces plus the real native title bar, where present.
    x, y = widget.winfo_rootx(), widget.winfo_rooty()
    ImageGrab.grab(bbox=(max(0, x-8), max(0, y-32), x+widget.winfo_width()+8,
                         y+widget.winfo_height()+8)).save(OUT/name)


window.add_paths([Path('C:/Filme/Unser Film_full_sbs.mkv'), Path('C:/Filme/Zweiter Film_half_ou.mp4')])
window.tree.selection_set(window.jobs[0].id)
window.selection_changed()
window.variables['target'].set('Anaglyph')
window.option_changed('target')
window.variables['profile'].set('Kompatibel · 8 Bit / 4:2:0')
window.option_changed('profile')
window.elapsed_time.set('Vergangene Zeit: 02:34')
window.elapsed.set('Restzeit: ca. 05:12')
snap(root, 'anaglyph.png')
window.variables['target'].set('BD-3D · 1080p')
window.option_changed('target')
snap(root, 'bd3d.png')
window.toggle_advanced()
snap(root, 'bd3d-audio.png')
window.status.set('BD-3D: Fertige Ausgabe vollständig dekodieren und beide Halbbilder prüfen')
window.elapsed.set('Restzeit: ca. 02:15')
window.progress['value'] = 94
snap(root, 'bd3d-check.png')
window.toggle_advanced()
window.show_log()
log = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel))
snap(log, 'log.png')
log.destroy()
viewer = PreviewWindow(root, lambda t: None)
viewer.duration = 123.5
viewer.scale.configure(to=123, state='normal')
viewer.position_changed(65.5)
viewer.dialog.update()
snap(viewer.dialog, 'preview.png')
viewer.dialog.destroy()
root.destroy()
ctypes.windll.user32.ShowWindow(taskbar, 5)
