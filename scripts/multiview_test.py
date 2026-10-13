"""Windows integration: real MVC discs, independent FRIM decode, Apple FATE sample."""
from pathlib import Path
from dataclasses import replace
import hashlib
import json
import subprocess
import sys
import tempfile
import threading
import traceback
import urllib.request
import zlib
from fractions import Fraction

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.core.engine import plan_job, execute, preview, probe, capture, Cancelled
from transcora.core.model import Job, Options
from transcora.core.multiview import runtime, decoder, PairClock
from transcora.core.bd3d_export import BdTools, decoded_digest, FRAME_BYTES
from transcora.core.toolchain import Toolchain
from transcora.core.mvc import annex_nals

OUT = ROOT/'output/multiview-integration'
FIXTURE_SHA = '414c2c4424b13aa9bd46da0e99bf318cac8ce6d85c20f37c0c4d6fc8b3eddae5'


def mvc_mkv_fixture(tools, source, base, dependent, destination):
    """Minimal conforming AVC Matroska fixture retaining MVC NALs and source PTS."""
    groups = []
    for path, delimiter in ((base, 9), (dependent, 24)):
        units = []
        with path.open('rb') as stream:
            for prefix, nal in annex_nals(stream):
                if nal[0]&31 == delimiter:
                    units.append([])
                if not units:
                    units.append([])
                units[-1].append(nal)
        groups.append(units)
    assert len(groups[0]) == len(groups[1]) == 48
    def element(identifier, data):
        for size in range(1, 9):
            if len(data) < (1<<(7*size))-1:
                length = ((1<<(7*size))|len(data)).to_bytes(size, 'big')
                return bytes.fromhex(identifier)+length+data
        raise AssertionError('Oversized test element')
    def integer(identifier, value):
        return element(identifier, value.to_bytes(max(1, (value.bit_length()+7)//8), 'big'))
    sps = next(n for n in groups[0][0] if n[0]&31 == 7)
    pps = [n for n in groups[0][0]+groups[1][0] if n[0]&31 == 8]
    avcc = (b'\x01'+sps[1:4]+b'\xff\xe1'+len(sps).to_bytes(2, 'big')+sps+bytes([len(pps)])
            + b''.join(len(n).to_bytes(2, 'big')+n for n in pps))
    header = element('1a45dfa3', integer('4286', 1)+integer('42f7', 1)+integer('42f2', 4)
        +integer('42f3', 8)+element('4282', b'matroska')+integer('4287', 4)+integer('4285', 2))
    info = element('1549a966', integer('2ad7b1', 1000)+element('4d80', b'Test')+element('5741', b'Test'))
    track = element('1654ae6b', element('ae', integer('d7', 1)+integer('73c5', 1)+integer('83', 1)
        +element('86', b'V_MPEG4/ISO/AVC')+element('63a2', avcc)+integer('23e383', 41708333)
        +element('e0', integer('b0', 1920)+integer('ba', 1080))))
    packets = json.loads(capture([str(tools.ffprobe), '-v', 'error', '-select_streams', '0', '-show_packets',
        '-show_entries', 'packet=pts', '-of', 'json', str(source)]))['packets']
    blocks = []
    for (left, right), packet in zip(zip(*groups), packets):
        stamp = round((int(packet['pts'])-int(packets[0]['pts']))*Fraction(100, 9))
        payload = b''.join(len(n).to_bytes(4, 'big')+n for n in left+right if n[0]&31 != 24)
        block = element('a0', element('a1', b'\x81\0\0\0'+payload))
        blocks.append(element('1f43b675', integer('e7', stamp)+block))
    destination.write_bytes(header+element('18538067', info+track+b''.join(blocks)))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    tools, bd = Toolchain.find(), BdTools.find()
    report = {'ok': False}
    cancel = threading.Event()
    try:
        sources = ROOT/'output/bd3d-integration'
        source = sources/'Native 23.976.m2ts'
        plan = plan_job(tools, Job(source, Options(container='mkv')), OUT, set(), cancel)
        assert plan.info['multiview']['kind'] == 'mvc'
        png = preview(tools, plan, cancel, .5)
        assert png.startswith(b'\x89PNG')
        # BD-3D control views display both decoded half-images without changing export options.
        import io
        from PIL import Image
        bd_preview=plan_job(tools,Job(source,Options(target='bd3d',container='iso')),OUT,set(),cancel)
        for view,width in [('parallel',3840),('cross',3840),('anaglyph',1920)]:
            with Image.open(io.BytesIO(preview(tools,bd_preview,cancel,.5,view=view))) as picture:
                assert picture.size==(width,1080)
        assert bd_preview.options.target=='bd3d' and bd_preview.options.container=='iso'
        report['bd_control_views']=['parallel','cross','anaglyph']
        # Compare every decoded sample against an independent decoder, both views.
        with runtime(tools, plan, cancel) as (working, process), (OUT/'decoder.log').open('w') as log:
            args = working.info['runtime_input']['args']
            base, dep = Path(args[1]), Path(args[2])
            expected = decoded_digest(bd, base, dep, 48, cancel, log)
            header = process.stdout.readline()
            assert header.startswith(b'YUV4MPEG2 W3840 H1080 ')
            digest, count = hashlib.sha256(), 0
            while True:
                line = process.stdout.readline()
                if not line:
                    break
                assert line == b'FRAME\n'
                remaining = FRAME_BYTES
                while remaining:
                    chunk = process.stdout.read(min(remaining, 1024*1024))
                    assert chunk, 'Truncated MVC pair'
                    digest.update(chunk)
                    remaining -= len(chunk)
                count += 1
            assert count == 48 and digest.hexdigest() == expected, 'edge264-mvc differs from FRIM'
        execute(tools, plan, cancel, lambda k, v: None, OUT/'mvc.log')
        result = probe(tools, plan.output)
        assert result['video']['width'] == 1920 and result['video']['height'] == 1080
        # Blu-ray LPCM -> FLAC must preserve every original sample and channel.
        original = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(source), '-map', '0:a:0',
                            '-c:a', 'pcm_s24le', '-f', 's24le', '-'], timeout=120)
        actual = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(plan.output), '-map', '0:a:0',
                          '-c:a', 'pcm_s24le', '-f', 's24le', '-'], timeout=120)
        assert original == actual, 'Lossless audio conversion changed samples/channel order'
        report['mvc'] = {'decoder_samples_match_frim': True, 'frames': count, 'audio_identical': True,
                         'preview_ok': True, 'output': plan.output.name}
        # Exercise the FRIM fallback pipeline, including seeking for a control image.
        fallback = replace(plan, output=OUT/'FRIM-fallback.mkv')
        fallback.info = json.loads(json.dumps(plan.info))
        fallback.info['multiview']['decoder'] = 'frim'
        assert preview(tools, fallback, cancel, .5).startswith(b'\x89PNG')
        execute(tools, fallback, cancel, lambda k, v: None, OUT/'frim-fallback.log')
        report['frim_fallback'] = True
        iso = sources/'Mein 3D Film – ÄÖÜ.iso'
        iso_plan = plan_job(tools, Job(iso, Options(target='mono', container='mkv')), OUT, set(), cancel)
        assert iso_plan.info['multiview']['iso_path'].endswith('.ssif')
        execute(tools, iso_plan, cancel, lambda k, v: None, OUT/'iso-input.log')
        report['iso_input'] = {'playlist': iso_plan.info['multiview']['playlist'], 'output': iso_plan.output.name}
        # MKV single-track MVC is imported by its actual NAL extensions.
        with tempfile.TemporaryDirectory() as tmp:
            mkv = Path(tmp)/'Combined MVC.mkv'
            with runtime(tools, plan, cancel) as (working, process):
                base, dep = map(Path, working.info['runtime_input']['args'][1:3])
                mvc_mkv_fixture(tools, source, base, dep, mkv)
                combined_plan = plan_job(tools, Job(mkv, Options(target='mono', container='mkv')), OUT, set(), cancel)
                assert combined_plan.info['multiview']['kind'] == 'mvc'
                assert preview(tools, combined_plan, cancel, .5).startswith(b'\x89PNG')
                execute(tools, combined_plan, cancel, lambda k, v: None, OUT/'mvc-mkv.log')
                # Stop this independent producer intentionally after one complete pair.
                process.stdout.readline(); process.stdout.readline(); process.stdout.read(FRAME_BYTES)
                while process.stdout.read(1024*1024):
                    pass
            report['combined_mvc_mkv'] = True
            mp4 = Path(tmp)/'Combined MVC.mp4'
            capture([str(tools.ffmpeg), '-v', 'error', '-i', str(mkv), '-c', 'copy', str(mp4)])
            mp4_plan = plan_job(tools, Job(mp4, Options(target='mono', container='mkv')), OUT, set(), cancel)
            assert mp4_plan.info['multiview']['kind'] == 'mvc'
            assert preview(tools, mp4_plan, cancel, .5).startswith(b'\x89PNG')
            execute(tools, mp4_plan, cancel, lambda k, v: None, OUT/'mvc-mp4.log')
            report['combined_mvc_mp4'] = True
        sample = OUT/'Apple-multiview.mov'
        with urllib.request.urlopen('https://fate-suite.ffmpeg.org/hevc/multiview.mov', timeout=60) as response:
            data = response.read(2*1024*1024)
        assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA
        sample.write_bytes(data)
        mv_plan = plan_job(tools, Job(sample, Options(container='mkv')), OUT, set(), cancel)
        original_video = mv_plan.info['multiview']['original_video']
        assert original_video['view_pos_available'] == '2,1', 'Fixture must exercise right base view'
        assert preview(tools, mv_plan, cancel, .1).startswith(b'\x89PNG')
        execute(tools, mv_plan, cancel, lambda k, v: None, OUT/'mvhevc.log')
        # Official FFmpeg conformance CRCs identify the correctly ordered views.
        raw = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(sample), '-map', '0:v:0:vpos:left',
                       '-frames:v', '1', '-c:v', 'rawvideo', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'], timeout=60)
        assert zlib.adler32(raw, 0) == 0xd0ce90de
        raw = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(sample), '-map', '0:v:0:vpos:right',
                       '-frames:v', '1', '-c:v', 'rawvideo', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'], timeout=60)
        assert zlib.adler32(raw, 0) == 0x1859a3ba
        report['mvhevc'] = {'frames': 11, 'left_right_crc_match_fate': True, 'right_base_handled': True,
                            'preview_ok': True, 'output': mv_plan.output.name}
        # Actual cancellation after the native decoder starts; no output publication.
        abort = replace(plan, output=OUT/'cancelled.mkv')
        stop = threading.Event()
        def emit(k, v):
            if k == 'progress':
                stop.set()
        try:
            execute(tools, abort, stop, emit, OUT/'cancel.log')
            raise AssertionError('Expected cancellation')
        except Cancelled:
            assert not abort.output.exists() and not list(OUT.glob('*.part.*'))
        report['cancel_cleanup'] = True
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        print(report['error'], flush=True)
    finally:
        (OUT/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        print(json.dumps(report, indent=2), flush=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
