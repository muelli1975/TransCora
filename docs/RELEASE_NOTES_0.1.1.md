# TransCora 0.1.1 — test build

- Remove fixed FFmpeg filter and HEVC encoder thread limits.
- Apply the stereo tools' shared dark palette, button states and Windows title bars.
- Add a control-frame timeline alongside the exact seconds field.
- Use MP4 by default and show only the selected CRF or target-bitrate input.
- Rename the actions to “Start” and “Testen”, and use “Anaglyphenverfahren”.
- Keep folder structure automatically when importing a folder, including subfolders.
- Handle missing HD-SDR colour tags automatically and report each assumption;
  respect existing tags and evaluate the signal range separately.
- Locate bundled FFmpeg tools automatically without an external-path setting.
- Remember conversion preferences and folders; reset source layout and eye swap
  on startup. Restore defaults for new jobs without changing existing jobs or paths.

The AnaglyphBatch matrices and LUTs remain unchanged. See
[the performance check](Performance-0.1.1.md) for measured improvements and limits.
