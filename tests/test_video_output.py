"""Exercise decoded field rate, stereo ordering and selectable export geometry."""
from dataclasses import replace
from fractions import Fraction
from pathlib import Path
import json
import subprocess
import tempfile
import threading
import unittest

from transcora.core.engine import capture, execute, plan_job, probe
from transcora.core.model import Job, Options, BD_BITRATES
from transcora.core.toolchain import Toolchain
from transcora.core.video import output_dimensions, deinterlace
from transcora.core.bd3d import encoder_args


class VideoOutputTests(unittest.TestCase):
    def test_cross_view_full_hd_keeps_circles_round_in_mp4_and_mkv(self):
        import io
        from PIL import Image, ImageDraw
        from transcora.core.engine import metadata_layout, preview
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            image = Image.new('RGB', (5120, 1440))
            draw = ImageDraw.Draw(image)
            for x, colour in ((0, 'red'), (2560, 'blue')):
                draw.rectangle((x, 0, x+2559, 1439), fill=colour)
                draw.ellipse((x+960, 400, x+1600, 1040), fill='white')
            picture = folder/'circles.png'; image.save(picture)
            source = folder/'circles_full_sbs.mkv'
            capture([str(tools.ffmpeg), '-v', 'error', '-y', '-i', str(picture),
                     '-frames:v', '1', '-c:v', 'ffv1', '-pix_fmt', 'gbrp',
                     '-colorspace', 'rgb', '-color_primaries', 'bt709',
                     '-color_trc', 'iec61966-2-1', '-color_range', 'pc', str(source)])
            for container in ('mp4', 'mkv'):
                for mode, expected in (('original', (5120,1440)), ('1080p', (3840,1080)), ('custom', (1920,540))):
                    with self.subTest(container=container, mode=mode):
                        plan = plan_job(tools, Job(source, Options(target='cross_sbs', container=container,
                                            video_size=mode, video_width=1920, video_height=540, crf=18)), folder/'out', set())
                        self.assertEqual(plan.size, expected)
                        execute(tools, plan, threading.Event(), lambda *a:None, folder/'export.log')
                        video = probe(tools, plan.output)['video']
                        self.assertEqual((video['width'], video['height']), expected)
                        self.assertEqual(video['sample_aspect_ratio'], '1:1')
                        self.assertEqual(Fraction(video['display_aspect_ratio'].replace(':','/')), Fraction(32,9))
                        self.assertEqual(metadata_layout(video), ('sbs',True) if container=='mkv' else None)
                        decoded = capture([str(tools.ffmpeg), '-v', 'error', '-i', str(plan.output),
                                           '-frames:v', '1', '-c:v', 'png', '-f', 'image2pipe', '-'])
                        # Check decoded eye shape, rather than only the stored raster.
                        with Image.open(io.BytesIO(decoded)) as frame:
                            eye_width = expected[0]//2
                            for x, blue in ((0, True), (eye_width, False)):
                                eye = frame.crop((x, 0, x+eye_width, expected[1])).convert('RGB')
                                r,g,b = eye.split()
                                white = g.point(lambda value: 255 if value > 220 else 0)
                                box = white.getbbox(); self.assertIsNotNone(box)
                                self.assertAlmostEqual(box[2]-box[0], box[3]-box[1], delta=4)
                                pixel = eye.getpixel((eye_width//8, expected[1]//2))
                                self.assertGreater(pixel[2] if blue else pixel[0], 200)
                        with Image.open(io.BytesIO(preview(tools, plan, threading.Event()))) as frame:
                            self.assertEqual(frame.size, expected)

    def test_abq_image_rows_are_reordered_without_resampling(self):
        from PIL import Image
        from transcora.core.images import ImageOptions, ImageJob, plans, execute_image
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            source = folder/'pattern-abq.png'
            a = Image.new('RGB', (1920, 540)); b = Image.new('RGB', a.size)
            for y in range(540):
                a.paste((y%256, 35, 210), (0,y,1920,y+1))
                b.paste((230, y%256, 15), (0,y,1920,y+1))
            packed = Image.new('RGB', (1920, 1080)); packed.paste(a); packed.paste(b,(0,540)); packed.save(source)
            stride = 1920*3
            for first in ('left', 'right'):
                opts = ImageOptions(target='row_interleaved', row_first=first, format='png', metadata=False)
                plan = plans([ImageJob(source, opts)], folder/'images', threading.Event())[0]
                execute_image(tools, plan, threading.Event(), lambda *a:None, folder/'image.log')
                with Image.open(plan.outputs[0]) as image:
                    self.assertEqual(image.size, (1920,1080))
                    result = image.convert('RGB').tobytes()
                eyes = (a.tobytes(), b.tobytes()) if first=='left' else (b.tobytes(), a.tobytes())
                for y in range(1080):
                    offset = y//2*stride
                    self.assertEqual(result[y*stride:(y+1)*stride], eyes[y%2][offset:offset+stride])

    def test_geometry_and_frame_rate_change_in_one_export(self):
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); source=folder/'red_blue_full_sbs.mkv'
            capture([str(tools.ffmpeg),'-v','error','-y','-f','lavfi','-i',
                     'color=red:s=160x90:r=60:d=0.5','-f','lavfi','-i','color=blue:s=160x90:r=60:d=0.5',
                     '-f','lavfi','-i','sine=r=48000:d=0.5', '-filter_complex','[0:v][1:v]hstack[v]',
                     '-map','[v]','-map','2:a','-c:v','ffv1','-c:a','aac',
                     '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv',str(source)])
            source_audio = capture([str(tools.ffmpeg),'-v','error','-i',str(source),'-map','0:a:0','-f','s16le','-'])
            for target, container, first, mode in [('full_sbs','mp4','left','source'),
                    ('full_sbs','mp4','left','custom'), ('row_interleaved','mp4','left','custom'),
                    ('row_interleaved','mkv','left','custom'), ('row_interleaved','mkv','right','custom')]:
                with self.subTest(target=target, container=container, first=first, mode=mode):
                    opts=Options(target=target,container=container,row_first=first,screen_width=320,screen_height=180,
                                 video_size='custom',video_width=320,video_height=180,fps_mode=mode,target_fps='30')
                    plan=plan_job(tools,Job(source,opts),folder/'out',set())
                    execute(tools,plan,threading.Event(),lambda *a:None,folder/'video.log')
                    video=probe(tools,plan.output)['video']
                    rate=30 if mode=='custom' else 60
                    if mode == 'custom':
                        self.assertEqual(Fraction(video['avg_frame_rate']),rate)
                    else:
                        # Source MKV timestamps have millisecond quantisation;
                        # preserving them can slightly alter MP4's avg rate.
                        self.assertAlmostEqual(float(Fraction(video['avg_frame_rate'])), rate, delta=.25)
                        stamps=lambda path: [f['best_effort_timestamp_time'] for f in json.loads(capture([
                            str(tools.ffprobe),'-v','error','-select_streams','v:0','-show_frames',
                            '-show_entries','frame=best_effort_timestamp_time','-of','json',str(path)]))['frames']]
                        before,after=stamps(source),stamps(plan.output)
                        self.assertEqual(len(before),len(after))
                        source_origin=float(probe(tools,source).get('format',{}).get('start_time',0))
                        output_origin=float(probe(tools,plan.output).get('format',{}).get('start_time',0))
                        for a,b in zip(before,after):
                            self.assertAlmostEqual(float(a)-source_origin,float(b)-output_origin,delta=.001)
                    self.assertEqual(video['field_order'],'progressive')
                    audio=capture([str(tools.ffmpeg),'-v','error','-i',str(plan.output),'-map','0:a:0','-f','s16le','-'])
                    self.assertEqual(audio,source_audio)
                    if target=='row_interleaved':
                        self.assertEqual((video['width'],video['height']),(320,180))
                        self.assertEqual(video['pix_fmt'],'yuv444p')
                        picture=capture([str(tools.ffmpeg),'-v','error','-i',str(plan.output),'-frames:v','1',
                                         '-pix_fmt','rgb24','-f','rawvideo','-'])
                        # Check encoded colours on consecutive physical rows.
                        for y in range(20,30):
                            rgb=picture[(y*320+160)*3:(y*320+160)*3+3]
                            red=(y%2==0) == (first=='left')
                            self.assertGreater(rgb[0] if red else rgb[2], (rgb[2] if red else rgb[0])+100)

    def test_legacy_frame_rate_lists_and_source_default(self):
        self.assertEqual(Options.from_dict({'target':'framerate','target_fps':'25'}).fps_mode,'custom')
        self.assertEqual(Options().fps_mode,'source')
        for changes in ({'screen_width':1919}, {'row_first':'auto'}, {'fps_mode':'guess'}):
            with self.assertRaises(ValueError): replace(Options(), **changes).validate()

    def test_geometry_and_bitrate_limits(self):
        self.assertEqual(output_dimensions(Options(target='cross_sbs',video_size='1080p'),1440,1080),(1920,1080))
        self.assertEqual(output_dimensions(Options(video_size='2160p'), 1920, 1080), (3840, 2160))
        self.assertEqual(output_dimensions(Options(target='full_sbs', video_size='2160p'), 1920, 1080), (3840, 2160))
        self.assertEqual(output_dimensions(Options(target='full_sbs'), 960, 540), (960, 540))
        self.assertEqual(output_dimensions(Options(target='full_sbs', video_size='1080p'), 1440, 1080), (1440, 1080))
        for value in BD_BITRATES:
            args=encoder_args(Path('encoder'), Path('l'), Path('r'), Path('base'), Path('dep'), value)
            self.assertEqual(args[args.index('-vbr')+1:args.index('-vbr')+3], [str(value*1000)]*2)
        for changes in ({'bd_bitrate_mbps': 45}, {'video_width': 1919}, {'video_height': 0}):
            with self.assertRaises(ValueError): replace(Options(), **changes).validate()
        self.assertIn('parity=tff', deinterlace({'field_order':'bt'}))
        self.assertIn('parity=bff', deinterlace({'field_order':'tb'}))

    def test_interlaced_stereo_keeps_field_rate_and_audio(self):
        tools=Toolchain.find()
        for order in ('top', 'bottom'):
            with self.subTest(order=order), tempfile.TemporaryDirectory() as tmp:
                folder=Path(tmp)
                source=folder/'fields_full_ou.mp4'
                capture([str(tools.ffmpeg), '-v', 'error', '-y', '-f', 'lavfi', '-i',
                         'testsrc2=s=320x360:r=50:d=0.32', '-f', 'lavfi', '-i',
                         'sine=r=48000:d=0.32', '-vf', 'tinterlace=mode=interleave_'+order,
                         '-c:v', 'libx264', '-preset', 'ultrafast', '-flags', '+ildct+ilme',
                         '-x264-params', 'tff=1' if order=='top' else 'bff=1',
                         '-pix_fmt', 'yuv420p', '-colorspace', 'bt709', '-color_primaries', 'bt709',
                         '-color_trc', 'bt709', '-color_range', 'tv', '-c:a', 'aac', str(source)])
                self.assertIn(probe(tools, source)['video'].get('field_order'), {'tt','bb','bt','tb'})
                for target in ('full_sbs', 'framerate'):
                    opts=Options(target=target, container='mkv', target_fps='50')
                    plan=plan_job(tools, Job(source, opts), folder, set())
                    execute(tools, plan, threading.Event(), lambda *a:None, folder/(target+'.log'))
                    info=probe(tools, plan.output)
                    self.assertEqual(Fraction(info['video']['avg_frame_rate']), 50)
                    self.assertEqual(info['video']['field_order'], 'progressive')
                    self.assertEqual([s['codec_name'] for s in info['streams'] if s['codec_type']=='audio'], ['aac'])
                    frames=json.loads(capture([str(tools.ffprobe), '-v','error','-select_streams','v:0',
                        '-show_frames','-show_entries','frame=best_effort_timestamp_time,interlaced_frame',
                        '-of','json',str(plan.output)]))['frames']
                    self.assertEqual(len(frames),16)
                    self.assertTrue(all(f['interlaced_frame']==0 for f in frames))
                    self.assertAlmostEqual(float(frames[-1]['best_effort_timestamp_time'])-
                                           float(frames[0]['best_effort_timestamp_time']), .3, places=3)

    def test_uhd_half_sbs_and_custom_full_geometry(self):
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); source=folder/'stereo_full_sbs.mkv'
            capture([str(tools.ffmpeg),'-v','error','-y','-f','lavfi','-i',
                     'testsrc2=s=640x180:r=24','-frames:v','1','-c:v','ffv1','-pix_fmt','yuv420p',
                     '-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-color_range','tv',str(source)])
            for opts, expected in [
                (Options(video_size='2160p',container='mkv'),(3840,2160)),
                (Options(target='cross_sbs',container='mkv',video_size='custom',video_width=1280,video_height=360),(1280,360))]:
                plan=plan_job(tools,Job(source,opts),folder,set())
                self.assertEqual(plan.size,expected)
                execute(tools,plan,threading.Event(),lambda *a:None,folder/(opts.target+'.log'))
                video=probe(tools,plan.output)['video']
                self.assertEqual((video['width'],video['height']),expected)

    def test_cross_view_mp4_has_right_eye_first_without_false_stereo_tag(self):
        import io
        from PIL import Image, ImageStat
        from transcora.core.engine import preview, metadata_layout
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp); source=folder/'red_blue_full_sbs.mkv'
            capture([str(tools.ffmpeg),'-v','error','-y','-f','lavfi','-i',
                     'color=red:s=160x90:r=24','-f','lavfi','-i','color=blue:s=160x90:r=24',
                     '-filter_complex','[0:v][1:v]hstack[v]','-map','[v]','-frames:v','2',
                     '-c:v','ffv1','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',
                     '-color_range','tv',str(source)])
            plan=plan_job(tools,Job(source,Options(target='cross_sbs',container='mp4')),folder,set())
            execute(tools,plan,threading.Event(),lambda *a:None,folder/'cross.log')
            self.assertTrue(plan.output.name.endswith('-rl.mp4'))
            self.assertIsNone(metadata_layout(probe(tools,plan.output)['video']))
            picture=capture([str(tools.ffmpeg),'-v','error','-i',str(plan.output),'-frames:v','1',
                             '-f','image2pipe','-c:v','png','-'])
            with Image.open(io.BytesIO(picture)) as image:
                a=ImageStat.Stat(image.crop((10,10,100,70))).mean
                b=ImageStat.Stat(image.crop((170,10,260,70))).mean
                self.assertGreater(a[2],a[0]+100)
                self.assertGreater(b[0],b[2]+100)

