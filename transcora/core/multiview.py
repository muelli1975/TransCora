"""Strict stereo input adapters. Compressed staging only; decoded frames use pipes."""
from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
from collections import deque
import json
import os
import re
import subprocess
import tempfile
import threading

from .model import app_root
from .toolchain import process_options


def decoder():
    exe = app_root()/'tools/mvc'/('TransCoraMVC.exe' if os.name == 'nt' else 'TransCoraMVC')
    if not exe.is_file():
        raise ValueError('Der portable MVC-Decoder fehlt. TransCora vollständig entpacken.')
    return exe


def raw_probe(tools, source, cancel):
    from .engine import capture
    result = json.loads(capture([str(tools.ffprobe), '-v', 'error', '-protocol_whitelist', 'file,pipe',
        '-show_streams', '-show_format', '-of', 'json', str(source)], cancel))
    videos = [s for s in result.get('streams', []) if s.get('codec_type') == 'video'
              and not s.get('disposition', {}).get('attached_pic')]
    if not videos:
        raise ValueError('Keine nutzbare Videospur gefunden.')
    return result, videos


def playlist_base_right(data):
    # AppInfoPlayList follows the fixed 40-byte MPLS header. The flag is the
    # fourth bit after the 64-bit UO mask (libbluray/tsMuxeR layout).
    if len(data) < 58 or data[:4] != b'MPLS':
        raise ValueError('Blu-ray: AppInfoPlayList fehlt.')
    length = int.from_bytes(data[40:44], 'big')
    if length < 14 or 44+length > len(data):
        raise ValueError('Blu-ray: AppInfoPlayList ist abgeschnitten.')
    return bool(data[56] & 0x10)


def iso_film(source):
    """Select the longest complete single-clip MVC playlist; never select a bonus instead."""
    from .udf import Disc
    with Disc(source) as disc:
        entries = disc.directory(disc.locate('BDMV/PLAYLIST'))
        films = []
        for name, address in entries.items():
            if not name.lower().endswith('.mpls'):
                continue
            size, _ = disc.allocations(disc.block(disc.physical(*address)), address[0])
            if size > 1024*1024:
                raise ValueError('Blu-ray-Playlist ist zu groß.')
            data = b''.join(disc.chunks(address))
            if len(data) < 20 or data[:4] != b'MPLS':
                raise ValueError('Ungültige Blu-ray-Playlist.')
            start = int.from_bytes(data[8:12], 'big')
            if start+10 > len(data):
                raise ValueError('Blu-ray-Playlist ist abgeschnitten.')
            count = int.from_bytes(data[start+6:start+8], 'big')
            pos, clips, duration = start+10, [], 0
            for _ in range(count):
                if pos+34 > len(data):
                    raise ValueError('Blu-ray-PlayItem ist abgeschnitten.')
                length = int.from_bytes(data[pos:pos+2], 'big')
                item = data[pos+2:pos+2+length]
                if len(item) != length or length < 32 or not item[:5].isdigit() or item[5:9] != b'M2TS':
                    raise ValueError('Nicht unterstütztes Blu-ray-PlayItem.')
                clip = item[:5].decode('ascii')
                duration += int.from_bytes(item[16:20], 'big')-int.from_bytes(item[12:16], 'big')
                clips.append((clip, int.from_bytes(item[12:16], 'big'), int.from_bytes(item[16:20], 'big')))
                pos += 2+length
            if clips:
                films.append((duration, name, clips, playlist_base_right(data)))
        if not films:
            raise ValueError('Keine Film-Playlist in der Blu-ray-ISO.')
        _, playlist, clips, base_right = max(films)
        if len(clips) != 1:
            raise ValueError('Diese Blu-ray verwendet mehrere Clips pro Film. Seamless Branching ist noch nicht freigegeben.')
        path = 'BDMV/STREAM/SSIF/'+clips[0][0]+'.ssif'
        disc.locate(path)
        # Trimming and alternate-angle branching need a dedicated playlist reader.
        return {'iso_path': path, 'playlist': playlist, 'in': clips[0][1], 'out': clips[0][2],
                'base_view_right': base_right}


def iso_extract(source, descriptor, destination, cancel, sample=False):
    from .udf import Disc
    from .engine import Cancelled
    with Disc(source) as disc, destination.open('xb') as out:
        total = 0
        for chunk in disc.chunks(disc.locate(descriptor['iso_path'])):
            if cancel and cancel.is_set():
                raise Cancelled()
            out.write(chunk)
            total += len(chunk)
            if sample and total >= 32*1024*1024:
                break


def demux_ts(source, pids, paths, cancel, sample=False):
    """Bounded PES extraction with continuity, scrambling and header checks."""
    from .engine import Cancelled
    with source.open('rb') as file:
        head = file.read(1024)
        packet = next((n for n in (188, 192, 204) if all(
            len(head) > n*i+(4 if n == 192 else 0) and head[n*i+(4 if n == 192 else 0)] == 0x47
            for i in range(4))), None)
        if not packet:
            raise ValueError('MVC: Kein unterstützter MPEG-Transportstrom.')
        file.seek(0)
        outputs = [p.open('xb') for p in paths]
        states = {pid: {'out': out, 'cc': None, 'last': None, 'header': bytearray(), 'need_header': False,
                        'remaining': None, 'active': False} for pid, out in zip(pids, outputs)}
        total = 0
        try:
            while True:
                if cancel and cancel.is_set():
                    raise Cancelled()
                block = file.read(packet*4096)
                if not block:
                    break
                if len(block) % packet:
                    if not sample:
                        raise ValueError('MVC: Transportstrom ist abgeschnitten.')
                    block = block[:len(block)//packet*packet]
                for offset in range(0, len(block), packet):
                    t = block[offset+(4 if packet == 192 else 0):offset+(4 if packet == 192 else 0)+188]
                    if t[0] != 0x47:
                        raise ValueError('MVC: Transportstrom-Synchronisation verloren.')
                    pid = ((t[1]&31)<<8)|t[2]
                    s = states.get(pid)
                    if s is None:
                        continue
                    if t[1]&0x80 or t[3]&0xc0:
                        raise ValueError('MVC: Beschädigter oder verschlüsselter Transportstrom.')
                    adaptation = (t[3]>>4)&3
                    if not adaptation:
                        raise ValueError('MVC: Ungültiger Transportstrom-Paketkopf.')
                    start = 4
                    if adaptation&2:
                        start += 1+t[4]
                        if start > 188:
                            raise ValueError('MVC: Ungültiges Adaptationsfeld.')
                    if not adaptation&1 or start >= 188:
                        continue
                    cc = t[3]&15
                    if s['cc'] is not None and cc != (s['cc']+1)&15:
                        if cc == s['cc'] and t == s['last']:
                            continue  # exact retransmission, not a second picture
                        raise ValueError('MVC: Paketlücke im Transportstrom.')
                    s['cc'], s['last'] = cc, t
                    data = t[start:]
                    if t[1]&0x40:
                        if s['need_header'] or s['remaining'] not in (None, 0):
                            raise ValueError('MVC: PES-Paket ist unvollständig.')
                        s.update(header=bytearray(), need_header=True, active=True, remaining=None)
                    if not s['active']:
                        continue
                    if s['need_header']:
                        s['header'].extend(data)
                        h = s['header']
                        if len(h) < 9:
                            continue
                        if h[:3] != b'\0\0\1' or h[6]&0xc0 != 0x80:
                            raise ValueError('MVC: Ungültiger PES-Kopf.')
                        length = 9+h[8]
                        if len(h) < length:
                            continue
                        pes_length = int.from_bytes(h[4:6], 'big')
                        if pes_length and pes_length < length-6:
                            raise ValueError('MVC: Ungültige PES-Länge.')
                        s['remaining'] = pes_length-(length-6) if pes_length else None
                        data = bytes(h[length:])
                        s['header'] = bytearray()
                        s['need_header'] = False
                    if s['remaining'] is not None:
                        data = data[:s['remaining']]
                        s['remaining'] -= len(data)
                    s['out'].write(data)
                total += len(block)
                if sample and total >= 32*1024*1024:
                    break
            if not sample and any(s['need_header'] or s['remaining'] not in (None, 0) for s in states.values()):
                raise ValueError('MVC: Letztes PES-Paket ist abgeschnitten.')
        finally:
            for out in outputs:
                out.close()
    if any(not p.stat().st_size for p in paths):
        raise ValueError('MVC: Eine der beiden Videospuren fehlt.')


def compressed_views(tools, source, info, folder, cancel, sample=False):
    from .engine import capture
    desc = info['multiview']
    base, dependent = folder/'base.264', folder/'dependent.mvc'
    if desc.get('pids'):
        demux_ts(source, desc['pids'], (base, dependent), cancel, sample)
        return base, dependent
    args = [str(tools.ffmpeg), '-v', 'error', '-nostdin', '-protocol_whitelist', 'file,pipe', '-i', str(source)]
    if sample:
        args += ['-t', '2']
    capture(args+['-map', '0:'+str(desc['source_index']), '-c', 'copy', '-an', '-f', 'h264', str(base)], cancel)
    return base, None


def frim_args(base, dependent):
    from .bd3d_export import BdTools
    bd = BdTools.find()
    args = [str(bd.decoder), '-sw', '-i:mvc', str(base)]
    if dependent:
        args.append(str(dependent))
    return bd, args


def check_decoder(process, cancel):
    if not process:
        return
    from .engine import Cancelled
    while process.poll() is None:
        if cancel and cancel.wait(.1):
            raise Cancelled()
    if process.returncode:
        raise ValueError('MVC: Dekodierung fehlgeschlagen · '+'\n'.join(process.mvc_errors))


def dual_source(info, videos):
    """Two independent streams form a pair only by an explicit input choice."""
    from .engine import color_spec
    first,second=videos
    geometry=lambda v:(v['width'],v['height'],v.get('sample_aspect_ratio','1:1'))
    if geometry(first)!=geometry(second):
        raise ValueError('Dual: Beide Halbbilder benötigen gleiche Auflösung und gleiches Pixelseitenverhältnis.')
    def eye(video):
        title=str(video.get('tags',{}).get('title','')).strip().casefold()
        return 'left' if title in {'left','l','links','linkes halbbild'} else 'right' if title in {'right','r','rechts','rechtes halbbild'} else None
    eyes=[eye(v) for v in videos]
    if eyes[0] and eyes[0]==eyes[1]:
        raise ValueError('Dual: Beide Videospuren sind demselben Halbbild zugeordnet.')
    if eyes[0]=='right' or eyes[1]=='left':
        videos=videos[::-1]
    for video in videos:
        color_spec(video)  # The existing SDR policy also applies to the second track.
        if any(s.get('side_data_type') in {'Display Matrix','Spherical Mapping'} for s in video.get('side_data_list',[])):
            raise ValueError('Gedrehte oder VR-projizierte Quelle: In dieser Version bitte vorher als normales SBS/OU vorbereiten.')
    info['multiview']={'kind':'dual','source_index':videos[0]['index'],'videos':deepcopy(videos)}
    virtual=deepcopy(videos[0])
    virtual.update(width=virtual['width']*2,pix_fmt='gbrp16le',color_space='gbr',
                   color_primaries='bt709',color_transfer='iec61966-2-1',color_range='pc')
    virtual['side_data_list']=[]
    info['video']=virtual
    return info


def inspect_source(tools, source, cancel=None, explicit='auto', phase=None):
    from .engine import capture
    from .mvc import annex_nals
    with tempfile.TemporaryDirectory(prefix='transcora-input-') as tmp:
        folder = Path(tmp)
        if phase:
            phase('Blu-ray-Playlist prüfen' if source.suffix.lower() == '.iso' else 'Video und Tonspuren analysieren')
        disc = iso_film(source) if source.suffix.lower() == '.iso' else None
        actual = source
        if disc:
            if phase:
                phase('Blu-ray-Filmdatei für die Prüfung lesen')
            actual = folder/'sample.ssif'
            iso_extract(source, disc, actual, cancel, sample=True)
        info, videos = raw_probe(tools, actual, cancel)
        valid = [v for v in videos if v.get('width') and v.get('height')]
        if len(valid) == 2:
            if explicit not in {'auto', 'dual'}:
                raise ValueError('Zwei eigenständige Videospuren: Dual als Quelllayout wählen.')
            if explicit == 'auto' and not re.search(r'-dual$', source.stem, re.I):
                raise ValueError('Zwei eigenständige Videospuren: Für ein L/R-Paar Dual als Quelllayout wählen.')
            return dual_source(info, valid)
        if len(valid) != 1:
            raise ValueError('Mehrere unabhängige Videospuren oder keine gültige Videoauflösung.')
        video = valid[0]
        info['video'] = video
        desc = None
        ids = str(video.get('view_ids_available', '')).split(',')
        positions = str(video.get('view_pos_available', '')).split(',')
        if video.get('codec_name') == 'hevc' and len(ids) > 1:
            if len(ids) != 2 or len(positions) != 2 or set(positions) != {'1', '2'}:
                raise ValueError('MV-HEVC: Zwei eindeutig als links/rechts gekennzeichnete Halbbilder sind erforderlich.')
            desc = {'kind': 'mvhevc', 'source_index': video['index']}
        elif video.get('codec_name') == 'h264':
            if phase:
                phase('MVC-Kennzeichnung der Quelle prüfen')
            if len(videos) > 1:
                if len(videos) != 2 or any(v.get('codec_name') != 'h264' for v in videos):
                    raise ValueError('MVC: Keine eindeutige AVC/MVC-Spurkombination.')
                other = next(v for v in videos if v is not video)
                desc = {'kind': 'mvc', 'source_index': video['index'],
                        'pids': [int(video['id'], 0), int(other['id'], 0)]}
            else:
                desc = {'kind': 'mvc', 'source_index': video['index']}
            info['multiview'] = desc
            base, dep = compressed_views(tools, actual, info, folder, cancel, sample=True)
            paths = [p for p in (base, dep) if p]
            kinds = set()
            for p in paths:
                with p.open('rb') as stream:
                    for _, nal in annex_nals(stream):
                        if nal:
                            kinds.add(nal[0]&31)
            if not {15, 20} <= kinds:
                if len(videos) > 1 or disc or explicit == 'mvc' or kinds & {15, 20}:
                    raise ValueError('MVC: Vollständiges Basis- und Zusatzhalbbild fehlen.')
                desc = None
                info.pop('multiview', None)
            else:
                try:
                    rate = Fraction(video['avg_frame_rate'])
                    if rate <= 0:
                        raise ValueError
                except (KeyError, ValueError, ZeroDivisionError):
                    raise ValueError('MVC: Verlässliche Quellframerate fehlt.') from None
                try:
                    if phase:
                        phase('MVC-Decoder an beiden Halbbildern testen')
                    tested = json.loads(capture([str(decoder()), str(base), str(dep) if dep else '-',
                        str(rate.numerator), str(rate.denominator), '0', '0', '1'], cancel))
                    desc['decoder'] = 'edge264-mvc'
                except ValueError as error:
                    if os.name != 'nt' or 'unsupported' not in str(error).lower():
                        raise
                    bd, args = frim_args(base, dep)
                    left, right = folder/'left.yuv', folder/'right.yuv'
                    # A successful full stereo sample, not a duplicated base view.
                    capture(args+['-o', str(left), str(right)], cancel)
                    frame_bytes = video['width']*video['height']*3//2
                    if not left.is_file() or not right.is_file() or not left.stat().st_size or (
                            left.stat().st_size != right.stat().st_size or left.stat().st_size % frame_bytes):
                        raise ValueError('FRIM: Keine vollständige dekodierte Stereobildfolge.')
                    tested = {'mvc': True, 'width': video['width']*2, 'height': video['height']}
                    desc['decoder'] = 'frim'
                if not tested.get('mvc') or (tested['width'], tested['height']) != (video['width']*2, video['height']):
                    raise ValueError('MVC: Decoder-Geometrie stimmt nicht mit der Quelle überein.')
        if explicit in {'mvc', 'mvhevc', 'dual'} and (not desc or desc['kind'] != explicit):
            raise ValueError('Die Quelle enthält nicht das gewählte Multiview-Format.')
        if len(videos) > 1 and not desc:
            raise ValueError('Mehrere unabhängige Videospuren sind noch nicht freigegeben.')
        if desc:
            info['multiview'] = desc
            if disc:
                desc.update(disc)
                # Sample duration is not the film duration.
                info['format']['duration'] = str((disc['out']-disc['in'])/45000)
                video['duration'] = info['format']['duration']
            desc['original_video'] = deepcopy(video)
            video['width'] *= 2
            if desc['kind'] == 'mvc':
                video['index'] = 0
                video['pix_fmt'] = 'yuv420p'
            video['side_data_list'] = [s for s in video.get('side_data_list', [])
                if s.get('side_data_type') != 'Stereo 3D' and not (
                    s.get('side_data_type') == 'Spherical Mapping' and s.get('projection') == 'rectilinear')]
        return info


def graph_prefix(info, graph, options=None):
    desc = info.get('multiview')
    if desc and desc['kind'] == 'dual':
        from .engine import color_spec
        from .video import requested_rate, rate_filters, deinterlace
        rate = requested_rate(options) if options else None
        prefix = []
        for side,video in zip(('left','right'),desc['videos']):
            colors,_=color_spec(video)
            from .sdr_color import rgb_input
            rgb = rgb_input(colors) + ","
            # Convert clocks while frame durations still belong to each decoded track.
            # Older hstack versions discard EOF duration needed by a following fps filter.
            timing = dict(video, _start_offset=info['video'].get('_start_offset', 0))
            conversion = (','+deinterlace(video)+','.join(rate_filters(timing, rate))) if rate else ''
            prefix.append(f"[0:{video['index']}]" + rgb +
                          f"settb=expr=1/1000000,showinfo@mv_{side}=checksum=0"+conversion+f"[d{side}]")
        prefix.append('[dleft][dright]hstack=inputs=2[stereo]')
        return ';'.join(prefix)+';'+graph.replace(f"[0:{info['video']['index']}]",'[stereo]')
    if not desc or desc['kind'] != 'mvhevc':
        return graph
    index = desc['source_index']
    prefix = (f'[0:{index}:vpos:left]showinfo@mv_left=checksum=0[ml];'
              f'[0:{index}:vpos:right]showinfo@mv_right=checksum=0[mr];'
              '[ml][mr]hstack=inputs=2:shortest=1[stereo];')
    return prefix+graph.replace(f'[0:{index}]', '[stereo]', 1)


class PairClock:
    def __init__(self):
        self.queues = {'left': deque(), 'right': deque()}
        self.count = 0

    def line(self, line):
        side = next((s for s in self.queues if 'showinfo@mv_'+s in line), None)
        if not side:
            return False
        if re.search(r'\bn:\s*\d+', line):
            match = re.search(r'\bpts:\s*(-?\d+)\s+pts_time:', line)
            if not match:
                raise ValueError('MV-HEVC: Fehlende Bildzeit eines Halbbildes.')
            self.queues[side].append(int(match[1]))
            while all(self.queues.values()):
                if self.queues['left'].popleft() != self.queues['right'].popleft():
                    raise ValueError('MV-HEVC: Halbbilder sind zeitlich nicht synchron.')
                self.count += 1
            if len(self.queues[side]) > 512:
                raise ValueError('MV-HEVC: Ein Halbbild fehlt oder bleibt zurück.')
        return True

    def finish(self, expected=None):
        if not self.count or any(self.queues.values()) or (expected and self.count != expected):
            raise ValueError('MV-HEVC: Unvollständige Stereobildfolge.')


def input_args(plan, copyts=False, seconds=None):
    runtime = plan.info.get('runtime_input')
    if runtime:
        stamp = float(plan.info['multiview']['original_video'].get('start_time') or 0) if copyts else plan.info['video']['_start_offset']
        args = ['-itsoffset', str(stamp), *runtime['format'], '-i', 'pipe:0']
        if seconds is None:
            args += ['-i', str(runtime['source'])]
        return args
    return (['-ss', str(seconds)] if seconds is not None else [])+['-i', str(plan.source)]


@contextmanager
def runtime(tools, plan, cancel, seconds=None, emit=None):
    """Own compressed temporary inputs and decoder lifetime for one operation."""
    desc = plan.info.get('multiview')
    if not desc or desc['kind'] != 'mvc':
        yield plan, None
        return
    from .engine import stop_process, Cancelled
    with tempfile.TemporaryDirectory(prefix='transcora-mvc-') as tmp:
        if emit:
            emit('phase', 'MVC: Komprimierte Eingabespuren vorbereiten')
        folder = Path(tmp)
        source = plan.source
        if desc.get('iso_path'):
            source = folder/'movie.ssif'
            iso_extract(plan.source, desc, source, cancel)
            complete, videos = raw_probe(tools, source, cancel)
            actual_duration = float(complete['format'].get('duration') or 0)
            expected_duration = (desc['out']-desc['in'])/45000
            video_start = float(next(v for v in videos if v.get('width')).get('start_time') or 0)
            if abs(actual_duration-expected_duration) > .1 or abs(video_start-desc['in']/45000) > .1:
                raise ValueError('Die Blu-ray-Playlist verwendet einen Ausschnitt. Clip-Trimmen ist noch nicht freigegeben.')
        base, dep = compressed_views(tools, source, plan.info, folder, cancel)
        info = deepcopy(plan.info)
        rate = Fraction(info['video']['avg_frame_rate'])
        start = int(seconds*float(rate)) if seconds is not None else 0
        args = [str(decoder()), str(base), str(dep) if dep else '-', str(rate.numerator), str(rate.denominator),
                str(start), '1' if seconds is not None else '0', '0']
        environment = None
        fmt = ['-f', 'yuv4mpegpipe']
        if desc['decoder'] == 'frim':
            bd, args = frim_args(base, dep)
            args += ['-sbs', '-o', '-']
            environment = bd.environment
            fmt = ['-f', 'rawvideo', '-pix_fmt', 'yuv420p', '-s', f"{info['video']['width']}x{info['video']['height']}", '-r', str(rate)]
            if seconds is not None:
                info['preview_trim'] = start
        if emit:
            emit('phase', 'MVC: Beide Halbbilder dekodieren · '+desc['decoder'])
        process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=environment, **process_options())
        errors = deque(maxlen=32)
        def stderr():
            for line in iter(process.stderr.readline, b''):
                errors.append(line.decode('utf-8', 'replace').strip())
        reader = threading.Thread(target=stderr, daemon=True)
        reader.start()
        process.mvc_errors = errors
        info['runtime_input'] = {'source': source, 'args': args, 'format': fmt}
        try:
            yield replace(plan, info=info), process
            if cancel and cancel.is_set():
                raise Cancelled()
            # The consumer must finish reading before this check.
            if seconds is None or desc['decoder'] != 'frim':
                check_decoder(process, cancel)
        finally:
            stop_process(process)
            reader.join(timeout=5)
            process.stdout.close()
            process.stderr.close()
