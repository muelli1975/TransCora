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
import re

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.core.engine import plan_job, execute, capture, Cancelled, preview
from transcora.core.model import Options, Job
from transcora.core.toolchain import Toolchain
from transcora.core.bd3d_export import BdTools, FRAME_BYTES
from transcora.core.bd3d import BD_RATE, prepare, output_mode
from transcora.core.udf import Disc

OUT = ROOT/'output/bd3d-integration'


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tools = Toolchain.find()
    capabilities = tools.inspect()
    bd = BdTools.find()
    report = {'ok': False}
    try:
        cases = [(r,c,t,ch,'1080p') for r,c,t,ch in [('24', 'iso', 'Mein 3D Film – ÄÖÜ', 2),
                                                 ('24000/1001', 'm2ts', 'Native 23.976', 6),
                                                 ('24000/1001', 'm2ts', 'Native 7.1', 8),
                                                 ('25', 'm2ts', 'Converted 25', 2),
                                                 ('30', 'm2ts', 'Converted 30', 2),
                                                 ('50', 'm2ts', 'Interlaced 50 fields', 2),
                                                 ('60000/1001', 'm2ts', 'Converted 59.94', 2)]]
        cases += [('50', 'iso', '720p50 stereo', 2, '720p50'),
                  ('60000/1001', 'iso', '720p5994 stereo', 2, '720p5994'),
                  ('25', 'm2ts', '720p50 converted', 2, '720p50'),
                  ('30000/1001', 'm2ts', '720p5994 converted', 2, '720p5994')]
        for rate, container, title, channels, mode in cases:
            if os.environ.get('TRANSCORA_BD_TEST_MODES') and mode not in os.environ['TRANSCORA_BD_TEST_MODES'].split(','):
                continue
            width, height, output_rate = output_mode(mode)
            eye_bytes = width*height*3//2
            case = mode+'-'+container + '-' + str(channels) + ('-'+rate.replace('/', '-') if channels == 2 and container == 'm2ts' else '')
            source = OUT/f'source-{case}_full_sbs.mkv'
            fields = rate == '50' and mode == '1080p'
            tones = '|'.join(f'0.1*sin(2*PI*{997+i*173}*t)' for i in range(channels))
            audio_fixture = f"aevalsrc={tones}:s=48000:c="+{2:'stereo', 6:'5.1', 8:'7.1'}[channels]
            # Distinct animated eyes; include 997 Hz on every audio channel.
            capture([str(tools.ffmpeg), '-hide_banner', '-y', '-filter_complex_threads', '1',
                '-f', 'lavfi', '-i', f'testsrc2=size=1920x1080:rate={rate}', '-f', 'lavfi', '-i',
                audio_fixture, '-filter_complex',
                '[0:v]split[a][b];[b]crop=1908:1080:12:0,pad=1920:1080:0:0:color=black[r];[a][r]hstack'+
                ('[packed];[packed]tinterlace=mode=interleave_top[v]' if fields else '[v]'),
                '-map', '[v]', '-map', '1:a', '-frames:v', '48', '-t', str(48*(2 if fields else 1)/float(Fraction(rate))),
                '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'yuv420p', '-colorspace', 'bt709',
                *(['-field_order', 'tt'] if fields else []),
                '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv',
                '-c:a', 'flac', '-sample_fmt', 's32', '-bits_per_raw_sample', '24', '-ac', str(channels), str(source)], timeout=120)
            job = Job(source, Options(target='bd3d', container=container, disc_title=title,
                                      bd_bitrate_mbps=30 if fields else 40, bd_mode=mode))
            plan = plan_job(tools, job, OUT, set(), threading.Event(), capabilities)
            png = preview(tools, plan, threading.Event(), .5)
            if not png.startswith(b'\x89PNG'):
                raise ValueError('BD preview failed')
            events = []
            execute(tools, plan, threading.Event(), lambda k, v: events.append((k, v)), OUT/f'{case}.log')
            if not plan.output.is_file() or not events or events[-1][1].get('percent') != 100:
                raise ValueError('Export/progress failed')
            if not any(k == 'progress' and 5 < v['percent'] < 70 for k, v in events):
                raise ValueError('MVC encoding did not report intermediate frame progress for the ETA')
            log_text = (OUT/f'{case}.log').read_text(encoding='utf-8')
            if log_text.count('-i:mvc') != 0:
                raise ValueError('Production export must leave full MVC decoding to development tests')
            packed = plan.output
            if container == 'iso':
                # Cross-check the runtime reader against an independent UDF tool.
                listing = subprocess.check_output([r'C:\Program Files\7-Zip\7z.exe', 'l', '-slt', '-sccUTF-8', str(plan.output)], encoding='utf-8')
                if 'Version = 2.50' not in listing or '00000.ssif' not in listing:
                    raise ValueError('Independent ISO structure check failed')
                with Disc(plan.output) as disc:
                    if disc.label != title:
                        raise ValueError('Unicode disc title not preserved')
                    packed = OUT/'iso-packed.ssif'
                    disc.extract('BDMV/STREAM/SSIF/00000.ssif', packed)
            video = json.loads(capture([str(tools.ffprobe), '-v', 'error', '-show_streams', '-of', 'json', str(packed)]))['streams'][0]
            if (video['width'],video['height']) != (width,height) or Fraction(video['r_frame_rate']) != output_rate:
                raise ValueError('Muxed BD dimensions/frame rate mismatch')
            # Independently compare each eye with the prepared source. This catches
            # a swapped/duplicated view or planar-SBS stdin error despite roundtrip equality.
            raw = OUT/f'raw-{case}'
            raw.mkdir(exist_ok=True)
            demux = raw/'demux'
            demux.mkdir()
            meta = raw/'demux.meta'
            meta.write_text(f'MUXOPT --demux\nV_MPEG4/ISO/AVC, "{packed}", track=4113\n'
                            f'V_MPEG4/ISO/MVC, "{packed}", track=4114\n', encoding='utf-8')
            subprocess.run([str(bd.muxer), str(meta), str(demux)], env=bd.environment, check=True, timeout=120)
            avc = next(demux.glob('*.264'))
            mvc = next(demux.glob('*.mvc'))
            subprocess.run([str(bd.decoder), '-sw', '-i:mvc', str(avc), str(mvc), '-o',
                            str(raw/'decoded-left.yuv'), str(raw/'decoded-right.yuv')],
                           env=bd.environment, check=True, timeout=120)
            args = [str(tools.ffmpeg), '-y', '-v', 'error', '-filter_complex_threads', '1',
                    '-i', str(source), '-filter_complex', prepare(plan.info['video'], plan.layout, plan.swap, mode).graph]
            for eye in ('left', 'right'):
                args += ['-map', '['+eye+']', '-c:v', 'rawvideo', '-pix_fmt', 'yuv420p',
                         '-fps_mode', 'passthrough', '-f', 'rawvideo', str(raw/(eye+'.yuv'))]
            subprocess.run(args, check=True, timeout=120)
            for eye in ('left', 'right'):
                result = subprocess.run([str(tools.ffmpeg), '-hide_banner', '-f', 'rawvideo', '-s', f'{width}x{height}',
                    '-pix_fmt', 'yuv420p', '-i', str(raw/(eye+'.yuv')), '-f', 'rawvideo', '-s', f'{width}x{height}',
                    '-pix_fmt', 'yuv420p', '-i', str(raw/('decoded-'+eye+'.yuv')), '-lavfi', 'psnr',
                    '-f', 'null', '-'], capture_output=True, encoding='utf-8', timeout=120, check=True)
                score = re.search(r'average:([0-9.]+)', result.stderr)
                if not score or float(score[1]) < 40:
                    raise ValueError('Source eye identity/quality failed: '+eye)
            frames = (raw/'left.yuv').stat().st_size//eye_bytes
            if (raw/'decoded-left.yuv').stat().st_size != frames*eye_bytes:
                raise ValueError('Converted output frame count differs from prepared stereo source')
            shutil.rmtree(raw)
            # Independently decode prepared audio to match the actual muxed LPCM.
            samples = round(frames*48000/float(output_rate))
            af = prepare(plan.info['video'], plan.layout, plan.swap, mode).audio_filter+f',apad,atrim=end_sample={samples}'
            expected_audio = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(source), '-map', '0:a:0',
                '-af', af, '-ar', '48000', '-c:a', 'pcm_s24le', '-f', 's24le', 'pipe:1'], timeout=120)
            actual_audio = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(packed), '-map', '0:a:0',
                '-c:a', 'pcm_s24le', '-f', 's24le', 'pipe:1'], timeout=120)
            # LPCM uses 5-ms blocks; the final block may contain fewer than 240
            # silent padding samples. Every source sample and channel must match.
            padding = actual_audio[len(expected_audio):]
            if (not actual_audio.startswith(expected_audio) or len(padding) >= 240*channels*3
                    or any(padding) or len(actual_audio) % (channels*3)):
                raise ValueError('LPCM roundtrip altered audio samples/channel order')
            # A second destination cannot overwrite an existing published movie.
            again = plan_job(tools, job, OUT, set(), threading.Event(), capabilities)
            if again.output == plan.output:
                raise ValueError('Output naming collision protection failed')
            report[case] = {'file': plan.output.name, 'size': plan.output.stat().st_size,
                                'frames': frames, 'source_rate': rate, 'rate': str(output_rate), 'channels': channels,
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
