"""Build-time download only. The desktop application never calls this script."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile


def main():
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root/'scripts/ffmpeg-windows.json').read_text())
    destination = root/'tools/ffmpeg'
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        archive = folder/'ffmpeg.zip'
        digest = hashlib.sha256()
        count = 0
        with urllib.request.urlopen(manifest['url'], timeout=120) as source, archive.open('wb') as out:
            while chunk := source.read(1024*1024):
                count += len(chunk)
                if count > manifest['size']:
                    raise ValueError('FFmpeg archive exceeds the pinned size')
                digest.update(chunk)
                out.write(chunk)
        if count != manifest['size'] or digest.hexdigest() != manifest['sha256']:
            raise ValueError('FFmpeg SHA256/size verification failed')
        unpacked = folder/'unpacked'
        with zipfile.ZipFile(archive) as package:
            if sum(member.file_size for member in package.infolist()) > 1_000_000_000:
                raise ValueError('FFmpeg archive exceeds the extraction limit')
            for member in package.infolist():
                target = (unpacked/member.filename).resolve()
                if not target.is_relative_to(unpacked.resolve()):
                    raise ValueError('Unsafe archive path')
            package.extractall(unpacked)
        executable = next(unpacked.rglob('ffmpeg.exe'))
        upstream = executable.parent.parent
        for entry in upstream.iterdir():
            if entry.is_dir():
                shutil.copytree(entry, destination/entry.name, dirs_exist_ok=True)
            else:
                shutil.copy2(entry, destination/entry.name)
        if not (destination/'bin/ffprobe.exe').is_file():
            raise ValueError('ffprobe missing in the pinned archive')
        shutil.copy2(root/'scripts/ffmpeg-windows.json', destination/'BUILD_MANIFEST.json')
        print('Verified FFmpeg toolchain:', manifest['build'])


if __name__ == '__main__':
    main()
