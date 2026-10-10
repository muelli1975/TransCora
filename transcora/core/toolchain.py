from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess

from .model import app_root


def process_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


@dataclass(frozen=True)
class Toolchain:
    ffmpeg: Path
    ffprobe: Path

    @classmethod
    def find(cls, custom: str = "") -> "Toolchain":
        ext = ".exe" if os.name == "nt" else ""
        roots = ([Path(custom)] if custom else []) + [app_root() / "tools" / "ffmpeg"]
        for root in roots:
            for folder in (root, root / "bin"):
                if all((folder / (name + ext)).is_file() for name in ("ffmpeg", "ffprobe")):
                    return cls((folder / ("ffmpeg" + ext)).resolve(), (folder / ("ffprobe" + ext)).resolve())
        if not custom:
            paths = [shutil.which(x) for x in ("ffmpeg", "ffprobe")]
            if all(paths):
                return cls(Path(paths[0]), Path(paths[1]))
        raise ValueError("ffmpeg und ffprobe fehlen. Den Ordner mit beiden Programmen über „FFmpeg-Ordner“ auswählen.")

    def inspect(self) -> dict:
        def run(*args: str) -> str:
            p = subprocess.run([str(self.ffmpeg), "-hide_banner", *args], capture_output=True,
                               encoding="utf-8", errors="replace", timeout=30, **process_options())
            if p.returncode:
                raise ValueError(p.stderr.strip() or "FFmpeg konnte nicht gestartet werden.")
            return p.stdout + p.stderr
        filters = run("-filters")
        required = {"zscale", "colorchannelmixer", "lutrgb", "blend", "crop", "scale", "pad",
                    "hstack", "vstack", "format", "setsar", "sidedata"}
        # FFmpeg 9 removed the third (command-support) flag from this listing.
        found = set(re.findall(r"^\s*[TSC.]{2,3}\s+(\w+)\s", filters, re.M))
        missing = required - found
        if missing:
            raise ValueError("FFmpeg-Build ungeeignet; fehlende Filter: " + ", ".join(sorted(missing)))
        encoders = run("-encoders")
        if not re.search(r"\blibx264\b", encoders):
            raise ValueError("Der FFmpeg-Build enthält keinen H.264-Encoder libx264.")
        capabilities = {"version": run("-version").splitlines()[0], "h265": "libx265" in encoders,
                        "h264_formats": run("-h", "encoder=libx264")}
        if capabilities["h265"]:
            capabilities["h265_formats"] = run("-h", "encoder=libx265")
        return capabilities
