"""Portable software MVC export; raw pictures only travel through bounded pipes."""
from dataclasses import dataclass
from collections import deque
from fractions import Fraction
from pathlib import Path
import hashlib
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time

from .bd3d import BD_RATE, prepare, check_cadence, encoder_args, mux_meta
from .engine import Cancelled, stop_process, publish_without_overwrite, capture, probe
from .model import app_root
from .mvc import tag_generated_stream
from .naming import default_disc_title
from .toolchain import process_options
from .udf import Disc, write_label

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


def run(args, cancel, log, env, on_output=None):
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


def scan(tools, plan, config, cancel, log, env):
    count, first, previous = 0, None, None
    def frames(pipe):
        nonlocal count, first, previous
        for line in iter(pipe.readline, b''):
            value = line.decode('ascii', 'replace').strip().split(',')[0]
            if not value:
                continue
            try:
                stamp = float(value)
            except ValueError:
                raise ValueError('BD-3D: Fehlende Bildzeit in der Quelle.') from None
            if previous is not None:
                check_cadence([previous, stamp], config.source_rate, plan.info['video']['time_base'])
            elif not math.isfinite(stamp):
                raise ValueError('BD-3D: Ungültige Bildzeit in der Quelle.')
            else:
                first = stamp
            previous = stamp
            count += 1
            if count % 240 == 0:
                check_cancel(cancel)
    run([tools.ffprobe, '-v', 'error', '-protocol_whitelist', 'file,pipe', '-select_streams', str(plan.info['video']['index']),
         '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time', '-of', 'csv=p=0', plan.source],
        cancel, log, env, frames)
    if count < 2:
        raise ValueError('BD-3D: Zu wenige Bilder für eine verlässliche Timing-Prüfung.')
    expected_span = float((count-1)/config.source_rate)
    tolerance = min(float(1/config.source_rate)/8, max(2.2*float(Fraction(plan.info['video']['time_base'])), .00001))
    if abs((previous-first)-expected_span) > tolerance:
        raise ValueError('BD-3D: Die tatsächliche Bildfolge entspricht nicht der angegebenen konstanten Framerate.')
    return count, first


def encode(tools, bd, plan, base, dependent, cancel, emit, log, frames):
    graph = plan.graph+';[left][right]hstack=inputs=2[packed]'
    args = [str(tools.ffmpeg), '-hide_banner', '-nostdin', '-loglevel', 'warning',
            '-progress', 'pipe:2', '-stats_period', '0.5', '-filter_complex_threads', '1',
            '-protocol_whitelist', 'file,pipe', '-noautorotate', '-i', str(plan.source),
            '-filter_complex', graph, '-map', '[packed]', '-an', '-c:v', 'rawvideo',
            '-pix_fmt', 'yuv420p', '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1']
    frim = encoder_args(bd.encoder, Path('-'), Path('-'), base, dependent)
    # The author's documented single-input SBS stdin mode, not two raw temp files.
    frim[frim.index('-i')+1:frim.index('-viewoutput')] = ['-']
    frim += ['-sbs', '2']
    producers = []
    readers = []
    tail = deque(maxlen=32)
    log.write('PIPELINE '+json.dumps([args, frim], ensure_ascii=False)+'\n')
    def drain(pipe, progress=False):
        fps = None
        for line in iter(pipe.readline, b''):
            text = line.decode('utf-8', 'replace').strip()
            log.write(text+'\n')
            tail.append(text)
            key, _, value = text.partition('=')
            if progress and key == 'frame':
                try:
                    emit('progress', {'percent': min(70, 5+65*int(value)/frames), 'seconds': int(value)/float(BD_RATE)})
                except ValueError:
                    pass
            elif progress and key == 'fps':
                fps = value
            elif progress and key == 'speed':
                emit('speed', {'speed': value, 'fps': fps})
    try:
        check_cancel(cancel)
        producer = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
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


def decoded_digest(bd, base, dependent, frames, cancel, log):
    count, digest = 0, hashlib.sha256()
    def pictures(pipe):
        nonlocal count
        while chunk := pipe.read(1024*1024):
            check_cancel(cancel)
            count += len(chunk)
            digest.update(chunk)
    run([bd.decoder, '-sw', '-i:mvc', base, dependent, '-sbs', '-o', '-'],
        cancel, log, bd.environment, pictures)
    if count != frames*FRAME_BYTES:
        raise ValueError('BD-3D: Die Dekodierung beider Augenbilder enthält nicht die erwartete Bildanzahl.')
    return digest.hexdigest()


def verify_mux(tools, bd, plan, movie, base, dependent, frames, expected_hash, audios, cancel, log, folder):
    info = json.loads(capture([str(tools.ffprobe), '-v', 'error', '-protocol_whitelist', 'file,pipe',
                               '-show_streams', '-show_format', '-of', 'json', str(movie)], cancel))
    base_tracks = [s for s in info.get('streams', []) if s.get('id') == '0x1011' and s.get('codec_name') == 'h264']
    dependent_tracks = [s for s in info.get('streams', []) if s.get('id') == '0x1012']
    if len(base_tracks) != 1 or len(dependent_tracks) != 1:
        raise ValueError('BD-3D: AVC-Basis oder MVC-Zweitansicht fehlt im Multiplex.')
    video = base_tracks[0]
    if (video.get('width'), video.get('height'), video.get('pix_fmt'), video.get('level')) != (1920, 1080, 'yuv420p', 41):
        raise ValueError('BD-3D: Ausgaberaster, Farbauflösung oder AVC-Level falsch.')
    if Fraction(video.get('r_frame_rate', '0/1')) != BD_RATE or any(video.get(key) != 'bt709' for key in
            ('color_space', 'color_primaries', 'color_transfer')) or video.get('color_range') != 'tv':
        raise ValueError('BD-3D: Bildrate oder Farbkennzeichnung falsch.')
    tracks = [s for s in info['streams'] if s.get('codec_type') == 'audio']
    if len(tracks) != len(audios) or any(s.get('codec_name') != 'pcm_bluray' or s.get('sample_rate') != '48000'
            or s.get('channels') != original.get('channels') or s.get('bits_per_raw_sample') != '24'
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
    if len(avc) != 1 or len(mvc) != 1 or decoded_digest(bd, avc[0], mvc[0], frames, cancel, log) != expected_hash:
        raise ValueError('BD-3D: Beide Augenbilder der gemuxten Ausgabe stimmen nicht mit der Kodierung überein.')


def export(tools, plan, cancel, emit, log_path):
    bd = BdTools.find()
    config = prepare(plan.info['video'], plan.layout, plan.swap)
    audios = [s for s in plan.info['streams'] if s.get('codec_type') == 'audio']
    validate_audio(audios)
    plan.output.parent.mkdir(parents=True, exist_ok=True)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.transcora-bd3d-', dir=plan.output.parent) as tmp, log_path.open('a', encoding='utf-8') as log:
        folder = Path(tmp)
        log.write('\nBD-3D '+json.dumps({'source': str(plan.source), 'output': str(plan.output), 'options': vars(plan.options)}, ensure_ascii=False)+'\n')
        def unchanged():
            stat = plan.source.stat()
            if (stat.st_mtime_ns, stat.st_size) != (plan.info['source_mtime_ns'], plan.info['source_size']):
                raise ValueError('Quelle seit der Prüfung geändert. Erneut prüfen.')
        unchanged()
        emit('phase', 'BD-3D: Bildzeiten vollständig prüfen')
        frames, video_start = scan(tools, plan, config, cancel, log, bd.environment)
        duration = frames/float(BD_RATE)
        # Compressed views, audio, mux, extracted SSIF and demux; no raw video files.
        required = duration*(40000*1000/8*4 + sum(s['channels']*48000*3 for s in audios)) + 256*1024*1024
        if shutil.disk_usage(folder).free < required:
            raise ValueError(f'BD-3D: Für Ausgabe und Prüfdaten werden ungefähr {required/1024**3:.1f} GB freier Platz benötigt.')
        for s in audios:
            if duration*s['channels']*48000*3 >= 0xffff0000:
                raise ValueError('BD-3D: Diese Audiospur überschreitet das geprüfte WAV-Limit von 4 GB. Kürzere Abschnitte verwenden.')
        emit('progress', {'percent': 5, 'seconds': 0})
        emit('phase', 'BD-3D: Beide Augenbilder in hoher Qualität kodieren')
        base, dependent = folder/'base.avc', folder/'dependent.mvc'
        encode(tools, bd, plan, base, dependent, cancel, emit, log, frames)
        emit('phase', 'BD-3D: Farbkennzeichnung und beide Augenbilder prüfen')
        for p in (base, dependent):
            log.write(f'BT709 {p.name}: {tag_generated_stream(p, lambda: check_cancel(cancel))} parameter sets\n')
        expected_hash = decoded_digest(bd, base, dependent, frames, cancel, log)
        emit('progress', {'percent': 80, 'seconds': duration})
        audio_paths = []
        samples = round(duration*48000)
        for number, audio in enumerate(audios):
            emit('phase', f'BD-3D: Audiospur {number+1} verlustfrei vorbereiten')
            path = folder/f'audio-{number}.wav'
            af = f'asetpts=PTS-{video_start}/TB,aresample=48000:async=1:first_pts=0,'+config.audio_filter+f',apad,atrim=end_sample={samples}'
            run([tools.ffmpeg, '-hide_banner', '-nostdin', '-v', 'error', '-n', '-copyts', '-protocol_whitelist',
                 'file,pipe', '-i', plan.source, '-map', f"0:{audio['index']}", '-af', af, '-ar', '48000',
                 '-c:a', 'pcm_s24le', path], cancel, log, bd.environment)
            audio_paths.append((path, audio.get('tags', {}).get('language', 'und')))
        emit('phase', 'BD-3D: '+('Blu-ray-ISO erstellen' if plan.options.container == 'iso' else 'M2TS erstellen'))
        movie = folder/('movie.'+plan.options.container)
        meta = folder/'movie.meta'
        label = plan.options.disc_title or default_disc_title(plan.source)
        meta.write_text(mux_meta(base, dependent, None, disc=plan.options.container == 'iso',
                                 label=label, audios=audio_paths), encoding='utf-8')
        run([bd.muxer, meta, movie], cancel, log, bd.environment)
        emit('progress', {'percent': 90, 'seconds': duration})
        emit('phase', 'BD-3D: Fertige Ausgabe und beide Augenbilder prüfen')
        packed = movie
        if plan.options.container == 'iso':
            write_label(movie, label)
            with Disc(movie) as disc:
                if disc.label != label:
                    raise ValueError('BD-3D: Der Disc-Titel wurde nicht korrekt gespeichert.')
                for name, magic in [('index.bdmv', b'INDX'), ('MovieObject.bdmv', b'MOBJ'), ('PLAYLIST/00000.mpls', b'MPLS')]:
                    address = disc.locate('BDMV/'+name)
                    size, _ = disc.allocations(disc.block(disc.physical(*address)), address[0])
                    if size > 1024*1024:
                        raise ValueError('BD-3D: Blu-ray-Struktur ungültig.')
                    data = b''.join(disc.chunks(address))
                    if not data.startswith(magic) or len(data) > 1024*1024:
                        raise ValueError('BD-3D: Blu-ray-Struktur unvollständig.')
                packed = folder/'verified.ssif'
                disc.extract('BDMV/STREAM/SSIF/00000.ssif', packed, lambda: check_cancel(cancel))
        verify_mux(tools, bd, plan, packed, base, dependent, frames, expected_hash, audios, cancel, log, folder)
        unchanged()
        check_cancel(cancel)
        publish_without_overwrite(movie, plan.output, cancel)
        log.write(f'VERIFIED BD3D frames={frames} rate={BD_RATE} both_views_sha256={expected_hash}\nCOMPLETED {plan.output}\n')
        emit('progress', {'percent': 100, 'seconds': duration})
