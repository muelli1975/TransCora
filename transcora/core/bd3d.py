"""Blu-ray 3D MVC preparation for 1080p23.976 and 720p50/59.94."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import math
import re

from .engine import color_spec

BD_RATE = Fraction(24000, 1001)


def output_mode(mode="1080p"):
    return {"1080p": (1920, 1080, BD_RATE),
            "720p50": (1280, 720, Fraction(50)),
            "720p5994": (1280, 720, Fraction(60000, 1001))}[mode]


@dataclass(frozen=True)
class Preparation:
    graph: str
    source_rate: Fraction
    speed: Fraction
    audio_filter: str
    warnings: tuple[str, ...]
    size: tuple[int, int]
    rate: Fraction


def prepare(video: dict, layout: str, swap: bool = False, mode: str = "1080p") -> Preparation:
    from .stereo_input import unpack, attach
    if layout in {'row_interleaved', 'frame_sequential'}:
        working, packed, prefix = unpack(video, layout)
        result = prepare(working, packed, swap, mode)
        from dataclasses import replace
        return replace(result, graph=attach(prefix, result.graph, video['index']))
    outw, outh, output_rate = output_mode(mode)
    rate_label = {"1080p": "23,976", "720p50": "50", "720p5994": "59,94"}[mode]
    if layout not in {'full_sbs', 'half_sbs', 'full_ou', 'half_ou'}:
        raise ValueError('BD-3D: Eindeutige SBS/OU-Quelle erforderlich.')
    from .video import interlaced, deinterlace
    fields = interlaced(video)
    def valid_rate(key):
        try:
            value = Fraction(video.get(key, '0/1'))
            return value if value > 0 else None
        except (ValueError, ZeroDivisionError, TypeError):
            return None
    rate, average = valid_rate('r_frame_rate'), valid_rate('avg_frame_rate')
    if rate is None and average is None:
        raise ValueError('BD-3D: Quellbildrate fehlt oder ist ungültig.')
    rate, average = rate or average, average or rate
    # Container rationals may round 24000/1001. Inspect actual PTS while encoding.
    if abs(rate - BD_RATE) <= BD_RATE / 1_000_000:
        rate = BD_RATE
    if abs(average - BD_RATE) <= BD_RATE / 1_000_000:
        average = BD_RATE
    if rate in {BD_RATE, Fraction(24)} and average in {BD_RATE, Fraction(24)}:
        # The average timing can be NTSC despite a rounded nominal 24-fps field.
        # Source PTS are checked independently while encoding.
        rate = average
    # A differing average is normal for VFR, not evidence of damaged video.
    variable = abs(average-rate) > rate/1000
    if variable:
        rate = average
    colors, warnings = color_spec(video, layout)
    w, h = video['width'], video['height']
    horizontal = layout.endswith('sbs')
    if w <= 0 or h <= 0 or (w if horizontal else h) % 2:
        raise ValueError('BD-3D: Ungültige oder unteilbare Stereo-Auflösung.')
    ew, eh = (w//2, h) if horizontal else (w, h//2)
    try:
        sar = Fraction(video.get('sample_aspect_ratio', '1:1').replace(':', '/'))
    except (ValueError, ZeroDivisionError):
        sar = Fraction(1)
    if sar <= 0:
        sar = Fraction(1)
    aspect = Fraction(ew, eh)*sar
    if layout == 'half_sbs':
        aspect *= 2
    elif layout == 'half_ou':
        aspect /= 2
    # Fit each reconstructed half-image without cropping or stretching.
    if aspect >= Fraction(16, 9):
        fitw, fith = outw, max(2, 2*int(Fraction(outw, 2)/aspect))
    else:
        fitw, fith = max(2, 2*int(Fraction(outh, 2)*aspect)), outh
    positions = [(0, 0), (ew, 0)] if horizontal else [(0, 0), (0, eh)]
    if swap:
        positions.reverse()
    # Normalise the complete packed pair before splitting it. Even a stream
    # labelled CFR may have valid timestamp jitter or variable frame durations.
    # Exact 24-fps sources retain their established 0.1% slowdown below.
    slowdown = mode == "1080p" and rate == 24 and not variable and not fields
    cadence_rate = Fraction(24) if slowdown else output_rate
    conversion = (f'setpts=PTS-STARTPTS,fps=fps={cadence_rate}:'
                  'start_time=0:round=near:eof_action=pass,')
    # MVC needs BT.709 YUV, unlike anaglyph matrices it needs no sRGB working
    # space. Preserve native Blu-ray samples instead of resampling chroma and
    # dithering twice in a YUV -> RGB -> YUV round trip.
    native = (colors == {'matrix': 'bt709', 'primaries': 'bt709',
                        'transfer': 'bt709', 'range': 'tv'}
              and video.get('pix_fmt') == 'yuv420p')
    from .sdr_color import display_transfer, SDR_TAGS
    transform = '' if native else (
        f"zscale=matrixin={colors['matrix']}:primariesin={colors['primaries']}:"
        f"transferin={display_transfer(colors['transfer'])}:rangein={'full' if colors['range']=='pc' else 'limited'}:"
        'matrix=bt709:primaries=bt709:transfer=iec61966-2-1:range=limited:dither=error_diffusion,format=yuv420p,'
        + SDR_TAGS + ',')
    graph = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D,"
             'sidedata=mode=delete:type=SPHERICAL,' + ('' if fields else conversion) + 'split[a][b]']
    for label, (x, y), eye in zip(('a', 'b'), positions, ('left', 'right')):
        sizing = (f'scale={fitw}:{fith}:flags=lanczos+accurate_rnd+full_chroma_int,'
                  f'pad={outw}:{outh}:(ow-iw)/2:(oh-ih)/2:color=black,') if (
                      (ew, eh) != (fitw, fith) or (fitw, fith) != (outw, outh)) else ''
        graph.append(f'[{label}]crop={ew}:{eh}:{x}:{y},' +
                     (deinterlace(video, y) + conversion if fields else '') + transform + sizing +
                     f'setsar=1,format=yuv420p,settb=1/{output_rate.numerator},setpts=N*{output_rate.denominator}[{eye}]')
    speed = BD_RATE / rate if slowdown else Fraction(1)
    if speed != 1:
        warnings.append('24 → 23,976 fps: Video und Ton werden um 0,1 % verlangsamt; bei konstanten Bildzeiten bleiben alle Bilder erhalten.')
    elif variable:
        warnings.append(f'Variable Bildzeiten → {rate_label} fps: Ganze Stereobildpaare werden bei Bedarf ausgelassen oder wiederholt. Laufzeit und Ton bleiben erhalten.')
    elif rate != output_rate:
        warnings.append(f'{float(rate):.3f} → {rate_label} fps: Ganze Stereobildpaare werden ausgelassen oder wiederholt. '
                        'Laufzeit und Ton bleiben erhalten; Bewegungen können ungleichmäßiger werden. '
                        'Keine Bewegungsinterpolation; Video wird nur einmal kodiert.')
    return Preparation(';'.join(graph), rate, speed,
                       'atempo=1000/1001' if speed != 1 else 'anull', tuple(warnings), (outw, outh), output_rate)


def check_cadence(timestamps: list[float], rate: Fraction, time_base: str) -> None:
    """Validate the fixed output cadence; variable source PTS use SourceClock."""
    if len(timestamps) < 2:
        raise ValueError('BD-3D: Zu wenige Bilder für eine verlässliche Timing-Prüfung.')
    period = float(1/rate)
    tolerance = min(period/8, max(float(Fraction(time_base))*1.1, 0.00001))
    if any(not math.isfinite(t) for t in timestamps) or any(
            abs((b-a)-period) > tolerance for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('BD-3D: Die erzeugte Bildfolge entspricht nicht der festen Ausgabebildrate.')


class Cadence:
    """Development-only clock measurement; production exports use FFmpeg timing."""
    def __init__(self, rate, time_base, name='bd_clock'):
        self.rate = rate
        self.name = name
        self.time_base = Fraction(time_base)
        self.count = 0
        self.first = self.previous = None

    def feed(self, stamp):
        if self.previous is None:
            if not math.isfinite(stamp):
                raise ValueError('BD-3D: Ungültige Bildzeit in der Quelle.')
            self.first = stamp
        else:
            check_cadence([self.previous, stamp], self.rate, str(self.time_base))
        self.previous = stamp
        self.count += 1

    def line(self, line):
        if 'showinfo@'+self.name not in line:
            return False
        match = re.search(r'config in time_base:\s*(\d+/\d+)', line)
        if match:
            self.time_base = Fraction(match[1])
        elif re.search(r'\bn:\s*\d+', line):
            match = re.search(r'\bpts:\s*(-?\d+)\s+pts_time:', line)
            if not match:
                raise ValueError('BD-3D: Fehlende Bildzeit in der Quelle.')
            self.feed(float(int(match[1])*self.time_base))
        return True

    def finish(self):
        if self.count < 2:
            raise ValueError('BD-3D: Zu wenige Bilder für eine verlässliche Timing-Prüfung.')
        period = float(1/self.rate)
        tolerance = min(period/8, max(2.2*float(self.time_base), .00001))
        if abs((self.previous-self.first)-float((self.count-1)/self.rate)) > tolerance:
            raise ValueError('BD-3D: Die tatsächliche Bildfolge entspricht nicht der angegebenen konstanten Framerate.')
        return self.count, self.first


class SourceClock(Cadence):
    """Validate source timestamps without treating valid VFR as corruption.

    Collected during encoding; no separate full decode or timestamp scan.
    The output still uses the strict Cadence checker on its fixed BD clock.
    """
    def __init__(self, rate, time_base):
        super().__init__(rate, time_base)
        self.constant = True
        self.max_interval = 0.0

    def feed(self, stamp):
        if not math.isfinite(stamp):
            raise ValueError('BD-3D: Ungültige Bildzeit in der Quelle.')
        if self.previous is None:
            self.first = stamp
        else:
            interval = stamp-self.previous
            if interval <= 0:
                raise ValueError(f'BD-3D: Nicht aufsteigende Bildzeit bei Bild {self.count+1}: {stamp:.6f} s nach {self.previous:.6f} s.')
            self.max_interval = max(self.max_interval, interval)
            try:
                check_cadence([self.previous, stamp], self.rate, str(self.time_base))
            except ValueError:
                self.constant = False
        self.previous = stamp
        self.count += 1

    def finish(self):
        if self.count < 2:
            raise ValueError('BD-3D: Zu wenige Bilder für eine verlässliche Timing-Prüfung.')
        tolerance = min(float(1/self.rate)/8, max(2.2*float(self.time_base), .00001))
        if abs((self.previous-self.first)-float((self.count-1)/self.rate)) > tolerance:
            self.constant = False
        return self.count, self.first


def encoder_args(executable: Path, left: Path, right: Path, base: Path, dependent: Path, bitrate_mbps: int = 40, *, mode="1080p") -> list[str]:
    from .model import BD_BITRATES
    if type(bitrate_mbps) is not int or bitrate_mbps not in BD_BITRATES:
        raise ValueError('Ungültige BD-3D-Bitrate.')
    kbps = str(bitrate_mbps * 1000)
    width, height, rate = output_mode(mode)
    # FRIM rate control is the aggregate of both views, per the author's manual.
    return list(map(str, [executable, '-sw', '-i', left, right, '-viewoutput', '-o:mvc', base, dependent,
                         '-w', str(width), '-h', str(height), '-f', str(rate), '-I420',
                         '-vbr', kbps, kbps, '-u', '1', '-profile', 'high', '-level', '4.1',
                         '-gop', '24' if mode == '1080p' else '48', '4', '0', 'S', '-cpbsize', '3750', '-l', '6', '-maxdpb', '4',
                         '-colormatrix', 'bt709', '-colorprim', 'bt709', '-colortransfer', 'bt709',
                         '-VuiNalHrd', 'on', '-PicTimingSEI', 'off', '-EndOfSequence', 'off']))


def mux_meta(base: Path, dependent: Path, audio: Path | None, *, disc=True, label=None, audios=None, mode="1080p") -> str:
    tracks = audios if audios is not None else ([(audio, 'und')] if audio else [])
    paths = [base, dependent] + [p for p, _ in tracks]
    if any(any(c in str(p) for c in ('"', '\n', '\r')) for p in paths):
        raise ValueError('BD-3D: Ungültiger Pfad für die Multiplexer-Datei.')
    result = 'MUXOPT --no-pcr-on-video-pid --new-audio-pes --vbr --vbv-len=500'
    if disc:
        result += ' --blu-ray'
        if label:
            if any(c in label for c in ('\"', '\n', '\r')):
                raise ValueError('BD-3D: Ungültiger Disc-Titel.')
            result += ' --label=\"' + label + '\"'
    result += '\n'
    fps = {'1080p': '23.976', '720p50': '50', '720p5994': '59.94'}[mode]
    result += f'V_MPEG4/ISO/AVC, "{base}", fps={fps}, insertSEI, contSPS\n'
    result += f'V_MPEG4/ISO/MVC, "{dependent}", fps={fps}, insertSEI, contSPS\n'
    for path, language in tracks:
        if len(language) != 3 or not language.isascii() or not language.isalpha():
            language = 'und'
        result += f'A_LPCM, "{path}", lang={language.lower()}\n'
    return result
