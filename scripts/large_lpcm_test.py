"""Prove the pinned tsMuxeR 2.6.12 handles >4 GiB Wave64 LPCM, sample-for-sample."""
from pathlib import Path
import ctypes
import hashlib
import json
import os
import struct
import subprocess
import sys
import tempfile
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.core.engine import capture
from transcora.core.bd3d_export import BdTools, run
from transcora.core.toolchain import Toolchain


def main():
    out = ROOT/'output/bd3d-integration'
    out.mkdir(parents=True, exist_ok=True)
    tools, bd = Toolchain.find(), BdTools.find()
    channels, samples = 8, 4000*48000
    length = channels*3*samples
    started = time.monotonic()
    report = {'ok': False, 'bytes': length, 'channels': channels}
    try:
        with tempfile.TemporaryDirectory(prefix='transcora-large-lpcm-') as tmp, (out/'large-lpcm.log').open('w', encoding='utf-8') as log:
            folder = Path(tmp)
            seed = folder/'seed.w64'
            capture([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi', '-i',
                     'anullsrc=r=48000:cl=7.1', '-t', '0.005', '-c:a', 'pcm_s24le', '-f', 'w64', str(seed)])
            header = seed.read_bytes()
            position = header.index(b'data')
            start = position+24
            header = bytearray(header[:start])
            struct.pack_into('<Q', header, 16, start+length)
            struct.pack_into('<Q', header, position+16, length+24)
            source, movie = folder/'long.w64', folder/'long.m2ts'
            # Allocate only the header/tail on NTFS; every hole reads as zero PCM.
            with source.open('wb') as stream:
                if os.name == 'nt':
                    import msvcrt
                    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
                    kernel.DeviceIoControl.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p,
                        ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
                    count = ctypes.c_ulong()
                    if not kernel.DeviceIoControl(msvcrt.get_osfhandle(stream.fileno()), 0x900c4,
                            None, 0, None, 0, ctypes.byref(count), None):
                        raise ctypes.WinError(ctypes.get_last_error())
                stream.write(header)
                stream.seek(start+length-48000*channels*3)
                frame = b''.join((i*173111+1).to_bytes(3, 'little', signed=True) for i in range(channels))
                tail = frame*48000
                stream.write(tail)
            meta = folder/'audio.meta'
            meta.write_text(f'MUXOPT --new-audio-pes --vbr\nA_LPCM, "{source}", lang=deu\n', encoding='utf-8')
            run([bd.muxer, meta, movie], threading.Event(), log, bd.environment)
            result = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(movie), '-map', '0:a:0',
                '-c:a', 'pcm_s24le', '-f', 'hash', '-hash', 'sha256', '-'], timeout=600).decode().strip()
            expected = hashlib.sha256()
            left = length-len(tail)
            zeroes = bytes(1024*1024)
            while left:
                amount = min(left, len(zeroes))
                expected.update(zeroes[:amount])
                left -= amount
            expected.update(tail)
            if result != 'SHA256='+expected.hexdigest():
                raise ValueError('Large LPCM roundtrip truncated or altered samples/channels: '+result)
            report.update(ok=True, audio_identical=True, seconds=time.monotonic()-started)
    finally:
        (out/'large-lpcm.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
