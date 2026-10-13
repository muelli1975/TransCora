"""Exercise Dual import/export inside the frozen application process."""
import io
import json
from pathlib import Path
import threading
from PIL import Image
from .engine import capture,plan_job,execute
from .model import Job,Options
from .toolchain import Toolchain


def check(folder):
    folder=Path(folder).resolve();folder.mkdir(parents=True,exist_ok=True)
    tools=Toolchain.find();cancel=threading.Event()
    picture=folder/'L-R.png'
    image=Image.new('RGB',(128,32),'red');image.paste('blue',(64,0,128,32));image.save(picture)
    source=folder/'Stereo ÄÖÜ-dual.mkv'
    capture([str(tools.ffmpeg),'-y','-v','error','-loop','1','-framerate','25','-i',str(picture),
             '-f','lavfi','-i','sine=frequency=700:sample_rate=48000:duration=0.48',
             '-filter_complex','[0:v]split[a][b];[a]crop=64:32:0:0[left];[b]crop=64:32:64:0[right]',
             '-map','[left]','-map','[right]','-map','1:a','-t','0.48','-c:v','ffv1','-pix_fmt','gbrp',
             '-colorspace','rgb','-color_primaries','bt709','-color_trc','iec61966-2-1','-color_range','pc',
             '-metadata:s:v:0','title=Left','-metadata:s:v:1','title=Right','-c:a','pcm_s16le',str(source)])
    checks=[]
    for container,swap in [('mp4',False),('mkv',True)]:
        options=Options(target='dual',container=container,swap=swap,video_size='custom',
                        video_width=64,video_height=32,audio_format='aac' if container=='mp4' else 'copy')
        plan=plan_job(tools,Job(source,options),folder/'outputs',set(),cancel)
        if plan.info['multiview']['kind']!='dual':raise ValueError('Dual input was not recognised')
        execute(tools,plan,cancel,lambda *args:None,folder/'export.log')
        report=json.loads(capture([str(tools.ffprobe),'-v','error','-count_frames','-show_streams','-of','json',str(plan.output)]))
        videos=[s for s in report['streams'] if s['codec_type']=='video']
        if len(videos)!=2 or any(int(v['nb_read_frames'])!=12 for v in videos):
            raise ValueError('Dual output must contain 12 pictures per video track')
        for index in (0,1):
            png=capture([str(tools.ffmpeg),'-v','error','-i',str(plan.output),'-map',f'0:v:{index}',
                         '-frames:v','1','-c:v','png','-f','image2pipe','-'])
            with Image.open(io.BytesIO(png)) as decoded:
                if decoded.size!=(64,32):raise ValueError('Dual eye geometry differs')
                red,_,blue=decoded.convert('RGB').getpixel((32,16))
                expected_blue=swap if index==0 else not swap
                if (blue if expected_blue else red)<180 or (red if expected_blue else blue)>50:
                    raise ValueError('Dual view assignment differs')
        if len([s for s in report['streams'] if s['codec_type']=='audio'])!=1:
            raise ValueError('Dual audio is missing')
        checks.append({'container':container,'swap':swap,'pictures_per_track':12,'left_right':True,'audio':True})
    return {'ok':True,'checks':checks}
