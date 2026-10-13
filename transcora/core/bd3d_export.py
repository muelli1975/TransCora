"""Portable software MVC export; raw pictures only travel through bounded pipes."""
from dataclasses import dataclass
from collections import deque
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
import time

from .bd3d import BD_RATE, prepare, encoder_args, mux_meta, output_mode
from .engine import Cancelled, stop_process, publish_without_overwrite, capture
from .model import app_root
from .mvc import tag_generated_stream, coded_fingerprint
from .naming import default_disc_title
from .toolchain import process_options
from .udf import write_label

FRAME_BYTES = 1920*1080*3  # two I420 views


@dataclass(frozen=True)
class BdTools:
    encoder: Path
    decoder: Path
    muxer: Path

    @classmethod
    def find(cls):
        root = app_root()/'tools'
        enc, dec, mux = root/'frim/FRIMEncode64.exe', root/'frim/FRIMDecode64.exe', root/'tsmuxer/tsMuxeR.exe'
        if os.name != 'nt':
            raise ValueError('BD-3D ist in der portablen Windows-Version verfügbar.')
        if not all(p.is_file() for p in (enc, dec, mux, root/'frim/libmfxsw64.dll')):
            raise ValueError('BD-3D-Werkzeuge fehlen. TransCora.zip vollständig entpacken.')
        return cls(enc.resolve(), dec.resolve(), mux.resolve())

    @property
    def environment(self):
        return dict(os.environ, PATH=str(self.encoder.parent)+os.pathsep+os.environ.get('PATH', ''))


def validate_audio(audios):
    for audio in audios:
        channels, layout = audio.get('channels'), audio.get('channel_layout')
        if channels in (1, 2) and layout in (None, 'unknown', 'unspecified'):
            continue  # Keep the one/two channels in their original order; no remapping.
        if (channels, layout) not in {
                (1, 'mono'), (2, 'stereo'), (6, '5.1'), (6, '5.1(side)'), (8, '7.1')}:
            raise ValueError('BD-3D: Audiospur mit nicht freigegebener Kanalbelegung; Mono, Stereo, 5.1 oder 7.1 verwenden.')


def check_cancel(cancel):
    if cancel.is_set():
        raise Cancelled()


def run(args, cancel, log, env, on_output=None, on_line=None):
    """Continuously consume subprocess output; cancel also interrupts blocked reads."""
    check_cancel(cancel)
    log.write('COMMAND '+json.dumps(list(map(str, args)), ensure_ascii=False)+'\n')
    log.flush()
    process = subprocess.Popen(list(map(str, args)), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               env=env, **process_options())
    errors, tail = [], deque(maxlen=32)
    def stdout():
        try:
            if on_output:
                on_output(process.stdout)
            else:
                for line in iter(process.stdout.readline, b''):
                    text = line.decode('utf-8', 'replace')
                    if on_line:
                        on_line(text)
                    log.write(text)
                    tail.append(text.strip())
        except BaseException as error:
            errors.append(error)
    def stderr():
        for line in iter(process.stderr.readline, b''):
            text = line.decode('utf-8', 'replace')
            log.write(text)
            tail.append(text.strip())
    readers = [threading.Thread(target=fn, daemon=True) for fn in (stdout, stderr)]
    try:
        for reader in readers:
            reader.start()
        while process.poll() is None:
            if errors:
                raise errors[0]
            if cancel.wait(.1):
                raise Cancelled()
        for reader in readers:
            reader.join(timeout=10)
        check_cancel(cancel)
        if errors:
            raise errors[0]
        if process.returncode:
            raise ValueError('BD-3D: Werkzeugfehler · '+'\n'.join(tail)[-3500:])
    finally:
        stop_process(process)
        for reader in readers:
            if reader.ident:
                reader.join(timeout=5)
        process.stdout.close()
        process.stderr.close()
        log.flush()


def encode(tools, bd, plan, base, dependent, cancel, emit, log, estimated_frames, decoder=None):
    from .multiview import input_args, check_decoder
    frames = 0
    _, _, output_rate = output_mode(plan.options.bd_mode)
    # FFmpeg supplies progress; source timing and cadence are not approval gates.
    graph = plan.graph+';[left][right]hstack=inputs=2[packed]'
    args = [str(tools.ffmpeg), '-hide_banner', '-nostdin', '-nostats', '-loglevel', 'info', '-copyts',
            '-progress', 'pipe:2', '-stats_period', '0.5', '-filter_complex_threads', '1',
            '-protocol_whitelist', 'file,pipe', '-noautorotate', *input_args(plan, copyts=True),
            '-filter_complex', graph, '-map', '[packed]', '-an', '-c:v', 'rawvideo',
            '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1']
    frim = encoder_args(bd.encoder, Path('-'), Path('-'), base, dependent, plan.options.bd_bitrate_mbps, mode=plan.options.bd_mode)
    # The author's documented single-input SBS stdin mode, not two raw temp files.
    frim[frim.index('-i')+1:frim.index('-viewoutput')] = ['-']
    frim += ['-sbs', '2']
    producers = []
    readers = []
    tail = deque(maxlen=32)
    log.write('PIPELINE '+json.dumps([args, frim], ensure_ascii=False)+'\n')
    def drain(pipe, progress=False):
        nonlocal frames
        fps = None
        for line in iter(pipe.readline, b''):
            text = line.decode('utf-8', 'replace').strip()
            log.write(text+'\n')
            tail.append(text)
            key, _, value = text.partition('=')
            if progress and key == 'frame':
                try:
                    frames = int(value)
                    emit('progress', {'percent': min(70, 5+65*int(value)/estimated_frames) if estimated_frames else None,
                                      'seconds': int(value)/float(output_rate)})
                except ValueError:
                    pass
            elif progress and key == 'fps':
                fps = value
            elif progress and key == 'speed':
                emit('speed', {'speed': value, 'fps': fps})
    try:
        check_cancel(cancel)
        producer = subprocess.Popen(args, stdin=decoder.stdout if decoder else None, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    env=bd.environment, **process_options())
        producers.append(producer)
        encoder = subprocess.Popen(frim, stdin=producer.stdout, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=bd.environment, **process_options())
        producers.append(encoder)
        producer.stdout.close()
        for pipe, progress in ((producer.stderr, True), (encoder.stdout, False), (encoder.stderr, False)):
            reader = threading.Thread(target=drain, args=(pipe, progress), daemon=True)
            reader.start()
            readers.append(reader)
        while any(p.poll() is None for p in producers):
            if cancel.wait(.1):
                raise Cancelled()
            if any(p.poll() not in (None, 0) for p in producers):
                raise ValueError('BD-3D: Kodierung fehlgeschlagen · '+'\n'.join(tail)[-3500:])
        for reader in readers:
            reader.join(timeout=10)
        if any(p.returncode for p in producers):
            raise ValueError('BD-3D: Kodierung fehlgeschlagen · '+'\n'.join(tail)[-3500:])
        check_decoder(decoder, cancel)
        if frames < 1 or any(not p.is_file() or not p.stat().st_size for p in (base, dependent)):
            raise ValueError('BD-3D: Der Encoder hat keine vollständige Ausgabe erstellt.')
        original = plan.info.get('multiview', {}).get('original_video', plan.info['video'])
        first = float(original.get('start_time') or 0)
        log.write(f'ENCODED BD3D frames={frames} rate={output_rate}\n')
        return frames, first
    finally:
        for p in reversed(producers):
            stop_process(p)
        for reader in readers:
            reader.join(timeout=5)
        for p in producers:
            if p.stdout and not p.stdout.closed:
                p.stdout.close()
            p.stderr.close()
        log.flush()


def decoded_digest(bd, base, dependent, frames, cancel, log, emit=None, *, mode="1080p"):
    count, digest = 0, hashlib.sha256()
    width,height,output_rate = output_mode(mode)
    frame_bytes = width*height*3
    last_report = 0
    started = time.monotonic()
    def pictures(pipe):
        nonlocal count, last_report
        while chunk := pipe.read(1024*1024):
            check_cancel(cancel)
            count += len(chunk)
            digest.update(chunk)
            now = time.monotonic()
            if emit and (now-last_report >= .5 or count == frames*frame_bytes):
                last_report = now
                elapsed = now-started
                remaining = max(0, frames*frame_bytes-count)*elapsed/count if elapsed >= 2 else None
                emit('progress', {'percent': 93+6*min(1, count/(frames*frame_bytes)),
                                  'seconds': count/frame_bytes/float(output_rate), 'remaining_seconds': remaining})
    run([bd.decoder, '-sw', '-i:mvc', base, dependent, '-sbs', '-o', '-'],
        cancel, log, bd.environment, pictures)
    if count != frames*frame_bytes:
        raise ValueError('BD-3D: Die Dekodierung beider Halbbilder enthält nicht die erwartete Bildanzahl.')
    return digest.hexdigest()


def verify_mux(tools, bd, plan, movie, base, dependent, frames, fingerprints, audios, cancel, log, folder, emit=None):
    from .audio import channels
    info = json.loads(capture([str(tools.ffprobe), '-v', 'error', '-protocol_whitelist', 'file,pipe',
                               '-show_streams', '-show_format', '-of', 'json', str(movie)], cancel))
    base_tracks = [s for s in info.get('streams', []) if s.get('id') == '0x1011' and s.get('codec_name') == 'h264']
    dependent_tracks = [s for s in info.get('streams', []) if s.get('id') == '0x1012']
    if len(base_tracks) != 1 or len(dependent_tracks) != 1:
        raise ValueError('BD-3D: AVC-Basis oder zweites MVC-Halbbild fehlt im Multiplex.')
    video = base_tracks[0]
    width,height,output_rate = output_mode(plan.options.bd_mode)
    if (video.get('width'), video.get('height'), video.get('pix_fmt'), video.get('level')) != (width, height, 'yuv420p', 41):
        raise ValueError('BD-3D: Ausgaberaster, Farbauflösung oder AVC-Level falsch.')
    if Fraction(video.get('r_frame_rate', '0/1')) != output_rate or any(video.get(key) != 'bt709' for key in
            ('color_space', 'color_primaries', 'color_transfer')) or video.get('color_range') != 'tv':
        raise ValueError('BD-3D: Bildrate oder Farbkennzeichnung falsch.')
    tracks = [s for s in info['streams'] if s.get('codec_type') == 'audio']
    if len(tracks) != len(audios) or any(s.get('codec_name') != 'pcm_bluray' or s.get('sample_rate') != '48000'
            or s.get('channels') != channels(original, plan.options) or s.get('bits_per_raw_sample') != '24'
            for s, original in zip(tracks, audios)):
        raise ValueError('BD-3D: Verlustfreie Audioübernahme stimmt nicht mit der Quelle überein.')
    if any(abs(float(s.get('start_time', '0'))-float(video.get('start_time', '0'))) > 1/48000+.000001 for s in tracks):
        raise ValueError('BD-3D: Audio und Video beginnen nicht synchron.')
    demux = folder/'demuxed'
    demux.mkdir()
    meta = folder/'demux.meta'
    meta.write_text(f'MUXOPT --demux\nV_MPEG4/ISO/AVC, "{movie}", track=4113\n'
                    f'V_MPEG4/ISO/MVC, "{movie}", track=4114\n', encoding='utf-8')
    run([bd.muxer, meta, demux], cancel, log, bd.environment)
    avc, mvc = list(demux.glob('*.264')), list(demux.glob('*.mvc'))
    if len(avc) != 1 or len(mvc) != 1:
        raise ValueError('BD-3D: Beide Halbbilder fehlen in der fertigen Ausgabe.')
    if emit:
        emit('phase', 'BD-3D: Kodierte Bilddaten mit der fertigen Ausgabe vergleichen')
    for path, expected in zip((avc[0], mvc[0]), fingerprints):
        if coded_fingerprint(path, lambda: check_cancel(cancel)) != expected:
            raise ValueError('BD-3D: Kodierte Halbbilder oder Bildparameter wurden beim Verpacken verändert.')
    if emit:
        emit('phase', 'BD-3D: Fertige Ausgabe vollständig dekodieren und beide Halbbilder prüfen')
    return decoded_digest(bd, avc[0], mvc[0], frames, cancel, log, emit, mode=plan.options.bd_mode)


def export(tools, plan, cancel, emit, log_path, decoder=None):
    from .audio import selected, channels
    bd = BdTools.find()
    config = prepare(plan.info['video'], plan.layout, plan.swap, plan.options.bd_mode)
    output_rate = config.rate
    audios = selected(plan.info, plan.options)
    validate_audio(audios)
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.transcora-bd3d-', dir=plan.output.parent) as tmp, log_path.open('a', encoding='utf-8') as log:
        folder = Path(tmp)
        log.write('\nBD-3D '+json.dumps({'source': str(plan.source), 'output': str(plan.output), 'options': vars(plan.options)}, ensure_ascii=False)+'\n')
        phase_started, previous_phase = time.monotonic(), None
        def phase(text):
            nonlocal phase_started, previous_phase
            now = time.monotonic()
            if previous_phase:
                log.write(f'PHASE COMPLETED {now-phase_started:.3f}s {previous_phase}\n')
            previous_phase, phase_started = text, now
            log.write('PHASE '+text+'\n')
            log.flush()
            emit('phase', text)
        def unchanged():
            stat = plan.source.stat()
            if (stat.st_mtime_ns, stat.st_size) != (plan.info['source_mtime_ns'], plan.info['source_size']):
                raise ValueError('Quelle seit der Prüfung geändert. Erneut prüfen.')
        unchanged()
        duration = plan.duration/float(config.speed)
        estimated_frames = max(2, round(duration*float(output_rate))) if duration > 0 else 0
        # Compressed views, audio, mux, extracted SSIF and demux; no raw video files.
        audio_copies = 3 if plan.options.container == 'iso' else 2
        required = duration*(40000*1000/8*4 + audio_copies*sum(
            channels(s, plan.options)*48000*3 for s in audios)) + 256*1024*1024
        if duration > 0 and shutil.disk_usage(folder).free < required:
            # This is a conservative VBR estimate, not the actual final size.
            log.write(f'WARNING BD-3D: Geschätzter Platzbedarf {required/1024**3:.1f} GB; '
                      'verfügbarer Platz liegt darunter. Kodierung wird versucht.\n')
        emit('progress', {'percent': 5, 'seconds': 0})
        phase('BD-3D: Beide Halbbilder in hoher Qualität kodieren')
        base, dependent = folder/'base.avc', folder/'dependent.mvc'
        frames, video_start = encode(tools, bd, plan, base, dependent, cancel, emit, log, estimated_frames, decoder)
        duration = frames/float(output_rate)
        phase('BD-3D: BT.709-Farbkennzeichnung in beiden Bildspuren setzen')
        for p in (base, dependent):
            log.write(f'BT709 {p.name}: {tag_generated_stream(p, lambda: check_cancel(cancel))} parameter sets\n')
        emit('progress', {'percent': 80, 'seconds': duration})
        audio_paths = []
        samples = round(duration*48000)
        for number, audio in enumerate(audios):
            phase(f'BD-3D: Audiospur {number+1} als LPCM vorbereiten')
            path = folder/f'audio-{number}.w64'
            af = f'asetpts=PTS-{video_start}/TB,aresample=48000:async=1:first_pts=0,'+config.audio_filter+f',apad,atrim=end_sample={samples}'
            run([tools.ffmpeg, '-hide_banner', '-nostdin', '-v', 'error', '-n', '-copyts', '-protocol_whitelist',
                 'file,pipe', '-i', plan.info.get('runtime_input', {}).get('source', plan.source), '-map', f"0:{audio['index']}", '-af', af, '-ar', '48000',
                 *(['-ac', '2'] if plan.options.audio_channels == 'stereo' else []),
                 '-c:a', 'pcm_s24le', '-f', 'w64', path], cancel, log, bd.environment)
            audio_paths.append((path, audio.get('tags', {}).get('language', 'und')))
        phase('BD-3D: '+('Blu-ray-ISO erstellen' if plan.options.container == 'iso' else 'M2TS erstellen'))
        movie = folder/('movie.'+plan.options.container)
        meta = folder/'movie.meta'
        label = plan.options.disc_title or default_disc_title(plan.source)
        meta.write_text(mux_meta(base, dependent, None, disc=plan.options.container == 'iso',
                                 label=label, audios=audio_paths, mode=plan.options.bd_mode), encoding='utf-8')
        run([bd.muxer, meta, movie], cancel, log, bd.environment)
        emit('progress', {'percent': 90, 'seconds': duration})
        if plan.options.container == 'iso':
            write_label(movie, label)
        if not movie.is_file() or not movie.stat().st_size:
            raise ValueError('BD-3D: Der Multiplexer hat keine Ausgabe erstellt.')
        unchanged()
        check_cancel(cancel)
        publish_without_overwrite(movie, plan.output, cancel)
        log.write(f'PHASE COMPLETED {time.monotonic()-phase_started:.3f}s {previous_phase}\n')
        log.write(f'COMPLETED BD3D frames={frames} rate={output_rate}\nCOMPLETED {plan.output}\n')
        emit('progress', {'percent': 100, 'seconds': duration})

