"""Create the portable one-folder distribution, preserving external tools/assets."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    if sys.platform != 'win32':
        raise SystemExit('Build on Windows to produce a Windows application.')
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
                    '--onedir', '--name', 'TransCora', '--icon', str(root/'assets/transcora.ico'),
                    str(root/'run_transcora.py')], cwd=root, check=True)
    output = root/'dist/TransCora'
    for name in ('assets', 'presets', 'tools', 'licenses'):
        shutil.copytree(root/name, output/name, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    (output/'docs').mkdir(exist_ok=True)
    shutil.copy2(root/'docs/RELEASE_NOTES_0.1.1.md', output/'docs/RELEASE_NOTES_0.1.1.md')
    python_license = next((p for p in (Path(sys.base_prefix)/'LICENSE.txt', Path(sys.base_prefix)/'LICENSE') if p.is_file()), None)
    if python_license is None:
        raise ValueError('Python license missing from the build installation')
    shutil.copy2(python_license, output/'licenses/PYTHON.txt')
    distribution = importlib.metadata.distribution('PyInstaller')
    notices = [p for p in distribution.files or [] if 'licenses' in p.parts]
    if not notices:
        raise ValueError('PyInstaller bootloader license notice missing')
    for notice in notices:
        path = Path(distribution.locate_file(notice))
        if path.is_file():
            shutil.copy2(path, output/'licenses'/('PYINSTALLER-'+path.name))
    for name in ('README.md', 'LICENSE', 'THIRD_PARTY.md', 'Start-TransCora.bat'):
        shutil.copy2(root/name, output/name)
    (output/'output').mkdir(exist_ok=True)
    manifest = {}
    for path in sorted(output.rglob('*')):
        if path.is_file():
            with path.open('rb') as source:
                manifest[path.relative_to(output).as_posix()] = hashlib.file_digest(source, 'sha256').hexdigest()
    (output/'BUILD_HASHES.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    archive = Path(shutil.make_archive(str(root/'dist/TransCora'), 'zip', root/'dist', 'TransCora'))
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    (root/'dist/TransCora.zip.sha256').write_text(digest+'  TransCora.zip\n', encoding='utf-8')
    print(archive)


if __name__ == '__main__':
    main()
