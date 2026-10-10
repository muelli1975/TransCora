# TransCora 0.1.2 — Windows test build

- Added **Only change frame rate**: exact rational rates, unchanged packed layout,
  resolution and eye order, source YUV chroma sampling and bit depth, copied audio.
  Integer reductions such as 60 → 30 and 60000/1001 → 30000/1001 keep every second
  complete frame. Other conversions drop or repeat frames without blending or
  motion interpolation. Video is re-encoded with the existing quality settings.
- Added editable, output-specific filename suffix choices and a live output name.
  AnaglyphBatch method suffixes remain the defaults. Previous settings and lists
  retain their existing naming choices.
- Recognize TransCora's own Full/Half-SBS and OU filename markers on import.
- **Testen** explains layout detection and planned stereo markers. Export validation
  now checks stereo markers, colour interpretation and requested frame rate.
- Stereo MP4 exports contain an explicit **st3d** box as well as H.264 frame-packing
  SEI. A lossless MKV-to-MP4 packaging pass writes st3d; video is encoded once.
  Frame-rate-only MP4 exports restore exact frame timestamps after MKV time-base
  rounding. Reversed-eye frame-rate-only sources require MKV, which preserves
  their StereoMode; st3d cannot represent the reversed order.
- Replaced the preview timeline with a continuous track and a single round gold
  handle. The first image loads automatically; slider release or Enter in the
  seconds field updates it. Removed the redundant **Laden** button.
- Improved selected-row contrast and consistent Start/Testen/Abbrechen styles.
  Windows title bars follow the existing tool-family behaviour.
- Portable archives exclude development references, tests and build sources.

The 17 anaglyph methods, their high-precision calculations and the default
H.264 / CRF 18 / slow quality settings are unchanged. Blu-ray 3D/MVC is planned
for a separate integration; this build does not create Blu-ray discs.

The test material is synthetic. Actual playback compatibility still needs testing
on the intended devices. Only the previously supported SDR colour interpretations
are accepted; no automatic HDR conversion or motion interpolation is included.
