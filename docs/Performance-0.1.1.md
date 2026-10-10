# TransCora 0.1.1 performance check

Measured on 10 October 2026 with Ubuntu FFmpeg 6.1.1, libx264, and 9 visible CPU
cores. Input: a lossless FFV1 Full-SBS test video, 3840 × 1080, 25 fps, 40 frames.
Output: one-eye 1920 × 1080, H.264, CRF 18, preset slow, 8-bit 4:4:4, without audio.
Each row uses the same input and encoder options. The timings include process and
encoder startup; this is a short diagnostic, not a general hardware benchmark.

| Pipeline | Filter-only time | H.264 time | H.264 speed |
| --- | ---: | ---: | ---: |
| TransCora 0.1.0, one filter thread | 2.284 s | 4.154 s | 0.385× |
| Same TransCora filters, automatic threading | 1.007 s | 2.847 s | 0.562× |
| Saved FFBatch Dubois LCD + red preset, automatic threading | 0.957 s | 2.855 s | 0.561× |

Automatic threading raised TransCora's end-to-end speed by approximately 46% in
this comparison. An earlier run of the same input measured 4.331 s versus 2.908 s
(approximately 49% higher speed). Filter-only processing more than doubled.
The FFBatch comparison uses the supplied LCD preset. Its BT.709 transfer handling
differs from the Batch-reference sRGB method adapter; it is a performance reference,
not a claim that every FFBatch preset has the same colour calculations or cost.
The user's 1.2–1.4× versus 0.4× observation concerns their own system and video and
still needs to be rechecked with this build and matching profiles.

## Changes retained

- Remove `-filter_complex_threads 1` from conversions and control-frame filtering.
  FFmpeg chooses its filter thread count automatically.
- Remove x265's explicit `pools=2:frame-threads=2` restriction. Encoder threading is
  automatic; no CPU count limit is imposed by TransCora.
- Keep preset slow, CRF, pixel formats, method matrices, LUTs and the colour adapter.
  Parallel work should improve throughput without changing the chosen method.

## Image verification

All 17 methods still match the original AnaglyphBatch composite pixel for pixel on
the existing colour-gradient reference fixture. A full-HD LCD frame also produced
an identical 16-bit RGB composite with one versus automatic filter threads.
The final 8-bit YUV error-diffusion quantization may distribute rounding differently
across parallel slices: on that full-HD frame the maximum difference was one code
value. It is therefore incorrect to promise bit-identical encoded files solely from
changing the thread count. The method and its calculated high-precision colours
remain unchanged.

A diagnostic fused-transfer variant saved little additional end-to-end time and
could change intermediate integer rounding. It was **not** adopted.

Tests cover export profiles, audio, VFR timestamps, cancellation, folder mirroring,
all 17 reference methods, thread equivalence on the small reference fixture, and
GUI behaviour. Windows runs repeat these checks with the bundled FFmpeg build.
