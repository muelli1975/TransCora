"""Create the portable one-folder distribution, preserving external tools/assets."""
from pathlib import Path
import hashlib
import importlib.metadata
import json
import shutil
import subprocess
import sys
import platform


def main():
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    from transcora import __version__
    subprocess.run([sys.executable, str(root/'scripts/prepare_heif.py')], cwd=root, check=True)
    icon_args = ['--icon', str(root/'assets/transcora.ico')] if sys.platform == 'win32' else []
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--windowed',
                    '--onedir', '--name', 'TransCora', '--collect-all=customtkinter', *icon_args,
                    str(root/'run_transcora.py')], cwd=root, check=True)
    output = root/'dist/TransCora'
    for name in ('assets', 'presets', 'tools', 'licenses'):
        shutil.copytree(root/name, output/name, ignore=shutil.ignore_patterns('__pycache__'), dirs_exist_ok=True)
    shutil.copytree(root/'docs', output/'docs', dirs_exist_ok=True)
    for name in ('transcora', 'native', 'scripts', 'tests', 'reference', 'assets', 'presets', 'licenses', 'docs', '.github'):
        shutil.copytree(root/name, output/'source'/name,
                        ignore=shutil.ignore_patterns('__pycache__', '*.pyc'), dirs_exist_ok=True)
    for name in ('.gitattributes', 'run_transcora.py', 'requirements-build.txt', 'BUILD.md', 'LICENSE', 'README.md', 'README_DE.md', 'THIRD_PARTY.md'):
        shutil.copy2(root/name, output/'source'/name)
    python_license = next((p for p in (Path(sys.base_prefix)/'LICENSE.txt', Path(sys.base_prefix)/'LICENSE',
                            Path(sys.base_prefix)/'lib'/f'python{sys.version_info.major}.{sys.version_info.minor}'/'LICENSE.txt')
                            if p.is_file()), None)
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
    pillow = importlib.metadata.distribution('Pillow')
    pillow_notices = [p for p in pillow.files or [] if 'licenses' in p.parts and Path(pillow.locate_file(p)).is_file()]
    if not pillow_notices:
        raise ValueError('Pillow dependency license notices missing')
    for notice in pillow_notices:
        source = Path(pillow.locate_file(notice))
        target = output/'licenses/Pillow'/Path(*notice.parts[notice.parts.index('licenses')+1:])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for package in ('customtkinter', 'darkdetect', 'packaging'):
        dependency = importlib.metadata.distribution(package)
        notices = [p for p in dependency.files or []
                   if 'license' in p.name.lower() and Path(dependency.locate_file(p)).is_file()]
        if not notices:
            raise ValueError(f'{package} license notices missing')
        for notice in notices:
            source = Path(dependency.locate_file(notice))
            shutil.copy2(source, output/'licenses'/(package+'-'+source.name))
    for name in ('README.md', 'README_DE.md', 'BUILD.md', 'LICENSE', 'THIRD_PARTY.md'):
        shutil.copy2(root/name, output/name)
    if sys.platform == 'darwin':
        subprocess.run(['ditto', str(root/'dist/TransCora.app'), str(output/'TransCora.app')], check=True)
        # Keep portable tools, settings and exports outside the signed app.
        # Verify the complete bundle after copying it into the distribution.
        subprocess.run(['codesign', '--force', '--sign', '-', str(output/'TransCora.app')], check=True)
        subprocess.run(['codesign', '--verify', '--deep', '--strict', str(output/'TransCora.app')], check=True)
    (output/'output').mkdir(exist_ok=True)
    manifest = {}
    for path in sorted(output.rglob('*')):
        if path.is_file():
            with path.open('rb') as source:
                manifest[path.relative_to(output).as_posix()] = hashlib.file_digest(source, 'sha256').hexdigest()
    (output/'BUILD_HASHES.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    label = ('Windows_x64' if sys.platform == 'win32' else 'Linux_x64' if sys.platform == 'linux'
             else 'macOS_AppleSilicon' if platform.machine() == 'arm64' else 'macOS_Intel')
    name = 'TransCora_'+__version__+'_'+label
    archive = Path(shutil.make_archive(str(root/'dist'/name), 'zip' if sys.platform == 'win32' else 'gztar', root/'dist', 'TransCora'))
    with archive.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    archive.with_name(archive.name+'.sha256').write_text(digest+'  '+archive.name+'\n', encoding='utf-8')
    print(archive)


if __name__ == '__main__':
    main()
