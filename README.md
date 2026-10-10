# TransCora

TransCora is a planned portable Python application for batch-oriented 3D video, image and file conversion, powered primarily by FFmpeg.

**Development status: workflow analysis and preset design. No runnable application or release is available yet.**

## Direction

- Local, offline operation without accounts, tracking or cloud dependencies.
- Individual files, freely assembled file lists and folders share one job model.
- Technical checks, clear output plans, progress and logs take priority over a large preview.
- Initial video workflows: Full-SBS to Half-SBS, Half-Over-Under, left-eye mono and anaglyph video.
- Anaglyph methods follow AnaglyphBatch: 17 existing methods, excluding CIELab. The method definitions are reference data; video color handling still requires validation.
- Image conversion, MPO splitting, L/R file preparation and image sequences follow in later phases.
- Blu-ray 3D/MVC is a separate future specialist mode.

## Development notes

- [Project foundation (German)](docs/TransCora-Konzept.md)
- [FFBatch analysis, preset model and AnaglyphBatch comparison (German)](docs/ffmpeg-Parameter-Auswertung.md)
- [Original FFBatch parameters](reference/FFBatch-Presets.txt)
- [Pinned AnaglyphBatch reference](reference/AnaglyphBatch_DE.bat)
- [Reference method catalog](presets/anaglyph_methods.reference.json)

The supplied icon and the existing tool-family completion sound are preserved unchanged under `assets/`.

## License

Project material is covered by the [MIT License](LICENSE). Third-party tools will retain their own licenses; their distribution will be documented when the portable toolchain is selected.
