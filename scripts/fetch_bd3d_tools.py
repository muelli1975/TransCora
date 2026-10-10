"""Build-time downloader for pinned portable MVC tools; no runtime network use."""
from pathlib import Path
import hashlib
import html
import json
import re
import shutil
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'build/bd3d-tools'


def main():
    manifest = json.loads((ROOT/'scripts/bd3d-tools.json').read_text())
    DEST.mkdir(parents=True, exist_ok=True)
    for key, item in manifest.items():
        archive = DEST / (key + ('.rar' if key == 'frim' else '.zip'))
        if not archive.exists() or hashlib.sha256(archive.read_bytes()).hexdigest() != item['sha256']:
            url = item.get('url')
            if not url:
                page = urllib.request.urlopen(item['download_page'], timeout=90).read().decode()
                match = re.search(r'href="(https://digital-digest.com/software/getdownload.php[^\"]+)"', page)
                if not match:
                    raise ValueError('Legacy tsMuxeR download link unavailable')
                url = html.unescape(match[1])
            with urllib.request.urlopen(url, timeout=120) as source:
                data = source.read(item['size'] + 1)
            if len(data) != item['size'] or hashlib.sha256(data).hexdigest() != item['sha256']:
                raise ValueError(f'{key}: Pinned size/SHA256 verification failed')
            archive.write_bytes(data)
        folder = DEST/key
        if key == 'frim':
            sevenzip = shutil.which('7z') or r'C:\Program Files\7-Zip\7z.exe'
            subprocess.run([sevenzip, 'x', '-y', str(archive), '-o'+str(folder)], check=True)
        else:
            with zipfile.ZipFile(archive) as z:
                for member in z.infolist():
                    if not (folder/member.filename).resolve().is_relative_to(folder.resolve()):
                        raise ValueError('Unsafe archive member')
                z.extractall(folder)
        print('Verified:', key, item['version'], item['sha256'], flush=True)
    shutil.copy2(ROOT/'scripts/bd3d-tools.json', DEST/'BUILD_MANIFEST.json')
    frim = ROOT/'tools/frim'
    muxer = ROOT/'tools/tsmuxer'
    frim.mkdir(parents=True, exist_ok=True)
    muxer.mkdir(parents=True, exist_ok=True)
    for name in ('FRIMEncode64.exe', 'FRIMDecode64.exe', 'libmfxsw64.dll'):
        shutil.copy2(DEST/'frim/x64'/name, frim/name)
    (frim/'doc').mkdir(exist_ok=True)
    for name in ('FRIMEncode_readme.pdf', 'FRIMDecode_readme.pdf', 'FRIM_setup_readme.pdf', 'FRIM_release_notes.txt'):
        shutil.copy2(DEST/'frim/doc'/name, frim/'doc'/name)
    shutil.copy2(DEST/'tsmuxer/tsMuxeR.exe', muxer/'tsMuxeR.exe')
    shutil.copy2(DEST/'tsmuxer/release_notes.txt', muxer/'release_notes.txt')
    shutil.copy2(DEST/'BUILD_MANIFEST.json', ROOT/'tools/BD3D_BUILD_MANIFEST.json')


if __name__ == '__main__':
    main()
