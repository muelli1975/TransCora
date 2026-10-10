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
