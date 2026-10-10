"""Isolated proof: portable FRIM software MVC, two-view decode, legacy 3D ISO."""
from pathlib import Path
import json
import os
import re
from fractions import Fraction
import subprocess
import sys
import traceback

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'output/bd3d-proof'
TOOLS = ROOT/'build/bd3d-tools'
FFMPEG = ROOT/'tools/ffmpeg/bin/ffmpeg.exe'
FFPROBE = ROOT/'tools/ffmpeg/bin/ffprobe.exe'
ENC = TOOLS/'frim/x64/FRIMEncode64.exe'
DEC = TOOLS/'frim/x64/FRIMDecode64.exe'
MUX = TOOLS/'tsmuxer/tsMuxeR.exe'
sys.path.insert(0, str(ROOT))
from transcora.core.bd3d import prepare, check_cadence, encoder_args, mux_meta, BD_RATE

ENV = dict(os.environ, PATH=str(ENC.parent)+os.pathsep+os.environ.get('PATH', ''))


def run(name, args, check=True, timeout=600):
    print(name, flush=True)
    result = subprocess.run([str(a) for a in args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=ENV, timeout=timeout)
    text = result.stdout.decode('utf-8', errors='replace')
    (OUT/(name+'.log')).write_text(text, encoding='utf-8')
    print(text[-3500:], flush=True)
    if check and result.returncode:
        raise RuntimeError(f'{name}: Exit {result.returncode}; see saved log')
    return text


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {'ok': False, 'frames': 240, 'rate': '24000/1001', 'source_rate': '24/1', 'platform': sys.platform,
              'tools': json.loads((ROOT/'scripts/bd3d-tools.json').read_text())}
    try:
        run('frim-encode-help', [ENC, '-help'], check=False)
        run('frim-decode-help', [DEC, '-help'], check=False)
        run('tsmuxer-help', [MUX], check=False)
        run('ffmpeg-version', [FFMPEG, '-version'])
        # Packed stereo fixture at exact 24 fps exercises the complete source preparation.
        # The right view is shifted by 12 pixels to give a clear, comfortable stereo plane.
        source_graph = ('[0:v]split[a][b];[b]crop=1908:1080:12:0,'
                        'pad=1920:1080:0:0:color=black[r];[a][r]hstack[v]')
        run('source-stereo', [FFMPEG, '-y', '-hide_banner', '-filter_complex_threads', '1',
                             '-f', 'lavfi', '-i', 'testsrc2=size=1920x1080:rate=24',
                             '-f', 'lavfi', '-i', 'sine=frequency=997:sample_rate=48000',
                             '-filter_complex', source_graph, '-map', '[v]', '-map', '1:a',
                             '-t', '10', '-c:v', 'ffv1', '-level', '3', '-pix_fmt', 'yuv420p',
                             '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                             '-color_range', 'tv', '-c:a', 'pcm_s24le', '-ac', '2', OUT/'source_full_sbs.mkv'])
        source = json.loads(run('source-probe', [FFPROBE, '-v', 'error', '-show_streams',
                                                '-show_frames', '-select_streams', 'v:0', '-of', 'json',
                                                OUT/'source_full_sbs.mkv']))
        video = source['streams'][0]
        config = prepare(video, 'full_sbs')
        check_cadence([float(f['best_effort_timestamp_time']) for f in source['frames']],
                      config.source_rate, video['time_base'])
        args = [FFMPEG, '-y', '-hide_banner', '-filter_complex_threads', '1', '-i',
                OUT/'source_full_sbs.mkv', '-filter_complex', config.graph]
        for eye in ('left', 'right'):
            args += ['-map', '['+eye+']', '-c:v', 'rawvideo', '-pix_fmt', 'yuv420p',
                     '-fps_mode', 'passthrough', '-f', 'rawvideo', OUT/(eye+'.yuv')]
        run('prepare-eyes', args)
        expected = 1920*1080*3//2*report['frames']
        if any((OUT/(eye+'.yuv')).stat().st_size != expected for eye in ('left', 'right')):
            raise ValueError('Source preparation dropped or duplicated frames')
        report['preparation'] = {'speed': str(config.speed), 'warnings': config.warnings}
        run('encode-mvc', encoder_args(ENC, OUT/'left.yuv', OUT/'right.yuv',
                                      OUT/'base.avc', OUT/'dependent.mvc'))
        run('decode-mvc', [DEC, '-sw', '-i:mvc', OUT/'base.avc', OUT/'dependent.mvc',
                          '-o', OUT/'decoded-left.yuv', OUT/'decoded-right.yuv'])
        expected = 1920*1080*3//2*report['frames']
        report['view_sizes'] = {eye: (OUT/('decoded-'+eye+'.yuv')).stat().st_size for eye in ('left', 'right')}
        if any(size != expected for size in report['view_sizes'].values()):
            raise ValueError('Decoded view frame count does not match')
        for eye in ('left', 'right'):
            quality = run('quality-'+eye, [FFMPEG, '-hide_banner', '-f', 'rawvideo', '-s', '1920x1080', '-pix_fmt', 'yuv420p',
                                '-i', OUT/(eye+'.yuv'), '-f', 'rawvideo', '-s', '1920x1080', '-pix_fmt', 'yuv420p',
                                '-i', OUT/('decoded-'+eye+'.yuv'), '-lavfi', 'psnr', '-f', 'null', '-'])
            score = re.search(r'average:([0-9.]+)', quality)
            if not score or float(score[1]) < 40:
                raise ValueError('MVC quality or eye/frame identity check failed')
        report['base_probe'] = json.loads(run('base-probe', [FFPROBE, '-v', 'error', '-count_frames',
                                                          '-show_streams', '-of', 'json', OUT/'base.avc']))
        samples = round(report['frames']/float(BD_RATE)*48000)
        run('prepare-audio', [FFMPEG, '-y', '-hide_banner', '-i', OUT/'source_full_sbs.mkv',
                             '-map', '0:a:0', '-af', config.audio_filter+f',apad,atrim=end_sample={samples}',
                             '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s24le', OUT/'audio.wav'])
        (OUT/'disc.meta').write_text(mux_meta(OUT/'base.avc', OUT/'dependent.mvc', OUT/'audio.wav'),
                                    encoding='utf-8')
        run('mux-iso', [MUX, OUT/'disc.meta', OUT/'TransCora-BD3D-Proof.iso'])
        sevenzip = r'C:\Program Files\7-Zip\7z.exe'
        report['iso_listing'] = run('iso-list', [sevenzip, 'l', '-slt', OUT/'TransCora-BD3D-Proof.iso'])
        if 'SSIF' not in report['iso_listing'] or '.ssif' not in report['iso_listing']:
            raise ValueError('No interleaved SSIF in 3D ISO')
        if 'Version = 2.50' not in report['iso_listing']:
            raise ValueError('Expected UDF 2.50 disc filesystem')
        run('extract-iso', [sevenzip, 'x', '-y', '-o'+str(OUT/'disc'), OUT/'TransCora-BD3D-Proof.iso'])
        base = OUT/'disc/BDMV/STREAM/00000.m2ts'
        dependent = OUT/'disc/BDMV/STREAM/00001.m2ts'
        ssif = OUT/'disc/BDMV/STREAM/SSIF/00000.ssif'
        packed = json.loads(run('disc-probe', [FFPROBE, '-v', 'error', '-count_frames', '-show_streams',
                                             '-show_packets', '-of', 'json', base]))
        v = next(stream for stream in packed['streams'] if stream.get('codec_type') == 'video')
        if (v.get('width'), v.get('height'), v.get('pix_fmt'), v.get('level')) != (1920, 1080, 'yuv420p', 41):
            raise ValueError('Disc video geometry/format/level check failed')
        if Fraction(v['r_frame_rate']) != BD_RATE or int(v['nb_read_frames']) != report['frames']:
            raise ValueError('Disc frame rate/count check failed')
        if any(v.get(key) != 'bt709' for key in ('color_space', 'color_primaries', 'color_transfer')):
            raise ValueError('Disc BT.709 signalling missing')
        times = sorted(float(p['pts_time']) for p in packed['packets'] if p['stream_index'] == v['index'])
        check_cadence(times, BD_RATE, v['time_base'])
        audio = next(stream for stream in packed['streams'] if stream.get('codec_type') == 'audio')
        if audio['codec_name'] != 'pcm_bluray' or audio['sample_rate'] != '48000' or audio['channels'] != 2:
            raise ValueError('Disc lossless stereo audio check failed')
        offset = float(audio['start_time'])-float(v['start_time'])
        if abs(offset) > 1/48000:
            raise ValueError('Disc A/V start alignment failed')
        report['disc_video'] = v
        report['disc_audio'] = audio
        report['disc_duration'] = report['frames']/float(BD_RATE)
        report['av_offset'] = offset
        # Decode from the actual interleaved SSIF, after muxer SEI insertion.
        (OUT/'demux.meta').write_text(f'MUXOPT --demux\nV_MPEG4/ISO/AVC, "{ssif}", track=4113\n'
                                    f'V_MPEG4/ISO/MVC, "{ssif}", track=4114\n', encoding='utf-8')
        demux = OUT/'demuxed'
        demux.mkdir(exist_ok=True)
        run('disc-demux', [MUX, OUT/'demux.meta', demux])
        avc = next(demux.glob('*.264'))
        mvc = next(demux.glob('*.mvc'))
        run('decode-disc', [DEC, '-sw', '-i:mvc', avc, mvc,
                            '-o', OUT/'disc-left.yuv', OUT/'disc-right.yuv'])
        for eye in ('left', 'right'):
            if (OUT/('disc-'+eye+'.yuv')).read_bytes() != (OUT/('decoded-'+eye+'.yuv')).read_bytes():
                raise ValueError('Disc roundtrip changed decoded '+eye+' view')
        report['disc_roundtrip_identical'] = True
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        print(report['error'], flush=True)
    finally:
        (OUT/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        # Raw proof frames are reproducible and very large; keep elementary streams, ISO and reports.
        for path in OUT.glob('*.yuv'):
            path.unlink()
        (OUT/'source_full_sbs.mkv').unlink(missing_ok=True)
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
