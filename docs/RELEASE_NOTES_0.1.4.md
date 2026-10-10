# TransCora 0.1.4

- Added BD-3D 1080p export with a fixed high-quality software AVC/MVC profile,
  editable disc title, Blu-ray ISO (default), or standalone two-view M2TS.
- Accept constant 23.976 and exact 24 fps SBS/OU sources. Exact 24 fps slows to
  24000/1001 without frame loss, with pitch-preserving audio adaptation.
- Check source cadence, both decoded eyes before/after muxing, LPCM audio,
  and actual UDF 2.50/SSIF contents. Stream raw pictures and rewrite SPS with bounded memory.
- Added named portable conversion presets; file lists, folders and film titles are excluded.
- Simplified the preview to one editable clock and a timeline; removed redundant seconds.
- Applied the dark palette to all log-window surfaces and added a themed scrollbar.
- Clarified the compatibility profile warning and recommendation for 4:4:4 anaglyphs.
- Added an approximate remaining-time estimate based on real processing progress.

Initial BD scope: SDR, progressive SBS/OU, constant 23.976/24 fps, known mono/stereo/5.1/7.1
channel layouts, 24-bit 48-kHz LPCM. A 4-GB WAV limit applies per temporary audio track.
No automatic VFR/other-rate conversion, subtitle authoring, menus or disc-size splitting.
Technical output validation does not constitute formal Blu-ray certification.
