# Portable MVC input decoder

`scripts/build_mvc_decoder.py` builds TransCoraMVC from pinned BSD sources:

- edge264-mvc: `e8f4b3b54e34d752c16760efa1e7ad966307eb2b`
- mvc-source shared core: `2acc004ffcb14ebe00abaff2b126b7133fe94bfd`

The executable statically links the decoder and needs neither AviSynth nor
VapourSynth. Both upstream license notices and a source/binary build manifest
are included in the portable package. TransCora's bridge preserves Unicode
Windows filenames and rejects missing or concealed MVC view pairs.

Supported decoder format: progressive H.264 MVC, two views, 8-bit 4:2:0.
FRIM is used as an explicitly checked fallback for unsupported decoder features
on Windows. MV-HEVC uses the bundled FFmpeg 7.1.1 decoder instead.
