"""Build-time regression: original Fuji W3 MPO, lossless pixels and JPEG scans."""
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import threading
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from PIL import Image
from transcora.core.images import ImageJob, ImageOptions, inspect, plans, execute_image, mpo_jpegs

URL = 'https://raw.githubusercontent.com/python-pillow/Pillow/11.3.0/Tests/images/fujifilm.mpo'
BLOB = 'ff0deb8a67691c42425d474ecb363861d95e813c'


def main():
    output = ROOT/'output/mpo-integration'
    output.mkdir(parents=True, exist_ok=True)
    report = {'fixture': URL, 'exports': []}
    with tempfile.TemporaryDirectory(prefix='transcora-camera-mpo-') as tmp:
        folder = Path(tmp)
        source = folder/'fujifilm.mpo'
        urllib.request.urlretrieve(URL, source)
        raw = source.read_bytes()
        assert hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == BLOB
        with Image.open(source) as image:
            report['camera'] = image.getexif().get(272)
            original_pixels = []
            for frame in range(2):
                image.seek(frame)
                original_pixels.append(image.convert('RGB').tobytes())
        assert inspect(source) == ((3648, 2736), True)
        jpegs = mpo_jpegs(source)
        for metadata in (False, True):
            cancel = threading.Event()
            options = ImageOptions(task='mpo', metadata=metadata)
            plan = plans([ImageJob(source, options)], folder/'out', cancel)[0]
            execute_image(None, plan, cancel, lambda *args: None, output/'run.jsonl')
            for frame, path in enumerate(plan.outputs):
                actual = path.read_bytes()
                assert actual == jpegs[frame]
                with Image.open(io.BytesIO(actual)) as image:
                    assert image.format == 'JPEG'
                    assert image.convert('RGB').tobytes() == original_pixels[frame]
            report['exports'].append({'metadata': metadata, 'identical_pixels': True,
                                      'unchanged_jpeg_scan': True})
        report['ok'] = True
    (output/'report.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
