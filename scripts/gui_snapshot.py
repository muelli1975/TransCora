"""CI-only Windows snapshots of the actual Tk application for visual review."""
from pathlib import Path
import ctypes
import sys
import tkinter as tk
import time
from PIL import ImageGrab, Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.gui.window import Window
from transcora.core.model import Job, Options, TARGETS, PROFILES
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
window.variables['profile'].set(window.t(PROFILES['compatible']))
window.option_changed('profile')
window.elapsed_time.set('Vergangene Zeit: 02:34')
window.elapsed.set('Restzeit: ca. 05:12')
snap(root, 'anaglyph.png')
window.variables['target'].set('BD-3D · 1080p')
window.option_changed('target')
snap(root, 'bd3d.png')
window.toggle_advanced()
snap(root, 'bd3d-audio.png')
window.show_audio_options()
snap(window.audio_dialog, 'audio-options.png')
window.close_audio_options()
window.status.set('BD-3D: Fertige Ausgabe vollständig dekodieren und beide Halbbilder prüfen')
window.elapsed.set('Restzeit: ca. 02:15')
window.progress['value'] = 94
snap(root, 'bd3d-check.png')
window.toggle_advanced()
window.show_log()
log = next(w for w in root.winfo_children() if isinstance(w, tk.Toplevel) and w.title() == 'TransCora · Log')
snap(log, 'log.png')
log.destroy()
viewer = PreviewWindow(root, lambda t: None)
viewer.duration = 123.5
viewer.scale.configure(to=123, state='normal')
viewer.position_changed(65.5)
viewer.dialog.update()
snap(viewer.dialog, 'preview.png')
viewer.dialog.destroy()
window.notebook.select(window.image_tab)
window.images.add_paths([Path('C:/Fotos/Diaschau_full_sbs.jpg'), Path('C:/Fotos/Kamera.mpo')])
window.images.tree.selection_set(window.images.jobs[0].id)
window.images.selection_changed()
snap(root, 'images.png')
window.images.variables['task'].set('MPO verlustfrei teilen')
window.images.changed('task')
snap(root, 'images-mpo.png')
root.geometry('780x680+20+0')
snap(root, 'images-minimum.png')
window.notebook.select(window.video_tab)
snap(root, 'video-minimum.png')
for language, name in [('en', 'English'), ('de', 'Deutsch')]:
    window.language = language; window.language_var.set(name); window.apply_language()
    window.notebook.select(window.image_tab)
    window.images.variables['task'].set(window.t('Bilder konvertieren')); window.images.changed('task')
    window.images.variables['size_mode'].set(window.t('Benutzerdefiniert')); window.images.changed('size_mode')
    window.images.variables['size_edge'].set(window.t('kurze Seite')); window.images.changed('size_edge')
    snap(root, 'images-custom-'+language+'.png')
    window.images.events.put(('preview', [Image.new('RGB', (2000, 1200), (38, 48, 58))]))
    window.images.poll()
    dialog = window.images.preview_dialog
    snap(dialog, 'image-preview-'+language+'.png')
    dialog.destroy()
    window.notebook.select(window.video_tab)
    window.variables['target'].set(window.t(TARGETS['cross_sbs']))
    window.option_changed('target')
    snap(root, 'video-'+language+'.png')
root.destroy()
ctypes.windll.user32.ShowWindow(taskbar, 5)
