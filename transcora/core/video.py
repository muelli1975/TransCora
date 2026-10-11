"""Progressive stereo preparation and explicit output geometry."""
from fractions import Fraction
import math


def requested_rate(options):
    from .model import frame_rate
    return frame_rate(options.target_fps) if options.fps_mode == 'custom' and options.target != 'bd3d' else None


def rate_ticks(video, rate):
    return math.lcm(rate.numerator, Fraction(video.get('time_base', '1/1000')).denominator)


def rate_filters(video, rate):
    """Convert complete stereo pairs on a fixed clock while retaining AV offset."""
    thinning = []
    try:
        source = Fraction(video.get('avg_frame_rate', '0/1')) * (2 if interlaced(video) else 1)
        nominal = Fraction(video.get('r_frame_rate', '0/1')) * (2 if interlaced(video) else 1)
        ratio = source / rate
        factor = round(ratio)
        if abs(source-nominal) <= source/1000 and abs(ratio-factor) <= Fraction(1, 1_000_000) and factor > 1:
            thinning = [f"select='not(mod(n,{factor}))'"]
    except (ValueError, ZeroDivisionError):
        pass
    return [*thinning, 'setpts=PTS-STARTPTS',
            f'fps=fps={rate}:start_time=0:round=near:eof_action=pass',
            f'settb=expr=1/{rate_ticks(video, rate)}',
            f"setpts=PTS+{video.get('_start_offset', 0)}/TB"]


def validate_screen(options):
    if any(type(v) is not int or not 2 <= v <= 16384 or v % 2
           for v in (options.screen_width, options.screen_height)):
        raise ValueError('Monitorauflösung: Gerade Pixelzahlen von 2 bis 16384 verwenden.')
    if options.row_first not in {'left', 'right'}:
        raise ValueError('Ungültige Augenzuordnung der ersten Zeile.')


def row_interleave_graph(options, display_width, display_height):
    """Resample once to the per-eye screen grid, then weave without filtering."""
    w, h = options.screen_width, options.screen_height
    factor = min(Fraction(w, display_width), Fraction(h, display_height))
    fw = max(2, min(w, 2*round(display_width*factor/2)))
    fh = max(1, min(h//2, round(display_height*factor/2)))
    graph = []
    for eye in ('l', 'r'):
        graph.append(f'[{eye}]scale={fw}:{fh}:flags=lanczos+accurate_rnd+full_chroma_int,'
                     f'pad={w}:{h//2}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,'
                     f'scale={w}:{h}:flags=neighbor[{eye}s]')
    order = '[rs][ls]' if options.row_first == 'right' else '[ls][rs]'
    graph.append(order + "blend=all_expr='if(eq(mod(Y,2),0),A,B)'[composite]")
    return graph


def interlaced(video):
    return video.get('field_order') in {'tt', 'bb', 'tb', 'bt'}


def deinterlace(video, y=0):
    if not interlaced(video):
        return ''
    top = video['field_order'] in {'tt', 'bt'}
    if y % 2:
        top = not top
    return 'bwdif=mode=send_field:parity='+('tff' if top else 'bff')+':deint=all,'


def output_dimensions(options, eye_width, eye_height):
    mode = options.video_size
    half = options.target in {'half_sbs', 'half_ou'}
    if mode == 'default':
        mode = '1080p' if half else 'original'
    if mode == 'original':
        return eye_width, eye_height
    if mode == 'custom':
        if options.target in {'full_sbs', 'cross_sbs'}:
            return options.video_width//2, options.video_height
        if options.target == 'full_ou':
            return options.video_width, options.video_height//2
        return options.video_width, options.video_height
    height = 1080 if mode == '1080p' else 2160
    if half or options.target == 'cross_sbs':
        # Cross-view presets specify a standard screen raster per eye.
        # Letterboxing in build_graph preserves the original picture shape.
        return height*16//9, height
    # Full layouts, mono and anaglyph keep the source eye's aspect ratio.
    return max(2, 2*round(Fraction(eye_width*height, 2*eye_height))), height
