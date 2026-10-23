"""One checked FFmpeg plan for manual files, folders and saved lists."""
from __future__ import annotations

from dataclasses import dataclass, replace, field
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

from .model import Job, Options, app_root, frame_rate, LAYOUTS, COMPATIBILITY_NOTE, ANAGLYPH_PLAYER_NOTE
from .naming import filename_layout, reserve_output
from .toolchain import Toolchain, process_options
from .mp4 import packed_stereo_boxes
from .video import requested_rate, rate_filters, rate_ticks
from .sdr_color import rgb_input, SDR_TAGS


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


def capture(args: list[str], cancel: threading.Event | None = None, timeout: float | None = None) -> bytes:
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **process_options())
    start = time.monotonic()
    try:
        while True:
            if cancel and cancel.is_set():
                raise Cancelled()
            if timeout is not None and time.monotonic() - start > timeout:
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


def probe(tools: Toolchain, path: Path, cancel: threading.Event | None = None, expected_videos: int = 1) -> dict:
    if not path.is_file():
        raise ValueError(f"Datei fehlt: {path}")
    args = [str(tools.ffprobe), "-v", "error", "-protocol_whitelist", "file,pipe",
            "-show_streams", "-show_format", "-of", "json", str(path.resolve())]
    result = json.loads(capture(args, cancel))
    videos = [s for s in result.get("streams", []) if s.get("codec_type") == "video"
              and not s.get("disposition", {}).get("attached_pic")]
    if not videos:
        raise ValueError("Keine nutzbare Videospur gefunden.")
    if len(videos) != expected_videos:
        raise ValueError("Die Anzahl der Videospuren entspricht nicht dem Ausgabeziel.")
    result["video"] = videos[0]
    return result


def methods() -> dict:
    path = app_root() / "presets" / "anaglyph_methods.reference.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return {m["id"]: m for m in data["methods"]}


def metadata_layout(video: dict) -> tuple[str, bool] | None:
    source_tags = {k.lower().rsplit('/', 1)[-1]: str(v).lower() for k, v in video.get('tags', {}).items()}
    tag = source_tags.get('stereo_mode', '')
    tags = {"left_right": ("sbs", False), "right_left": ("sbs", True),
            "top_bottom": ("ou", False), "bottom_top": ("ou", True),
            "row_interleaved_lr": ("rows", False), "row_interleaved_rl": ("rows", True),
            "block_lr": ("frames", False), "block_rl": ("frames", True)}
    if tag in tags:
        return tags[tag]
    numeric = {'1': ('sbs', False), '11': ('sbs', True), '3': ('ou', False), '2': ('ou', True),
               '7': ('rows', False), '6': ('rows', True), '13': ('frames', False), '14': ('frames', True)}
    if tag in numeric:
        return numeric[tag]
    wmv = {'sidebysidelf': ('sbs', False), 'sidebysiderf': ('sbs', True),
           'overunderlt': ('ou', False), 'overunderrt': ('ou', True)}
    if source_tags.get('stereoscopiclayout') in wmv:
        return wmv[source_tags['stereoscopiclayout']]
    for side in video.get("side_data_list", []):
        if side.get("side_data_type") == "Stereo 3D":
            kind = {"side by side": "sbs", "top and bottom": "ou", "interleaved lines": "rows", "frame alternate": "frames"}.get(side.get("type"))
            if kind:
                return kind, bool(side.get("inverted", 0))
            if side.get("type") not in (None, "2D", "unspecified"):
                raise ValueError("Dieses Stereo-Layout ist noch nicht freigegeben. SBS/OU-Quelle verwenden.")
    return None


def layout_axis(layout):
    return {'row_interleaved': 'rows', 'frame_sequential': 'frames'}.get(
        layout, 'sbs' if layout.endswith('sbs') else 'ou')


def metadata_full_half(video: dict) -> tuple[str, bool] | None:
    stereo = metadata_layout(video)
    if not stereo:
        return None
    axis, swap = stereo
    if axis in {'rows', 'frames'}:
        return ('row_interleaved' if axis == 'rows' else 'frame_sequential', swap)
    tags = {k.lower().rsplit('/', 1)[-1]: str(v).lower() for k, v in video.get('tags', {}).items()}
    half = tags.get('stereoscopichalfwidth' if axis == 'sbs' else 'stereoscopichalfheight')
    if half in {'1', 'true', 'yes'}:
        return ('half_'+axis, swap)
    if half in {'0', 'false', 'no'}:
        return ('full_'+axis, swap)
    sar = video.get('sample_aspect_ratio')
    if sar == ('2:1' if axis == 'sbs' else '1:2'):
        return ('half_'+axis, swap)
    # StereoMode alone specifies arrangement/order, not Full versus Half.
    return None


def color_spec(video: dict, layout=None) -> tuple[dict, list[str]]:
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
    # Existing values are authoritative; fill only missing SDR descriptions.
    for key, value in fields.items():
        if value not in missing_values and value not in supported[key]:
            raise ValueError(f"Noch nicht freigegebene Farbinterpretation: {key}={value}.")
    pixel_format = str(video.get("pix_fmt", ""))
    rgb = pixel_format.startswith(("gbr", "rgb", "bgr"))
    unknown_color = [key for key in ("matrix", "primaries", "transfer") if fields[key] in missing_values]
    if unknown_color:
        # Untagged ordinary SDR is usable. Follow existing colour hints first,
        # then the usual RGB/HD, PAL or NTSC interpretation, with a warning.
        family = next((fields[key] for key in ('matrix', 'primaries')
                       if fields[key] in {'bt709', 'bt470bg', 'smpte170m'}), None)
        if family is None:
            height = video.get('height', 0)//(2 if layout == 'full_ou' else 1)
            family = ('bt709' if rgb or height >= 720 else
                      'bt470bg' if height > 480 else 'smpte170m')
        defaults = {"matrix": "gbr" if rgb else family, "primaries": family,
                    "transfer": "iec61966-2-1" if rgb else
                    'smpte170m' if family in {'smpte170m', 'bt470bg'} else 'bt709'}
        for key in unknown_color:
            fields[key] = defaults[key]
            warnings.append(f"Farbannahme {key}={fields[key]} (fehlende SDR-Angabe)")
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
    review_warnings: list[str] = field(default_factory=list)

    @property
    def stereo(self) -> tuple[str, bool] | None:
        layout = self.layout if self.options.target == "framerate" else self.options.target
        # MP4 st3d cannot represent right-eye-first packing. Its physical R/L
        # raster stays intact; omit misleading stereo tags rather than claim L/R.
        if layout == "cross_sbs": return ("sbs", True) if self.options.container == "mkv" else None
        if layout == "row_interleaved":
            return ('rows', (self.swap if self.options.target == 'framerate' else self.options.row_first == 'right')) if self.options.container == 'mkv' else None
        if layout not in {"half_sbs", "full_sbs", "half_ou", "full_ou"}:
            return None
        if self.options.target == 'framerate' and self.swap and self.options.container == 'mp4':
            return None
        return ("sbs" if layout.endswith("sbs") else "ou", self.swap if self.options.target == "framerate" else False)

    @property
    def stereo_summary(self) -> str:
        if self.options.target == 'row_interleaved':
            return ('Zeilenverschachtelt: ' + ('R/L' if self.options.row_first == 'right' else 'L/R') +
                    (' · MKV-StereoMode' if self.options.container == 'mkv' else ' · MP4 ohne Stereo-Kennzeichnung'))
        if self.options.target == 'cross_sbs' and self.options.container == 'mp4':
            return 'Kreuzblick: R/L-Anordnung; MP4 ohne Stereo-Kennzeichnung.'
        if self.options.target == 'framerate' and self.swap and self.options.container == 'mp4':
            return 'Umgekehrte Augenreihenfolge bleibt erhalten; MP4 ohne Stereo-Kennzeichnung.'
        if self.options.target == "dual":
            return "Dual: Zwei eigenständige Videospuren · Links, dann rechts"
        if self.options.target == "bd3d":
            return "3D-Kennzeichnung: AVC-Basis + zweites MVC-Halbbild · Linkes Halbbild zuerst"
        if not self.stereo:
            return "3D-Kennzeichnung: Keine SBS/OU-Kennzeichnung"
        axis, inverted = self.stereo
        flags = "MKV-StereoMode" if self.options.container == "mkv" else "MP4-st3d"
        if self.options.codec == "h264" and not inverted:
            flags += f" · H.264 Frame-Packing {dict(sbs='3', ou='4', rows='2')[axis]}"
        return f"3D-Kennzeichnung: {flags} · {dict(sbs='SBS', ou='OU', rows='Zeilenverschachtelt')[axis]} · " + ("R/L" if inverted else "L/R")

    @property
    def summary(self) -> str:
        return self.summary_text()

    def summary_text(self, translate=None) -> str:
        from .audio import summary as audio_summary
        t = translate or (lambda text: text)
        video = self.info["video"]
        rate = video.get("avg_frame_rate", "?")
        try:
            fps = f"{float(Fraction(rate)):.3f}"
        except (ValueError, ZeroDivisionError):
            fps = "?"
        timing = ""
        if requested_rate(self.options):
            target = requested_rate(self.options)
            timing = f" → {float(target):.3f} fps ({target}) · Laufzeit unverändert"
        if self.options.target == "bd3d":
            from .bd3d import prepare, BD_RATE
            config = prepare(video, self.layout, self.swap, self.options.bd_mode)
            timing = f" → {float(config.rate):.3f} fps ({config.rate}) · " + (
                t("Video und Ton um 0,1 % verlangsamen") if config.speed != 1
                else t("Bildzeiten bei Bedarf anpassen") + " · " + t("Laufzeit erhalten"))
        codec = "AVC/MVC" if self.options.target == "bd3d" else self.options.codec.upper()
        return (f"{video['width']} × {video['height']} · {video.get('codec_name', '?')} · "
                f"{fps} fps ({rate}){timing} → {self.size[0]} × {self.size[1]} · "
                f"{codec} / {self.pixel_format}\n{self.layout_reason}\n"
                f"{self.stereo_summary}\n{audio_summary(self.info, self.options, translate)}\n{self.output}")


def build_graph(video: dict, options: Options, layout: str, swap: bool, colors: dict,
                method: dict) -> tuple[str, tuple[int, int], str]:
    from .video import deinterlace, interlaced, output_dimensions
    from .stereo_input import unpack, attach
    if layout in {'row_interleaved', 'frame_sequential'} and options.target != 'framerate':
        working, packed, prefix = unpack(video, layout)
        graph, size, pixel = build_graph(working, options, packed, swap, colors, method)
        return attach(prefix, graph, video['index']), size, pixel
    if options.target == 'dual':
        packed=replace(options,target='full_sbs',
                       video_width=options.video_width*2 if options.video_size=='custom' else options.video_width)
        graph,size,pixel=build_graph(video,packed,layout,swap,colors,method)
        width,height=size[0]//2,size[1]
        graph=graph.removesuffix('[v]')+'[dualpacked];[dualpacked]split[dl][dr];'
        graph+=f'[dl]crop={width}:{height}:0:0[left];[dr]crop={width}:{height}:{width}:0[right]'
        return graph,(width,height),pixel
    if layout == 'row_interleaved':
        video = dict(video, field_order='progressive')
    width, height = video["width"], video["height"]
    if options.target == "framerate":
        pixel_format = video.get("pix_fmt", "")
        rate = requested_rate(options)
        filters = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D",
                   "sidedata=mode=delete:type=SPHERICAL",
                   *([deinterlace(video).rstrip(",")] if interlaced(video) else []),
                   *(rate_filters(video, rate) if rate else [])]
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
        if interlaced(video) and layout != 'mono':
            horizontal = layout.endswith('sbs')
            ew, eh = (width//2, height) if horizontal else (width, height//2)
            x, y = (ew, 0) if horizontal else (0, eh)
            first = deinterlace(video).rstrip(',')
            second = deinterlace(video, y).rstrip(',')
            prefix = (f"[0:{video['index']}]split[fielda][fieldb];"
                      f"[fielda]crop={ew}:{eh}:0:0,{first}[fieldl];"
                      f"[fieldb]crop={ew}:{eh}:{x}:{y},{second}[fieldr];"
                      f"[fieldl][fieldr]{'hstack' if horizontal else 'vstack'}=inputs=2[fieldpacked];")
            filters[0] = filters[0].replace(f"[0:{video['index']}]", '[fieldpacked]')
            filters.remove(deinterlace(video).rstrip(','))
            return prefix + ",".join(filters), (width, height), pixel_format
        return ",".join(filters), (width, height), pixel_format
    horizontal = layout.endswith("sbs")
    eye_w, eye_h = (width // 2, height) if horizontal else (width, height // 2)
    display_w = eye_w * (2 if layout == "half_sbs" else 1)
    display_h = eye_h * (2 if layout == "half_ou" else 1)
    # Keep conventional SDR display values; method-specific linearization stays below.
    rgb = rgb_input(colors)
    # Crop before chroma reconstruction when the eye boundaries match the
    # source subsampling grid, so neighbouring eyes do not share interpolation.
    separate_colour = eye_w % 2 == 0 and eye_h % 2 == 0
    graph = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D,"
             'sidedata=mode=delete:type=SPHERICAL,' + ('' if separate_colour else rgb+',') + 'split[a][b]']
    positions = ((0, 0), (eye_w, 0)) if horizontal else ((0, 0), (0, eye_h))
    if swap:
        positions = positions[::-1]
    for label, (x, y), out in zip(("a", "b"), positions, ("l", "r")):
        scaling = ('' if options.target == 'row_interleaved' else
                   f'scale={display_w}:{display_h}:flags=lanczos+accurate_rnd+full_chroma_int,')
        graph.append(f"[{label}]crop={eye_w}:{eye_h}:{x}:{y}," +
                     deinterlace(video, y) + (rgb+',' if separate_colour else '') + scaling + f"setsar=1[{out}]")
    out_w, out_h = output_dimensions(options, display_w, display_h)
    if options.target == 'row_interleaved':
        from .video import row_interleave_graph
        graph.extend(row_interleave_graph(options, display_w, display_h))
        size = options.screen_width, options.screen_height
    elif options.target in {"half_sbs", "half_ou"}:
        # Letterbox each eye at full display geometry before halving one axis.
        for label in ("l", "r"):
            packed_w, packed_h = (out_w//2, out_h) if options.target == "half_sbs" else (out_w, out_h//2)
            graph.append(f"[{label}]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:"
                         "force_divisible_by=2:flags=lanczos+accurate_rnd+full_chroma_int,"
                         f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,"
                         f"scale={packed_w}:{packed_h}:flags=lanczos+accurate_rnd+full_chroma_int[{label}p]")
        stack = "hstack" if options.target == "half_sbs" else "vstack"
        graph.append(f"[lp][rp]{stack}=inputs=2[composite]")
        size = (out_w, out_h)
    elif options.target in {"full_sbs", "full_ou", "cross_sbs"}:
        for label in ("l", "r"):
            graph.append(f"[{label}]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:"
                         "force_divisible_by=2:flags=lanczos+accurate_rnd+full_chroma_int,"
                         f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black[{label}s]")
        stack = "hstack" if options.target in {"full_sbs", "cross_sbs"} else "vstack"
        order = "[rs][ls]" if options.target == "cross_sbs" else "[ls][rs]"
        graph.append(f"{order}{stack}=inputs=2[composite]")
        size = (out_w * (2 if options.target in {'full_sbs', 'cross_sbs'} else 1),
                out_h * (2 if options.target == 'full_ou' else 1))
    elif options.target == "mono":
        selected = 'l' if options.mono_eye == 'left' else 'r'
        other = 'r' if selected == 'l' else 'l'
        graph.append(f"[{other}]nullsink")
        graph.append(f"[{selected}]null[composite]")
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
    if options.target in {"mono", "anaglyph"} and (out_w, out_h) != size:
        graph[-1] = graph[-1].replace("[composite]", "[unscaled]")
        graph.append(f"[unscaled]scale={out_w}:{out_h}:force_original_aspect_ratio=decrease:"
                     "force_divisible_by=2:flags=lanczos+accurate_rnd+full_chroma_int,"
                     f"pad={out_w}:{out_h}:(ow-iw)/2:(oh-ih)/2:color=black[composite]")
        size = (out_w, out_h)
    pixel_format = "yuv420p"
    if options.target == 'row_interleaved' or options.target == "anaglyph" and options.profile != "compatible":
        pixel_format = "yuv444p10le" if options.profile == "quality10" else "yuv444p"
    if pixel_format == "yuv420p" and (size[0] % 2 or size[1] % 2):
        raise ValueError("4:2:0 benötigt gerade Ausgabemaße; diese Quelle muss zuerst passend vorbereitet werden.")
    # Matroska DisplayWidth/Height describe one reconstructed half-image.
    # FFmpeg divides the display axis by two when StereoMode is present.
    output_sar = ('2' if options.target == 'half_sbs' else '1/2') if (
        options.container == 'mkv' and options.target in {'half_sbs', 'half_ou'}) else '1'
    graph.append("[composite]zscale=matrixin=gbr:primariesin=bt709:transferin=iec61966-2-1:rangein=full:"
                 "matrix=bt709:primaries=bt709:transfer=iec61966-2-1:range=limited:dither=error_diffusion,"
                 f"format={pixel_format},{SDR_TAGS},setsar={output_sar}[v]")
    rate = requested_rate(options)
    if rate:
        graph[-1] = graph[-1].removesuffix('[v]')+'[beforefps]'
        graph.append('[beforefps]'+','.join(rate_filters(video, rate))+'[v]')
    return ";".join(graph), size, pixel_format


def plan_job(tools: Toolchain, job: Job, output_root: Path, reserved: set[str],
             cancel: threading.Event | None = None, capabilities: dict | None = None, phase=None) -> Plan:
    options = Options.from_dict(vars(job.options))  # Freeze decisions for execution.
    catalog = methods()
    if options.method not in catalog:
        raise ValueError("Anaglyphenverfahren nicht im geprüften Batch-Katalog.")
    before = job.source.stat() if job.source.is_file() else None
    from .multiview import inspect_source, graph_prefix
    def stage(text):
        if phase:
            phase(('BD-3D: ' if options.target == 'bd3d' else 'Testen: ')+text)
    info = inspect_source(tools, job.source, cancel, options.layout, phase=stage)
    after = job.source.stat()
    if not before or (before.st_mtime_ns, before.st_size) != (after.st_mtime_ns, after.st_size):
        raise ValueError("Die Quelldatei wurde während der Prüfung geändert.")
    info["source_mtime_ns"] = after.st_mtime_ns
    info["source_size"] = after.st_size
    video = info["video"]
    # ASF/WMV may carry stereo tags at container level; stream tags win.
    video['tags'] = {**info.get('format', {}).get('tags', {}), **video.get('tags', {})}
    video["_start_offset"] = max(0, float(video.get("start_time") or 0) - float(info.get("format", {}).get("start_time") or 0))
    width, height = video.get("width", 0), video.get("height", 0)
    if not width or not height:
        raise ValueError("Keine gültige Videoauflösung.")
    sar = video.get("sample_aspect_ratio", "1:1")
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
    multiview = info.get('multiview')
    warnings = [hint_warning] if hint_warning else []
    review_warnings = list(warnings)
    def review(message):
        warnings.append(message)
        review_warnings.append(message)
    from .video import interlaced
    try:
        metadata = None if multiview else metadata_layout(video)
        geometry_hint = None if multiview else metadata_full_half(video)
    except ValueError:
        if options.layout == 'auto':
            raise
        metadata = geometry_hint = None
        review('Manuelle Quellinterpretation ersetzt abweichende Stereo-Metadaten.')
    if multiview:
        if options.layout not in {'auto', 'mvc', 'mvhevc', 'dual'}:
            raise ValueError('Diese Quelle enthält echte Multiview-Halbbilder. Automatisch oder das passende Multiview-Format wählen.')
        if options.target == 'framerate':
            raise ValueError('Layout beibehalten erhält gepackte SBS/OU-Quellen. Für MVC/MV-HEVC zuerst das gewünschte Ausgabe-Layout wählen.')
        layout, swap = 'full_sbs', options.swap ^ bool(multiview.get('base_view_right', False))
        warnings.append('Dual: Zwei eigenständige Videospuren werden als L/R-Paar dekodiert.' if multiview['kind']=='dual' else 'Zwei vollständige Multiview-Halbbilder werden dekodiert.')
        if multiview['kind'] == 'mvc':
            warnings.append('MVC: Basis-Halbbild laut Blu-ray-Playlist '+('rechts' if multiview['base_view_right'] else 'links')+'.'
                if 'base_view_right' in multiview else
                'MVC: Links/rechts nicht gekennzeichnet; Basis-Halbbild wird als links verwendet. Bei umgekehrter Tiefenwirkung L/R tauschen.')
            if 'base_view_right' not in multiview:
                review_warnings.append(warnings[-1])
        if multiview.get('playlist'):
            warnings.append('Blu-ray-ISO: Längste Film-Playlist '+multiview['playlist']+' ausgewählt.')
    elif options.layout == "auto":
        if not hint:
            hint = geometry_hint
        if not hint:
            raise ValueError("Full/Half-Layout nicht eindeutig erkennbar. Quelllayout für diese Datei auswählen.")
        layout, swapped = hint
        if metadata and metadata != (layout_axis(layout), swapped):
            raise ValueError("Dateiname und Stereo-Metadaten widersprechen sich. Quelllayout bewusst auswählen.")
        swap = swapped ^ options.swap
    else:
        if options.layout in {'mvc', 'mvhevc', 'dual'}:
            raise ValueError('Die Quelle enthält nicht das gewählte Multiview-Format.')
        layout, swap = options.layout, options.swap
        if hint and hint != (layout, swap):
            review("Manuell gewähltes Layout/L/R weicht vom Dateinamen ab.")
        if metadata and metadata != (layout_axis(layout), swap):
            review("Manuelle Quellinterpretation ersetzt abweichende Stereo-Metadaten.")
    if interlaced(video) and layout != 'row_interleaved':
        warnings.append("Interlaced: Ein progressives Bild je Halbbildzeit; die zeitliche Auflösung bleibt erhalten. BD-3D und die Zielbildrate passen die Bildfolge anschließend an.")
    if layout == 'frame_sequential':
        if options.target == 'framerate':
            raise ValueError('Frame sequential: Ausgabe-Layout wählen; die Zielbildrate gilt für vollständige Stereobildpaare.')
        warnings.append('Frame sequential: Je zwei aufeinanderfolgende Halbbilder bilden ein Stereobildpaar. Die Paarbildrate ist die halbe Quellbildrate; ein ungepaartes Schlussbild wird ausgelassen.')
    elif layout == 'row_interleaved':
        warnings.append('Zeilenquelle: Stereo-Zeilen werden vor Skalierung getrennt. Die halbe vertikale Detailauflösung je Halbbild bleibt erhalten.')
    if options.target != 'framerate' and sar not in {'1:1', '0:1', 'N/A', None}:
        if (layout, sar) in {('half_sbs', '2:1'), ('half_ou', '1:2')}:
            video['sample_aspect_ratio'] = '1:1'
            warnings.append('Half-Layout: Gestauchte Achse wird je Halbbild rekonstruiert.')
        else:
            raise ValueError(f'Nichtquadratische Pixel (SAR {sar}): Quelllayout und Stereo-Metadaten prüfen.')
    if layout == "mono" and options.target != "framerate":
        raise ValueError("Mono/2D ist als Quelle für ‚Layout beibehalten‘ verfügbar; andere Ziele benötigen SBS/OU.")
    if options.target == "framerate":
        if options.swap:
            raise ValueError("Layout beibehalten erhält die Halbbildreihenfolge. L/R tauschen ausschalten.")
        orientation = layout_axis(layout)
        swap = metadata[1] if metadata and metadata[0] == orientation else hint[1] if hint and hint[0] == layout else False
        if layout == "mono":
            if metadata or hint:
                raise ValueError("Stereo-Kennzeichnung an einer als Mono/2D gewählten Quelle; Quelllayout prüfen.")
            swap = False
        if swap and options.container == "mp4":
            warnings.append('Umgekehrte Augenreihenfolge bleibt erhalten; MP4 ohne Stereo-Kennzeichnung.')
    if requested_rate(options):
        warnings.append("Ganze Bilder werden ausgelassen/wiederholt; keine Überblendung oder Bewegungsinterpolation. "
                        "Video wird neu kodiert; Ton und Wiedergabegeschwindigkeit bleiben erhalten.")
    if layout not in {"mono", "frame_sequential"} and (width if layout.endswith("sbs") else height) % 2:
        raise ValueError("Das gepackte Raster lässt sich nicht in zwei gleich große Halbbilder teilen.")
    colors, color_warnings = color_spec(video, layout)
    warnings.extend(color_warnings)
    # Established SDR defaults are explanations, not requests for user action.
    # Unsupported/ambiguous input still reports its existing actionable error.
    if layout.startswith('half_') and options.target in {'full_sbs', 'full_ou', 'cross_sbs'}:
        warnings.append('Half → Full: Die gestauchte Achse wird hochskaliert. Verlorene Bilddetails werden nicht wiederhergestellt.')
    if any(s.get("codec_type") == "subtitle" for s in info["streams"]):
        warnings.append("Untertitel werden nicht übernommen.")
    from .audio import validate
    stage('Auflösung, Bildrate und Tonoptionen prüfen')
    audios = validate(info, options)
    if options.target == "anaglyph":
        warnings.append(COMPATIBILITY_NOTE
                        if options.profile == "compatible" else ANAGLYPH_PLAYER_NOTE)
        if options.profile != 'compatible':
            review_warnings.append(ANAGLYPH_PLAYER_NOTE)
    if options.target == 'bd3d':
        from .bd3d import prepare
        from .bd3d_export import BdTools, validate_audio
        BdTools.find()
        preparation = prepare(video, layout, swap, options.bd_mode)
        validate_audio(audios)
        warnings.extend(preparation.warnings)
        warnings.append('BD-3D: FFmpeg bereitet die Quelle vor, FRIM kodiert AVC/MVC und tsMuxeR erstellt die Ausgabe. Gewählter Ton wird als LPCM gespeichert.')
        graph, size, pixel_format = preparation.graph, preparation.size, 'yuv420p'
    else:
        dual_rate = multiview and multiview['kind'] == 'dual' and requested_rate(options)
        graph_options = replace(options, fps_mode='source') if dual_rate else options
        graph_video = dict(video, field_order='progressive') if dual_rate else video
        graph, size, pixel_format = build_graph(graph_video, graph_options, layout, swap, colors, catalog[options.method])
    if options.target == 'dual':
        warnings.append('Dual: Zwei eigenständige Videospuren; Ausgabegröße gilt je Halbbild. Links ist die erste Spur, rechts die zweite.')
    graph = graph_prefix(info, graph, options)
    output_colors = dict(colors) if options.target == "framerate" else {
        "matrix": "bt709", "primaries": "bt709", "transfer": "bt709", "range": "tv"}
    if output_colors["matrix"] == "gbr":
        output_colors["matrix"] = "bt709"
    if capabilities and options.target != "bd3d":
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
    reason = (f"{multiview['kind'].upper()} · Zwei vollständige Halbbilder aus dem Bitstream" if multiview else
              f"{LAYOUTS[layout]} · " + ((f"erkannt am Dateizusatz in {job.source.name}" if filename_layout(job.source.stem)
                  else 'erkannt an Stereo-Metadaten und Halbbildgeometrie') if options.layout == "auto" else "manuell gewählt"))
    warnings = list(dict.fromkeys(warnings))
    review_warnings = list(dict.fromkeys(review_warnings))
    return Plan(job.source.resolve(), output, options, info, layout, swap, size, pixel_format, graph, duration, warnings, output_colors, reason, review_warnings)


def command(tools: Toolchain, plan: Plan, temporary: Path) -> list[str]:
    from .multiview import input_args
    options = plan.options
    mv = plan.info.get('multiview', {}).get('kind') in {'mvhevc','dual'}
    args = [str(tools.ffmpeg), "-hide_banner", "-nostdin", "-n", "-loglevel", "info" if mv else "warning",
            *(['-xerror', '-err_detect', 'explode'] if mv else []),
            "-progress", "pipe:1", "-stats_period", "0.3",
            "-protocol_whitelist", "file,pipe", "-noautorotate", *input_args(plan),
            "-filter_complex", plan.graph, *(['-map', '[left]', '-map', '[right]'] if options.target=='dual' else ['-map', '[v]']), "-sn", "-dn",
            "-map_metadata", "-1", "-c:v", "libx264" if options.codec == "h264" else "libx265",
            "-preset", "slow", "-pix_fmt", plan.pixel_format,
            "-fps_mode", "passthrough", "-enc_time_base",
            '1/'+str(rate_ticks(plan.info['video'], requested_rate(options))) if requested_rate(options)
            else str(Fraction(plan.info['video'].get('time_base', '1/1000')) /
                     (2 if plan.info['video'].get('field_order') in {'tt', 'bb', 'tb', 'bt'} else 1)), "-c:a", "copy",
            "-colorspace", plan.colors['matrix'], "-color_primaries", plan.colors['primaries'],
            "-color_trc", plan.colors['transfer'], "-color_range", plan.colors['range']]
    if options.rate_mode == "abr":
        args += ["-b:v", str(round(options.bitrate_mbps * 1_000_000))]
    else:
        args += ["-crf", str(options.crf)]
    from .audio import arguments
    args += arguments(plan.info, options, 1 if plan.info.get('runtime_input') else 0)
    layout = {("sbs", False): "left_right", ("sbs", True): "right_left",
              ("ou", False): "top_bottom", ("ou", True): "bottom_top",
              ("rows", False): "row_interleaved_lr", ("rows", True): "row_interleaved_rl"}.get(plan.stereo, "mono")
    args += ["-metadata:s:v:0", "stereo_mode=" + layout]
    if options.codec == "h264" and plan.stereo and not plan.stereo[1]:
        args += ["-x264-params", "frame-packing=" + {'sbs': '3', 'ou': '4', 'rows': '2'}[plan.stereo[0]]]
    if options.container == "mp4" and temporary.suffix == ".mp4":
        args += ["-movflags", "+faststart"]
    for name in ("creation_time", "title", "artist", "copyright"):
        value = plan.info.get("format", {}).get("tags", {}).get(name)
        if isinstance(value, str):
            args += ["-metadata", name + "=" + value]
    if options.target == 'dual':
        args += ['-metadata:s:v:0','title=Left','-metadata:s:v:1','title=Right',
                 '-disposition:v:0','default','-disposition:v:1','0']
    return args + [str(temporary)]


def verify_output_video(plan, video):
    """Apply the existing output metadata checks independently to each view."""
    if (video.get("width"), video.get("height")) != plan.size or str(video.get("pix_fmt", "")).replace("yuvj", "yuv") != plan.pixel_format:
        raise ValueError("Ausgabemaße oder Pixelformat entsprechen nicht dem geprüften Plan.")
    if video.get("codec_name") != ("h264" if plan.options.codec == "h264" else "hevc"):
        raise ValueError("Unerwarteter Ausgabecodec.")
    if any(video.get(k) != plan.colors[v] for k, v in (
            ("color_space", "matrix"), ("color_transfer", "transfer"), ("color_primaries", "primaries"), ("color_range", "range"))):
        raise ValueError("Die Farbkennzeichnung der Ausgabe stimmt nicht mit dem Plan überein.")
    from .video import interlaced
    if interlaced(plan.info['video']) and video.get('field_order') not in (None, 'unknown', 'progressive'):
        raise ValueError('Die deinterlacte Ausgabe ist nicht progressiv gekennzeichnet.')
    if metadata_layout(video) != plan.stereo:
        raise ValueError("Die Stereo-Kennzeichnung der Ausgabe stimmt nicht mit dem Plan überein: " + json.dumps(video.get('side_data_list', [])))
    if requested_rate(plan.options):
        if Fraction(video.get("r_frame_rate", "0/1")) != requested_rate(plan.options):
            raise ValueError("Die Zielbildrate wurde nicht korrekt gespeichert: " + json.dumps({k: video.get(k) for k in (
                'r_frame_rate', 'avg_frame_rate', 'time_base', 'start_time', 'duration', 'nb_frames')}))
        if plan.options.container == "mp4" and Fraction(video.get("avg_frame_rate", "0/1")) != frame_rate(plan.options.target_fps):
            raise ValueError("Die MP4-Bildzeiten entsprechen nicht der exakten Zielbildrate: " +
                             json.dumps({k: video.get(k) for k in ('r_frame_rate', 'avg_frame_rate',
                                                                  'time_base', 'duration', 'nb_frames')}))
    if plan.options.target == "framerate":
        if video.get("sample_aspect_ratio", "1:1") != plan.info['video'].get("sample_aspect_ratio", "1:1"):
            raise ValueError("Das Pixelseitenverhältnis wurde unerwartet geändert.")


def verify(tools: Toolchain, plan: Plan, path: Path, cancel: threading.Event) -> None:
    info = probe(tools, path, cancel, expected_videos=2 if plan.options.target=='dual' else 1)
    video = info["video"]
    videos = [stream for stream in info['streams'] if stream.get('codec_type') == 'video'
              and not stream.get('disposition',{}).get('attached_pic')]
    for output_video in videos:
        verify_output_video(plan, output_video)
    from .audio import selected, codec, channels
    tracks = selected(plan.info, plan.options)
    expected_audio = [codec(s, plan.options) for s in tracks]
    actual_audio = [s.get("codec_name") for s in info["streams"] if s.get("codec_type") == "audio"]
    if actual_audio != expected_audio:
        raise ValueError("Die Audioübernahme stimmt nicht mit der Quelle überein.")
    actual_channels = [s.get('channels') for s in info['streams'] if s.get('codec_type') == 'audio']
    if actual_channels != [channels(s, plan.options) for s in tracks]:
        raise ValueError('Die Kanalzahl des ausgegebenen Tons stimmt nicht mit dem Plan überein.')
    if plan.options.container == "mp4" and plan.stereo:
        if packed_stereo_boxes(path) != [2 if plan.stereo[0] == "sbs" else 1]:
            raise ValueError("Die explizite MP4-st3d-Kennzeichnung fehlt oder ist falsch.")
    if plan.stereo and plan.options.codec == "h264" and not plan.stereo[1]:
        frame_info = json.loads(capture([str(tools.ffprobe), "-v", "error", "-select_streams", "v:0",
            "-read_intervals", "%+#1", "-show_frames", "-of", "json", str(path)], cancel))
        if not frame_info.get("frames") or metadata_layout(frame_info["frames"][0]) != plan.stereo:
            raise ValueError("Die H.264-Frame-Packing-Kennzeichnung fehlt oder ist falsch.")
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
    from .multiview import runtime
    with runtime(tools, plan, cancel, emit=emit) as (working, decoder):
        return execute_prepared(tools, working, cancel, emit, log_path, decoder)


def execute_prepared(tools: Toolchain, plan: Plan, cancel: threading.Event, emit, log_path: Path, decoder=None) -> None:
    if plan.options.target == 'bd3d':
        from .bd3d_export import export
        return export(tools, plan, cancel, emit, log_path, decoder)
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = plan.output.with_name("." + plan.output.stem + "." + uuid.uuid4().hex + ".part." + plan.options.container)
    # MKV exposes StereoMode as stream side data. A lossless remux transfers it
    # into MP4's st3d box; metadata:s:v alone does not create that MP4 box.
    # FPS exports also use this pass to set every packet's exact target duration,
    # including the last packet in very short 2D files.
    remux_mp4 = plan.options.container == "mp4" and (plan.stereo and plan.stereo[0] != "rows" or requested_rate(plan.options))
    encoded = temporary.with_suffix(".mkv") if remux_mp4 else temporary
    args = command(tools, plan, encoded)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    tail = deque(maxlen=24)
    process = None
    readers = []
    from .multiview import PairClock, check_decoder
    pair_clock = PairClock() if plan.info.get('multiview', {}).get('kind') in {'mvhevc','dual'} else None
    errors = []
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
            process = subprocess.Popen(args, stdin=decoder.stdout if decoder else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       text=True, encoding="utf-8", errors="replace", bufsize=1, **process_options())
            def read_errors():
                for line in process.stderr:
                    if pair_clock:
                        try:
                            if pair_clock.line(line):
                                continue
                        except ValueError as error:
                            errors.append(error)
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
                if errors:
                    raise errors[0]
                if cancel.wait(.1):
                    stop_process(process)
                    break
            for reader in readers:
                reader.join(timeout=5)
            if cancel.is_set():
                raise Cancelled()
            if process.returncode:
                raise ValueError("FFmpeg: " + "\n".join(tail)[-3500:])
            if errors:
                raise errors[0]
            check_decoder(decoder, cancel)
            if pair_clock:
                pair_clock.finish()
            if encoded != temporary:
                emit("phase", "MP4-3D-Kennzeichnung schreiben" if plan.stereo else "MP4-Bildzeiten schreiben")
                remux = [str(tools.ffmpeg), "-v", "error", "-nostdin", "-n", "-i", str(encoded),
                         "-map", "0", "-c", "copy", "-strict", "unofficial", "-movflags", "+faststart"]
                if requested_rate(plan.options):
                    # Recover the exact CFR grid after MKV's millisecond time base.
                    rate = requested_rate(plan.options)
                    ticks = rate_ticks(plan.info['video'], rate)
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


def preview(tools: Toolchain, plan: Plan, cancel: threading.Event, seconds: float = 0, view: str = 'parallel') -> bytes:
    if not math.isfinite(seconds) or seconds < 0 or (plan.duration and seconds >= plan.duration):
        raise ValueError("Zeitstelle liegt außerhalb des Videos.")
    from .multiview import runtime, input_args
    with runtime(tools, plan, cancel, seconds) as (working, decoder):
        if view not in {'parallel', 'cross', 'anaglyph'}:
            raise ValueError('Ungültige Kontrollbildansicht.')
        stereo = ''
        if plan.options.target in {'bd3d','dual'}:
            order = '[right][left]' if view == 'cross' else '[left][right]'
            stereo = ';' + order + 'hstack=inputs=2'
            if view == 'anaglyph':
                stereo += ',stereo3d=sbsl:arcd'
            stereo += '[v]'
        graph = working.graph + stereo + ";[v]format=rgb24[preview]"
        if working.info.get('preview_trim'):
            index = working.info['video']['index']
            graph = graph.replace(f'[0:{index}]', f"[0:{index}]trim=start_frame={working.info['preview_trim']},", 1)
        args = [str(tools.ffmpeg), "-hide_banner", "-loglevel", "error", "-nostdin",
                "-protocol_whitelist", "file,pipe", "-noautorotate", *input_args(working, seconds=seconds),
                "-filter_complex", graph, "-map", "[preview]", "-frames:v", "1", "-c:v", "png", "-threads", "1",
                "-f", "image2pipe", "pipe:1"]
        if not decoder:
            return capture(args, cancel, timeout=60)
        process = subprocess.Popen(args, stdin=decoder.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **process_options())
        try:
            start = time.monotonic()
            while True:
                if cancel.is_set():
                    raise Cancelled()
                if time.monotonic()-start > 60:
                    raise ValueError('Kontrollbild: Dekodierung dauert zu lange.')
                try:
                    out, err = process.communicate(timeout=.15)
                    break
                except subprocess.TimeoutExpired:
                    continue
            if process.returncode:
                raise ValueError(err.decode('utf-8', 'replace')[-3500:])
            return out
        finally:
            stop_process(process)
