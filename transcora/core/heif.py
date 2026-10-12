"""JSON/PNG interface to the separate HEIF reader process."""
import json
from pathlib import Path
import sys
import tempfile

from .model import app_root

EXTENSIONS = {'.heic', '.heif'}


def reader_command():
    name = 'TransCora-HEIF.exe' if sys.platform == 'win32' else 'TransCora-HEIF'
    binary = app_root()/'tools/heif'/name
    if binary.is_file():
        return [str(binary)]
    if not getattr(sys, 'frozen', False):
        return [sys.executable, str(app_root()/'native/heif/read_heif.py')]
    raise ValueError('HEIF-Leser fehlt. TransCora vollständig entpacken.')


def response(arguments, cancel=None, timeout=60):
    from .engine import capture
    try:
        return json.loads(capture(reader_command()+arguments, cancel, timeout=timeout))
    except ValueError as error:
        messages = {
            'HDR HEIF requires deliberate tone mapping; this reader handles SDR.':
                'HDR-HEIF: SDR-Kopie mit bewusster Tonwertwandlung verwenden.',
            'HEIF contains more than one applicable stereo group.':
                'HEIF enthält mehrere passende Stereo-Gruppen; das gewünschte Paar separat exportieren.',
            'HEIF stereo group does not reference two readable half-images.':
                'HEIF-Stereo-Gruppe enthält keine zwei lesbaren Halbbilder.',
            'HEIF half-images have different dimensions.': 'HEIF-Halbbilder haben unterschiedliche Maße.',
            'Unsupported HEIF SDR colour description.': 'Nicht unterstützte HEIF-SDR-Farbinterpretation.',
            'HEIF non-square pixels are not supported by this reader.': 'HEIF mit nichtquadratischen Pixeln wird noch nicht unterstützt.',
        }
        raise ValueError(messages.get(str(error), str(error))) from None


def inspect(path, cancel=None):
    return response([str(path)], cancel)


def decode(path, tools, cancel=None):
    from .engine import capture
    from PIL import Image
    with tempfile.TemporaryDirectory(prefix='transcora-heif-') as tmp:
        folder = Path(tmp)
        report = response([str(path), '--decode-to', str(folder), '--ffmpeg', str(tools.ffmpeg)], cancel, timeout=180)
        images = []
        for index, description in enumerate(report['images']):
            with Image.open(folder/f'{index}.png') as image:
                image.load()
                if list(image.size) != description['size']:
                    raise ValueError('HEIF-Leser meldet widersprüchliche Bildmaße.')
                images.append(image.copy())
        return images, report
