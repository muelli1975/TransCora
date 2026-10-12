"""Real MVC export of valid jitter/VFR, including audio and nonzero source PTS."""
from pathlib import Path
import hashlib
import json
import re
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from transcora.core.bd3d import BD_RATE
from transcora.core.bd3d_export import BdTools, verify_mux
from transcora.core.mvc import coded_fingerprint
from transcora.core.engine import capture, execute, plan_job
from transcora.core.model import Job, Options
from transcora.core.toolchain import Toolchain
from transcora.core.udf import Disc


def main():
    out = ROOT/'output/bd3d-timing'
    out.mkdir(parents=True, exist_ok=True)
    tools = Toolchain.find()
    BdTools.find()
    capabilities = tools.inspect()
    report = {}
    for name, container, timing, duration in [
            ('jitter', 'm2ts', '7/TB+(N/25+0.003*mod(N,2))/TB', .963),
            ('native-jitter', 'm2ts', '7/TB+(N*1001/24000+0.003*mod(N,2))/TB', 1.004),
            ('variable', 'iso', '7/TB+(N+floor(N/6))/25/TB', 1.08)]:
        source = out/(name+'_full_sbs.mp4')
        capture([str(tools.ffmpeg), '-y', '-v', 'error', '-f', 'lavfi', '-i',
            'nullsrc=s=1280x360:r='+('24000/1001' if name == 'native-jitter' else '25'), '-f', 'lavfi', '-i',
            f'sine=frequency=997:sample_rate=48000:duration={duration}', '-filter_complex',
            "[0:v]geq=lum='if(lt(X,W/2),48+mod(N,5)*10,160-mod(N,5)*10)':cb=128:cr=128,"
            f"settb=1/1000000,setpts='{timing}'[v];[1:a]asetpts=PTS+7/TB[a]",
            '-map', '[v]', '-map', '[a]', '-frames:v', '24', '-fps_mode', 'passthrough',
            '-c:v', 'libx264', '-crf', '0', '-preset', 'ultrafast', '-pix_fmt', 'yuv420p',
            '-video_track_timescale', '1000000', '-colorspace', 'bt709', '-color_primaries', 'bt709',
            '-color_trc', 'bt709', '-color_range', 'tv', '-c:a', 'aac', '-b:a', '192k', str(source)], timeout=120)
        plan = plan_job(tools, Job(source, Options(target='bd3d', container=container)), out,
                        set(), capabilities=capabilities)
        events = []
        log = out/(name+'.log')
        execute(tools, plan, threading.Event(), lambda k, v: events.append((k, v)), log)
        packed = plan.output
        if container == 'iso':
            packed = out/'variable.ssif'
            with Disc(plan.output) as disc:
                disc.extract('BDMV/STREAM/SSIF/00000.ssif', packed)
        log_text = log.read_text(encoding='utf-8')
        assert log_text.count('-i:mvc') == 0  # no mandatory decode in user exports
        frame_count = int(re.search(r'COMPLETED BD3D frames=(\d+)', log_text)[1])
        actual_duration = frame_count/float(BD_RATE)
        # Independent source timeline, not the generated preparation graph.
        times = json.loads(capture([str(tools.ffprobe), '-v', 'error', '-select_streams', 'v:0',
            '-show_frames', '-show_entries', 'frame=best_effort_timestamp_time,duration_time,pkt_duration_time',
            '-of', 'json', str(source)]))['frames']
        origin = float(times[0]['best_effort_timestamp_time'])
        end = float(times[-1]['best_effort_timestamp_time']) + float(
            times[-1].get('duration_time') or times[-1].get('pkt_duration_time') or .04)
        assert abs(actual_duration-(end-origin)) <= 1/float(BD_RATE), (actual_duration, end-origin)
        # Full structural/decoded validation belongs to this development test.
        import tempfile
        with tempfile.TemporaryDirectory(dir=out) as tmp:
            folder=Path(tmp); demux=folder/'tracks'; demux.mkdir()
            meta=folder/'tracks.meta'
            meta.write_text(f'MUXOPT --demux\nV_MPEG4/ISO/AVC, "{packed}", track=4113\nV_MPEG4/ISO/MVC, "{packed}", track=4114\n')
            capture([str(bd.muxer),str(meta),str(demux)],timeout=120)
            base=next(demux.glob('*.264')); dep=next(demux.glob('*.mvc'))
            from transcora.core.audio import selected
            with (out/(name+'-validation.log')).open('w') as validation:
                verify_mux(tools,bd,plan,packed,base,dep,frame_count,
                           [coded_fingerprint(base),coded_fingerprint(dep)],
                           selected(plan.info,plan.options),threading.Event(),validation,folder)
        # Preserve the original A/V start offset and every decoded audio sample.
        samples = round(actual_duration*48000)
        expected = capture([str(tools.ffmpeg), '-v', 'error', '-copyts', '-i', str(source), '-map', '0:a:0',
            '-af', f'asetpts=PTS-{origin}/TB,aresample=48000:async=1:first_pts=0,apad,atrim=end_sample={samples}',
            '-c:a', 'pcm_s24le', '-f', 's24le', '-'], timeout=120)
        actual = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(packed), '-map', '0:a:0',
            '-c:a', 'pcm_s24le', '-f', 's24le', '-'], timeout=120)
        assert actual.startswith(expected)
        assert len(actual)-len(expected) < 240*3 and not any(actual[len(expected):])
        report[name] = dict(frames=frame_count, duration=actual_duration,
                            source_span=end-origin, audio_sha256=hashlib.sha256(expected).hexdigest())
        source.unlink()
        if packed != plan.output:
            packed.unlink()
    (out/'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
