"""Desktop entry point; no network operations or package installation."""
import tkinter as tk
from tkinter import messagebox
import json
from pathlib import Path
import sys


def main():
    if len(sys.argv) == 4 and sys.argv[1] == '--self-test-heif':
        try:
            from transcora.core.heif_check import check
            report = check(Path(sys.argv[3]))
        except Exception as error:
            import traceback
            traceback.print_exc()
            report = {'ok': False, 'error': str(error)}
        Path(sys.argv[2]).write_text(json.dumps(report, indent=2), encoding='utf-8')
        raise SystemExit(0 if report['ok'] else 1)
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
            bd = BdTools.find() if sys.platform == 'win32' else None
            from transcora.core.multiview import decoder
            mvc_decoder = decoder() if sys.platform == 'win32' or (app_root()/'tools/mvc/TransCoraMVC').is_file() else None
            from transcora.core.images import exiftool
            from transcora.core.engine import capture
            image_tools = bool(capture(exiftool()+['-ver']).strip())
            from transcora.core.cielab import verify_tool
            cielab_tool = verify_tool()
            from transcora.core.heif import response
            heif_reader = response(['--version'])
            if not (app_root() / "assets" / "ready.wav").is_file():
                raise ValueError("Completion sound is missing")
            Path(sys.argv[2]).write_text(json.dumps({"ok": True, "methods": len(window.catalog),
                "root": str(app_root()), "ffmpeg": capabilities["version"], "mvc": bool(mvc_decoder and mvc_decoder.is_file()),
                "bd3d": bool(bd and bd.encoder.is_file() and bd.muxer.is_file()), "images": image_tools,
                "cielab": cielab_tool.is_file(), "heif": heif_reader}), encoding="utf-8")
            root.destroy()
            return
        root.mainloop()
    except Exception as error:
        if self_test:
            import traceback
            traceback.print_exc()
            Path(sys.argv[2]).write_text(json.dumps({"ok": False, "error": str(error)}), encoding="utf-8")
            root.destroy()
            raise SystemExit(1)
        messagebox.showerror("TransCora", str(error), parent=root)
        root.destroy()
        raise SystemExit(1)


if __name__ == "__main__":
    main()
