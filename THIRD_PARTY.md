# Third-party components

TransCora's source is MIT licensed. Its portable distribution contains separately
licensed components. The MIT license does not replace their terms.

## FFmpeg

FFmpeg 7.1.1 full shared Windows build from Gyan.dev, pinned with SHA256 in
`scripts/ffmpeg-windows.json`. FFmpeg and ffprobe remain external programs under
`tools/ffmpeg/bin`; the application starts them as separate processes.
The GPL-enabled build includes libx264, libx265, zimg and other upstream libraries.
Keep the supplied `tools/ffmpeg/LICENSE`, documentation and build manifest together
with the binaries. Upstream component notices and configurations are in that folder.

- Build and configuration information: https://www.gyan.dev/ffmpeg/builds/
- Exact binary release: https://github.com/GyanD/codexffmpeg/releases/tag/7.1.1
- FFmpeg source revision: https://github.com/FFmpeg/FFmpeg/tree/db69d06eeeab4f46da15030a80d539efb4503ca8
- FFmpeg licensing: https://ffmpeg.org/legal.html
- FFmpeg source: https://ffmpeg.org/download.html
- x264 source: https://code.videolan.org/videolan/x264
- x265 source: https://bitbucket.org/multicoreware/x265_git
- zimg source: https://github.com/sekrit-twc/zimg

Before distributing a public release, keep a corresponding source package/build
record for the exact GPL toolchain and its enabled components. The development
artifact is an early test build, with upstream license and build documents included.

## Python, Tcl/Tk and PyInstaller

Python and Tcl/Tk are included in the frozen desktop application. Their full
license notices are retained under `licenses/`, with Python's license taken
directly from the exact build installation. Tcl/Tk notices come verbatim from
the upstream 8.6.14 `license.terms` files. The Python
license is available at https://docs.python.org/3/license.html and Tcl/Tk licensing
at https://www.tcl-lang.org/software/tcltk/license.html.
The installed PyInstaller license/bootloader notices are also retained there.
PyInstaller's bootloader exception permits distribution of bundled applications;
see https://pyinstaller.org/en/stable/license.html.

## AnaglyphBatch and assets

The method catalog comes from Christoph Müller's AnaglyphBatch repository and
retains its attribution. The pinned Batch reference is kept in the source repository
for development checks, not in the portable application. TransCora uses the supplied
original icon and the existing tool-family completion sound without alteration.

## FRIM and legacy tsMuxeR

The portable BD-3D path starts external FRIM 1.31 x64 and tsMuxeR 2.6.12 processes.
Archives are size/SHA256 pinned in `scripts/bd3d-tools.json` and recorded under `tools/`.
FRIM's original manuals and release notes are retained under `tools/frim/doc`.
The author describes FRIM as free software built on the freely distributable Intel Media SDK.
The software SDK DLL is retained with the encoder and decoder; no HEVC plugins are shipped.

- FRIM author/download/documentation: https://sites.google.com/site/videofan3d/software/frim-encoder
- Intel Media SDK project: https://github.com/Intel-Media-SDK/MediaSDK
- Legacy tsMuxeR download record: https://www.digital-digest.com/software/tsMuxeR.html
- Maintained tsMuxeR project: https://github.com/justdan96/tsMuxer

The legacy tsMuxeR binary is the exact tested 2.6.12 release, not a newly compiled fork.
Its original release notes are included. Keep third-party notices with the portable tools.

## edge264-mvc and mvc-source

The portable MVC input bridge statically links the BSD-licensed decoder and
shared source core. Exact source commits are pinned in `scripts/build_mvc_decoder.py`.
TransCora's adaptations preserve UTF-8/Unicode Windows paths and propagate
concealment flags so missing/damaged views cannot be silently replaced.
Original license notices and a source/binary manifest are bundled in `tools/mvc`.

- Decoder source: https://github.com/jens-duttke/edge264-mvc
- Shared source core: https://github.com/jens-duttke/mvc-source

Integration tests download one SHA256-pinned MV-HEVC conformance sample from
FFmpeg's FATE suite. It is test material, not a bundled application dependency.
