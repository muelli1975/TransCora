# TransCora 0.1.5

- Add progressive H.264 MVC input from M2TS/TS/SSIF, single-track MVC MKV/MP4
  and unencrypted single-clip Blu-ray 3D ISO playlists. Both views are decoded
  with a pinned portable edge264-mvc bridge; FRIM remains available as a checked
  Windows fallback. No installed frameserver is required.
- Add SDR MV-HEVC input with explicitly tagged left/right views. Decode both
  views with FFmpeg, honor right-eye base layers, and check view timestamps.
  HDR, immersive projections and ambiguous view positions remain blocked.
- Convert supported progressive CFR sources directly to the BD-3D target clock,
  before one MVC encode. Keep native 23.976 fps; preserve every 24 fps frame with
  the existing 0.1% slowdown. Other rates preserve running time and audio while
  selecting/repeating complete stereo pairs, with a visible motion warning.
- Validate every original BD-3D frame timestamp during the necessary decode
  rather than in a separate full decode. Also validate the resulting target clock.
- Show an animated activity bar during checking and finalization, with clear
  phase labels. Keep elapsed and remaining time beside each other.
- Keep disabled anaglyph controls visible for all other targets; use “Halbbilder”
  consistently in BD-3D checks and simplify the control-image time label.
- Keep run logs in the application folder under `logs`; retain the last ten
  owned logs. Remove the redundant batch launcher from the portable ZIP.

MVC export quality remains FRIM software / Target Usage 1 / aggregate VBR
28 Mbit/s target, 40 Mbit/s maximum. Anaglyph method calculations and the
Compatibility encoding profile are unchanged.

MV-HEVC output for Apple devices is planned separately; this version adds input.
ISO playlists using seamless branching, alternate angles or clip trims are not
silently flattened or replaced with a different title.
