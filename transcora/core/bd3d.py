"""Experimental 1080p MVC preparation. Kept separate from released GUI targets."""
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
import math

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
        raise ValueError('BD-3D: Interlaced-Quellen sind im Probelauf noch nicht freigegeben.')
    try:
        rate = Fraction(video['r_frame_rate'])
        average = Fraction(video['avg_frame_rate'])
    except (KeyError, ValueError, ZeroDivisionError):
        raise ValueError('BD-3D: Quellbildrate fehlt oder ist ungültig.') from None
    # Container rationals may round 24000/1001. Actual cadence must also be scanned.
    if abs(rate - BD_RATE) <= BD_RATE / 1_000_000:
        rate = BD_RATE
    if rate not in {BD_RATE, Fraction(24)} or abs(average-rate) > rate/1000:
        raise ValueError('BD-3D: Der erste Probelauf unterstützt konstante 23,976 oder 24 fps.')
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
    # Fit each reconstructed eye; never crop content or stretch mismatched aspect ratios.
    if aspect >= Fraction(16, 9):
        fitw, fith = 1920, max(2, 2*int(Fraction(1920, 2)/aspect))
    else:
        fitw, fith = max(2, 2*int(540*aspect)), 1080
    positions = [(0, 0), (ew, 0)] if horizontal else [(0, 0), (0, eh)]
    if swap:
        positions.reverse()
    graph = [f"[0:{video['index']}]sidedata=mode=delete:type=STEREO3D,"
             'sidedata=mode=delete:type=SPHERICAL,'
             f"zscale=matrixin={colors['matrix']}:primariesin={colors['primaries']}:"
             f"transferin={colors['transfer']}:rangein={'full' if colors['range']=='pc' else 'limited'}:"
             'matrix=gbr:primaries=bt709:transfer=iec61966-2-1:range=full,format=gbrp16,split[a][b]']
    for label, (x, y), eye in zip(('a', 'b'), positions, ('left', 'right')):
        graph.append(f'[{label}]crop={ew}:{eh}:{x}:{y},'
                     f'scale={fitw}:{fith}:flags=lanczos+accurate_rnd+full_chroma_int,'
                     'pad=1920:1080:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,'
                     'zscale=matrixin=gbr:primariesin=bt709:transferin=iec61966-2-1:rangein=full:'
                     'matrix=bt709:primaries=bt709:transfer=bt709:range=limited:dither=error_diffusion,'
                     f'format=yuv420p,settb=1/24000,setpts=N*1001[{eye}]')
    speed = BD_RATE / rate
    if speed != 1:
        warnings.append('24 → 23,976 fps: Alle Bilder bleiben erhalten; Ton wird um 0,1 % verlangsamt.')
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


def encoder_args(executable: Path, left: Path, right: Path, base: Path, dependent: Path) -> list[str]:
    # FRIM rate control is the aggregate of both views, per the author's manual.
    return list(map(str, [executable, '-sw', '-i', left, right, '-viewoutput', '-o:mvc', base, dependent,
                         '-w', '1920', '-h', '1080', '-f', str(BD_RATE), '-I420',
                         '-vbr', '28000', '40000', '-u', '1', '-profile', 'high', '-level', '4.1',
                         '-gop', '24', '4', '0', 'O', '-cpbsize', '3570', '-l', '6', '-rf', '4',
                         '-colormatrix', 'bt709', '-colorprim', 'bt709', '-colortransfer', 'bt709',
                         '-VuiNalHrd', 'on', '-PicTimingSEI', 'off', '-EndOfSequence', 'off']))


def mux_meta(base: Path, dependent: Path, audio: Path | None) -> str:
    paths = [base, dependent] + ([audio] if audio else [])
    if any(any(c in str(p) for c in ('"', '\n', '\r')) for p in paths):
        raise ValueError('BD-3D: Ungültiger Pfad für die Multiplexer-Datei.')
    result = 'MUXOPT --no-pcr-on-video-pid --new-audio-pes --blu-ray --vbr --vbv-len=500\n'
    result += f'V_MPEG4/ISO/AVC, "{base}", fps=23.976, insertSEI, contSPS\n'
    result += f'V_MPEG4/ISO/MVC, "{dependent}", fps=23.976, insertSEI, contSPS\n'
    if audio:
        result += f'A_LPCM, "{audio}", lang=deu\n'
    return result
