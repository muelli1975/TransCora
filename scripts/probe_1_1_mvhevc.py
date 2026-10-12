"""Test an actual multiview x265 CLI and candidate containers, outside the product."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def run(args):
    result = subprocess.run(list(map(str, args)), capture_output=True, timeout=120)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf-8', 'replace')[-5000:])
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--x265', required=True, type=Path)
    parser.add_argument('--ffmpeg', required=True, type=Path)
    parser.add_argument('--ffprobe', required=True, type=Path)
    parser.add_argument('--folder', required=True, type=Path)
    args = parser.parse_args()
    folder = args.folder.resolve(); folder.mkdir(parents=True, exist_ok=True)
    x265, ffmpeg, ffprobe = args.x265.resolve(), args.ffmpeg.resolve(), args.ffprobe.resolve()
    report = {'development_probe': True, 'x265_source': 'e9b88125dc21393b3fd8d68e98083bdfb89778a8',
              'status': 'blocked', 'checks': [], 'not_checked': ['Apple device playback', 'production integration']}
    try:
        originals = []
        for index, colour in enumerate(((65, 95, 200), (130, 190, 80))):
            pixels = b''.join(bytes([colour[0]+n])*128*64 + bytes([colour[1]])*64*32
                              + bytes([colour[2]])*64*32 for n in range(12))
            originals.append(pixels); (folder/f'{index}.yuv').write_bytes(pixels)
        config = folder/'multiview.cfg'
        config.write_text('--num-views 2\n--format 0\n'+''.join(
            f'--input "{(folder / f"{index}.yuv").as_posix()}"\n' for index in range(2)), 'utf-8')
        raw = folder/'stereo.hevc'
        run([x265, '--multiview-config', config, '--input-res', '128x64', '--fps', '25', '--frames', '12',
             '--input-csp', 'i420', '--input-depth', '8', '--preset', 'ultrafast', '--lossless',
             '--bframes', '0', '--keyint', '12', '--repeat-headers', '--pools', 'none',
             '--frame-threads', '1', '--output', raw])
        report['encoder'] = 'passed'
        audio = folder/'audio.wav'
        run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=700:sample_rate=48000',
             '-t', '.48', '-c:a', 'pcm_s16le', audio])
        candidates = [raw]
        for tag in ('hev1', 'hvc1'):
            path = folder/f'{tag}.mp4'
            try:
                run([ffmpeg, '-v', 'error', '-r', '25', '-i', raw, '-i', audio, '-map', '0:v',
                     '-map', '1:a', '-c:v', 'copy', '-tag:v', tag, '-c:a', 'aac', '-movflags', '+faststart', path])
                candidates.append(path)
            except Exception as error:
                report['checks'].append({'container': tag, 'result': 'blocked', 'reason': str(error)})
        for path in candidates:
            check = {'container': path.name, 'result': 'blocked'}
            try:
                streams = json.loads(run([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', path]))['streams']
                video = next(stream for stream in streams if stream['codec_type'] == 'video')
                check['views'] = {key: video.get(key) for key in ('view_ids_available', 'view_pos_available')}
                decoded = []
                for index in range(2):
                    pixels = run([ffmpeg, '-v', 'error', '-i', path, '-map', f'0:v:0:vidx:{index}',
                                  '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'])
                    assert pixels == originals[index], f'View {index}: frames, pixels or ordering differ'
                    decoded.append(hashlib.sha256(pixels).hexdigest())
                check['both_views_pixel_exact'] = decoded
                # vidx-only success is insufficient for the application's
                # explicit left/right decoder path or Apple interoperability.
                for index, side in enumerate(('left', 'right')):
                    pixels = run([ffmpeg, '-v', 'error', '-i', path, '-map', f'0:v:0:vpos:{side}',
                                  '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'])
                    assert pixels == originals[index], f'Explicit {side} view is missing or differs'
                if path.suffix == '.mp4':
                    timestamps = json.loads(run([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                                                 '-show_packets', '-of', 'json', path]))['packets']
                    assert len(timestamps) == 12
                    assert all(abs(float(packet['pts_time'])-n/25) < .0001 for n, packet in enumerate(timestamps))
                    assert any(stream['codec_type'] == 'audio' for stream in streams)
                check['result'] = 'passed'
            except Exception as error:
                check['reason'] = str(error)
            report['checks'].append(check)
        if any(check['result'] == 'passed' and check['container'].endswith('.mp4') for check in report['checks']):
            report['status'] = 'candidate'
    except Exception as error:
        report['reason'] = str(error)
    (folder/'report.json').write_text(json.dumps(report, indent=2)+'\n', 'utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
