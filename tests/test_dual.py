"""Dual tracks keep both independently marked views, clocks and selected audio."""
from dataclasses import replace
from pathlib import Path
from fractions import Fraction
import io
import json
import tempfile
import threading
import unittest
from PIL import Image
from transcora.core.engine import capture, execute, plan_job, preview
from transcora.core.model import Job, Options
from transcora.core.toolchain import Toolchain
from transcora.core.naming import filename_layout, suffix_choices
from transcora.core.multiview import dual_source


class DualTests(unittest.TestCase):
    def fixture(self,folder,tools,shift=False,rate='25'):
        picture=folder/'stereo.png'
        image=Image.new('RGB',(128,32),'red');image.paste('blue',(64,0,128,32));image.save(picture)
        source=folder/('shift-dual.mkv' if shift else 'source-dual.mkv')
        graph='[0:v]split[a][b];[a]crop=64:32:0:0[left];[b]crop=64:32:64:0'
        graph+=',setpts=PTS+0.12/TB' if shift else ''
        graph+='[right]'
        capture([str(tools.ffmpeg),'-v','error','-loop','1','-framerate',rate,'-i',str(picture),
                 '-f','lavfi','-i','sine=frequency=700:sample_rate=48000:duration=0.48',
                 '-filter_complex',graph,'-map','[left]','-map','[right]','-map','1:a',
                 '-t','0.48','-c:v','ffv1','-pix_fmt','gbrp','-colorspace','rgb',
                 '-color_primaries','bt709','-color_trc','iec61966-2-1','-color_range','pc',
                 '-metadata:s:v:0','title=Left','-metadata:s:v:1','title=Right','-c:a','pcm_s16le',str(source)])
        return source

    def test_dual_names_and_geometry_do_not_guess_unrelated_tracks(self):
        self.assertEqual(filename_layout('Film-dual'),('dual',False))
        self.assertEqual(suffix_choices(Options(target='dual'),''),['-dual','Keiner'])
        video=dict(index=0,width=64,height=32,pix_fmt='yuv420p',sample_aspect_ratio='1:1')
        with self.assertRaisesRegex(ValueError,'Auflösung'):
            dual_source({'streams':[]},[video,dict(video,index=1,width=128)])

    def test_mp4_and_mkv_have_two_correct_views_and_selected_audio(self):
        tools=Toolchain.find(); cancel=threading.Event()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=self.fixture(folder,tools)
            for container,swap,blue in [('mp4',False,False),('mkv',True,True)]:
                options=Options(target='dual',container=container,swap=swap,
                                audio_format='aac' if container=='mp4' else 'copy',
                                fps_mode='custom',target_fps='25',video_size='custom',video_width=64,video_height=32)
                plan=plan_job(tools,Job(source,options),folder/'out',set())
                self.assertEqual(plan.info['multiview']['kind'],'dual')
                self.assertEqual(plan.size,(64,32)); self.assertTrue(plan.output.name.endswith('-dual.'+container))
                execute(tools,plan,cancel,lambda *args:None,folder/'export.log')
                report=json.loads(capture([str(tools.ffprobe),'-v','error','-count_frames','-show_streams','-of','json',str(plan.output)]))
                videos=[s for s in report['streams'] if s['codec_type']=='video']
                self.assertEqual(len(videos),2)
                self.assertEqual([int(v['nb_read_frames']) for v in videos],[12,12])
                self.assertTrue(all(Fraction(v['avg_frame_rate'])==25 for v in videos))
                for index in (0,1):
                    png=capture([str(tools.ffmpeg),'-v','error','-i',str(plan.output),'-map',f'0:v:{index}',
                                 '-frames:v','1','-c:v','png','-f','image2pipe','-'])
                    with Image.open(io.BytesIO(png)) as image:
                        r,_,b=image.convert('RGB').getpixel((32,16))
                        expect_blue=blue if index==0 else not blue
                        self.assertGreater(b if expect_blue else r,180)
                        self.assertLess(r if expect_blue else b,50)
                self.assertEqual(len([s for s in report['streams'] if s['codec_type']=='audio']),1)
                imported=plan_job(tools,Job(plan.output,Options(target='mono',container='mkv')),folder/'again',set())
                self.assertEqual(imported.info['multiview']['kind'],'dual')

    def test_preview_views_are_stereoscopic_and_do_not_change_output(self):
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=self.fixture(folder,tools)
            options=Options(target='dual',container='mkv',video_size='custom',video_width=64,video_height=32)
            plan=plan_job(tools,Job(source,options),folder/'out',set())
            for view,size,blue in [('parallel',(128,32),False),('cross',(128,32),True),('anaglyph',(64,32),None)]:
                png=preview(tools,plan,threading.Event(),view=view)
                with Image.open(io.BytesIO(png)) as image:
                    self.assertEqual(image.size,size)
                    if blue is not None:
                        r,_,b=image.convert('RGB').getpixel((16,16))
                        self.assertGreater(b if blue else r,180)
            self.assertEqual(plan.options,options)

    def test_unsynchronised_tracks_and_cancellation_do_not_publish_outputs(self):
        from transcora.core.engine import Cancelled
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            shifted=self.fixture(folder,tools,shift=True)
            options=Options(target='dual',container='mkv')
            plan=plan_job(tools,Job(shifted,options),folder/'out',set())
            with self.assertRaisesRegex(ValueError,'synchron'):
                execute(tools,plan,threading.Event(),lambda *args:None,folder/'shift.log')
            self.assertFalse(plan.output.exists())
            source=self.fixture(folder,tools)
            plan=plan_job(tools,Job(source,options),folder/'out',set())
            cancel=threading.Event()
            def stop(kind,data):
                if kind=='progress': cancel.set()
            with self.assertRaises(Cancelled):
                execute(tools,plan,cancel,stop,folder/'cancel.log')
            self.assertFalse(plan.output.exists())

    def test_explicit_dual_and_track_titles_control_assignment(self):
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=self.fixture(folder,tools)
            generic=folder/'Two camera tracks.mkv'
            capture([str(tools.ffmpeg),'-v','error','-i',str(source),'-map','0:v:1',
                     '-map','0:v:0','-map','0:a','-c','copy',
                     '-metadata:s:v:1','title=',str(generic)])
            with self.assertRaisesRegex(ValueError,'Dual'):
                plan_job(tools,Job(generic,Options(target='mono')),folder/'out',set())
            options=Options(layout='dual',target='mono',container='mkv')
            plan=plan_job(tools,Job(generic,options),folder/'out',set())
            png=preview(tools,plan,threading.Event())
            with Image.open(io.BytesIO(png)) as image:
                red,_,blue=image.convert('RGB').getpixel((32,16))
                self.assertGreater(red,180);self.assertLess(blue,50)

    def test_fractional_pair_rate_and_copied_audio_remain_identical(self):
        tools=Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);source=self.fixture(folder,tools,rate='30000/1001')
            options=Options(target='dual',container='mkv',fps_mode='custom',
                            target_fps='30000/1001',audio_format='copy')
            plan=plan_job(tools,Job(source,options),folder/'out',set())
            execute(tools,plan,threading.Event(),lambda *args:None,folder/'fractional.log')
            report=json.loads(capture([str(tools.ffprobe),'-v','error','-count_frames',
                                      '-show_streams','-of','json',str(plan.output)]))
            videos=[s for s in report['streams'] if s['codec_type']=='video']
            self.assertEqual([int(s['nb_read_frames']) for s in videos],[14,14])
            self.assertTrue(all(Fraction(s['avg_frame_rate'])==Fraction(30000,1001) for s in videos))
            def audio(path):
                return capture([str(tools.ffmpeg),'-v','error','-i',str(path),'-map','0:a:0',
                                '-c:a','pcm_s16le','-f','s16le','-'])
            self.assertEqual(audio(source),audio(plan.output))
