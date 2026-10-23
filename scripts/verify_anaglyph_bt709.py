"""Validate the published video adapters against the original Batch on BT.709 input."""
import json
import re
import subprocess
import tempfile
from pathlib import Path
from PIL import Image
from transcora.core.engine import build_graph, color_spec, methods
from transcora.core.model import Options, app_root
from transcora.core.sdr_color import rgb_input

LEVELS=[0,16,32,64,96,128,192,255]
COLORS=[(64,96,128),(160,64,96),(96,160,64),(64,96,160),
        (192,128,64),(128,64,192),(64,192,128),(160,160,96)]
TAGS="setparams=colorspace=bt709:color_primaries=bt709:color_trc=bt709:range=limited"

def ff(*args):
    return subprocess.check_output(["ffmpeg","-v","error","-nostdin","-y",
        "-filter_complex_threads","1",*map(str,args)])

def probe(path):
    return json.loads(subprocess.check_output(["ffprobe","-v","error","-show_streams","-of","json",str(path)]))["streams"][0]

def sample(raw):
    image=Image.frombytes("RGB",(256,144),raw)
    return [image.getpixel((32*i+16,y)) for y in (36,108) for i in range(8)]

def difference(a,b):
    return max(abs(x-y) for p,q in zip(a,b) for x,y in zip(p,q))

def decode(path):
    return sample(ff("-i",path,"-frames:v","1","-vf",
        "scale=in_color_matrix=bt709:in_range=limited:out_range=full",
        "-pix_fmt","rgb24","-f","rawvideo","pipe:1"))

def encode(source,graph,path,lossless=False):
    ff("-i",source,"-filter_complex",graph,"-map","[v]","-frames:v","1",
       "-c:v","libx264","-preset","slow",*(["-qp","0"] if lossless else ["-crf","18"]),"-pix_fmt","yuv444p",
       "-colorspace","bt709","-color_primaries","bt709","-color_trc","bt709","-color_range","tv",path)
    v=probe(path)
    assert [v.get(k) for k in ("color_space","color_primaries","color_transfer","color_range")]==["bt709","bt709","bt709","tv"]

batch=(app_root()/"reference/AnaglyphBatch_DE.bat").read_text(encoding="utf-8-sig")
templates=dict(re.findall(r'if "%MATRIXMODE%"=="(\w+)" \(\s*set "VF=(.*?)"',batch))
blocks=re.findall(r'if "%~1"=="\d+" \((.*?)\n\)',batch,re.S)
definitions=[dict(re.findall(r'set "([^=]+)=(.*?)"',b)) for b in blocks]
definitions={x.get("MATRIXNAME"):x for x in definitions}
report=[]
with tempfile.TemporaryDirectory() as temp:
    root=Path(temp)
    photo=root/"stereo.png"
    pair=Image.new("RGB",(512,144))
    for eye in range(2):
        for i,g in enumerate(LEVELS):
            pair.paste((g,g,g),(256*eye+32*i,0,256*eye+32*(i+1),72))
            color=COLORS[(i+3*eye)%8]
            pair.paste(color,(256*eye+32*i,72,256*eye+32*(i+1),144))
    pair.save(photo)
    source=root/"BT709_limited_full_sbs.mkv"
    ff("-i",photo,"-vf","scale=in_range=full:out_range=limited:out_color_matrix=bt709,format=yuv420p,"+TAGS,
       "-frames:v","1","-c:v","ffv1",source)
    video=probe(source)
    assert [video.get(k) for k in ("color_space","color_primaries","color_transfer","color_range")]==["bt709","bt709","bt709","tv"]
    colors,_=color_spec(video,"full_sbs")
    new_input=rgb_input(colors)
    old_input=new_input.replace("transferin=iec61966-2-1:rangein=limited","transferin=bt709:rangein=limited")
    assert old_input!=new_input
    for key,method in methods().items():
        reference=templates[method["pipeline_type"]]
        for variable,value in {**definitions[key],"SCALEPART":""}.items():
            reference=reference.replace("%"+variable+"%",value)
        assert "%" not in reference
        graph,size,pixel=build_graph(video,Options(target="anaglyph",method=key,profile="quality"),"full_sbs",False,colors,method)
        assert size==(256,144) and pixel=="yuv444p"
        reference_raw=sample(ff("-i",source,"-filter_complex",reference+"[v]","-map","[v]",
                               "-frames:v","1","-pix_fmt","rgb24","-f","rawvideo","pipe:1"))
        internal_graph=graph.split(";[composite]zscale=")[0]+";[composite]format=rgb24[v]"
        actual_raw=sample(ff("-i",source,"-filter_complex",internal_graph,"-map","[v]",
                            "-frames:v","1","-pix_fmt","rgb24","-f","rawvideo","pipe:1"))
        ref_file=root/(key+"-batch.mp4")
        new_file=root/(key+"-published.mp4")
        old_file=root/(key+"-previous.mp4")
        reference_out=reference+",scale=in_range=full:out_range=limited:out_color_matrix=bt709,format=yuv444p,"+TAGS+"[v]"
        encode(source,reference_out,ref_file)
        encode(source,graph,new_file)
        old_graph=graph.replace(new_input,old_input).replace(
            "matrix=bt709:primaries=bt709:transfer=iec61966-2-1:range=limited",
            "matrix=bt709:primaries=bt709:transfer=bt709:range=limited")
        assert old_graph!=graph
        encode(source,old_graph,old_file)
        reference_decoded=decode(ref_file)
        ref_lossless=root/(key+"-batch-lossless.mp4")
        new_lossless=root/(key+"-published-lossless.mp4")
        encode(source,reference_out,ref_lossless,lossless=True)
        encode(source,graph,new_lossless,lossless=True)
        reference_lossless_decoded=decode(ref_lossless)
        published_lossless_decoded=decode(new_lossless)
        report.append(dict(method=key,mode=method["pipeline_type"],
                           working_rgb_max_error=difference(actual_raw,reference_raw),
                           lossless_mp4_max_error=difference(published_lossless_decoded,reference_lossless_decoded),
                           reference_codec_max_error=difference(reference_decoded,reference_lossless_decoded),
                           published_codec_max_error=difference(decode(new_file),published_lossless_decoded),
                           published_mp4_max_error=difference(decode(new_file),reference_decoded),
                           previous_mp4_max_error=difference(decode(old_file),reference_decoded)))
Path("anaglyph-bt709-verification.json").write_text(json.dumps(report,indent=2),encoding="utf-8")
print(json.dumps(report,indent=2),flush=True)
assert len(report)==17
assert all(x["working_rgb_max_error"]<=3 for x in report), "Working RGB differs from Batch"
assert all(x["lossless_mp4_max_error"]<=3 for x in report), "Lossless MP4 differs from Batch policy"
# A separate CRF18 encode may amplify a one-code-value RGB rounding difference.
# Keep the same five-code-value colour-patch envelope as the SDR regression tests.
assert all(x["published_mp4_max_error"]<=5 for x in report), "CRF18 MP4 exceeds colour-patch envelope"
print("PASS: all 17 methods, actual limited BT.709 video input, RGB and encoded/decoded MP4.")
