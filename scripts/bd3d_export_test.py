"""Exercise the shipped export path, two-view roundtrip, labels, audio and cancel."""
from pathlib import Path
from dataclasses import replace
from fractions import Fraction
import json
import os
import subprocess
import sys
import threading
import traceback
import shutil
import struct
import hashlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.core.engine import plan_job, execute, capture, Cancelled, preview
from transcora.core.model import Options, Job
from transcora.core.toolchain import Toolchain
from transcora.core.bd3d_export import BdTools, FRAME_BYTES
from transcora.core.bd3d import BD_RATE, prepare
from transcora.core.udf import Disc

OUT = ROOT/'output/bd3d-integration'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tools = Toolchain.find()
    capabilities = tools.inspect()
    bd = BdTools.find()
    report = {'ok': False}
    try:
        for rate, container, title, channels in [('24', 'iso', 'Mein 3D Film – ÄÖÜ', 2),
                                                 ('24000/1001', 'm2ts', 'Native 23.976', 6)]:
            source = OUT/f'source-{container}_full_sbs.mkv'
            # Distinct animated eyes; include 997 Hz on every audio channel.
            capture([str(tools.ffmpeg), '-hide_banner', '-y', '-filter_complex_threads', '1',
                '-f', 'lavfi', '-i', f'testsrc2=size=1920x1080:rate={rate}', '-f', 'lavfi', '-i',
                'sine=frequency=997:sample_rate=48000', '-filter_complex',
                '[0:v]split[a][b];[b]crop=1908:1080:12:0,pad=1920:1080:0:0:color=black[r];[a][r]hstack[v]',
                '-map', '[v]', '-map', '1:a', '-frames:v', '48', '-t', str(48/float(Fraction(rate))),
                '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
                '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                '-c:a', 'pcm_s24le', '-ac', str(channels), str(source)], timeout=120)
            job = Job(source, Options(target='bd3d', container=container, disc_title=title))
            plan = plan_job(tools, job, OUT, set(), threading.Event(), capabilities)
            png = preview(tools, plan, threading.Event(), .5)
            if not png.startswith(b'\x89PNG'):
                raise ValueError('BD preview failed')
            events = []
            execute(tools, plan, threading.Event(), lambda k, v: events.append((k, v)), OUT/f'{container}.log')
            if not plan.output.is_file() or not events or events[-1][1].get('percent') != 100:
                raise ValueError('Export/progress failed')
            packed = plan.output
            if container == 'iso':
                # Cross-check the runtime reader against an independent UDF tool.
                listing = subprocess.check_output([r'C:\Program Files\7-Zip\7z.exe', 'l', '-slt', str(plan.output)], encoding='utf-8')
                if 'Version = 2.50' not in listing or '00000.ssif' not in listing:
                    raise ValueError('Independent ISO structure check failed')
                with Disc(plan.output) as disc:
                    if disc.label != title:
                        raise ValueError('Unicode disc title not preserved')
                    packed = OUT/'iso-packed.ssif'
                    disc.extract('BDMV/STREAM/SSIF/00000.ssif', packed)
            # Independently decode prepared audio to match the actual muxed LPCM.
            af = prepare(plan.info['video'], plan.layout).audio_filter+',apad,atrim=end_sample=96096'
            expected_audio = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(source), '-map', '0:a:0',
                '-af', af, '-ar', '48000', '-c:a', 'pcm_s24le', '-f', 's24le', 'pipe:1'], timeout=120)
            actual_audio = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(packed), '-map', '0:a:0',
                '-c:a', 'pcm_s24le', '-f', 's24le', 'pipe:1'], timeout=120)
            if actual_audio != expected_audio:
                raise ValueError('LPCM roundtrip altered audio samples/channel order')
            # A second destination cannot overwrite an existing published movie.
            again = plan_job(tools, job, OUT, set(), threading.Event(), capabilities)
            if again.output == plan.output:
                raise ValueError('Output naming collision protection failed')
            report[container] = {'file': plan.output.name, 'size': plan.output.stat().st_size,
                                'frames': 48, 'rate': str(BD_RATE), 'channels': channels,
                                'audio_identical': True, 'preview_ok': True}
            source.unlink()
            if packed != plan.output:
                packed.unlink()
        # Abort after the encoder has started (not just a pre-cancelled call).
        source = OUT/'cancel_full_sbs.mkv'
        capture([str(tools.ffmpeg), '-y', '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=1280x360:r=24',
                 '-frames:v', '48', '-c:v', 'ffv1', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                 '-color_trc', 'bt709', str(source)], timeout=120)
        plan = plan_job(tools, Job(source, Options(target='bd3d', container='m2ts')), OUT, set(), capabilities=capabilities)
        cancel = threading.Event()
        def emit(kind, value):
            if kind == 'progress' and value['percent'] > 5:
                cancel.set()
        try:
            execute(tools, plan, cancel, emit, OUT/'cancel.log')
            raise ValueError('Expected export cancellation')
        except Cancelled:
            if plan.output.exists() or list(OUT.glob('.transcora-bd3d-*')):
                raise ValueError('Cancelled export left output or temporary files')
        source.unlink()
        report['cancel_cleanup'] = True
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        print(report['error'], flush=True)
    finally:
        (OUT/'report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
        print(json.dumps(report, ensure_ascii=False, indent=2), flush=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
