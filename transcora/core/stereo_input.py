"""Separate spatial rows or temporal half-images before existing transforms."""
from fractions import Fraction


def unpack(video, layout):
    """Return packed working geometry and an FFmpeg prefix, without decoding."""
    if layout not in {'row_interleaved', 'frame_sequential'}:
        return video, layout, ''
    working = dict(video, sample_aspect_ratio='1:1')
    pixel = str(video.get('pix_fmt', ''))
    depth = '10le' if any(n in pixel for n in ('10', '12', '16')) else ''
    # stereo3d needs planar samples. Reconstruct existing subsampled chroma
    # before rearranging rows; no temporal deinterlacer may touch stereo rows.
    planar = ('gbrp' if pixel.startswith(('gbr', 'rgb', 'bgr')) else 'yuv444p') + depth
    working['pix_fmt'] = planar
    if layout == 'row_interleaved':
        working['field_order'] = 'progressive'
        if video['height'] % 2:
            raise ValueError('Zeilenquelle benötigt eine gerade Zeilenzahl.')
        mode, packed = 'irl:ab2l', 'half_ou'
    else:
        working['width'] *= 2
        for key in ('avg_frame_rate', 'r_frame_rate'):
            try:
                working[key] = str(Fraction(video.get(key, '0/1')) / 2)
            except (ValueError, ZeroDivisionError):
                pass
        mode, packed = 'al:sbsl', 'full_sbs'
    prefix = (f"[0:{video['index']}]format={planar},stereo3d={mode},"
              'setsar=1[stereopair];')
    return working, packed, prefix


def attach(prefix, graph, index):
    return prefix + graph.replace(f'[0:{index}]', '[stereopair]') if prefix else graph
