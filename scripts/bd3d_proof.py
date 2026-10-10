"""Isolated proof: portable FRIM software MVC, two-view decode, legacy 3D ISO."""
from pathlib import Path
import json
import os
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
    report = {'ok': False, 'frames': 48, 'rate': '24000/1001', 'platform': sys.platform,
              'tools': json.loads((ROOT/'scripts/bd3d-tools.json').read_text())}
    try:
        run('frim-encode-help', [ENC, '-help'], check=False)
        run('frim-decode-help', [DEC, '-help'], check=False)
        run('tsmuxer-help', [MUX], check=False)
        run('ffmpeg-version', [FFMPEG, '-version'])
        # YUV420 fixture deliberately differs between eyes; no AviSynth, registry or installer.
        for eye, graph in [('left', 'testsrc2=size=1920x1080:rate=24000/1001'),
                           ('right', 'testsrc2=size=1920x1080:rate=24000/1001,drawbox=x=480:y=270:w=960:h=540:color=white:t=fill')]:
            run('source-'+eye, [FFMPEG, '-y', '-hide_banner', '-f', 'lavfi', '-i', graph,
                               '-frames:v', '48', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', OUT/(eye+'.yuv')])
        run('encode-mvc', [ENC, '-sw', '-i', OUT/'left.yuv', OUT/'right.yuv',
                          '-viewoutput', '-o:mvc', OUT/'base.avc', OUT/'dependent.mvc',
                          '-w', '1920', '-h', '1080', '-f', '24000/1001', '-I420',
                          '-vbr', '28000', '40000', '-u', '1', '-profile', 'high', '-level', '4.1',
                          '-gop', '24', '4', '0', 'O', '-cpbsize', '3570', '-l', '6',
                          '-PicTimingSEI', 'off', '-EndOfSequence', 'off'])
        run('decode-mvc', [DEC, '-sw', '-i:mvc', OUT/'base.avc', OUT/'dependent.mvc',
                          '-o', OUT/'decoded-left.yuv', OUT/'decoded-right.yuv'])
        expected = 1920*1080*3//2*48
        report['view_sizes'] = {eye: (OUT/('decoded-'+eye+'.yuv')).stat().st_size for eye in ('left', 'right')}
        if any(size != expected for size in report['view_sizes'].values()):
            raise ValueError('Decoded view frame count does not match')
        for eye in ('left', 'right'):
            run('quality-'+eye, [FFMPEG, '-hide_banner', '-f', 'rawvideo', '-s', '1920x1080', '-pix_fmt', 'yuv420p',
                                '-i', OUT/(eye+'.yuv'), '-f', 'rawvideo', '-s', '1920x1080', '-pix_fmt', 'yuv420p',
                                '-i', OUT/('decoded-'+eye+'.yuv'), '-lavfi', 'psnr', '-f', 'null', '-'])
        report['base_probe'] = json.loads(run('base-probe', [FFPROBE, '-v', 'error', '-count_frames',
                                                          '-show_streams', '-of', 'json', OUT/'base.avc']))
        run('source-audio', [FFMPEG, '-y', '-hide_banner', '-f', 'lavfi', '-i', 'sine=frequency=997:sample_rate=48000',
                             '-t', '2.002', '-ac', '2', '-c:a', 'pcm_s24le', OUT/'audio.wav'])
        meta = 'MUXOPT --no-pcr-on-video-pid --new-audio-pes --blu-ray --vbr --vbv-len=500\n'
        meta += f'V_MPEG4/ISO/AVC, "{OUT / "base.avc"}", fps=23.976, insertSEI, contSPS\n'
        meta += f'V_MPEG4/ISO/MVC, "{OUT / "dependent.mvc"}", fps=23.976, insertSEI, contSPS\n'
        meta += f'A_LPCM, "{OUT / "audio.wav"}", lang=deu\n'
        (OUT/'disc.meta').write_text(meta, encoding='utf-8')
        run('mux-iso', [MUX, OUT/'disc.meta', OUT/'TransCora-BD3D-Proof.iso'])
        sevenzip = r'C:\Program Files\7-Zip\7z.exe'
        report['iso_listing'] = run('iso-list', [sevenzip, 'l', '-slt', OUT/'TransCora-BD3D-Proof.iso'])
        if 'SSIF' not in report['iso_listing'] or '.ssif' not in report['iso_listing']:
            raise ValueError('No interleaved SSIF in 3D ISO')
        report['ok'] = True
    except Exception:
        report['error'] = traceback.format_exc()
        print(report['error'], flush=True)
    finally:
        (OUT/'report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding='utf-8')
        # Raw proof frames are reproducible and very large; keep elementary streams, ISO and reports.
        for path in OUT.glob('*.yuv'):
            path.unlink()
    if not report['ok']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
