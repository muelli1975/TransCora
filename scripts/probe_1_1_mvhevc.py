"""Test an actual multiview x265 CLI and candidate containers, outside the product."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from mvhevc_probe_tools import picture_counts, signal_stereo, stereo_sei, consolidate_headers, annexb_nals
from mvhevc_mp4_probe import configure_stereo_mp4, boxes


def decoder_diagnostics(ffmpeg, source, folder, originals):
    """Compare a shared decoder with independent requests and thread counts."""
    checks = []
    for threads in (0, 1):
        stem = source.stem+f'-threads-{threads}'
        outputs = [folder/f'{stem}-view-{i}.yuv' for i in range(2)]
        command = [ffmpeg, '-y', '-v', 'warning', '-threads', str(threads), '-i', source]
        for index, target in enumerate(outputs):
            command += ['-map', f'0:v:0:vidx:{index}', '-fps_mode', 'passthrough',
                        '-pix_fmt', 'yuv420p', '-f', 'rawvideo', target]
        check = {'threads': threads, 'shared_decoder': True, 'views': []}
        try:
            run(command, folder/(stem+'.log'))
            for i, target in enumerate(outputs):
                pixels = target.read_bytes()
                check['views'].append({'index': i, 'frames': len(pixels)/(128*64*3/2),
                    'pixel_exact': pixels == originals[i],
                    'first_luma_per_frame': list(pixels[::128*64*3//2])})
        except Exception as error:
            check['reason'] = str(error)
        checks.append(check)
    return checks


def run(args, log=None, input_data=None):
    result = subprocess.run(list(map(str, args)), input=input_data, capture_output=True, timeout=120)
    if log is not None:
        log.write_bytes(result.stderr)
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
        frames = 36
        originals = []
        for index, colour in enumerate(((65, 95, 200), (130, 190, 80))):
            pixels = b''.join(bytes([colour[0]+n])*128*64 + bytes([colour[1]])*64*32
                              + bytes([colour[2]])*64*32 for n in range(frames))
            originals.append(pixels); (folder/f'{index}.yuv').write_bytes(pixels)
        config = folder/'multiview.cfg'
        config.write_text('--num-views 2\n--format 0\n'+''.join(
            f'--input "{(folder / f"{index}.yuv").as_posix()}"\n' for index in range(2)), 'utf-8')
        raw = folder/'stereo.hevc'
        run([x265, '--multiview-config', config, '--input-res', '128x64', '--fps', '25', '--frames', str(frames),
             '--input-csp', 'i420', '--input-depth', '8', '--preset', 'ultrafast', '--lossless',
             '--bframes', '0', '--keyint', '12', '--repeat-headers', '--pools', 'none',
             '--frame-threads', '1', '--output', raw], folder/'encoder.log')
        initial_headers = folder/'stereo-initial-headers.hevc'
        run([x265, '--multiview-config', config, '--input-res', '128x64', '--fps', '25', '--frames', str(frames),
             '--input-csp', 'i420', '--input-depth', '8', '--preset', 'ultrafast', '--lossless',
             '--bframes', '0', '--keyint', '12', '--no-repeat-headers', '--pools', 'none',
             '--frame-threads', '1', '--output', initial_headers], folder/'initial-headers-encoder.log')
        report['encoder'] = 'passed'
        report['coded_pictures_per_layer'] = picture_counts(raw.read_bytes())
        report['decoder_diagnostics'] = {
            'original': decoder_diagnostics(ffmpeg, raw, folder, originals)}
        paired = folder/'stereo-paired.hevc'
        paired.write_bytes(consolidate_headers(raw.read_bytes()))
        report['decoder_diagnostics']['headers_consolidated'] = decoder_diagnostics(ffmpeg, paired, folder, originals)
        report['decoder_diagnostics']['initial_headers_only'] = decoder_diagnostics(ffmpeg, initial_headers, folder, originals)
        # A single packed SBS input can be streamed directly from FFmpeg. This
        # avoids two uncompressed full-length intermediate video files.
        packed = bytearray()
        for n in range(frames):
            for left,right,w,h in [(65+n,130+n,128,64),(95,190,64,32),(200,80,64,32)]:
                packed.extend((bytes([left])*w+bytes([right])*w)*h)
        pipe_config = folder/'multiview-stdin.cfg'
        pipe_config.write_text('--num-views 2\n--format 1\n--input -\n', 'utf-8')
        streamed = folder/'stereo-streamed.hevc'
        run([x265,'--multiview-config',pipe_config,'--input-res','128x64','--fps','25',
             '--input-csp','i420','--input-depth','8','--preset','ultrafast','--lossless',
             '--bframes','0','--keyint','12','--no-repeat-headers','--output',streamed],
            folder/'streamed-encoder.log',bytes(packed))
        report['decoder_diagnostics']['sbs_stdin_auto_threads'] = decoder_diagnostics(ffmpeg,streamed,folder,originals)
        tagged = folder/'stereo-lr.hevc'
        tagged.write_bytes(signal_stereo(initial_headers.read_bytes()))
        report['decoder_diagnostics']['stereo_signalled'] = decoder_diagnostics(ffmpeg, tagged, folder, originals)
        report['signalled_streams'] = json.loads(run([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', tagged]))['streams']
        reversed_tag = folder/'stereo-rl.hevc'
        reversed_tag.write_bytes(signal_stereo(initial_headers.read_bytes(),1,0))
        audio = folder/'audio.wav'
        run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'sine=frequency=700:sample_rate=48000',
             '-t', str(frames/25), '-c:a', 'pcm_s16le', audio])
        candidates = [raw, initial_headers, streamed, paired, tagged]
        for name, source, tag in [('hev1', raw, 'hev1'), ('hvc1', raw, 'hvc1'), ('stereo-lr', tagged, 'hvc1'),
                                  ('stereo-rl', reversed_tag, 'hvc1')]:
            path = folder/f'{name}.mp4'
            try:
                run([ffmpeg, '-v', 'error', '-r', '25', '-i', source, '-i', audio, '-map', '0:v',
                     '-map', '1:a', '-c:v', 'copy', '-tag:v', tag, '-c:a', 'aac', '-movflags', '+faststart', path])
                candidates.append(path)
                if name in ('stereo-lr','stereo-rl'):
                    configured = folder/(name+'-apple-config.mp4')
                    before = path.read_bytes()
                    sei = stereo_sei(1,0) if name=='stereo-rl' else stereo_sei()
                    after = configure_stereo_mp4(before, sei, annexb_nals(source.read_bytes()))
                    media = lambda data: next(payload for _,kind,payload in boxes(data) if kind == b'mdat')
                    assert media(before) == media(after), 'Media data changed during configuration'
                    configured.write_bytes(after); candidates.append(configured)
                    before_audio = run([ffmpeg,'-v','error','-i',path,'-map','0:a:0','-f','s16le','-'])
                    after_audio = run([ffmpeg,'-v','error','-i',configured,'-map','0:a:0','-f','s16le','-'])
                    assert before_audio == after_audio, 'Decoded audio changed during configuration'
            except Exception as error:
                report['checks'].append({'container': tag, 'result': 'blocked', 'reason': str(error)})
        for path in candidates:
            check = {'container': path.name, 'result': 'blocked'}
            try:
                streams = json.loads(run([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', path]))['streams']
                video = next(stream for stream in streams if stream['codec_type'] == 'video')
                check['views'] = {key: video.get(key) for key in ('view_ids_available', 'view_pos_available')}
                decoded = []
                check['decoded_views'] = []
                for index in range(2):
                    pixels = run([ffmpeg, '-v', 'error', '-i', path, '-map', f'0:v:0:vidx:{index}',
                                  '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'])
                    check['decoded_views'].append({'index': index, 'bytes': len(pixels),
                        'expected_bytes': len(originals[index]), 'first_samples': list(pixels[:4]),
                        'sha256': hashlib.sha256(pixels).hexdigest(),
                        'expected_sha256': hashlib.sha256(originals[index]).hexdigest()})
                    assert pixels == originals[index], f'View {index}: frames, pixels or ordering differ'
                    decoded.append(hashlib.sha256(pixels).hexdigest())
                check['both_views_pixel_exact'] = decoded
                # vidx-only success is insufficient for the application's
                # explicit left/right decoder path or Apple interoperability.
                for index, side in enumerate(('left', 'right')):
                    pixels = run([ffmpeg, '-v', 'error', '-i', path, '-map', f'0:v:0:vpos:{side}',
                                  '-fps_mode', 'passthrough', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', '-'])
                    expected = originals[1-index] if path.name.startswith('stereo-rl') else originals[index]
                    assert pixels == expected, f'Explicit {side} view is missing or differs'
                if path.suffix == '.mp4':
                    timestamps = json.loads(run([ffprobe, '-v', 'error', '-select_streams', 'v:0',
                                                 '-show_packets', '-of', 'json', path]))['packets']
                    assert len(timestamps) == frames
                    assert all(abs(float(packet['pts_time'])-n/25) < .0001 for n, packet in enumerate(timestamps))
                    assert any(stream['codec_type'] == 'audio' for stream in streams)
                    check['apple_decoder_records'] = b'lhvC' in path.read_bytes()
                    assert check['apple_decoder_records'], 'Separate base/enhancement decoder configuration missing'
                    assert set(str(video.get('view_pos_available','')).split(',')) == {'1','2'}, 'Explicit L/R positions are absent'
                    assert video.get('profile') in ('Main','Main 10'), 'Base decoder profile is not Main/Main 10'
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
