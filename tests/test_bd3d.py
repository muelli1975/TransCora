from fractions import Fraction
from pathlib import Path
import json
import shutil
import subprocess
import tempfile
import unittest

from transcora.core.bd3d import prepare, check_cadence, BD_RATE
from transcora.core.toolchain import Toolchain


class BdPreparationTests(unittest.TestCase):
    def test_cadence_accepts_container_rounding_but_rejects_gaps(self):
        check_cadence([0, .042, .083, .125], BD_RATE, '1/1000')
        with self.assertRaises(ValueError):
            check_cadence([0, .042, .125], BD_RATE, '1/1000')
        with self.assertRaises(ValueError):
            check_cadence([0, float('nan')], BD_RATE, '1/1000')

    def test_stereo_preparation_preserves_every_frame_and_retimes_audio(self):
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for layout, size in [('full_sbs', '1280x360'), ('half_sbs', '640x360'),
                                 ('full_ou', '640x720'), ('half_ou', '640x360')]:
                for rate in ('24000/1001', '24'):
                    source = folder/'input.mkv'
                    subprocess.run([str(tools.ffmpeg), '-y', '-v', 'error', '-f', 'lavfi', '-i',
                                    f'testsrc2=s={size}:r={rate}', '-frames:v', '6', '-c:v', 'ffv1',
                                    '-color_primaries', 'bt709', '-color_trc', 'bt709', '-colorspace', 'bt709',
                                    str(source)], check=True)
                    info = json.loads(subprocess.check_output([str(tools.ffprobe), '-v', 'error',
                                                              '-show_streams', '-of', 'json', str(source)]))['streams'][0]
                    config = prepare(info, layout)
                    args = [str(tools.ffmpeg), '-y', '-v', 'error', '-filter_complex_threads', '1',
                            '-i', str(source), '-filter_complex', config.graph]
                    for eye in ('left', 'right'):
                        args += ['-map', f'[{eye}]', '-c:v', 'rawvideo', '-pix_fmt', 'yuv420p',
                                 '-fps_mode', 'passthrough', '-f', 'rawvideo', str(folder/(eye+'.yuv'))]
                    subprocess.run(args, check=True)
                    for eye in ('left', 'right'):
                        self.assertEqual((folder/(eye+'.yuv')).stat().st_size, 1920*1080*3//2*6)
                    self.assertEqual(config.speed, Fraction(1000, 1001) if rate == '24' else 1)
                    if rate == '24':
                        audio = subprocess.check_output([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi',
                            '-i', 'sine=frequency=997:sample_rate=48000:duration=2', '-af',
                            config.audio_filter+',apad,atrim=end_sample=96096', '-ac', '2',
                            '-f', 's24le', '-'])
                        self.assertEqual(len(audio), 96096*2*3)
            invalid = dict(info, r_frame_rate='25/1', avg_frame_rate='25/1')
            with self.assertRaises(ValueError):
                prepare(invalid, 'half_ou')


class MvcMetadataTests(unittest.TestCase):
    def test_stream_rewrite_is_bounded_idempotent_and_preserves_slices(self):
        from transcora.core.mvc import annex_nals, tag_generated_stream, tag_sps
        import io
        sps = bytes.fromhex('27640029ac2d140780227e5c05a8101012000007d200017701c0c0000a67540001db575ef7c140')
        prefix = b'\x00\x00\x00\x01'
        nal = b'\x65' + b'abcdefgh'*200
        original = prefix+sps+prefix+nal+b'\x00\x00\x01'+sps
        for chunk_size in (1, 2, 3, 7, 101):
            self.assertEqual(b''.join(p+n for p, n in annex_nals(io.BytesIO(original), chunk_size=chunk_size)), original)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)/'video.avc'
            path.write_bytes(original)
            self.assertEqual(tag_generated_stream(path), 2)
            expected = prefix+tag_sps(sps)+prefix+nal+b'\x00\x00\x01'+tag_sps(sps)
            self.assertEqual(path.read_bytes(), expected)
            tag_generated_stream(path)
            self.assertEqual(path.read_bytes(), expected)
            path.write_bytes(prefix+nal)
            with self.assertRaises(ValueError):
                tag_generated_stream(path)
            self.assertEqual(path.read_bytes(), prefix+nal)

    def test_generated_sps_and_subset_sps_keep_every_other_bit(self):
        from transcora.core.mvc import tag_sps, signal_bounds
        # Actual parameter sets from the SHA-pinned FRIM 1.31 software proof.
        fixtures = [
            '27640029ac2d140780227e5c05a8101012000007d200017701c0c0000a67540001db575ef7c140',
            '2f8000294b0b4501e0089f97016a040404800001f480005dc0703000022ade8000630f57bdf0554b5ca61522',
        ]
        for fixture in fixtures:
            original = bytes.fromhex(fixture)
            tagged = tag_sps(original)
            before, start, end = signal_bounds(original[1:])
            after, new_start, new_end = signal_bounds(tagged[1:])
            self.assertEqual(before.bits[:start], after.bits[:new_start])
            self.assertEqual(before.bits[end:].rstrip('0'), after.bits[new_end:].rstrip('0'))
            self.assertEqual(after.bits[new_start:new_end], '110101'+'00000001'*3)
            self.assertEqual(tag_sps(tagged), tagged)
        # Coded pictures and view-extension NALs must remain exactly identical.
        for nal in [b'\x65\x00\x00\x03\x00\x12', b'\x74\x81\x23\x45']:
            self.assertEqual(tag_sps(nal), nal)
