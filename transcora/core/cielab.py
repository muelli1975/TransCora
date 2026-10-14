"""The same separately executed, hash-pinned CIELab tool used by AnaChroma."""
from pathlib import Path
import hashlib
import json
import sys
from PIL import Image
from .model import app_root
from .engine import capture, Cancelled


def executable():
    folder = app_root()/'tools/cielab'
    tool = folder/('cielab.exe' if sys.platform == 'win32' else 'cielab')
    if not tool.is_file():
        raise ValueError('CIELAB fehlt. TransCora.zip vollständig entpacken.')
    return tool


def verify_tool():
    tool = executable()
    info = json.loads((tool.parent/'BUILD_INFO.json').read_text(encoding='utf-8'))
    if hashlib.sha256(tool.read_bytes()).hexdigest() != info['binary_sha256']:
        raise ValueError('CIELAB-Werkzeug stimmt nicht mit dem geprüften Build überein.')
    return tool


def render(image, plan, folder: Path, cancel, emit):
    from .images import resized_dimensions, fixed_image_size, fit_image_pixels
    if cancel.is_set(): raise Cancelled()
    horizontal = plan.layout.endswith('sbs')
    w, h = image.size
    if horizontal:
        halves = [image.crop((0, 0, w//2, h)), image.crop((w//2, 0, w, h))]
    else:
        halves = [image.crop((0, 0, w, h//2)), image.crop((0, h//2, w, h))]
    if plan.swap: halves.reverse()
    w, h = halves[0].size
    if plan.layout == 'half_sbs': w *= 2
    if plan.layout == 'half_ou': h *= 2
    # AnaChroma resizes before the iterative solver. Each half uses identical
    # dimensions and Lanczos; no additional transfer/gamma is applied here.
    frame = fixed_image_size(plan.options)
    size = frame or resized_dimensions((w, h), plan.options)
    for side, half in zip(('left', 'right'), halves):
        if frame:
            half = fit_image_pixels(half, (w, h), frame, plan.options.size_fit)
        elif half.size != size:
            half = half.resize(size, Image.Resampling.LANCZOS)
        half.convert('RGB').save(folder/(side+'.png'), compress_level=0)
    output = folder/'pixels.png'
    emit('phase', 'CIELAB: Halbbilder iterativ berechnen')
    capture([str(verify_tool()), str(folder/'left.png'), str(folder/'right.png'), '-o', str(output)], cancel, timeout=600)
    with Image.open(output) as result:
        result.load()
        if result.size != size or result.mode != 'RGB':
            raise ValueError('CIELAB liefert unerwartete Bildmaße oder ein falsches Farbformat.')
    return output

