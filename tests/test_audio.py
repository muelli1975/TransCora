from dataclasses import replace
from pathlib import Path
import tempfile
import threading
import unittest

from transcora.core import audio
from transcora.core.engine import capture, plan_job, execute, probe
from transcora.core.model import Options, Job
from transcora.core.toolchain import Toolchain


class AudioTests(unittest.TestCase):
    def test_selection_validates_numbers_and_codec_copy_is_default(self):
        self.assertEqual(audio.selection_numbers('3, 1, 2-4'), [1, 2, 3, 4])
        for value in ('', '0', '4-2', '1;2', '1001', '1,'):
            with self.assertRaises(ValueError):
                audio.selection_numbers(value)
        track = dict(index=2, codec_type='audio', codec_name='aac', channels=6)
        info = {'streams': [track]}
        args = audio.arguments(info, Options(), 1)
        self.assertIn('1:2', args)
        self.assertEqual(args[args.index('-c:a:0')+1], 'copy')
        self.assertNotIn('-ac:a:0', args)
        with self.assertRaises(ValueError):
            audio.selected(info, Options(audio_tracks='selected', audio_selection='2'))

    def test_real_track_selection_copy_aac_stereo_and_no_audio(self):
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder/'source.mkv'
            capture([str(tools.ffmpeg), '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=s=128x64:r=30:d=1',
                '-f', 'lavfi', '-i', 'sine=frequency=997:duration=1', '-f', 'lavfi', '-i',
                'aevalsrc=0.1*sin(2*PI*173*t)|0.1*sin(2*PI*347*t)|0.1*sin(2*PI*521*t)|0.1*sin(2*PI*691*t)|0.1*sin(2*PI*863*t)|0.1*sin(2*PI*1039*t):s=48000:c=5.1:d=1',
                '-map', '0:v', '-map', '1:a', '-map', '2:a', '-c:v', 'ffv1', '-c:a', 'flac',
                '-colorspace', 'bt709', '-color_trc', 'bt709', '-color_primaries', 'bt709', '-color_range', 'tv',
                '-metadata:s:a:0', 'language=deu', '-metadata:s:a:1', 'language=eng',
                '-metadata:s:a:1', 'title=Surround', str(source)])
            original = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(source), '-map', '0:a:1', '-f', 's16le', '-'])
            defaults = Options(target='framerate', fps_mode='custom', layout='mono', target_fps='30', container='mkv')
            cases = [replace(defaults, audio_tracks='selected', audio_selection='2'),
                     replace(defaults, container='mp4', audio_format='aac'),
                     replace(defaults, container='mp4', audio_tracks='selected', audio_selection='2', audio_channels='stereo'),
                     replace(defaults, container='mp4', audio_tracks='none')]
            for number, options in enumerate(cases):
                plan = plan_job(tools, Job(source, options), folder/str(number), set())
                execute(tools, plan, threading.Event(), lambda *_: None, folder/f'{number}.log')
                tracks = audio.sources(probe(tools, plan.output))
                if number == 0:
                    self.assertEqual([s['codec_name'] for s in tracks], ['flac'])
                    self.assertEqual(tracks[0]['channels'], 6)
                    actual = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(plan.output), '-map', '0:a:0', '-f', 's16le', '-'])
                    self.assertEqual(original, actual)
                    self.assertEqual(tracks[0]['tags']['language'], 'eng')
                    self.assertEqual(tracks[0]['tags']['title'], 'Surround')
                elif number == 1:
                    self.assertEqual([s['codec_name'] for s in tracks], ['aac', 'aac'])
                    self.assertEqual([s['channels'] for s in tracks], [1, 6])
                elif number == 2:
                    self.assertEqual(len(tracks), 1)
                    self.assertEqual(tracks[0]['channels'], 2)
                    self.assertEqual(tracks[0]['codec_name'], 'aac')
                else:
                    self.assertFalse(tracks)


if __name__ == '__main__':
    unittest.main()
