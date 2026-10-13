# Third-party components

TransCora's source is MIT licensed. Its portable distribution contains separately
licensed components. The MIT license does not replace their terms.

## Pillow and ExifTool

The shared Stereo Tools checkbox uses CustomTkinter 5.2.2 (MIT), with darkdetect
0.8.0 (BSD) and packaging (Apache-2.0/BSD). The package includes their installed
license notices under `licenses/` and CustomTkinter's fonts and themes.

Still-image loading, MPO indexing, EXIF orientation, ICC colour handling and
JPEG encoding use Pillow 11.3.0. FFmpeg performs the stereo/layout/matrix transforms.
The portable package retains Pillow's license and bundled library notices under
`licenses/Pillow/`. Source: https://github.com/python-pillow/Pillow/tree/11.3.0

Metadata copying uses official ExifTool 13.59 as a separate process. Its pinned
Windows executable, all `exiftool_files` support files, original source archive,
license notices and checksum record are included. The Windows package contains
its own Perl runtime; it does not require the user to install Perl.
Source and licensing: https://exiftool.org/ . Pins: `scripts/prepare_exiftool.py`.

## Separate HEIF reader

HEIC/HEIF loading runs in `tools/heif/TransCora-HEIF`, a separate replaceable
process. The main application does not load pillow-heif. The helper includes
pillow-heif 1.8.1 (BSD-3-Clause), libheif 1.23.6 and libde265 1.1.3 (LGPLv3),
and x265 4.3 (GPLv2 or later). The combined helper is distributed under
GPL-3.0-or-later, with component notices and pinned corresponding source archives.
See `native/heif/LICENSE.md`, `scripts/heif-sources.json` and the helper's
`BUILD_READER.json` for the actual libraries in the platform build. The native
libraries remain beside the helper so they can be replaced.

## FFmpeg toolchain

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
TransCora's adaptations preserve UTF-8/Unicode Windows paths and retain
actual decoder errors without adding a concealment-based approval gate.
Original license notices and a source/binary manifest are bundled in `tools/mvc`.

- Decoder source: https://github.com/jens-duttke/edge264-mvc
- Shared source core: https://github.com/jens-duttke/mvc-source

Integration tests download one SHA256-pinned MV-HEVC conformance sample from
FFmpeg's FATE suite. It is test material, not a bundled application dependency.

## CIELAB Least Squares

The image-only CIELAB method executes the same native PNG port as AnaChroma,
from AnaChroma commit `1f5284dce7958be1165d7167b6631da760fd84c6`. The mathematical
sources and solver are retained unchanged from `mbrown1413/anaglyph` commit
`4db425343687f796b85f04ae204e05a43e5742f0`; SHA256 hashes are verified before building.
The GPL-3.0-or-later tool communicates through PNG files as a separate process.
It statically links pinned libpng 1.6.59 and zlib 1.3.2. The executable, matching
offline source archive, provenance and complete CIELAB/levmar/libpng/zlib license
texts are bundled under `tools/cielab`. See `native/cielab/README.md` and
`SOURCES.json`. The original numerical method and iteration limits are unchanged.
