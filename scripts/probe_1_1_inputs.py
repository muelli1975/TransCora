"""Development-only FFmpeg probes for proposed TransCora 1.1 inputs.

Uses generated, lossless fixtures; does not change application acceptance rules.
No downloads, dependency installation or user-media scans are performed.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


def run(command):
    result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            timeout=30, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace"))
    return result.stdout


def fixture():
    """Three pairs with distinct halves, rows, columns, planes and frame indices."""
    packed, left, right = bytearray(), bytearray(), bytearray()
    for frame in range(3):
        for plane in range(3):
            for row in range(8):
                first = bytes(32 + frame * 11 + plane * 19 + row + x % 3 for x in range(16))
                second = bytes(160 + frame * 7 + plane * 13 + row + x % 5 for x in range(16))
                packed.extend(first + second)
                left.extend(first)
                right.extend(second)
    return bytes(packed), bytes(left), bytes(right)


def packed_fixture(layout, left, right):
    """Generate inputs independently of FFmpeg's conversion filter."""
    data = bytearray()
    for frame in range(3):
        first, second = left[frame * 384:(frame + 1) * 384], right[frame * 384:(frame + 1) * 384]
        if layout in {"irr", "ar"}:
            first, second = second, first
        if layout in {"al", "ar"}:
            data.extend(first + second)
        else:
            for plane in range(3):
                for row in range(8):
                    offset = plane * 128 + row * 16
                    data.extend(first[offset:offset + 16] + second[offset:offset + 16])
    return bytes(data)


def probe(ffprobe, path):
    return json.loads(run([ffprobe, "-v", "error", "-count_frames", "-show_streams",
                           "-show_format", "-of", "json", str(path)]))


def stream_check(data, width, height, frames, rate):
    video = next(s for s in data["streams"] if s["codec_type"] == "video")
    actual = (video["width"], video["height"], int(video["nb_read_frames"]),
              Fraction(video["avg_frame_rate"]))
    expected = width, height, frames, Fraction(rate)
    if actual != expected:
        raise AssertionError(f"Video properties: {actual!r} != {expected!r}")
    # Matroska writes millisecond timestamps; allow one timestamp tick.
    duration = float(data["format"]["duration"])
    if abs(duration - frames / float(Fraction(rate))) > .0011:
        raise AssertionError(f"Duration: {duration!r}")
    return {"width": width, "height": height, "frames": frames,
            "fps": str(Fraction(rate)), "duration_seconds": duration}


def dependency_versions():
    result = {}
    for name in ("Pillow", "pillow-heif"):
        try:
            result[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            result[name] = None
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ffmpeg", default=shutil.which("ffmpeg"))
    parser.add_argument("--ffprobe", default=shutil.which("ffprobe"))
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    if not args.ffmpeg:
        parser.error("Provide --ffmpeg or put FFmpeg on PATH")
    ffmpeg = str(Path(args.ffmpeg).resolve())
    ffprobe = str(Path(args.ffprobe).resolve()) if args.ffprobe else str(
        Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix))
    report = {"development_probe": True,
              "ffmpeg_version": run([ffmpeg, "-version"]).decode().splitlines()[0],
              "fixture_generation": "independent raw YUV generator",
              "host_dependencies": dependency_versions(), "checks": [],
              "not_checked": ["TransCora GUI or import integration", "audio synchronization",
                              "HEIC/HEIF/AVIF decoding and stereo metadata"]}
    original, left, right = fixture()
    with tempfile.TemporaryDirectory(prefix="transcora-1-1-input-probe-") as temporary:
        folder = Path(temporary)
        source = folder / "source.yuv"
        source.write_bytes(original)
        prefix = [ffmpeg, "-hide_banner", "-loglevel", "error", "-y"]
        for layout in ("irl", "irr", "al", "ar"):
            packed = folder / (layout + ".mkv")
            restored = folder / (layout + "-restored.mkv")
            sequential = layout in {"al", "ar"}
            input_pixels = folder / (layout + ".yuv")
            input_pixels.write_bytes(packed_fixture(layout, left, right))
            run(prefix + ["-f", "rawvideo", "-pixel_format", "yuv444p", "-video_size",
                          "16x8" if sequential else "16x16", "-framerate", "48" if sequential else "24",
                          "-i", str(input_pixels),
                          "-fps_mode", "passthrough", "-c:v", "ffv1", str(packed)])
            input_properties = stream_check(probe(ffprobe, packed), 16, 8 if sequential else 16,
                                            6 if sequential else 3, 48 if sequential else 24)
            run(prefix + ["-i", str(packed), "-vf", "stereo3d=" + layout + ":sbsl",
                          "-fps_mode", "passthrough", "-c:v", "ffv1", str(restored)])
            output_properties = stream_check(probe(ffprobe, restored), 32, 8, 3, 24)
            pixels = run(prefix + ["-i", str(restored), "-pix_fmt", "yuv444p",
                                   "-f", "rawvideo", "pipe:1"])
            if pixels != original:
                raise AssertionError(layout + ": left/right order or pixels changed")
            report["checks"].append({"layout": layout, "result": "passed",
                                     "input": input_properties, "output": output_properties,
                                     "pixels_equal": True})
        for output, expected in (("ml", left), ("mr", right)):
            pixels = run(prefix + ["-f", "rawvideo", "-pixel_format", "yuv444p", "-video_size", "32x8",
                                   "-framerate", "24", "-i", str(source), "-vf", "stereo3d=sbsl:" + output,
                                   "-pix_fmt", "yuv444p", "-f", "rawvideo", "pipe:1"])
            if pixels != expected:
                raise AssertionError(output + ": wrong left/right view selected")
            report["checks"].append({"layout": output, "result": "passed", "pixels_equal": True})
    content = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.write_text(content, encoding="utf-8")
    print(content, end="")


if __name__ == "__main__":
    main()
