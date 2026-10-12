"""Build pinned decoder sources; the resulting executable needs no frameserver."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PINS = {'edge264-mvc': 'e8f4b3b54e34d752c16760efa1e7ad966307eb2b',
        'mvc-source': '2acc004ffcb14ebe00abaff2b126b7133fe94bfd'}


def main():
    build = ROOT/'build/mvc-decoder'
    build.mkdir(parents=True, exist_ok=True)
    for name, sha in PINS.items():
        folder = build/name
        if not (folder/'.git').is_dir():
            subprocess.run(['git', 'clone', '--no-checkout', 'https://github.com/jens-duttke/'+name+'.git', str(folder)], check=True)
        subprocess.run(['git', '-C', str(folder), 'checkout', '--detach', sha], check=True)
        actual = subprocess.check_output(['git', '-C', str(folder), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != sha:
            raise ValueError('Decoder source revision mismatch')
    edge, source = build/'edge264-mvc', build/'mvc-source/src'
    cc = os.environ.get('TRANSCORA_MVC_CC', 'gcc')
    subprocess.run(['make', '-C', str(edge), '-j4', 'STATIC=yes', 'BUILDTEST=no',
                    'VARIANTS=x86-64-v2,x86-64-v3', 'CFLAGS=-march=x86-64', 'CC='+cc, 'V=no',
                    *(['OS=windows'] if os.name == 'nt' else [])], check=True)
    patched = build/'core'
    patched.mkdir(exist_ok=True)
    for name in ('mvcsource.h', 'cache_budget.h', 'h264poc.h'):
        shutil.copy2(source/name, patched/name)
    s = (source/'mvcsource.c').read_text(encoding='utf-8')
    # UTF-8 argv and Unicode Windows paths: upstream currently uses CreateFileA.
    needle = 'HANDLE hf = CreateFileA(path, GENERIC_READ, FILE_SHARE_READ, NULL,'
    assert needle in s
    s = s.replace(needle, 'wchar_t wide[32768];\n\tif (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, wide, 32768)) return NULL;\n\tHANDLE hf = CreateFileW(wide, GENERIC_READ, FILE_SHARE_READ, NULL,', 1)
    (patched/'mvcsource.c').write_text(s, encoding='utf-8')
    dest = ROOT/'tools/mvc'
    dest.mkdir(parents=True, exist_ok=True)
    exe = dest/('TransCoraMVC.exe' if os.name == 'nt' else 'TransCoraMVC')
    args = [cc, '-std=gnu11', '-O2', '-march=x86-64', '-pthread', '-I'+str(edge), '-I'+str(patched),
            str(ROOT/'native/mvc_decode.c'), str(edge/'libedge264mvc.a')]
    if os.name == 'nt':
        args += ['-static', '-municode']
    subprocess.run(args+['-o', str(exe)], check=True)
    for name in PINS:
        license_file = build/name/('LICENSE_BSD.txt' if name == 'edge264-mvc' else 'LICENSE')
        shutil.copy2(license_file, dest/(name+'-LICENSE.txt'))
    (dest/'BUILD_MANIFEST.json').write_text(json.dumps({'sources': PINS, 'sha256': hashlib.sha256(exe.read_bytes()).hexdigest()}, indent=2))
    print('Built portable MVC decoder:', exe)


if __name__ == '__main__':
    main()
