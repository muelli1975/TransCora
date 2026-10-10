from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from fractions import Fraction
import re
import sys
import uuid


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mk3d", ".mov", ".m2ts", ".ts", ".avi"}
LAYOUTS = {"auto": "Automatisch", "full_sbs": "Full-SBS", "half_sbs": "Half-SBS",
           "full_ou": "Full-OU", "half_ou": "Half-OU", "mono": "Mono / 2D"}
TARGETS = {"half_sbs": "Half-SBS · 1080p", "half_ou": "Half-OU · 1080p",
           "anaglyph": "Anaglyph", "mono": "Mono · linkes Auge", "framerate": "Nur Framerate ändern"}
NAMING = {"original": "Kein Layout-Zusatz", "layout": "Layout-Zusatz",
          "players": "Player-Kürzel (Kodi/Bino)"}
PROFILES = {"quality": "Qualität · 8 Bit / 4:4:4", "quality10": "Qualität · 10 Bit / 4:4:4",
            "compatible": "Kompatibel · 8 Bit / 4:2:0"}
FPS_CHOICES = ("23,976", "24", "25", "29,97", "30", "50", "59,94", "60")


def frame_rate(value: str) -> Fraction:
    value = value.strip().replace(",", ".")
    aliases = {"23.976": "24000/1001", "29.97": "30000/1001", "59.94": "60000/1001"}
    try:
        rate = Fraction(aliases.get(value, value))
        if not 1 <= rate <= 240 or rate.denominator > 1_000_000:
            raise ValueError
        return rate
    except (ValueError, ZeroDivisionError, TypeError):
        raise ValueError("Zielbildrate: 1 bis 240 fps, als Zahl oder Bruch (z. B. 24000/1001).") from None


def app_root() -> Path:
    # A one-folder frozen application keeps assets and tools beside its executable.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


@dataclass
class Options:
    layout: str = "auto"
    swap: bool = False
    target: str = "half_sbs"
    method: str = "dubois_lcd"
    profile: str = "quality"
    naming: str = "layout"
    suffix: str | None = None
    target_fps: str = "30"
    container: str = "mp4"
    codec: str = "h264"
    rate_mode: str = "crf"
    crf: float = 18.0
    bitrate_mbps: float = 20.0

    @classmethod
    def from_dict(cls, data: dict) -> "Options":
        if not isinstance(data, dict):
            raise ValueError("Ungültige Jobeinstellungen.")
        data = dict(data)
        # Version 0.1 lists stored a manual checkbox. Colour interpretation is now
        # automatic; retain every other per-file choice when loading old lists.
        legacy = data.pop("assume_bt709", False)
        if not isinstance(legacy, bool):
            raise ValueError("Ungültige Farbeinstellung in der Jobliste.")
        allowed = cls.__dataclass_fields__
        if set(data) - set(allowed):
            raise ValueError("Unbekannte Einstellungen in der Jobliste.")
        result = cls(**data)
        result.validate()
        return result

    def validate(self) -> None:
        for name, values in (("layout", LAYOUTS), ("target", TARGETS), ("profile", PROFILES),
                             ("naming", NAMING), ("container", {"mp4", "mkv"}),
                             ("codec", {"h264", "h265"}), ("rate_mode", {"crf", "abr"})):
            if getattr(self, name) not in values:
                raise ValueError(f"Ungültige Einstellung: {name}.")
        if not isinstance(self.swap, bool):
            raise ValueError("Ungültige L/R-Einstellung.")
        if not isinstance(self.method, str):
            raise ValueError("Ungültiges Anaglyphenverfahren.")
        if self.suffix is not None and (not isinstance(self.suffix, str) or len(self.suffix) > 80
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', self.suffix) or self.suffix.endswith((" ", "."))):
            raise ValueError("Dateinamenszusatz: Höchstens 80 Zeichen, ohne Pfad- oder ungültige Dateizeichen.")
        if not isinstance(self.target_fps, str):
            raise ValueError("Ungültige Zielbildrate.")
        frame_rate(self.target_fps)
        if not isinstance(self.crf, (int, float)) or not 1 <= self.crf <= 51:
            raise ValueError("CRF muss zwischen 1 und 51 liegen.")
        if not isinstance(self.bitrate_mbps, (int, float)) or not 0 < self.bitrate_mbps <= 1000:
            raise ValueError("Die Zielbitrate muss größer als 0 und höchstens 1000 Mbit/s sein.")
        if self.codec == "h265" and self.container != "mkv":
            raise ValueError("H.265 ist in dieser Version nur mit MKV freigegeben.")


@dataclass
class Job:
    source: Path
    options: Options = field(default_factory=Options)
    source_root: Path | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"
    detail: str = "Noch nicht geprüft"
    plan: object | None = None

    def serializable(self) -> dict:
        return {"source": str(self.source), "source_root": str(self.source_root) if self.source_root else None,
                "options": asdict(self.options)}

    @classmethod
    def from_dict(cls, data: dict) -> "Job":
        if not isinstance(data, dict) or not isinstance(data.get("source"), str):
            raise ValueError("Ungültiger Dateieintrag.")
        source_root = data.get("source_root")
        if source_root is not None and not isinstance(source_root, str):
            raise ValueError("Ungültige Ordnerwurzel.")
        return cls(Path(data["source"]).expanduser().resolve(), Options.from_dict(data.get("options", {})),
                   Path(source_root).expanduser().resolve() if source_root else None)
