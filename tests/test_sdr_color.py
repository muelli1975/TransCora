"""Real SDR boundary tests: photos, existing videos, frame rate and BD preparation."""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from PIL import Image
from transcora.core.engine import build_graph, color_spec
from transcora.core.model import Options
from transcora.core.toolchain import Toolchain

GRAYS = [0,16,32,64,96,128,192,255]
COLORS = [(64,96,128),(160,64,96),(96,160,64),(64,96,160),
          (192,128,64),(128,64,192),(64,192,128),(160,160,96)]
RGB = dict(matrix="gbr",primaries="bt709",transfer="iec61966-2-1",range="pc")


class SDRColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tools = Toolchain.find()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        eye = Image.new("RGB",(256,144))
        for i,g in enumerate(GRAYS):
            eye.paste((g,g,g),(32*i,0,32*(i+1),72))
            eye.paste(COLORS[i],(32*i,72,32*(i+1),144))
        pair = Image.new("RGB",(512,144))
        pair.paste(eye,(0,0));pair.paste(eye,(256,0))
        self.photo = self.root/"pair.png"
        pair.save(self.photo)

    def run_ff(self,*args):
        return subprocess.run([str(self.tools.ffmpeg),"-hide_banner","-v","error","-nostdin","-y",*map(str,args)],
                              check=True,capture_output=True).stdout

    def video(self,path):
        return json.loads(subprocess.check_output(
            [str(self.tools.ffprobe),"-v","error","-show_streams","-of","json",str(path)]))["streams"][0]

    def fixture(self,kind):
        path = self.root/(kind+".mkv")
        if kind=="rgb":
            vf="format=bgr0,setparams=colorspace=gbr:color_primaries=bt709:color_trc=iec61966-2-1:range=full"
        else:
            full=kind=="full"
            vf=("scale=in_range=full:out_range="+("full" if full else "limited")+":out_color_matrix=bt709,"
                "format="+("yuv444p" if full else "yuv420p")+
                ",setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range="+("full" if full else "limited"))
        self.run_ff("-loop","1","-framerate","30","-i",self.photo,"-vf",vf,
                    "-frames:v","3","-c:v","ffv1",path)
        return path

    def decode(self,path,seconds=None):
        v=self.video(path)
        args=["-i",path]
        if seconds is not None:args+=["-ss",str(seconds)]
        raw=self.run_ff(*args,"-frames:v","1","-vf",
                        "scale=in_color_matrix=bt709:in_range="+("full" if v.get("color_range")=="pc" else "limited")+":out_range=full",
                        "-f","rawvideo","-pix_fmt","rgb24","pipe:1")
        return Image.frombytes("RGB",(v["width"],v["height"]),raw)

    def samples(self,image,target="full_sbs",bd=False):
        w,h=image.size
        ew,eh=(w//2,h) if target=="full_sbs" else (w,h//2)
        if bd:
            # Original eye is 16:9, matching the BD output, with no padding.
            pass
        return [[image.getpixel((round((i+.5)*ew/8),round(y*eh))) for i in range(8)] for y in (.25,.75)]

    def check_chart(self,image,target):
        rows=self.samples(image,target)
        for row,expected,tolerance in [(rows[0],[(g,g,g) for g in GRAYS],3),(rows[1],COLORS,5)]:
            for actual,wanted in zip(row,expected):
                self.assertLessEqual(max(abs(a-b) for a,b in zip(actual,wanted)),tolerance,(actual,wanted))

    def export(self,source,target):
        v=self.video(source);colors,_=color_spec(v,"full_sbs")
        graph,size,pixel=build_graph(v,Options(target=target,container="mkv"),"full_sbs",False,colors,{})
        out=self.root/(source.stem+"-"+target+".mkv")
        self.run_ff("-filter_complex_threads","1","-i",source,"-filter_complex",graph,"-map","[v]",
                    "-frames:v","2","-c:v","libx264","-crf","18","-preset","slow","-pix_fmt",pixel,
                    "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",out)
        return out

    def test_finished_rgb_photos_keep_tone_values(self):
        source=self.fixture("rgb")
        for target in ("full_sbs","half_ou"):
            with self.subTest(target=target):
                out=self.export(source,target)
                self.check_chart(self.decode(out),target)
                v=self.video(out)
                self.assertEqual([v.get(k) for k in ("color_space","color_primaries","color_transfer","color_range")],
                                 ["bt709","bt709","bt709","tv"])

    def test_existing_limited_and_full_range_rec709_video(self):
        for kind in ("limited","full"):
            source=self.fixture(kind)
            expected=self.samples(self.decode(source))
            for target in ("full_sbs","half_ou","framerate"):
                with self.subTest(kind=kind,target=target):
                    # Frame-rate-only retains source colour metadata, not the normal SDR tags.
                    if target=="framerate":
                        v=self.video(source);colors,_=color_spec(v,"full_sbs")
                        graph,size,pixel=build_graph(v,Options(target="framerate"),"full_sbs",False,colors,{})
                        out=self.root/(kind+"-fps.mkv")
                        self.run_ff("-filter_complex_threads","1","-i",source,"-filter_complex",graph,
                                    "-map","[v]","-frames:v","2","-c:v","ffv1","-pix_fmt",pixel,out)
                    else:out=self.export(source,target)
                    actual=self.samples(self.decode(out),"full_sbs" if target=="framerate" else target)
                    for row_a,row_b in zip(actual,expected):
                        for a,b in zip(row_a,row_b):
                            self.assertLessEqual(max(abs(x-y) for x,y in zip(a,b)),5,(kind,target,a,b))

    def test_bd_rgb_and_native_rec709_preparation(self):
        from transcora.core.bd3d import prepare
        for kind in ("rgb","limited"):
            with self.subTest(kind=kind):
                source=self.fixture(kind);v=self.video(source)
                prepared=prepare(v,"full_sbs",False,"720p50")
                graph=prepared.graph+";[left][right]hstack=inputs=2[v]"
                out=self.root/(kind+"-bd.mkv")
                self.run_ff("-filter_complex_threads","1","-i",source,"-filter_complex",graph,"-map","[v]",
                            "-frames:v","1","-c:v","ffv1","-pix_fmt","yuv420p",out)
                self.check_chart(self.decode(out),"full_sbs")

    def test_dual_video_input_keeps_display_tones(self):
        from transcora.core.model import LAYOUTS
        if "dual" not in LAYOUTS:
            self.skipTest("Dual-video input is not part of this legacy version")
        try:
            from transcora.core.multiview import graph_prefix
        except ImportError:
            self.skipTest("Dual-video input is not part of this legacy version")
        source=self.fixture("limited")
        dual=self.root/"dual.mkv"
        self.run_ff("-i",source,"-filter_complex","[0:v]split[a][b];[a]crop=256:144:0:0[l];[b]crop=256:144:256:0[r]",
                    "-map","[l]","-map","[r]","-c:v","ffv1",
                    "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",dual)
        streams=json.loads(subprocess.check_output([str(self.tools.ffprobe),"-v","error","-show_streams","-of","json",str(dual)]))["streams"]
        virtual=dict(streams[0],width=512,index=0,pix_fmt="gbrp16le",color_space="gbr",color_transfer="iec61966-2-1",color_range="pc")
        options=Options(target="half_ou")
        graph,_,pixel=build_graph(virtual,options,"full_sbs",False,RGB,{})
        graph=graph_prefix(dict(video=virtual,multiview=dict(kind="dual",videos=streams)),graph,options)
        out=self.root/"dual-output.mkv"
        self.run_ff("-filter_complex_threads","1","-i",dual,"-filter_complex",graph,"-map","[v]",
                    "-frames:v","1","-c:v","libx264","-crf","18","-pix_fmt",pixel,
                    "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",out)
        self.check_chart(self.decode(out),"half_ou")


if __name__=="__main__":unittest.main()
