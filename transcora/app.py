"""Desktop entry point; no network operations or package installation."""
import tkinter as tk
from tkinter import messagebox
import json
from pathlib import Path
import sys


def main():
    root = tk.Tk()
    self_test = len(sys.argv) == 3 and sys.argv[1] == "--self-test"
    try:
        from transcora.gui.window import Window
        window = Window(root)
        if self_test:
            from transcora.core.model import app_root
            from transcora.core.toolchain import Toolchain
            root.update()
            capabilities = Toolchain.find().inspect()
            from transcora.core.bd3d_export import BdTools
            bd = BdTools.find()
            from transcora.core.multiview import decoder
            mvc_decoder = decoder()
            from transcora.core.images import exiftool
            from transcora.core.engine import capture
            image_tools = bool(capture(exiftool()+['-ver']).strip())
            if not (app_root() / "assets" / "ready.wav").is_file():
                raise ValueError("Completion sound is missing")
            Path(sys.argv[2]).write_text(json.dumps({"ok": True, "methods": len(window.catalog),
                "root": str(app_root()), "ffmpeg": capabilities["version"], "mvc": mvc_decoder.is_file(),
                "bd3d": bd.encoder.is_file() and bd.muxer.is_file(), "images": image_tools}), encoding="utf-8")
            root.destroy()
            return
        root.mainloop()
    except Exception as error:
        if self_test:
            Path(sys.argv[2]).write_text(json.dumps({"ok": False, "error": str(error)}), encoding="utf-8")
            root.destroy()
            raise SystemExit(1)
        messagebox.showerror("TransCora", str(error), parent=root)
        root.destroy()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
