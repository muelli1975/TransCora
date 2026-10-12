"""Development-only HEIF probe using pinned public upstream test fixtures."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import urllib.request

FIXTURES = {
    'stereo_pair.heic': ('heif_other', '628d02b8111e9ee8bb9e30935d3b54c32c1dab7c6a852067fcbe315412715b20'),
    'entity_groups.heic': ('heif_special', '463966c69196ee4bc204581fe97c6092bd386d8f8282010ffd622275be0e5c16'),
    'spatial_photo.heic': ('heif_other', 'ef941d328072a2df034adb3c3b46f41117606bfc8fcc100dff975d31f55ec028'),
    'arrow.heic': ('heif_other', '73f604d7353df4848505a1f45a5517f736857fe047372f95c2f3d671df92c22c'),
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg', required=True)
    parser.add_argument('--folder', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    args.folder.mkdir(parents=True, exist_ok=True)
    root = Path(__file__).resolve().parents[1]
    from PIL import Image
    import pillow_heif
    report = {'development_probe': True, 'reader': pillow_heif.__version__,
              'libraries': pillow_heif.libheif_info(), 'checks': [],
              'not_checked': ['packaged readers on all platforms', 'TransCora import integration',
                              'HDR tone mapping', 'Apple device playback']}
    for name, (directory, digest) in FIXTURES.items():
        url = f'https://raw.githubusercontent.com/bigcat88/pillow_heif/v1.8.1/tests/images/{directory}/{name}'
        source = args.folder/name
        if not source.exists():
            with urllib.request.urlopen(url, timeout=30) as response:
                source.write_bytes(response.read())
        assert hashlib.sha256(source.read_bytes()).hexdigest() == digest, name
        output = args.folder/source.stem
        result = subprocess.run([sys.executable, str(root/'native/heif/read_heif.py'), str(source),
                                 '--decode-to', str(output), '--ffmpeg', str(Path(args.ffmpeg).resolve())],
                                capture_output=True, text=True, check=True, timeout=90)
        metadata = json.loads(result.stdout)
        assert metadata['stereo'] == (name != 'arrow.heic'), name
        decoded = []
        for index, description in enumerate(metadata['images']):
            with Image.open(output/f'{index}.png') as image:
                image.load()
                assert list(image.size) == description['size'], name
                assert bool(image.info.get('icc_profile')) == description['icc'], name
                if name in {'stereo_pair.heic', 'entity_groups.heic'}:
                    pixel = image.convert('RGB').getpixel((32, 32))
                    blue = (index == 1) if name == 'stereo_pair.heic' else (index == 0)
                    assert pixel[2 if blue else 0] > 240 and pixel[0 if blue else 2] < 10
                decoded.append({'size': list(image.size), 'pixel_sha256': hashlib.sha256(image.tobytes()).hexdigest(),
                                'icc_preserved': description['icc']})
        if len(decoded) == 2:
            assert decoded[0]['pixel_sha256'] != decoded[1]['pixel_sha256'], name
        report['checks'].append({'source': url, 'sha256': digest, 'result': 'passed',
                                 'metadata': metadata, 'decoded': decoded})
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2)+'\n', 'utf-8')
    print(f"HEIF probe: {len(report['checks'])} passed; report: {args.report}")


if __name__ == '__main__':
    main()
