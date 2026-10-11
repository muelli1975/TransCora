from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import shutil
import subprocess
import sys
from functools import cached_property

from .model import app_root


def process_options() -> dict:
    return {"creationflags": subprocess.CREATE_NO_WINDOW} if os.name == "nt" else {}


@dataclass(frozen=True)
class Toolchain:
    ffmpeg: Path
    ffprobe: Path

    @cached_property
    def setts_prescale(self) -> str:
        result = subprocess.run([str(self.ffmpeg), "-hide_banner", "-h", "bsf=setts"],
                                capture_output=True, encoding="utf-8", errors="replace",
                                timeout=30, **process_options())
        # New setts versions rescale expression results unless prescale is set.
        # Our expressions already produce ticks in the requested output time base.
        return ":prescale=1" if re.search(r"^\s*-?prescale\s", result.stdout + result.stderr, re.M) else ""

    @classmethod
    def find(cls) -> "Toolchain":
        ext = ".exe" if os.name == "nt" else ""
        roots = [app_root() / "tools" / "ffmpeg"]
        if os.name != 'nt':
            roots += [Path('/opt/homebrew/opt/ffmpeg@7'), Path('/usr/local/opt/ffmpeg@7'),
                      Path('/opt/homebrew/opt/ffmpeg-full'), Path('/usr/local/opt/ffmpeg-full'),
                      Path('/opt/homebrew'), Path('/usr/local'), Path('/usr')]
        for root in roots:
            for folder in (root, root / "bin"):
                if all((folder / (name + ext)).is_file() for name in ("ffmpeg", "ffprobe")):
                    return cls((folder / ("ffmpeg" + ext)).resolve(), (folder / ("ffprobe" + ext)).resolve())
        if not getattr(sys, "frozen", False) or os.name != 'nt':
            paths = [shutil.which(x) for x in ("ffmpeg", "ffprobe")]
            if all(paths):
                return cls(Path(paths[0]), Path(paths[1]))
        raise ValueError("Die mitgelieferten Programme ffmpeg und ffprobe fehlen. "
                         "TransCora.zip vollständig entpacken und den gesamten Programmordner zusammenhalten.")

    def inspect(self) -> dict:
        def run(*args: str) -> str:
            p = subprocess.run([str(self.ffmpeg), "-hide_banner", *args], capture_output=True,
                               encoding="utf-8", errors="replace", timeout=30, **process_options())
            if p.returncode:
                raise ValueError(p.stderr.strip() or "FFmpeg konnte nicht gestartet werden.")
            return p.stdout + p.stderr
        filters = run("-filters")
        required = {"zscale", "colorchannelmixer", "lutrgb", "blend", "crop", "scale", "pad",
                    "hstack", "vstack", "format", "setsar", "sidedata", "bwdif"}
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
