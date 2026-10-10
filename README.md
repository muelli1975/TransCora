# TransCora

TransCora is a planned portable Python application for batch-oriented 3D video, image and file conversion, powered primarily by FFmpeg.

**Development status: workflow analysis and preset design. No runnable application or release is available yet.**

## Direction

- Local, offline operation without accounts, tracking or cloud dependencies.
- Individual files, freely assembled file lists and folders share one job model.
- Technical checks, clear output plans, progress and logs take priority over a large preview.
- The default output directory is `output` beside the portable application unless a custom destination is selected or remembered.
- Initial video workflows: Full-SBS to Half-SBS, Half-Over-Under, left-eye mono and anaglyph video.
- Anaglyph methods exclusively follow AnaglyphBatch: 17 existing methods, excluding CIELab. Old FFBatch anaglyph chains are analysis examples, not additional product methods. The method definitions are reference data; video color handling still requires validation.
- Anaglyph output defaults to 4:4:4 with a player-support notice. An optional 4:2:0 compatibility profile includes a quality-loss notice; H.264 10-bit/4:4:4 is planned as an additional quality option subject to validation.
- Image conversion, MPO splitting, L/R file preparation and image sequences follow in later phases.
- Blu-ray 3D/MVC is a separate future specialist mode.

## Development notes

- [Project foundation (German)](docs/TransCora-Konzept.md)
- [FFBatch analysis, preset model and AnaglyphBatch comparison (German)](docs/ffmpeg-Parameter-Auswertung.md)
- [Video workflow, player naming, bit depth and compact UI proposal (German)](docs/Video-Workflow-und-Oberflaeche.md)
- [Original FFBatch parameters](reference/FFBatch-Presets.txt)
- [Pinned AnaglyphBatch reference](reference/AnaglyphBatch_DE.bat)
- [Reference method catalog](presets/anaglyph_methods.reference.json)

The supplied icon and the existing tool-family completion sound are preserved unchanged under `assets/`.

## License

Project material is covered by the [MIT License](LICENSE). Third-party tools will retain their own licenses; their distribution will be documented when the portable toolchain is selected.
