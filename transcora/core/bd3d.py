"""Fixed, tested 1080p23.976 MVC preparation."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import math
import re

from .engine import color_spec

BD_RATE = Fraction(24000, 1001)


@dataclass(frozen=True)
class Preparation:
    graph: str
    source_rate: Fraction
    speed: Fraction
    audio_filter: str
    warnings: tuple[str, ...]


def prepare(video: dict, layout: str, swap: bool = False) -> Preparation:
    if layout not in {'full_sbs', 'half_sbs', 'full_ou', 'half_ou'}:
        raise ValueError('BD-3D: Eindeutige SBS/OU-Quelle erforderlich.')
    if video.get('field_order') not in (None, 'unknown', 'progressive'):
        raise ValueError('BD-3D: Interlaced-Quellen sind noch nicht freigegeben.')
    try:
        rate = Fraction(video['r_frame_rate'])
        average = Fraction(video['avg_frame_rate'])
    except (KeyError, ValueError, ZeroDivisionError):
        raise ValueError('BD-3D: Quellbildrate fehlt oder ist ungültig.') from None
    # Container rationals may round 24000/1001. Actual cadence must also be scanned.
    if abs(rate - BD_RATE) <= BD_RATE / 1_000_000:
        rate = BD_RATE
    if abs(average - BD_RATE) <= BD_RATE / 1_000_000:
        average = BD_RATE
    if rate in {BD_RATE, Fraction(24)} and average in {BD_RATE, Fraction(24)}:
        # The average timing can be NTSC despite a rounded nominal 24-fps field.
        # A full timestamp scan below independently confirms the chosen clock.
        rate = average
    if not 1 <= rate <= 240 or abs(average-rate) > rate/1000:
        raise ValueError('BD-3D: Eine konstante, progressive Quellbildrate zwischen 1 und 240 fps ist erforderlich.')
    colors, warnings = color_spec(video)
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
        fitw, fith = 1920, max(2, 2*int(Fraction(1920, 2)/aspect))
    else:
        fitw, fith = max(2, 2*int(540*aspect)), 1080
    positions = [(0, 0), (ew, 0)] if horizontal else [(0, 0), (0, eh)]
    if swap:
        positions.reverse()
    conversion = '' if rate in {BD_RATE, Fraction(24)} else (
        f'setpts=PTS-STARTPTS,fps=fps={BD_RATE}:start_time=0:round=near:eof_action=pass,')
    # MVC needs BT.709 YUV, unlike anaglyph matrices it needs no sRGB working
    # space. Preserve native Blu-ray samples instead of resampling chroma and
    # dithering twice in a YUV -> RGB -> YUV round trip.
    native = (colors == {'matrix': 'bt709', 'primaries': 'bt709',
                        'transfer': 'bt709', 'range': 'tv'}
              and video.get('pix_fmt') == 'yuv420p')
    transform = '' if native else (
        f"zscale=matrixin={colors['matrix']}:primariesin={colors['primaries']}:"
        f"transferin={colors['transfer']}:rangein={'full' if colors['range']=='pc' else 'limited'}:"
        'matrix=bt709:primaries=bt709:transfer=bt709:range=limited:dither=error_diffusion,format=yuv420p,')
    graph = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D,"
             'sidedata=mode=delete:type=SPHERICAL,' + conversion + 'split[a][b]']
    for label, (x, y), eye in zip(('a', 'b'), positions, ('left', 'right')):
        sizing = (f'scale={fitw}:{fith}:flags=lanczos+accurate_rnd+full_chroma_int,'
                  'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,') if (
                      (ew, eh) != (fitw, fith) or (fitw, fith) != (1920, 1080)) else ''
        graph.append(f'[{label}]crop={ew}:{eh}:{x}:{y},' + transform + sizing +
                     f'setsar=1,format=yuv420p,settb=1/24000,setpts=N*1001[{eye}]')
    speed = BD_RATE / rate if rate == 24 else Fraction(1)
    if speed != 1:
        warnings.append('24 → 23,976 fps: Alle Bilder bleiben erhalten; Ton wird um 0,1 % verlangsamt.')
    elif rate != BD_RATE:
        warnings.append(f'{float(rate):.3f} → 23,976 fps: Ganze Stereobildpaare werden ausgelassen oder wiederholt. '
                        'Laufzeit und Ton bleiben erhalten; Bewegungen können ungleichmäßiger werden. '
                        'Keine Bewegungsinterpolation; Video wird nur einmal kodiert.')
    return Preparation(';'.join(graph), rate, speed,
                       'atempo=1000/1001' if speed != 1 else 'anull', tuple(warnings))


def check_cadence(timestamps: list[float], rate: Fraction, time_base: str) -> None:
    """Reject VFR and broken gaps instead of silently dropping/repeating source frames."""
    if len(timestamps) < 2:
        raise ValueError('BD-3D: Zu wenige Bilder für eine verlässliche Timing-Prüfung.')
    period = float(1/rate)
    tolerance = min(period/8, max(float(Fraction(time_base))*1.1, 0.00001))
    if any(not math.isfinite(t) for t in timestamps) or any(
            abs((b-a)-period) > tolerance for a, b in zip(timestamps, timestamps[1:])):
        raise ValueError('BD-3D: Variable Bildzeiten oder Bildlücken sind noch nicht freigegeben.')


class Cadence:
    """Check the original decoded clock while the encoder consumes the same frames."""
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


def encoder_args(executable: Path, left: Path, right: Path, base: Path, dependent: Path) -> list[str]:
    # FRIM rate control is the aggregate of both views, per the author's manual.
    return list(map(str, [executable, '-sw', '-i', left, right, '-viewoutput', '-o:mvc', base, dependent,
                         '-w', '1920', '-h', '1080', '-f', str(BD_RATE), '-I420',
                         '-vbr', '40000', '40000', '-u', '1', '-profile', 'high', '-level', '4.1',
                         '-gop', '24', '4', '0', 'S', '-cpbsize', '3750', '-l', '6', '-maxdpb', '4',
                         '-colormatrix', 'bt709', '-colorprim', 'bt709', '-colortransfer', 'bt709',
                         '-VuiNalHrd', 'on', '-PicTimingSEI', 'off', '-EndOfSequence', 'off']))


def mux_meta(base: Path, dependent: Path, audio: Path | None, *, disc=True, label=None, audios=None) -> str:
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
    result += f'V_MPEG4/ISO/AVC, "{base}", fps=23.976, insertSEI, contSPS\n'
    result += f'V_MPEG4/ISO/MVC, "{dependent}", fps=23.976, insertSEI, contSPS\n'
    for path, language in tracks:
        if len(language) != 3 or not language.isascii() or not language.isalpha():
            language = 'und'
        result += f'A_LPCM, "{path}", lang={language.lower()}\n'
    return result
