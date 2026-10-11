"""Checked still-image batches; FFmpeg transforms pixels, ExifTool copies metadata."""
from __future__ import annotations
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
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

EXTENSIONS = {'.jpg', '.jpeg', '.jps', '.png', '.pns', '.tif', '.tiff', '.bmp', '.webp', '.mpo'}
TASKS = {'convert': 'Bilder konvertieren', 'mpo': 'MPO verlustfrei teilen'}
LAYOUTS = {'auto': 'Automatisch', 'mono': 'Mono / 2D', 'full_sbs': 'Full-SBS', 'half_sbs': 'Half-SBS',
           'full_ou': 'Full-OU', 'half_ou': 'Half-OU'}
TARGETS = {'keep': 'Layout beibehalten', 'full_sbs': 'Full-SBS', 'full_ou': 'Full-OU',
           'half_sbs': 'Half-SBS', 'half_ou': 'Half-OU', 'anaglyph': 'Anaglyph',
           'left': 'Linkes Halbbild', 'right': 'Rechtes Halbbild', 'split': 'Beide Halbbilder teilen'}
FORMATS = {'jpeg': 'JPEG', 'png': 'PNG', 'tiff': 'TIFF', 'webp': 'WebP (verlustfrei)'}
SIZES = {'original': 'Original', '1080p': '1080p', '2160p': '2160p',
         '2048': '2048 lange Seite', 'custom': 'Benutzerdefiniert'}
SIZE_EDGES = {'long': 'lange Seite', 'short': 'kurze Seite'}
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
    size_edge: str = 'long'
    size_pixels: int = 2048
    swap: bool = False
    metadata: bool = True
    method: str = 'dubois_lcd'

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
        for key, choices in [('task', TASKS), ('layout', LAYOUTS), ('target', TARGETS), ('format', FORMATS)]:
            if getattr(self, key) not in choices:
                raise ValueError('Ungültige Bildeinstellung: '+key)
        if self.quality not in (90, 95) or type(self.long_edge) is not int or not 0 <= self.long_edge <= 20000:
            raise ValueError('JPEG-Qualität: 90/95. Lange Kante: 0 (Original) bis 20000 Pixel.')
        if type(self.swap) is not bool or type(self.metadata) is not bool or self.method not in image_methods():
            raise ValueError('Ungültige Bild-, Metadaten- oder Anaglypheneinstellung.')
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


def inspect(path: Path):
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
            if other != size:
                raise ValueError('MPO-Halbbilder haben unterschiedliche Maße oder Orientierung.')
        return size, mpo


def mpo_jpegs(path: Path) -> tuple[bytes, bytes]:
    """Extract MP-index byte ranges; remove only the obsolete MPF APP2 index."""
    with Image.open(path) as image:
        if image.format != 'MPO' or image.n_frames != 2:
            raise ValueError('MPO mit genau zwei Halbbildern erforderlich.')
        entries = image.mpinfo[0xB002]
        positions = []
        for frame in range(2):
            image.seek(frame)
            positions.append(image.offset)
    result = []
    with path.open('rb') as source:
        for offset, entry in zip(positions, entries):
            source.seek(offset)
            data = source.read(entry['Size'])
            if len(data) != entry['Size'] or not data.startswith(b'\xff\xd8') or not data.endswith(b'\xff\xd9'):
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


def plans(jobs: list[ImageJob], output: Path, cancel: threading.Event) -> list[ImagePlan]:
    reserved = set(); result = []
    for job in jobs:
        if cancel.is_set():
            raise Cancelled()
        opts = ImageOptions.from_dict(asdict(job.options)); source = job.source.resolve()
        if source.suffix.lower() not in EXTENSIONS:
            raise ValueError('Nicht unterstütztes Bildformat: '+source.name)
        size, mpo = inspect(source)
        if opts.metadata and opts.task in {'convert', 'mpo'}:
            exiftool()
        if opts.task == 'convert' and opts.target == 'anaglyph' and opts.method == 'cielab':
            from .cielab import verify_tool
            verify_tool()
        warnings = []
        hint = filename_layout(source.stem)
        if mpo:
            layout, swap = 'full_sbs', opts.swap
            warnings.append('MPO: Erstes Halbbild als links angenommen; L/R-Reihenfolge kontrollieren.')
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
        if opts.task == 'mpo' and not mpo:
            raise ValueError('Verlustfreies Teilen benötigt eine MPO-Datei: '+source.name)
        if layout == 'mono' and opts.target != 'keep' and opts.task == 'convert':
            raise ValueError('Dieses Ziel benötigt zwei Halbbilder: '+source.name)
        packed = (size[0]*2, size[1]) if mpo else size
        if layout != 'mono' and (packed[0] if layout.endswith('sbs') else packed[1]) % 2:
            raise ValueError('Bild lässt sich nicht in zwei gleich große Halbbilder teilen.')
        if layout.startswith('half_') and opts.target.startswith('full_'):
            warnings.append('Half → Full skaliert die gestauchte Achse; keine zusätzlichen Bilddetails.')
        folder = output.resolve()
        if job.source_root:
            folder /= source.parent.relative_to(job.source_root.resolve())
        ext = '.jpg' if opts.task == 'mpo' else SUFFIX[opts.format]
        suffixes = ('_l'+ext, '_r'+ext) if opts.task == 'mpo' or opts.target == 'split' else (
            ('_'+image_methods()[opts.method]['suffix'] if opts.target == 'anaglyph' else
             {'left': '_l', 'right': '_r'}.get(opts.target, '_'+opts.target) if opts.target != 'keep' else '')+ext,)
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


def image_graph(plan):
    opts = plan.options; target = opts.target
    if target == 'keep':
        graph = '[0:v]null[composite]'; size = plan.size
    elif target == 'anaglyph':
        if opts.method == 'cielab':
            w, h = plan.size
            size = (w//2, h) if plan.layout.endswith('sbs') else (w, h//2)
            if plan.layout == 'half_sbs': size = (size[0]*2, size[1])
            if plan.layout == 'half_ou': size = (size[0], size[1]*2)
            return None, resized_dimensions(size, opts)
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
            scale = f',scale={dw}:{dh}:flags=lanczos' if (ew, eh) != (dw, dh) else ''
            parts.append(f'[{name}]crop={ew}:{eh}:{x}:{y}{scale},setsar=1[{label}]')
        ou = target.endswith('ou')
        parts.append(f"[l][r]{'vstack' if ou else 'hstack'}=inputs=2[composite]")
        graph = ';'.join(parts); size = (dw, dh*2) if ou else (dw*2, dh)
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
    with Image.open(source) as original:
        orientation = 1 if oriented else original.getexif().get(274, 1)
    args = exiftool()+['-overwrite_original', '-TagsFromFile', str(source), '-EXIF:all', '-XMP:all', '-IPTC:all',
        '-Orientation#='+str(orientation), '-ThumbnailImage=', '-PreviewImage=', '-JpgFromRaw=', '-OtherImage=',
        '-IFD1:all=', '-MakerNotes:all=', '-MPF:all=', '-ExifImageWidth=', '-ExifImageHeight=',
        '-XMP-tiff:ImageWidth=', '-XMP-tiff:ImageHeight=', str(target)]
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
                    if opts.metadata:
                        copy_metadata(plan.sources[0], target, cancel, oriented=False)
                    staged.append(target)
            else:
                emit('phase', 'Bild orientieren und Farbprofil lesen')
                image = normalized(plan.sources[0])
                with Image.open(plan.sources[0]) as original:
                    mpo = original.format == 'MPO'
                if mpo:
                    right = normalized(plan.sources[0], 1)
                    packed = Image.new('RGB', (image.width*2, image.height), 'white')
                    for half, x in [(image, 0), (right, image.width)]:
                        packed.paste(half, (x, 0), half.getchannel('A') if half.mode == 'RGBA' else None)
                    image = packed
                elif image.mode == 'RGBA' and opts.target != 'keep':
                    flattened = Image.new('RGB', image.size, 'white'); flattened.paste(image, mask=image.getchannel('A')); image = flattened
                # Temporary PNGs need lossless pixels, not costly compression.
                if opts.target == 'anaglyph' and opts.method == 'cielab':
                    from .cielab import render
                    rendered = render(image, plan, folder, cancel, emit)
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
