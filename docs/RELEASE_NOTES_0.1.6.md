# TransCora 0.1.6

- BD-3D: Compare the ordered coded pictures and distinct parameter sets before
  and after muxing, then fully decode both views from the actual final output.
  This preserves encoder/frame-count and packaging validation while removing
  one complete MVC decode. Frame times remain checked inline during encoding.
- Name every initial/export/check phase in the main status. Use an indeterminate
  bar for unmeasurable phases, show progress during the full final decode, and
  display Restzeit: — until an estimate can be made. Record phase durations in logs.
- Add advanced original/AAC audio, all/selected/no-track and explicit stereo-downmix
  options; default to all original channels and avoid another lossy encode.
  Blu-ray output remains 48 kHz, 24-bit LPCM. Use Wave64 for long surround tracks.
- Read the MVC base-eye flag from ISO playlists. Explain the left-eye assumption
  for sources without that flag and retain the manual L/R swap.
- Keep FRIM 1.31 software quality settings and the compatible anaglyph profile
  unchanged. Retain tsMuxeR 2.6.12, the existing title bar and gold selection palette.

Image/MPO batch tools and Apple MV-HEVC output remain planned extensions.
