from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from fractions import Fraction
import re
import sys
import uuid


VIDEO_EXTENSIONS = {".mp4", ".mkv", ".mk3d", ".mkv3d", ".mov", ".m2ts", ".mts", ".ts", ".ssif", ".iso", ".avi", ".wmv"}
LAYOUTS = {"auto": "Automatisch", "full_sbs": "Full-SBS", "half_sbs": "Half-SBS",
           "full_ou": "Full-OU", "half_ou": "Half-OU", "mono": "Mono / 2D",
           "mvc": "MVC / Blu-ray 3D", "mvhevc": "MV-HEVC", "dual": "Dual (L/R-Spuren)",
           "row_interleaved": "Zeilenverschachtelt", "frame_sequential": "Frame sequential"}
TARGETS = {"half_sbs": "Half-SBS", "half_ou": "Half-OU",
           "row_interleaved": "Zeilenverschachtelt (Polfilter)",
           "cross_sbs": "Kreuzblick · Full-SBS R/L", "full_sbs": "Full-SBS", "full_ou": "Full-OU",
           "anaglyph": "Anaglyph", "dual": "Dual · L/R-Spuren", "mono": "Mono", "framerate": "Layout beibehalten", "bd3d": "BD-3D"}
NAMING = {"original": "Kein Layout-Zusatz", "layout": "Layout-Zusatz",
          "players": "Player-Kürzel (Kodi/Bino)"}
PROFILES = {"quality": "Qualität · 8 Bit / 4:4:4", "quality10": "Hohe Farbtiefe · 10 Bit / 4:4:4",
            "compatible": "Kompatibel · 8 Bit / 4:2:0"}
COMPATIBILITY_NOTE = ("Breitere Player-Unterstützung, jedoch mit deutlich geringerer Farbauflösung. "
                      "Farbdetails und farbige Kanten können sichtbar leiden. "
                      "Für hochwertige Anaglyphen wird 4:4:4 empfohlen.")
ANAGLYPH_PLAYER_NOTE = "4:4:4 wird nicht von allen Playern/Hardwaredecodern unterstützt."
FPS_CHOICES = ("23,976", "24", "25", "29,97", "30", "50", "59,94", "60")
FPS_MODES = {'source': 'Quelle beibehalten', 'custom': 'Zielbildrate wählen'}
VIDEO_SIZES = {'default': 'Standard', 'original': 'Original', '1080p': '1080p', '2160p': '2160p', 'custom': 'Benutzerdefiniert'}
BD_MODES = {"1080p": "1080p · 23,976 fps", "720p50": "720p · 50 fps", "720p5994": "720p · 59,94 fps"}
BD_BITRATES = (20, 25, 30, 35, 40)
ROW_ORDERS = {'left': 'Linkes Halbbild', 'right': 'Rechtes Halbbild'}
AUDIO_FORMATS = {'copy': 'Original beibehalten', 'aac': 'AAC · Hohe Kompatibilität'}
AUDIO_TRACKS = {'all': 'Alle übernehmen', 'selected': 'Ausgewählte Spuren', 'none': 'Ohne Ton'}
AUDIO_CHANNELS = {'source': 'Quelle beibehalten', 'stereo': 'In Stereo umwandeln'}


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
        folder = Path(sys.executable).resolve().parent
        if sys.platform == 'darwin' and folder.name == 'MacOS' and folder.parents[1].suffix == '.app':
            # The portable app and its tools share an external application folder.
            # Settings and exports must not modify signed bundle resources.
            return folder.parents[2]
        return folder
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
    fps_mode: str = 'source'
    disc_title: str | None = None
    container: str = "mp4"
    codec: str = "h264"
    rate_mode: str = "crf"
    crf: float = 18.0
    bitrate_mbps: float = 20.0
    video_size: str = 'default'
    video_width: int = 1920
    video_height: int = 1080
    bd_bitrate_mbps: int = 40
    bd_mode: str = "1080p"
    screen_width: int = 1920
    screen_height: int = 1080
    row_first: str = 'left'
    audio_format: str = 'copy'
    audio_tracks: str = 'all'
    audio_selection: str = '1'
    audio_channels: str = 'source'
    mono_eye: str = 'left'

    @classmethod
    def from_dict(cls, data: dict) -> "Options":
        if not isinstance(data, dict):
            raise ValueError("Ungültige Jobeinstellungen.")
        data = dict(data)
        # Earlier lists used the standalone frame-rate target exclusively.
        if data.get('target') == 'framerate' and 'fps_mode' not in data:
            data['fps_mode'] = 'custom'
        # Version 0.1 lists stored a manual checkbox. Colour interpretation is now
        # automatic; retain every other per-file choice when loading old lists.
        legacy = data.pop("assume_bt709", False)
        if not isinstance(legacy, bool):
            raise ValueError("Ungültige Farbeinstellung in der Jobliste.")
        allowed = cls.__dataclass_fields__
        if set(data) - set(allowed):
            raise ValueError("Unbekannte Einstellungen in der Jobliste.")
        if data.get('target') == 'row_interleaved':
            data = dict(data)
            data['profile'] = 'quality'
        result = cls(**data)
        result.validate()
        return result

    def validate(self) -> None:
        for name, values in (("layout", LAYOUTS), ("target", TARGETS), ("profile", PROFILES),
                             ("naming", NAMING), ("container", {"mp4", "mkv", "iso", "m2ts"}),
                             ("codec", {"h264", "h265"}), ("rate_mode", {"crf", "abr"}),
                             ('mono_eye', {'left', 'right'})):
            if getattr(self, name) not in values:
                raise ValueError(f"Ungültige Einstellung: {name}.")
        if self.video_size not in VIDEO_SIZES:
            raise ValueError('Ungültige Video-Ausgabegröße.')
        from .video import validate_screen
        validate_screen(self)
        for value in (self.video_width, self.video_height):
            if type(value) is not int or not 2 <= value <= 16384 or value % 2:
                raise ValueError('Videomaße: Gerade Pixelzahlen von 2 bis 16384 verwenden.')
        if type(self.bd_bitrate_mbps) is not int or self.bd_bitrate_mbps not in BD_BITRATES:
            raise ValueError('BD-3D-Bitrate: 20, 25, 30, 35 oder 40 Mbit/s wählen.')
        if self.bd_mode not in BD_MODES:
            raise ValueError("Ungültiger BD-3D-Ausgabemodus.")
        if not isinstance(self.swap, bool):
            raise ValueError("Ungültige L/R-Einstellung.")
        if not isinstance(self.method, str):
            raise ValueError("Ungültiges Anaglyphenverfahren.")
        for name, choices in (('audio_format', AUDIO_FORMATS), ('audio_tracks', AUDIO_TRACKS),
                              ('audio_channels', AUDIO_CHANNELS)):
            if getattr(self, name) not in choices:
                raise ValueError('Ungültige Toneinstellung: '+name+'.')
        from .audio import selection_numbers
        selection_numbers(self.audio_selection)
        if self.suffix is not None and (not isinstance(self.suffix, str) or len(self.suffix) > 80
                or re.search(r'[<>:"/\\|?*\x00-\x1f]', self.suffix) or self.suffix.endswith((" ", "."))):
            raise ValueError("Dateinamenszusatz: Höchstens 80 Zeichen, ohne Pfad- oder ungültige Dateizeichen.")
        if not isinstance(self.target_fps, str):
            raise ValueError("Ungültige Zielbildrate.")
        frame_rate(self.target_fps)
        if self.fps_mode not in FPS_MODES:
            raise ValueError('Ungültige Bildratenwahl.')
        if not isinstance(self.crf, (int, float)) or not 1 <= self.crf <= 51:
            raise ValueError("CRF muss zwischen 1 und 51 liegen.")
        if not isinstance(self.bitrate_mbps, (int, float)) or not 0 < self.bitrate_mbps <= 1000:
            raise ValueError("Die Zielbitrate muss größer als 0 und höchstens 1000 Mbit/s sein.")
        if self.disc_title is not None and (not isinstance(self.disc_title, str) or not self.disc_title.strip()
                or len(self.disc_title.encode('utf-16-be')) > 124 or re.search(r'[<>:"/\\|?*\x00-\x1f]', self.disc_title)
                or self.disc_title.endswith((" ", "."))):
            raise ValueError("Disc-Titel: Höchstens 62 Unicode-Zeichen, ohne ungültige Dateizeichen.")
        if self.target == "bd3d":
            if self.container not in {"iso", "m2ts"} or self.codec != "h264":
                raise ValueError("BD-3D benötigt ISO oder M2TS mit AVC/MVC.")
        elif self.container not in {"mp4", "mkv"}:
            raise ValueError("ISO/M2TS ist nur für BD-3D verfügbar.")
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
    source_fps: str | None = None
    source_duration: float | None = None
    result: object | None = None

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
