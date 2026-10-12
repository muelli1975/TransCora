"""Verify and extract the official x265 source archive for the isolated probe."""
import argparse
import hashlib
import json
from pathlib import Path
import tarfile
import urllib.request


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--folder', type=Path, default=Path('work/x265-source'))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pins = json.loads((root/'scripts/heif-sources.json').read_text('utf-8'))
    pin = next(entry for entry in pins['sources'] if entry['file'] == 'x265_4.3.tar.gz')
    folder = args.folder.resolve(); folder.mkdir(parents=True, exist_ok=True)
    archive = folder/pin['file']
    if not archive.is_file():
        with urllib.request.urlopen(pin['url'], timeout=60) as response:
            archive.write_bytes(response.read())
    if archive.stat().st_size != pin['size'] or hashlib.sha256(archive.read_bytes()).hexdigest() != pin['sha256']:
        raise ValueError('x265 source archive checksum mismatch')
    with tarfile.open(archive, 'r:gz') as package:
        package.extractall(folder, filter='data')
    source = folder/'x265_4.3'
    if not (source/'x265Version.txt').is_file():
        raise ValueError('Official x265 version information missing')
    print(source)


if __name__ == '__main__':
    main()
