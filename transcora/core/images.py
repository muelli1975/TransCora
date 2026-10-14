"""Checked still-image batches; FFmpeg transforms pixels, ExifTool copies metadata."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from fractions import Fraction
import io
import json
import os
import re
import shutil
import sys
import tempfile
import threading
import uuid

from PIL import Image, ImageCms, ImageOps
from .engine import Cancelled, build_graph, capture, methods, publish_without_overwrite
from .model import Options, app_root
from .naming import clean_stem, filename_layout
from .storage import write_json

from .heif import EXTENSIONS as HEIF_EXTENSIONS

EXTENSIONS = HEIF_EXTENSIONS | {'.jpg', '.jpeg', '.jps', '.png', '.pns', '.tif', '.tiff', '.bmp', '.webp', '.mpo'}
TASKS = {'convert': 'Bilder konvertieren', 'mpo': 'MPO verlustfrei teilen'}
LAYOUTS = {'auto': 'Automatisch', 'mono': 'Mono / 2D', 'full_sbs': 'Full-SBS', 'half_sbs': 'Half-SBS',
           'full_ou': 'Full-OU', 'half_ou': 'Half-OU', 'row_interleaved': 'Zeilenverschachtelt'}
TARGETS = {'keep': 'Layout beibehalten', 'full_sbs': 'Full-SBS', 'full_ou': 'Full-OU',
           'row_interleaved': 'Zeilenverschachtelt (Polfilter)',
           'half_sbs': 'Half-SBS', 'half_ou': 'Half-OU', 'anaglyph': 'Anaglyph',
           'left': 'Linkes Halbbild', 'right': 'Rechtes Halbbild', 'split': 'Beide Halbbilder teilen'}
FORMATS = {'jpeg': 'JPEG', 'png': 'PNG', 'tiff': 'TIFF', 'webp': 'WebP (verlustfrei)'}
SIZES = {'original': 'Original', '1080p': '1080p', '2160p': '2160p',
         '2048': '2048 lange Seite', 'custom': 'Benutzerdefiniert'}
SIZE_EDGES = {'long': 'lange Seite', 'short': 'kurze Seite'}
SIZE_FITS = {'scale': 'Proportional skalieren', 'pad': 'Mit schwarzen Balken auffüllen',
             'crop': 'Bildfüllend zuschneiden'}
SUFFIX = {'jpeg': '.jpg', 'png': '.png', 'tiff': '.tif', 'webp': '.webp'}
SRGB = ImageCms.ImageCmsProfile(ImageCms.createProfile('sRGB')).tobytes()


def image_methods():
    return dict(methods(), cielab={'label': 'CIELAB Least Squares (David McAllister)', 'suffix': 'cielab'})


@dataclass
class ImageOptions:
    task: str = 'convert'
    layout: str = 'auto'
    target: str = 'keep'
    format: str = 'jpeg'
    quality: int = 90
    long_edge: int = 0
    size_mode: str = 'original'
    size_fit: str = 'scale'
    size_edge: str = 'long'
    size_pixels: int = 2048
    swap: bool = False
    metadata: bool = True
    method: str = 'dubois_lcd'
    screen_width: int = 1920
    screen_height: int = 1080
    row_first: str = 'left'

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or set(data)-set(cls.__dataclass_fields__):
            raise ValueError('Ungültige Bildeinstellungen.')
        data = dict(data)
        if 'size_mode' not in data and data.get('long_edge', 0):
            data.update(size_mode='custom', size_pixels=data['long_edge'], long_edge=0)
        result = cls(**data)
        result.validate()
        return result

    def validate(self):
        from .video import validate_screen
        validate_screen(self)
        for key, choices in [('task', TASKS), ('layout', LAYOUTS), ('target', TARGETS), ('format', FORMATS)]:
            if getattr(self, key) not in choices:
                raise ValueError('Ungültige Bildeinstellung: '+key)
        if self.quality not in (90, 95) or type(self.long_edge) is not int or not 0 <= self.long_edge <= 20000:
            raise ValueError('JPEG-Qualität: 90/95. Lange Kante: 0 (Original) bis 20000 Pixel.')
        if type(self.swap) is not bool or type(self.metadata) is not bool or self.method not in image_methods():
            raise ValueError('Ungültige Bild-, Metadaten- oder Anaglypheneinstellung.')
        if self.size_fit not in SIZE_FITS:
            raise ValueError('Ungültige Bildanpassung.')
        if self.size_mode not in SIZES or self.size_edge not in SIZE_EDGES or type(self.size_pixels) is not int or not 1 <= self.size_pixels <= 20000:
            raise ValueError('Eine positive Pixelzahl bis 20000 und lange/kurze Seite wählen.')


@dataclass
class ImageJob:
    source: Path
    options: ImageOptions = field(default_factory=ImageOptions)
    source_root: Path | None = None
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = 'queued'
    detail: str = 'Noch nicht geprüft'
    result: object | None = None

    def serializable(self):
        return {'source': str(self.source), 'source_root': str(self.source_root) if self.source_root else None,
                'options': asdict(self.options)}


@dataclass(frozen=True)
class ImagePlan:
    sources: tuple[Path, ...]
    outputs: tuple[Path, ...]
    options: ImageOptions
    layout: str
    swap: bool
    size: tuple[int, int]
    stamps: tuple[tuple[int, int], ...]
    warnings: tuple[str, ...]

    @property
    def summary(self):
        if self.options.task == 'mpo':
            return (f'{TASKS[self.options.task]}\nAusgabe: Original-JPEGs ohne Neukodierung\n' +
                    '\n'.join(map(str, self.outputs)) +
                    ('\n'+'\n'.join(self.warnings) if self.warnings else ''))
        if self.options.task == 'convert':
            _, size = image_graph(self)
            if self.options.target == 'split': size = (size[0]//2, size[1])
        else:
            size = (self.size[0]//2, self.size[1]) if self.options.task == 'mpo' else self.size
        return (f'{TASKS[self.options.task]} · {self.size[0]} × {self.size[1]} · '
                f'{LAYOUTS.get(self.layout, self.layout)}\nAusgabe: {size[0]} × {size[1]} Pixel je Datei\n' + '\n'.join(map(str, self.outputs)) +
                ('\n'+'\n'.join(self.warnings) if self.warnings else ''))


def exiftool() -> list[str]:
    if os.name == 'nt':
        path = app_root()/'tools/exiftool.exe'
        if path.is_file():
            return [str(path)]
    else:
        path = app_root()/'tools/exiftool'
        if path.is_file():
            return ['perl', str(path)]
    system = shutil.which('exiftool') if not getattr(sys, 'frozen', False) else None
    if system:
        return [system]
    raise ValueError('ExifTool fehlt. TransCora.zip vollständig entpacken.')


def inspect(path: Path, *, require_equal_size=True, cancel=None):
    if path.suffix.lower() in HEIF_EXTENSIONS:
        from .heif import inspect as inspect_heif
        report = inspect_heif(path, cancel)
        return tuple(report['images'][0]['size']), report['stereo']
    with Image.open(path) as image:
        count = getattr(image, 'n_frames', 1)
        mpo = image.format == 'MPO'
        if (mpo and count != 2) or (not mpo and count != 1):
            raise ValueError('Nur einzelne Bilder oder MPO mit genau zwei Halbbildern werden unterstützt.')
        if image.mode.startswith('I') or image.mode == 'F':
            raise ValueError('16-Bit-/Fließkommabilder sind noch nicht freigegeben; 8-Bit-Kopie verwenden.')
        size = image.size
        orientation = image.getexif().get(274, 1)
        if orientation in (5, 6, 7, 8):
            size = size[::-1]
        image.load()
        if mpo:
            image.seek(1)
            other = image.size[::-1] if image.getexif().get(274, 1) in (5, 6, 7, 8) else image.size
            image.load()
            if require_equal_size and other != size:
                raise ValueError('MPO-Halbbilder haben unterschiedliche Maße oder Orientierung.')
        return size, mpo


def mpo_jpegs(path: Path) -> tuple[bytes, bytes]:
    """Extract the JPEGs at Pillow's frame offsets; remove the obsolete MPF APP2."""
    with Image.open(path) as image:
        if image.format != 'MPO' or image.n_frames != 2:
            raise ValueError('MPO mit genau zwei Halbbildern erforderlich.')
        positions = []
        for frame in range(2):
            image.seek(frame)
            positions.append(image.offset)
    result = []
    with path.open('rb') as source:
        source.seek(0, os.SEEK_END)
        ends = positions[1:]+[source.tell()]
        for offset, end in zip(positions, ends):
            if end <= offset:
                raise ValueError('Beschädigter MPO-Index oder unvollständiges JPEG-Halbbild.')
            source.seek(offset)
            # Actual frame boundaries are sufficient; camera-reported Sizes
            # need not agree about padding or the JPEG end marker.
            data = source.read(end-offset)
            # Fuji camera indexes include zero padding after EOI in the image
            # size. It belongs to the MPO container, not the standalone JPEG.
            data = data.rstrip(b'\x00')
            if not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
                raise ValueError('Beschädigter MPO-Index oder unvollständiges JPEG-Halbbild.')
            out = bytearray(data[:2]); pos = 2
            while pos < len(data):
                start = pos
                if data[pos] != 255:
                    raise ValueError('Ungültiger JPEG-Marker im MPO.')
                while pos < len(data) and data[pos] == 255:
                    pos += 1
                marker = data[pos]; pos += 1
                if marker == 0xda:
                    out.extend(data[start:]); break
                length = int.from_bytes(data[pos:pos+2], 'big')
                if length < 2 or pos+length > len(data):
                    raise ValueError('Ungültige JPEG-Segmentlänge.')
                if not (marker == 0xe2 and data[pos+2:pos+6] == b'MPF\0'):
                    out.extend(data[start:pos+length])
                pos += length
            with Image.open(io.BytesIO(out)) as standalone:
                standalone.load()
                if standalone.format != 'JPEG':
                    raise ValueError('MPO-Extraktion ergibt kein selbständiges JPEG.')
            result.append(bytes(out))
    return tuple(result)


def reserve(paths, folder, stem, suffixes, reserved):
    number = 1
    while True:
        middle = '' if number == 1 else f'_{number}'
        outputs = tuple(folder/(stem+middle+suffix) for suffix in suffixes)
        keys = [str(p.resolve()).casefold() for p in outputs]
        existing = {p.name.casefold() for p in folder.iterdir()} if folder.is_dir() else set()
        if all(k not in reserved and p.name.casefold() not in existing and p.resolve() not in paths
               for k, p in zip(keys, outputs)):
            reserved.update(keys)
            return outputs
        number += 1


def plans(jobs: list[ImageJob], output: Path, cancel: threading.Event, *, reserved=None) -> list[ImagePlan]:
    reserved = set() if reserved is None else reserved
    result = []
    for job in jobs:
        if cancel.is_set():
            raise Cancelled()
        opts = ImageOptions.from_dict(asdict(job.options)); source = job.source.resolve()
        if source.suffix.lower() not in EXTENSIONS:
            raise ValueError('Nicht unterstütztes Bildformat: '+source.name)
        size, mpo = inspect(source, require_equal_size=opts.task != 'mpo', cancel=cancel)
        if opts.metadata and opts.task == 'convert':
            exiftool()
        if opts.task == 'convert' and opts.target == 'anaglyph' and opts.method == 'cielab':
            from .cielab import verify_tool
            verify_tool()
        warnings = []
        hint = filename_layout(source.stem)
        heif = source.suffix.lower() in HEIF_EXTENSIONS
        if mpo:
            layout, swap = 'full_sbs', opts.swap
            warnings.append('HEIF: Halbbilder anhand der Stereo-Gruppe links/rechts zugeordnet.' if heif else
                            'MPO: Erstes Halbbild als links angenommen; L/R-Reihenfolge kontrollieren.')
        else:
            layout, swap = hint if opts.layout == 'auto' and hint else (opts.layout, False)
            swap ^= opts.swap
            if layout == 'auto':
                if source.suffix.lower() in {'.jps', '.pns'}:
                    layout, swap = 'full_sbs', not opts.swap
                    warnings.append('JPS/PNS: Full-SBS mit rechtem Halbbild zuerst angenommen; Reihenfolge kontrollieren.')
                elif opts.target == 'keep':
                    layout = 'mono'
                else:
                    raise ValueError('Stereo-Quelllayout nicht eindeutig. Layout auswählen: '+source.name)
        if opts.task == 'mpo' and (not mpo or heif):
            raise ValueError('Verlustfreies Teilen benötigt eine MPO-Datei: '+source.name)
        if layout == 'mono' and opts.target != 'keep' and opts.task == 'convert':
            raise ValueError('Dieses Ziel benötigt zwei Halbbilder: '+source.name)
        packed = (size[0]*2, size[1]) if mpo else size
        if layout != 'mono' and (packed[0] if layout.endswith('sbs') else packed[1]) % 2:
            raise ValueError('Bild lässt sich nicht in zwei gleich große Halbbilder teilen.')
        if layout.startswith('half_') and opts.target.startswith('full_'):
            warnings.append('Half → Full skaliert die gestauchte Achse; keine zusätzlichen Bilddetails.')
        if layout == 'row_interleaved':
            warnings.append('Zeilenquelle: Stereo-Zeilen werden vor Skalierung getrennt. Die halbe vertikale Detailauflösung je Halbbild bleibt erhalten.')
        folder = output.resolve()
        if job.source_root:
            folder /= source.parent.relative_to(job.source_root.resolve())
        ext = '.jpg' if opts.task == 'mpo' else SUFFIX[opts.format]
        suffixes = ('_l'+ext, '_r'+ext) if opts.task == 'mpo' or opts.target == 'split' else (
            ('_'+image_methods()[opts.method]['suffix'] if opts.target == 'anaglyph' else
             {'left': '_l', 'right': '_r', 'row_interleaved': '_rows_'+('rl' if opts.row_first == 'right' else 'lr')}.get(opts.target, '_'+opts.target) if opts.target != 'keep' else '')+ext,)
        # Retaining the layout also retains its existing filename marker.
        stem = source.stem if opts.target == 'keep' and opts.task == 'convert' else clean_stem(source.stem)
        outputs = reserve({source}, folder, stem, suffixes, reserved)
        stat = source.stat()
        result.append(ImagePlan((source,), outputs, opts, layout, swap, packed,
                                ((stat.st_size, stat.st_mtime_ns),), tuple(warnings)))
    return result


def normalized(source: Path, frame=0):
    with Image.open(source) as original:
        original.seek(frame)
        profile = original.info.get('icc_profile')
        image = ImageOps.exif_transpose(original).copy()
    return normalize_pixels(image, profile)


def normalize_pixels(image, profile=None):
    alpha = image.getchannel('A') if 'A' in image.getbands() else (
        image.convert('RGBA').getchannel('A') if 'transparency' in image.info else None)
    image = image.convert('RGB')
    if profile:
        image = ImageCms.profileToProfile(image, ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                                         ImageCms.ImageCmsProfile(io.BytesIO(SRGB)), outputMode='RGB')
    if alpha is not None:
        image.putalpha(alpha)
    return image


def resized_dimensions(size, options):
    """Match AnaChroma SizeSpec: fit presets, long/short edge and nearest pixel."""
    w, h = size
    mode = options.size_mode
    if options.long_edge and mode == 'original':
        factor = options.long_edge/max(w, h)
    elif mode == 'original': return size
    elif mode == '1080p': factor = min(1920/w, 1080/h)
    elif mode == '2160p': factor = min(3840/w, 2160/h)
    elif mode == '2048': factor = 2048/max(w, h)
    else: factor = options.size_pixels/(max(w, h) if options.size_edge == 'long' else min(w, h))
    return max(1, round(w*factor)), max(1, round(h*factor))


def fixed_image_size(options):
    """Fixed canvases are opt-in; edge-based sizes and screen rows keep their rules."""
    if (options.task == 'convert' and options.size_fit != 'scale' and options.target != 'row_interleaved'
            and not (options.target == 'keep' and options.layout == 'row_interleaved')):
        return {'1080p': (1920, 1080), '2160p': (3840, 2160)}.get(options.size_mode)
    return None


def fitted_dimensions(display_size, frame, mode, packed=None):
    """Fit in display geometry, then map to the stored (possibly half-size) grid."""
    dw, dh = display_size; w, h = frame
    pw, ph = packed or frame
    factor = (min if mode == 'pad' else max)(Fraction(w, dw), Fraction(h, dh))
    fw = max(1, round(dw*factor*pw/w)); fh = max(1, round(dh*factor*ph/h))
    return (min(pw, fw), min(ph, fh)) if mode == 'pad' else (max(pw, fw), max(ph, fh))


def image_fit_filter(display_size, frame, mode, packed=None):
    w, h = packed or frame
    fw, fh = fitted_dimensions(display_size, frame, mode, packed)
    fit = (f'pad={w}:{h}:{(w-fw)//2}:{(h-fh)//2}:color=black' if mode == 'pad' else
           f'crop={w}:{h}:{(fw-w)//2}:{(fh-h)//2}')
    return f'scale={fw}:{fh}:flags=lanczos,{fit},setsar=1'


def fit_image_pixels(image, display_size, frame, mode):
    """The CIELAB path fits each half before running the separate colour solver."""
    size = fitted_dimensions(display_size, frame, mode)
    image = image.resize(size, Image.Resampling.LANCZOS)
    if mode == 'pad':
        canvas = Image.new(image.mode, frame, 'black')
        canvas.paste(image, ((frame[0]-size[0])//2, (frame[1]-size[1])//2))
        return canvas
    x, y = (size[0]-frame[0])//2, (size[1]-frame[1])//2
    return image.crop((x, y, x+frame[0], y+frame[1]))


def fixed_stereo_graph(plan, frame):
    """Fit independent halves before packing, keeping identical crops and borders."""
    opts = plan.options
    target = plan.layout if opts.target == 'keep' else opts.target
    pixel = 'rgba' if opts.target == 'keep' else 'rgb24'
    if target == 'mono':
        return f'[0:v]format={pixel},'+image_fit_filter(plan.size, frame, opts.size_fit)+'[v]', frame
    w, h = plan.size; horizontal = plan.layout.endswith('sbs')
    ew, eh = (w//2, h) if horizontal else (w, h//2)
    display = (ew*(2 if plan.layout == 'half_sbs' else 1),
               eh*(2 if plan.layout == 'half_ou' else 1))
    positions = [(0, 0), (ew, 0)] if horizontal else [(0, 0), (0, eh)]
    if plan.swap and opts.target != 'keep': positions.reverse()
    if target in {'left', 'right'}:
        x, y = positions[target == 'right']
        return (f'[0:v]format={pixel},crop={ew}:{eh}:{x}:{y},'+
                image_fit_filter(display, frame, opts.size_fit)+'[v]'), frame
    tw, th = frame
    logical = (tw//2, th) if target == 'full_sbs' else (tw, th//2) if target == 'full_ou' else frame
    packed = (tw//2, th) if target in {'full_sbs', 'half_sbs'} else (tw, th//2) if target in {'full_ou', 'half_ou'} else frame
    parts = [f'[0:v]format={pixel},split[a][b]']
    for name, (x, y), label in zip(('a', 'b'), positions, ('l', 'r')):
        parts.append(f'[{name}]crop={ew}:{eh}:{x}:{y},'+
                     image_fit_filter(display, logical, opts.size_fit, packed)+f'[{label}]')
    stack = 'vstack' if target.endswith('ou') else 'hstack'
    parts.append(f'[l][r]{stack}=inputs=2,format={pixel}[v]')
    return ';'.join(parts), (tw*2, th) if target == 'split' else frame


def image_graph(plan):
    opts = plan.options; target = opts.target
    if plan.layout == 'row_interleaved':
        if target == 'keep' and resized_dimensions(plan.size, opts) == plan.size:
            return '[0:v]null,format=rgba[v]', plan.size
        if target == 'keep':
            w, h = resized_dimensions(plan.size, opts)
            opts = replace(opts, target='row_interleaved', size_mode='original', long_edge=0,
                           screen_width=w, screen_height=max(2, 2*round(h/2)), row_first='left')
        packed = replace(plan, layout='half_ou', options=opts, swap=False if target == 'keep' else plan.swap)
        graph, size = image_graph(packed)
        if graph is None:
            return None, size
        prefix = '[0:v]format=gbrp,stereo3d=irl:ab2l[stereopair];'
        return prefix + graph.replace('[0:v]', '[stereopair]').replace('[0:0]', '[stereopair]'), size
    frame = fixed_image_size(opts)
    if frame and target != 'anaglyph':
        return fixed_stereo_graph(plan, frame)
    if target == 'keep':
        graph = '[0:v]null[composite]'; size = plan.size
    elif target == 'anaglyph':
        if opts.method == 'cielab':
            w, h = plan.size
            size = (w//2, h) if plan.layout.endswith('sbs') else (w, h//2)
            if plan.layout == 'half_sbs': size = (size[0]*2, size[1])
            if plan.layout == 'half_ou': size = (size[0], size[1]*2)
            return None, frame or resized_dimensions(size, opts)
        video = dict(index=0, width=plan.size[0], height=plan.size[1], pix_fmt='rgb24')
        graph, size, _ = build_graph(video, Options(target='anaglyph'), plan.layout, plan.swap,
            dict(matrix='gbr', primaries='bt709', transfer='iec61966-2-1', range='pc'), methods()[opts.method])
        graph = graph.rsplit(';[composite]', 1)[0]
    else:
        w, h = plan.size; horizontal = plan.layout.endswith('sbs')
        ew, eh = (w//2, h) if horizontal else (w, h//2)
        dw, dh = ew*(2 if plan.layout == 'half_sbs' else 1), eh*(2 if plan.layout == 'half_ou' else 1)
        positions = [(0, 0), (ew, 0)] if horizontal else [(0, 0), (0, eh)]
        if plan.swap: positions.reverse()
        parts = ['[0:v]format=rgb24,split[a][b]']
        for name, (x, y), label in zip(('a', 'b'), positions, ('l', 'r')):
            scale = f',scale={dw}:{dh}:flags=lanczos' if (ew, eh) != (dw, dh) and target != 'row_interleaved' else ''
            parts.append(f'[{name}]crop={ew}:{eh}:{x}:{y}{scale},setsar=1[{label}]')
        if target == 'row_interleaved':
            from .video import row_interleave_graph
            # Planar RGB keeps all colour channels at one sample per screen row.
            parts[0] = '[0:v]format=gbrp,split[a][b]'
            parts.extend(row_interleave_graph(opts, dw, dh))
            return ';'.join(parts)+';[composite]format=rgb24,setsar=1[v]', (opts.screen_width, opts.screen_height)
        ou = target.endswith('ou')
        parts.append(f"[l][r]{'vstack' if ou else 'hstack'}=inputs=2[composite]")
        graph = ';'.join(parts); size = (dw, dh*2) if ou else (dw*2, dh)
    if frame:
        return graph+';[composite]'+image_fit_filter(size, frame, opts.size_fit)+',format=rgb24[v]', frame
    filters = []
    if target in {'left', 'right', 'split'}:
        width, height = size[0]//2, size[1]
        offset = width if target == 'right' else 0
        if target != 'split':
            filters.append(f'crop={width}:{height}:{offset}:0')
            size = width, height
    elif target.startswith('half_'):
        size = (size[0]//2, size[1]) if target == 'half_sbs' else (size[0], size[1]//2)
        filters.append(f'scale={size[0]}:{size[1]}:flags=lanczos')
    if opts.long_edge or opts.size_mode != 'original':
        # In split mode resize the two reconstructed halves equally.
        half_size = (size[0]//2, size[1]) if target == 'split' else size
        output_size = resized_dimensions(half_size, opts)
        size = (output_size[0]*2, output_size[1]) if target == 'split' else output_size
        filters.append(f'scale={size[0]}:{size[1]}:flags=lanczos')
    filters.extend(['setsar=1', 'format=rgba' if target == 'keep' else 'format=rgb24'])
    return graph+';[composite]'+','.join(filters)+'[v]', size


def copy_metadata(source, target, cancel, *, oriented=True):
    # Structural tags and embedded source previews must describe the new pixels.
    orientation = 1
    if not oriented:
        with Image.open(source) as original:
            orientation = original.getexif().get(274, 1)
    with Image.open(target) as rendered:
        width, height = rendered.size
    args = exiftool()+['-overwrite_original', '-TagsFromFile', str(source), '-EXIF:all', '-XMP:all', '-IPTC:all',
        '-Orientation#='+str(orientation), '-ThumbnailImage=', '-PreviewImage=', '-JpgFromRaw=', '-OtherImage=',
        '-IFD1:all=', '-MakerNotes:all=', '-MPF:all=', f'-EXIF:ExifImageWidth={width}', f'-EXIF:ExifImageHeight={height}',
        '-XMP-tiff:ImageWidth=', '-XMP-tiff:ImageHeight=']
    if oriented:
        # Transformed pixels carry an sRGB ICC profile. Source EXIF may instead
        # name Adobe RGB or an uncalibrated space; it must describe the output.
        args += ['-EXIF:ColorSpace#=1']
    args.append(str(target))
    capture(args, cancel, timeout=120)


def execute_image(tools, plan, cancel, emit, log_path):
    opts = plan.options; published = []
    for source, stamp in zip(plan.sources, plan.stamps):
        stat = source.stat()
        if (stat.st_size, stat.st_mtime_ns) != stamp:
            raise ValueError('Bildquelle wurde seit dem Test verändert: '+source.name)
    for output in plan.outputs:
        output.parent.mkdir(parents=True, exist_ok=True)
    # All temporary files belong to this batch and stay on the destination volume.
    with tempfile.TemporaryDirectory(prefix='.transcora-images-', dir=plan.outputs[0].parent) as temp:
        folder = Path(temp); staged = []
        try:
            if cancel.is_set():
                raise Cancelled()
            if opts.task == 'mpo':
                data = mpo_jpegs(plan.sources[0])
                if plan.swap:
                    data = data[::-1]
                for i, item in enumerate(data):
                    target = folder/(str(i)+'.jpg'); target.write_bytes(item)
                    # Each original JPEG already carries its own metadata.
                    # Copying frame 0 tags over frame 1 can change orientation
                    # and camera-specific fields. Extraction needs no tool.
                    staged.append(target)
            else:
                emit('phase', 'Bild orientieren und Farbprofil lesen')
                heif = plan.sources[0].suffix.lower() in HEIF_EXTENSIONS
                if heif:
                    from .heif import decode
                    halves, description = decode(plan.sources[0], tools, cancel)
                    halves = [normalize_pixels(half, half.info.get('icc_profile')) for half in halves]
                    image, mpo = halves[0], len(halves) == 2
                else:
                    image = normalized(plan.sources[0])
                    with Image.open(plan.sources[0]) as original:
                        mpo = original.format == 'MPO'
                if mpo:
                    right = halves[1] if heif else normalized(plan.sources[0], 1)
                    packed = Image.new('RGB', (image.width*2, image.height), 'white')
                    for half, x in [(image, 0), (right, image.width)]:
                        packed.paste(half, (x, 0), half.getchannel('A') if half.mode == 'RGBA' else None)
                    image = packed
                elif image.mode == 'RGBA' and opts.target != 'keep':
                    flattened = Image.new('RGB', image.size, 'white'); flattened.paste(image, mask=image.getchannel('A')); image = flattened
                # Temporary PNGs need lossless pixels, not costly compression.
                if opts.target == 'anaglyph' and opts.method == 'cielab':
                    from .cielab import render
                    render_plan = plan
                    if plan.layout == 'row_interleaved':
                        packed = Image.new(image.mode, image.size)
                        for y in range(image.height):
                            packed.paste(image.crop((0, y, image.width, y+1)),
                                         (0, y//2 + (image.height//2 if y % 2 else 0)))
                        image, render_plan = packed, replace(plan, layout='half_ou')
                    rendered = render(image, render_plan, folder, cancel, emit)
                else:
                    input_file = folder/'normalized.png'; image.save(input_file, compress_level=0)
                    graph, _ = image_graph(plan)
                    rendered = folder/'pixels.png'
                    emit('phase', 'Bild mit FFmpeg verarbeiten')
                    capture([str(tools.ffmpeg), '-v', 'error', '-nostdin', '-n', '-filter_complex_threads', '1',
                        '-i', str(input_file), '-filter_complex', graph, '-map', '[v]', '-frames:v', '1',
                        '-c:v', 'png', '-compression_level', '0', '-threads', '1', str(rendered)], cancel, timeout=180)
                with Image.open(rendered) as pixels:
                    pictures = ([pixels.crop((0, 0, pixels.width//2, pixels.height)),
                                 pixels.crop((pixels.width//2, 0, pixels.width, pixels.height))]
                                if opts.target == 'split' else [pixels.copy()])
                emit('phase', 'Bildformat und Metadaten schreiben')
                for i, pixels in enumerate(pictures):
                    target = folder/(str(i)+plan.outputs[i].suffix)
                    if opts.format == 'jpeg':
                        if pixels.mode == 'RGBA':
                            plain = Image.new('RGB', pixels.size, 'white'); plain.paste(pixels, mask=pixels.getchannel('A')); pixels = plain
                        # One JPEG pass; Huffman optimisation changes file size,
                        # not decoded pixels, and needlessly delays the preview.
                        pixels.convert('RGB').save(target, quality=opts.quality, subsampling=0, icc_profile=SRGB)
                    elif opts.format == 'webp':
                        pixels.save(target, lossless=True, method=6, icc_profile=SRGB)
                    elif opts.format == 'tiff':
                        pixels.save(target, compression='tiff_deflate', icc_profile=SRGB)
                    else:
                        pixels.save(target, icc_profile=SRGB)
                    if opts.metadata:
                        copy_metadata(plan.sources[0], target, cancel)
                    with Image.open(target) as verified:
                        verified.load()
                        if verified.size != pixels.size:
                            raise ValueError('Ausgabemaße stimmen nicht mit dem Bildplan überein.')
                    staged.append(target)
            for i, target in enumerate(staged):
                source = plan.sources[0]
                stat = source.stat(); os.utime(target, ns=(stat.st_atime_ns, stat.st_mtime_ns))
            for source, stamp in zip(plan.sources, plan.stamps):
                stat = source.stat()
                if (stat.st_size, stat.st_mtime_ns) != stamp:
                    raise ValueError('Bildquelle während der Verarbeitung verändert.')
            for temporary, output in zip(staged, plan.outputs):
                publish_without_overwrite(temporary, output, cancel); published.append(output)
            with log_path.open('a', encoding='utf-8') as log:
                log.write(json.dumps({'images': [str(p) for p in plan.sources], 'outputs': [str(p) for p in plan.outputs],
                                      'options': asdict(opts), 'verified': True}, ensure_ascii=False)+'\n')
        except BaseException:
            # Roll back only files created by this transaction; never old files.
            for owned in published:
                owned.unlink(missing_ok=True)
            raise


def save_images(path, jobs):
    write_json(path, {'schema_version': 1, 'kind': 'transcora-images', 'jobs': [j.serializable() for j in jobs]})


def load_images(path):
    data = json.loads(path.read_text(encoding='utf-8'))
    if data.get('schema_version') != 1 or data.get('kind') != 'transcora-images' or not isinstance(data.get('jobs'), list):
        raise ValueError('Keine TransCora-Bildliste.')
    result = []
    for item in data['jobs']:
        if not isinstance(item, dict) or not isinstance(item.get('source'), str):
            raise ValueError('Ungültiger Bildeintrag.')
        root = item.get('source_root')
        if root is not None and not isinstance(root, str):
            raise ValueError('Ungültiger Bildordner.')
        result.append(ImageJob(Path(item['source']).expanduser().resolve(), ImageOptions.from_dict(item.get('options', {})),
                               Path(root).expanduser().resolve() if root else None))
    return result

