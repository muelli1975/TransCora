"""Independent row/frame fixtures exercise the real import and export paths."""
from fractions import Fraction
from pathlib import Path
import tempfile
import threading
import unittest

from transcora.core.engine import capture, execute, metadata_full_half, plan_job, probe
from transcora.core.model import Job, Options
from transcora.core.toolchain import Toolchain
from transcora.core.bd3d import prepare


def raw_halves(frame):
    # Distinct luma, chroma, row detail and pair index; no inverse stereo filter.
    return tuple(b''.join(bytes([base + frame + y % 3]) * 32
                         for base in colours for y in range(16))
                 for colours in ((65, 95, 200), (130, 190, 80)))


def fixture(tools, folder, layout, rate='48', *, swap=False, odd=False, vfr=False):
    data = bytearray()
    for n in range(12):
        halves = raw_halves(n)
        if swap:
            halves = halves[::-1]
        if layout == 'frame_sequential':
            data.extend(b''.join(halves))
        else:
            for plane in range(3):
                for y in range(16):
                    offset = (plane*16+y)*32
                    data.extend(halves[0][offset:offset+32]+halves[1][offset:offset+32])
    if odd:
        data.extend(raw_halves(12)[0])
    raw = folder/'source.yuv'; raw.write_bytes(data)
    marker = 'seq' if layout == 'frame_sequential' else 'rows'
    source = folder/f'source_{marker}_{"rl" if swap else "lr"}.mkv'
    args = [str(tools.ffmpeg), '-v', 'error', '-f', 'rawvideo', '-pixel_format', 'yuv444p',
            '-video_size', '32x16' if marker == 'seq' else '32x32', '-framerate', rate,
            '-i', str(raw), '-f', 'lavfi', '-i', 'sine=frequency=700:sample_rate=48000',
            '-t', str(len(data)/(32*(16 if marker == 'seq' else 32)*3*float(Fraction(rate))) + (.10 if vfr else 0))]
    if vfr:
        args += ['-vf', "setpts=PTS+floor(N/4)*0.02/TB"]
    capture(args + ['-fps_mode', 'passthrough', '-c:v', 'ffv1', '-c:a', 'pcm_s16le',
                    '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
                    '-color_range', 'tv', str(source)])
    return source


class StereoInputTests(unittest.TestCase):
    def test_stereo_metadata_identifies_rows_and_frame_order_without_full_half_guess(self):
        for tag, expected in [('row_interleaved_lr', ('row_interleaved', False)),
                              ('row_interleaved_rl', ('row_interleaved', True)),
                              ('block_lr', ('frame_sequential', False)),
                              ('14', ('frame_sequential', True))]:
            self.assertEqual(metadata_full_half({'tags': {'stereo_mode': tag}}), expected)

    def test_rows_keep_order_geometry_and_temporal_rate_in_video_and_image(self):
        from PIL import Image
        from transcora.core.images import ImageJob, ImageOptions, plans, execute_image
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for swap in (False, True):
                source = fixture(tools, folder, 'row_interleaved', rate='25', swap=swap)
                plan = plan_job(tools, Job(source, Options(target='full_sbs', video_size='original',
                                                          container='mkv', crf=1)), folder/'out', set())
                self.assertEqual(plan.layout, 'row_interleaved')
                self.assertEqual(plan.size, (64, 32))
                self.assertNotIn('bwdif', plan.graph)
                execute(tools, plan, threading.Event(), lambda *a: None, folder/'export.log')
                decoded = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(plan.output),
                                   '-pix_fmt', 'yuv444p', '-f', 'rawvideo', '-'])
                self.assertEqual(len(decoded), 12*64*32*3)
                self.assertLess(decoded[0], decoded[32])
                self.assertEqual(Fraction(probe(tools, plan.output)['video']['avg_frame_rate']), 25)
                picture = folder/f'photo_rows_{"rl" if swap else "lr"}.png'
                image = Image.new('RGB', (32, 32))
                for y in range(32):
                    colour = 'red' if (y % 2 == 0) ^ swap else 'blue'
                    image.paste(colour, (0, y, 32, y+1))
                image.save(picture)
                image_plan = plans([ImageJob(picture, ImageOptions(target='split', format='png', metadata=False))],
                                   folder/'out', threading.Event())[0]
                execute_image(tools, image_plan, threading.Event(), lambda *a: None, folder/'image.log')
                for output, expected in zip(image_plan.outputs, ((255, 0, 0), (0, 0, 255))):
                    with Image.open(output) as half:
                        self.assertEqual(half.size, (32, 32))
                        self.assertEqual(half.getpixel((16, 16)), expected)

    def test_frame_pairs_preserve_duration_audio_and_final_pair_at_multiple_rates(self):
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for rate, swapped, odd in [('48', False, False), ('50', True, False),
                                       ('60000/1001', False, False), ('120', True, True)]:
                folder = root/rate.replace('/', '-'); folder.mkdir()
                source = fixture(tools, folder, 'frame_sequential', rate, swap=swapped, odd=odd)
                plan = plan_job(tools, Job(source, Options(target='full_sbs', video_size='original',
                                                          container='mkv', crf=1)), folder/'out', set())
                self.assertEqual(plan.size, (64, 16))
                execute(tools, plan, threading.Event(), lambda *a: None, folder/'export.log')
                decoded = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(plan.output),
                                   '-pix_fmt', 'yuv444p', '-f', 'rawvideo', '-'])
                self.assertEqual(len(decoded), 12*64*16*3, (rate, odd))
                for n in range(12):
                    self.assertLess(decoded[n*64*16*3], decoded[n*64*16*3+32])
                output = probe(tools, plan.output)
                self.assertAlmostEqual(float(Fraction(output['video']['avg_frame_rate'])),
                                       float(Fraction(rate)/2), delta=.1)
                self.assertAlmostEqual(float(output['format']['duration']), plan.duration,
                                       delta=float(2/Fraction(rate))+.003)
                src_audio = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(source),
                                     '-map', '0:a', '-f', 's16le', '-'])
                out_audio = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(plan.output),
                                     '-map', '0:a', '-f', 's16le', '-'])
                self.assertEqual(src_audio, out_audio)

    def test_pair_conversion_precedes_bd_and_custom_fps_for_vfr_input(self):
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = fixture(tools, folder, 'frame_sequential', '120', vfr=True)
            plan = plan_job(tools, Job(source, Options(target='full_sbs', container='mkv', video_size='original',
                                                      fps_mode='custom', target_fps='25')),
                            folder/'out', set())
            self.assertLess(plan.graph.index('stereo3d='), plan.graph.index('fps=fps=25'))
            execute(tools, plan, threading.Event(), lambda *a: None, folder/'export.log')
            self.assertAlmostEqual(float(probe(tools, plan.output)['format']['duration']), plan.duration, delta=.045)
            for mode in ('1080p', '720p50', '720p5994'):
                preparation = prepare(plan.info['video'], 'frame_sequential', False, mode)
                self.assertLess(preparation.graph.index('stereo3d='), preparation.graph.index('fps=fps='))
                self.assertNotIn('bwdif', preparation.graph)
                packed = folder/f'{mode}.mkv'
                capture([str(tools.ffmpeg), '-v', 'error', '-i', str(source), '-filter_complex',
                         preparation.graph+';[left][right]hstack=inputs=2[checked]', '-map', '[checked]',
                         '-an', '-c:v', 'ffv1', '-frames:v', '2', str(packed)])
                self.assertEqual(probe(tools, packed)['video']['width'], preparation.size[0]*2)
