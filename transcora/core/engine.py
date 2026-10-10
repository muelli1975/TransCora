"""One checked FFmpeg plan for manual files, folders and saved lists."""
from __future__ import annotations

from dataclasses import dataclass, replace
from fractions import Fraction
from pathlib import Path
from collections import deque
import json
import math
import os
import shutil
import subprocess
import threading
import time
import uuid

from .model import Job, Options, app_root, frame_rate, LAYOUTS
from .naming import filename_layout, reserve_output
from .toolchain import Toolchain, process_options
from .mp4 import packed_stereo_boxes


class Cancelled(Exception):
    pass


def stop_process(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def capture(args: list[str], cancel: threading.Event | None = None, timeout: float = 30) -> bytes:
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **process_options())
    start = time.monotonic()
    try:
        while True:
            if cancel and cancel.is_set():
                raise Cancelled()
            if time.monotonic() - start > timeout:
                raise ValueError("Die technische Prüfung hat zu lange gedauert.")
            try:
                out, err = process.communicate(timeout=.15)
                break
            except subprocess.TimeoutExpired:
                continue
        if process.returncode:
            raise ValueError(err.decode("utf-8", "replace")[-4000:].strip() or "Externes Tool meldet einen Fehler.")
        return out
    finally:
        stop_process(process)


def probe(tools: Toolchain, path: Path, cancel: threading.Event | None = None) -> dict:
    if not path.is_file():
        raise ValueError(f"Datei fehlt: {path}")
    args = [str(tools.ffprobe), "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_streams", "-show_format", "-of", "json", str(path.resolve())]
    result = json.loads(capture(args, cancel))
    videos = [s for s in result.get("streams", []) if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise ValueError("Keine nutzbare Videospur gefunden.")
    if len(videos) > 1:
        raise ValueError("Mehrere Videospuren: getrennte L/R-Spuren sind in Version 0.1 noch nicht freigegeben.")
    result["video"] = videos[0]
    return result


def methods() -> dict:
    path = app_root() / "presets" / "anaglyph_methods.reference.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in data["methods"]}


def metadata_layout(video: dict) -> tuple[str, bool] | None:
    tag = video.get("tags", {}).get("stereo_mode", "").lower()
    tags = {"left_right": ("sbs", False), "right_left": ("sbs", True),
            "top_bottom": ("ou", False), "bottom_top": ("ou", True)}
    if tag in tags:
        return tags[tag]
    for side in video.get("side_data_list", []):
        if side.get("side_data_type") == "Stereo 3D":
            kind = {"side by side": "sbs", "top and bottom": "ou"}.get(side.get("type"))
            if kind:
                return kind, bool(side.get("inverted", 0))
            if side.get("type") not in (None, "2D", "unspecified"):
                raise ValueError("Dieses Stereo-Layout ist noch nicht freigegeben. SBS/OU-Quelle verwenden.")
    return None


def color_spec(video: dict) -> tuple[dict, list[str]]:
    fields = {"matrix": video.get("color_space"), "primaries": video.get("color_primaries"),
              "transfer": video.get("color_transfer"), "range": video.get("color_range")}
    hdr_side_data = ("mastering display", "content light", "dovi", "dolby vision", "hdr")
    if fields["transfer"] in {"smpte2084", "arib-std-b67"} or any(
            any(hint in str(side.get("side_data_type", "")).lower() for hint in hdr_side_data)
            for side in video.get("side_data_list", [])):
        raise ValueError("HDR-Quelle: Diese Version verarbeitet geprüftes SDR, ohne automatische HDR-/SDR-Wandlung.")
    warnings = []
    supported = {"matrix": {"bt709", "bt470bg", "smpte170m", "gbr"},
                 "primaries": {"bt709", "bt470bg", "smpte170m"},
                 "transfer": {"bt709", "smpte170m", "iec61966-2-1", "gamma22", "gamma28"},
                 "range": {"tv", "pc"}}
    missing_values = (None, "unknown", "unspecified")
    # Reject HDR/wide-gamut and other explicit unsupported tags before guessing
    # any missing field. Existing values are always authoritative.
    for key, value in fields.items():
        if value not in missing_values and value not in supported[key]:
            raise ValueError(f"Noch nicht freigegebene Farbinterpretation: {key}={value}.")
    pixel_format = str(video.get("pix_fmt", ""))
    rgb = pixel_format.startswith(("gbr", "rgb", "bgr"))
    unknown_color = [key for key in ("matrix", "primaries", "transfer") if fields[key] in missing_values]
    if unknown_color:
        # Resolution supports a fallback; it cannot prove a colour space. Keep
        # PAL/NTSC and partially tagged legacy sources out of the HD fallback.
        legacy = any(fields[key] in {"bt470bg", "smpte170m", "gamma22", "gamma28"}
                     for key in ("matrix", "primaries", "transfer"))
        hd = video.get("width", 0) >= 1280 and video.get("height", 0) >= 720
        hd_hint = fields["matrix"] == "bt709" or fields["primaries"] == "bt709"
        if legacy or not (hd or hd_hint):
            raise ValueError("Farbangaben unvollständig; keine eindeutige HD-SDR-Annahme möglich. "
                             "Quelle prüfen und fehlende Farbangaben vor dem Import ergänzen.")
        defaults = {"matrix": "gbr" if rgb else "bt709", "primaries": "bt709",
                    "transfer": "iec61966-2-1" if rgb else "bt709"}
        for key in unknown_color:
            fields[key] = defaults[key]
            warnings.append(f"Farbannahme {key}={fields[key]} (fehlende HD-SDR-Angabe)")
    if fields["range"] in missing_values:
        if rgb or pixel_format.startswith("yuvj"):
            fields["range"] = "pc"
            explanation = "Vollbereich für RGB/JPEG-YUV"
        elif pixel_format.startswith(("yuv", "nv12", "nv21", "p010", "p012", "p016")):
            fields["range"] = "tv"
            explanation = "üblicher begrenzter YUV-Videobereich; Quelle bei abweichendem Kontrast prüfen"
        else:
            raise ValueError("Helligkeitswertebereich fehlt und ist für dieses Pixelformat nicht bestimmbar.")
        warnings.append(f"Farbannahme range={fields['range']} ({explanation})")
    return fields, warnings


@dataclass
class Plan:
    source: Path
    output: Path
    options: Options
    info: dict
    layout: str
    swap: bool
    size: tuple[int, int]
    pixel_format: str
    graph: str
    duration: float
    warnings: list[str]
    colors: dict
    layout_reason: str

    @property
    def stereo(self) -> tuple[str, bool] | None:
        layout = self.layout if self.options.target == "framerate" else self.options.target
        if layout not in {"half_sbs", "full_sbs", "half_ou", "full_ou"}:
            return None
        return ("sbs" if layout.endswith("sbs") else "ou", self.swap if self.options.target == "framerate" else False)

    @property
    def stereo_summary(self) -> str:
        if not self.stereo:
            return "3D-Kennzeichnung: keine SBS/OU-Kennzeichnung"
        axis, inverted = self.stereo
        flags = "MKV-StereoMode" if self.options.container == "mkv" else "MP4-st3d"
        if self.options.codec == "h264" and not inverted:
            flags += f" · H.264 Frame-Packing {'3' if axis == 'sbs' else '4'}"
        return f"3D-Kennzeichnung: {flags} · {'SBS' if axis == 'sbs' else 'OU'} · " + ("R/L" if inverted else "L/R")

    @property
    def summary(self) -> str:
        video = self.info["video"]
        rate = video.get("avg_frame_rate", "?")
        try:
            fps = f"{float(Fraction(rate)):.3f}"
        except (ValueError, ZeroDivisionError):
            fps = "?"
        timing = ""
        if self.options.target == "framerate":
            target = frame_rate(self.options.target_fps)
            timing = f" → {float(target):.3f} fps ({target}) · Laufzeit unverändert"
        return (f"{video['width']} × {video['height']} · {video.get('codec_name', '?')} · "
                f"{fps} fps ({rate}){timing} → {self.size[0]} × {self.size[1]} · "
                f"{self.options.codec.upper()} / {self.pixel_format}\n{self.layout_reason}\n"
                f"{self.stereo_summary}\n{self.output}")


def build_graph(video: dict, options: Options, layout: str, swap: bool, colors: dict,
                method: dict) -> tuple[str, tuple[int, int], str]:
    width, height = video["width"], video["height"]
    if options.target == "framerate":
        pixel_format = video.get("pix_fmt", "")
        rate = frame_rate(options.target_fps)
        ticks = math.lcm(rate.numerator, Fraction(video.get("time_base", "1/1000")).denominator)
        offset = video.get("_start_offset", 0)
        thinning = []
        try:
            source_rate = Fraction(video.get("avg_frame_rate", "0/1"))
            ratio = source_rate / rate
            nominal = Fraction(video.get("r_frame_rate", "0/1"))
            factor = round(ratio)
            # Matroska's rational frame-rate field may approximate NTSC rates;
            # accept at most one part per million around an integer reduction.
            if abs(source_rate-nominal) <= source_rate/1000 and abs(ratio-factor) <= Fraction(1, 1_000_000) and factor > 1:
                thinning = [f"select='not(mod(n,{factor}))'"]
        except (ValueError, ZeroDivisionError):
            pass
        filters = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D",
                   "sidedata=mode=delete:type=SPHERICAL", *thinning, "setpts=PTS-STARTPTS",
                   f"fps=fps={rate}:start_time=0:round=near:eof_action=pass",
                   f"settb=expr=1/{ticks}", f"setpts=PTS+{offset}/TB"]
        if colors["matrix"] == "gbr":
            filters.append(f"zscale=matrixin=gbr:primariesin={colors['primaries']}:"
                           f"transferin={colors['transfer']}:rangein=full:matrix=bt709:"
                           f"primaries={colors['primaries']}:transfer={colors['transfer']}:range=full")
            pixel_format = "yuv444p10le" if any(n in pixel_format for n in ("10", "12", "16")) else "yuv444p"
        pixel_format = pixel_format.replace("yuvj", "yuv")
        pixel_format = {"nv12": "yuv420p", "nv21": "yuv420p", "p010le": "yuv420p10le",
                        "p012le": "yuv420p12le", "p016le": "yuv420p16le"}.get(pixel_format, pixel_format)
        matrix = "bt709" if colors['matrix'] == "gbr" else colors['matrix']
        filters.append(f"format={pixel_format},setparams=colorspace={matrix}:"
                       f"color_primaries={colors['primaries']}:color_trc={colors['transfer']}:"
                       f"range={'full' if colors['range'] == 'pc' else 'limited'}[v]")
        return ",".join(filters), (width, height), pixel_format
    horizontal = layout.endswith("sbs")
    eye_w, eye_h = (width // 2, height) if horizontal else (width, height // 2)
    display_w = eye_w * (2 if layout == "half_sbs" else 1)
    display_h = eye_h * (2 if layout == "half_ou" else 1)
    # A single adapter brings video into the Batch method's sRGB working space.
    rgb = (f"zscale=matrixin={colors['matrix']}:primariesin={colors['primaries']}:"
           f"transferin={colors['transfer']}:rangein={'full' if colors['range'] == 'pc' else 'limited'}:"
           "matrix=gbr:primaries=bt709:transfer=iec61966-2-1:range=full,format=gbrp16")
    graph = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D,"
             f"sidedata=mode=delete:type=SPHERICAL,{rgb},split[a][b]"]
    positions = ((0, 0), (eye_w, 0)) if horizontal else ((0, 0), (0, eye_h))
    if swap:
        positions = positions[::-1]
    for label, (x, y), out in zip(("a", "b"), positions, ("l", "r")):
        graph.append(f"[{label}]crop={eye_w}:{eye_h}:{x}:{y},"
                     f"scale={display_w}:{display_h}:flags=lanczos+accurate_rnd+full_chroma_int,"
                     f"setsar=1[{out}]")
    if options.target in {"half_sbs", "half_ou"}:
        # Letterbox each eye at full display geometry before halving one axis.
        for label in ("l", "r"):
            packed_w, packed_h = (960, 1080) if options.target == "half_sbs" else (1920, 540)
            graph.append(f"[{label}]scale=1920:1080:force_original_aspect_ratio=decrease:"
                         "force_divisible_by=2:flags=lanczos+accurate_rnd+full_chroma_int,"
                         "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
                         f"scale={packed_w}:{packed_h}:flags=lanczos+accurate_rnd+full_chroma_int[{label}p]")
        stack = "hstack" if options.target == "half_sbs" else "vstack"
        graph.append(f"[lp][rp]{stack}=inputs=2[composite]")
        size = (1920, 1080)
    elif options.target == "mono":
        graph.append("[r]nullsink")
        graph.append("[l]null[composite]")
        size = (display_w, display_h)
    else:
        mode = method["pipeline_type"]
        for label, matrix in (("l", "left_matrix_ffmpeg"), ("r", "right_matrix_ffmpeg")):
            prefix = ""
            if mode == "linear":
                prefix = "zscale=transferin=iec61966-2-1:transfer=linear,format=gbrp16,"
            if mode == "iaian7":
                special = method["special_pipeline"]
                side = "left" if label == "l" else "right"
                filt = f"colorchannelmixer={special[side + '_matrix_ffmpeg']},{special[side + '_lut_ffmpeg']}"
            else:
                filt = f"colorchannelmixer={method[matrix]}"
                if mode == "rendepth":
                    filt += ",lutrgb=r='clip(val,0,maxval)':g='clip(val,0,maxval)':b='clip(val,0,maxval)'"
            graph.append(f"[{label}]{prefix}{filt}[{label}m]")
        after = ""
        if mode == "linear":
            after = ",zscale=transferin=linear:transfer=iec61966-2-1,format=gbrp16"
        if mode == "iaian7":
            after += ",colorchannelmixer=" + method["special_pipeline"]["post_matrix_ffmpeg"]
        else:
            after += method.get("post_filter_ffmpeg", "")
        graph.append(f"[lm][rm]blend=all_mode=addition{after}[composite]")
        size = (display_w, display_h)
    pixel_format = "yuv420p"
    if options.target == "anaglyph" and options.profile != "compatible":
        pixel_format = "yuv444p10le" if options.profile == "quality10" else "yuv444p"
    if pixel_format == "yuv420p" and (size[0] % 2 or size[1] % 2):
        raise ValueError("4:2:0 benötigt gerade Ausgabemaße; diese Quelle muss zuerst passend vorbereitet werden.")
    graph.append("[composite]zscale=matrixin=gbr:primariesin=bt709:transferin=iec61966-2-1:rangein=full:"
                 "matrix=bt709:primaries=bt709:transfer=bt709:range=limited:dither=error_diffusion,"
                 f"format={pixel_format},setsar=1[v]")
    return ";".join(graph), size, pixel_format


def plan_job(tools: Toolchain, job: Job, output_root: Path, reserved: set[str],
             cancel: threading.Event | None = None, capabilities: dict | None = None) -> Plan:
    options = Options.from_dict(vars(job.options))  # Freeze decisions for execution.
    catalog = methods()
    if options.method not in catalog:
        raise ValueError("Anaglyphenverfahren nicht im geprüften Batch-Katalog.")
    before = job.source.stat() if job.source.is_file() else None
    info = probe(tools, job.source, cancel)
    after = job.source.stat()
    if not before or (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError("Die Quelldatei wurde während der Prüfung geändert.")
    info["source_mtime_ns"] = after.st_mtime_ns
    info["source_size"] = after.st_size
    video = info["video"]
    video["_start_offset"] = max(0, float(video.get("start_time") or 0) - float(info.get("format", {}).get("start_time") or 0))
    width, height = video.get("width", 0), video.get("height", 0)
    if not width or not height:
        raise ValueError("Keine gültige Videoauflösung.")
    if video.get("field_order", "unknown") not in {"progressive", "unknown"}:
        raise ValueError("Interlaced-Quelle: Eine geprüfte Deinterlacing-Regel ist noch nicht verfügbar.")
    sar = video.get("sample_aspect_ratio", "1:1")
    if options.target != "framerate" and sar not in {"1:1", "0:1", "N/A", None}:
        raise ValueError(f"Nichtquadratische Pixel (SAR {sar}) sind in dieser ersten Version noch nicht freigegeben.")
    for side in video.get("side_data_list", []):
        if side.get("side_data_type") in {"Spherical Mapping", "Display Matrix"}:
            raise ValueError("Gedrehte oder VR-projizierte Quelle: In dieser Version bitte vorher als normales SBS/OU vorbereiten.")
    hint_warning = None
    try:
        hint = filename_layout(job.source.stem)
    except ValueError as error:
        if options.layout == "auto":
            raise
        hint = None
        hint_warning = str(error) + " Manuelle Quellinterpretation verwendet."
    metadata = metadata_layout(video)
    warnings = [hint_warning] if hint_warning else []
    if options.layout == "auto":
        if not hint:
            raise ValueError("Full/Half-Layout nicht eindeutig erkennbar. Quelllayout für diese Datei auswählen.")
        layout, swapped = hint
        if metadata and metadata != ("sbs" if layout.endswith("sbs") else "ou", swapped):
            raise ValueError("Dateiname und Stereo-Metadaten widersprechen sich. Quelllayout bewusst auswählen.")
        swap = swapped ^ options.swap
    else:
        layout, swap = options.layout, options.swap
        if hint and hint != (layout, swap):
            warnings.append("Manuell gewähltes Layout/L/R weicht vom Dateinamen ab.")
        if metadata and metadata != ("sbs" if layout.endswith("sbs") else "ou", swap):
            warnings.append("Manuelle Quellinterpretation ersetzt abweichende Stereo-Metadaten.")
    if layout == "mono" and options.target != "framerate":
        raise ValueError("Mono/2D ist als Quelle für ‚Nur Framerate ändern‘ verfügbar; andere Ziele benötigen SBS/OU.")
    if options.target == "framerate":
        if options.swap:
            raise ValueError("Nur Framerate ändern erhält die Augenreihenfolge. L/R tauschen ausschalten.")
        orientation = "sbs" if layout.endswith("sbs") else "ou"
        swap = metadata[1] if metadata and metadata[0] == orientation else hint[1] if hint and hint[0] == layout else False
        if layout == "mono":
            if metadata or hint:
                raise ValueError("Stereo-Kennzeichnung an einer als Mono/2D gewählten Quelle; Quelllayout prüfen.")
            swap = False
        if swap and options.container == "mp4":
            raise ValueError("R/L-Quelle: Für unveränderte Augenreihenfolge MKV wählen; MP4-st3d unterstützt diese Umkehrung nicht.")
        warnings.append("Ganze Bilder werden ausgelassen/wiederholt; keine Überblendung oder Bewegungsinterpolation. "
                        "Video wird neu kodiert; Ton und Wiedergabegeschwindigkeit bleiben erhalten.")
    if layout != "mono" and (width if layout.endswith("sbs") else height) % 2:
        raise ValueError("Das gepackte Raster lässt sich nicht in zwei gleich große Ansichten teilen.")
    colors, color_warnings = color_spec(video)
    warnings.extend(color_warnings)
    if any(s.get("codec_type") == "subtitle" for s in info["streams"]):
        warnings.append("Untertitel werden in Version 0.1 nicht übernommen.")
    audios = [s for s in info["streams"] if s.get("codec_type") == "audio"]
    if options.container == "mp4":
        unsupported = {s.get("codec_name", "?") for s in audios} - {"aac", "mp3", "ac3", "eac3", "alac"}
        if unsupported:
            raise ValueError("Audio passt nicht zum MP4-Kopierprofil (" + ", ".join(sorted(unsupported)) + "). MKV wählen.")
    if options.target == "anaglyph":
        warnings.append("4:2:0: geringere Farbauflösung kann Anaglyphenqualität beeinträchtigen."
                        if options.profile == "compatible" else "4:4:4 wird nicht von allen Playern/Hardwaredecodern unterstützt.")
    graph, size, pixel_format = build_graph(video, options, layout, swap, colors, catalog[options.method])
    output_colors = dict(colors) if options.target == "framerate" else {
        "matrix": "bt709", "primaries": "bt709", "transfer": "bt709", "range": "tv"}
    if output_colors["matrix"] == "gbr":
        output_colors["matrix"] = "bt709"
    if capabilities:
        if options.codec == "h265" and not capabilities.get("h265"):
            raise ValueError("Dieser FFmpeg-Build enthält keinen H.265-Encoder.")
        if pixel_format not in capabilities.get(options.codec + "_formats", ""):
            raise ValueError("Der Encoder unterstützt das gewählte Pixelformat nicht.")
    folder = output_root.resolve()
    if job.source_root:
        try:
            folder = folder / job.source.resolve().parent.relative_to(job.source_root.resolve())
        except ValueError:
            raise ValueError("Quelle liegt nicht unter der gespeicherten Ordnerwurzel.") from None
    naming_options = replace(options, layout=layout, swap=swap) if options.target == "framerate" else options
    output = reserve_output(job.source, folder, naming_options, catalog[options.method]["suffix"], reserved)
    duration = 0.0
    try:
        duration = float(video.get("duration") or info.get("format", {}).get("duration") or 0)
        if not math.isfinite(duration) or duration < 0:
            duration = 0.0
    except (ValueError, TypeError):
        pass
    reason = f"{LAYOUTS[layout]} · " + (f"erkannt am Dateizusatz in {job.source.name}" if options.layout == "auto" else "manuell gewählt")
    return Plan(job.source.resolve(), output, options, info, layout, swap, size, pixel_format, graph, duration, warnings, output_colors, reason)


def command(tools: Toolchain, plan: Plan, temporary: Path) -> list[str]:
    options = plan.options
    args = [str(tools.ffmpeg), "-hide_banner", "-nostdin", "-n", "-loglevel", "warning",
            "-progress", "pipe:1", "-stats_period", "0.3",
            "-protocol_whitelist", "file,pipe", "-noautorotate", "-i", str(plan.source),
            "-filter_complex", plan.graph, "-map", "[v]", "-map", "0:a?", "-sn", "-dn",
            "-map_metadata", "-1", "-c:v", "libx264" if options.codec == "h264" else "libx265",
            "-preset", "slow", "-pix_fmt", plan.pixel_format,
            "-fps_mode", "passthrough", "-enc_time_base", "1/" + str(math.lcm(frame_rate(options.target_fps).numerator,
            Fraction(plan.info['video'].get('time_base', '1/1000')).denominator)) if options.target == "framerate"
            else str(plan.info['video'].get('time_base', '1/1000')), "-c:a", "copy",
            "-colorspace", plan.colors['matrix'], "-color_primaries", plan.colors['primaries'],
            "-color_trc", plan.colors['transfer'], "-color_range", plan.colors['range']]
    if options.rate_mode == "abr":
        args += ["-b:v", str(round(options.bitrate_mbps * 1_000_000))]
    else:
        args += ["-crf", str(options.crf)]
    layout = {("sbs", False): "left_right", ("sbs", True): "right_left",
              ("ou", False): "top_bottom", ("ou", True): "bottom_top"}.get(plan.stereo, "mono")
    args += ["-metadata:s:v:0", "stereo_mode=" + layout]
    if options.codec == "h264" and plan.stereo and not plan.stereo[1]:
        args += ["-x264-params", "frame-packing=" + ("3" if plan.stereo[0] == "sbs" else "4")]
    if options.container == "mp4" and temporary.suffix == ".mp4":
        args += ["-movflags", "+faststart"]
    for name in ("creation_time", "title", "artist", "copyright"):
        value = plan.info.get("format", {}).get("tags", {}).get(name)
        if isinstance(value, str):
            args += ["-metadata", name + "=" + value]
    return args + [str(temporary)]


def verify(tools: Toolchain, plan: Plan, path: Path, cancel: threading.Event) -> None:
    info = probe(tools, path, cancel)
    video = info["video"]
    if (video.get("width"), video.get("height")) != plan.size or str(video.get("pix_fmt", "")).replace("yuvj", "yuv") != plan.pixel_format:
        raise ValueError("Ausgabemaße oder Pixelformat entsprechen nicht dem geprüften Plan.")
    if video.get("codec_name") != ("h264" if plan.options.codec == "h264" else "hevc"):
        raise ValueError("Unerwarteter Ausgabecodec.")
    if any(video.get(k) != plan.colors[v] for k, v in (
            ("color_space", "matrix"), ("color_transfer", "transfer"), ("color_primaries", "primaries"), ("color_range", "range"))):
        raise ValueError("Die Farbkennzeichnung der Ausgabe stimmt nicht mit dem Plan überein.")
    expected_audio = [s.get("codec_name") for s in plan.info["streams"] if s.get("codec_type") == "audio"]
    actual_audio = [s.get("codec_name") for s in info["streams"] if s.get("codec_type") == "audio"]
    if actual_audio != expected_audio:
        raise ValueError("Die Audioübernahme stimmt nicht mit der Quelle überein.")
    if metadata_layout(video) != plan.stereo:
        raise ValueError("Die Stereo-Kennzeichnung der Ausgabe stimmt nicht mit dem Plan überein: " + json.dumps(video.get('side_data_list', [])))
    if plan.options.container == "mp4" and plan.stereo:
        if packed_stereo_boxes(path) != [2 if plan.stereo[0] == "sbs" else 1]:
            raise ValueError("Die explizite MP4-st3d-Kennzeichnung fehlt oder ist falsch.")
    if plan.stereo and plan.options.codec == "h264" and not plan.stereo[1]:
        frame_info = json.loads(capture([str(tools.ffprobe), "-v", "error", "-select_streams", "v:0",
            "-read_intervals", "%+#1", "-show_frames", "-of", "json", str(path)], cancel))
        if not frame_info.get("frames") or metadata_layout(frame_info["frames"][0]) != plan.stereo:
            raise ValueError("Die H.264-Frame-Packing-Kennzeichnung fehlt oder ist falsch.")
    if plan.options.target == "framerate":
        if Fraction(video.get("r_frame_rate", "0/1")) != frame_rate(plan.options.target_fps):
            raise ValueError("Die Zielbildrate wurde nicht korrekt gespeichert: " + json.dumps({k: video.get(k) for k in (
                'r_frame_rate', 'avg_frame_rate', 'time_base', 'start_time', 'duration', 'nb_frames')}))
        if plan.options.container == "mp4" and Fraction(video.get("avg_frame_rate", "0/1")) != frame_rate(plan.options.target_fps):
            raise ValueError("Die MP4-Bildzeiten entsprechen nicht der exakten Zielbildrate.")
        if video.get("sample_aspect_ratio", "1:1") != plan.info['video'].get("sample_aspect_ratio", "1:1"):
            raise ValueError("Das Pixelseitenverhältnis wurde unerwartet geändert.")
    if path.stat().st_size == 0:
        raise ValueError("Die Ausgabe ist leer.")


def publish_without_overwrite(temporary: Path, destination: Path, cancel: threading.Event) -> None:
    if cancel.is_set():
        raise Cancelled()
    try:
        os.link(temporary, destination)  # Atomic, fails if a destination already exists.
    except FileExistsError:
        raise ValueError("Das Ausgabeziel wurde zwischenzeitlich angelegt; es wird nicht überschrieben.") from None
    except OSError:
        # FAT/exFAT cannot hard-link: exclusive creation still protects existing files.
        owned = False
        try:
            with destination.open("xb") as out, temporary.open("rb") as source:
                owned = True
                while chunk := source.read(1024 * 1024):
                    if cancel.is_set():
                        raise Cancelled()
                    out.write(chunk)
        except BaseException:
            if owned:
                destination.unlink(missing_ok=True)
            raise
    temporary.unlink()


def execute(tools: Toolchain, plan: Plan, cancel: threading.Event, emit, log_path: Path) -> None:
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = plan.output.with_name("." + plan.output.stem + "." + uuid.uuid4().hex + ".part." + plan.options.container)
    # MKV exposes StereoMode as stream side data. A lossless remux transfers it
    # into MP4's st3d box; metadata:s:v alone does not create that MP4 box.
    encoded = temporary.with_suffix(".mkv") if plan.stereo and plan.options.container == "mp4" else temporary
    args = command(tools, plan, encoded)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tail = deque(maxlen=24)
    process = None
    readers = []
    with log_path.open("a", encoding="utf-8") as log:
        log.write("\n" + json.dumps({"source": str(plan.source), "output": str(plan.output),
                  "options": vars(plan.options), "warnings": plan.warnings, "args": args}, ensure_ascii=False) + "\n")
        log.flush()
        try:
            if cancel.is_set():
                raise Cancelled()
            stat = plan.source.stat()
            if (stat.st_mtime_ns, stat.st_size) != (plan.info["source_mtime_ns"], plan.info["source_size"]):
                raise ValueError("Quelle seit der Prüfung geändert. Erneut prüfen.")
            process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding="utf-8", errors="replace", bufsize=1, **process_options())
            def read_errors():
                for line in process.stderr:
                    tail.append(line.strip())
                    log.write(line)
            def read_progress():
                fps = None
                for line in process.stdout:
                    key, _, value = line.strip().partition("=")
                    if key == "out_time_us":
                        try:
                            seconds = max(0, int(value) / 1_000_000)
                            percent = min(99.0, seconds / plan.duration * 100) if plan.duration else None
                            emit("progress", {"percent": percent, "seconds": seconds})
                        except ValueError:
                            pass
                    elif key == "speed":
                        emit("speed", {"speed": value, "fps": fps})
                    elif key == "fps":
                        fps = value
            readers = [threading.Thread(target=f, daemon=True) for f in (read_errors, read_progress)]
            for reader in readers:
                reader.start()
            while process.poll() is None:
                if cancel.wait(.1):
                    stop_process(process)
                    break
            for reader in readers:
                reader.join(timeout=5)
            if cancel.is_set():
                raise Cancelled()
            if process.returncode:
                raise ValueError("FFmpeg: " + "\n".join(tail)[-3500:])
            if encoded != temporary:
                emit("phase", "MP4-3D-Kennzeichnung schreiben")
                remux = [str(tools.ffmpeg), "-v", "error", "-nostdin", "-n", "-i", str(encoded),
                         "-map", "0", "-c", "copy", "-strict", "unofficial", "-movflags", "+faststart"]
                if plan.options.target == "framerate":
                    # Recover the exact CFR grid after MKV's millisecond time base.
                    rate = frame_rate(plan.options.target_fps)
                    ticks = math.lcm(rate.numerator, Fraction(plan.info['video'].get('time_base', '1/1000')).denominator)
                    offset = plan.info['video']['_start_offset']
                    expression = lambda field: f"round(({field}*TB-{offset})*{rate.numerator}/{rate.denominator})*{ticks}*{rate.denominator}/{rate.numerator}+{offset}*{ticks}"
                    remux += ["-bsf:v", f"setts=time_base=1/{ticks}:pts={expression('PTS')}:dts={expression('DTS')}:duration={ticks}*{rate.denominator}/{rate.numerator}" + tools.setts_prescale]
                log.write("REMUX " + json.dumps(remux, ensure_ascii=False) + "\n")
                capture(remux + [str(temporary)], cancel, timeout=3600)
                packed_stereo_boxes(temporary, normalize=True)
            emit("phase", "Ausgabe prüfen")
            verify(tools, plan, temporary, cancel)
            if plan.source.stat().st_mtime_ns != plan.info["source_mtime_ns"]:
                raise ValueError("Die Quelldatei wurde während der Verarbeitung geändert.")
            emit("phase", "Abschließen")
            publish_without_overwrite(temporary, plan.output, cancel)
            log.write("VERIFIED " + plan.stereo_summary + "\nCOMPLETED " + str(plan.output) + "\n")
            emit("progress", {"percent": 100.0, "seconds": plan.duration})
        finally:
            if process:
                stop_process(process)
                for reader in readers:
                    reader.join(timeout=5)
                process.stdout.close()
                process.stderr.close()
            temporary.unlink(missing_ok=True)
            if encoded != temporary:
                encoded.unlink(missing_ok=True)


def preview(tools: Toolchain, plan: Plan, cancel: threading.Event, seconds: float = 0) -> bytes:
    if not math.isfinite(seconds) or seconds < 0 or (plan.duration and seconds >= plan.duration):
        raise ValueError("Zeitstelle liegt außerhalb des Videos.")
    graph = plan.graph + ";[v]scale=640:360:force_original_aspect_ratio=decrease:flags=lanczos,format=rgb24[preview]"
    return capture([str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin",
                    "-protocol_whitelist", "file,pipe", "-noautorotate",
                    "-ss", str(seconds), "-i", str(plan.source), "-filter_complex", graph,
                    "-map", "[preview]", "-frames:v", "1", "-c:v", "png", "-threads", "1",
                    "-f", "image2pipe", "pipe:1"], cancel, timeout=60)
