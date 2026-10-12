# TransCora 1.0

TransCora converts stereoscopic videos and images for 3D players, cross-view viewing, anaglyph glasses and polarised monitors. It runs locally and provides German and English interfaces.

- Video output: Full/Half Side-by-Side and Over/Under, Full-SBS cross-view R/L, anaglyphs, row-interleaved stereo and separate eyes. MP4 is the default; MKV carries native stereo metadata.
- Adjustable output size, including Original, 1080p, 2160p and custom dimensions. Optional frame-rate conversion and progressive output from interlaced sources at field rate.
- Image conversion: common image formats, JPS/PNS and two-eye MPO; 17 anaglyph methods plus native CIELAB Least Squares for images. Lossless MPO eye extraction, metadata preservation and JPEG, PNG, TIFF or WebP output.
- Row-interleaved images and videos for polarised monitors, with adjustable screen resolution and eye order.
- Windows Blu-ray 3D export to ISO or M2TS, with AVC/MVC video, LPCM audio and a selectable 20–40 Mbit/s bitrate. Valid variable frame rates and timestamp jitter are accepted.
- Batch processing, saved presets, previews, duration and frame-rate columns, per-file logs and cancellation.
- Ordinary settings fit the initial window on sufficiently tall displays. Advanced BD-3D settings group video bitrate and audio options, with irrelevant codec/CRF controls hidden. File warnings use a gold warning triangle; scrolling closed settings menus preserves their values. The factory BD-3D bitrate remains 40 Mbit/s in both languages; individual file settings remain independent. The Log view supports mouse selection and copying selected text from its context menu.

## Downloads and requirements

- **Windows x64:** extract the ZIP and run TransCora.exe. Python, FFmpeg, image tools and BD-3D tools are included.
- **Linux x64:** extract the archive and run TransCora. Install FFmpeg and Perl separately (`sudo apt install ffmpeg perl` on Ubuntu/Debian). Includes the MVC reader.
- **macOS Apple Silicon:** extract the archive and open TransCora.app. Install `brew install ffmpeg@7`; system Perl is also required. This package is not notarised and currently supports packed stereo and ordinary video input without an MVC reader.

Native BD-3D encoding is available in the Windows package. Linux and macOS include the application runtime, CIELAB and ExifTool and do not require a separate Python installation.

Read [the English guide](https://github.com/muelli1975/TransCora/blob/main/README.md) or [die deutsche Anleitung](https://github.com/muelli1975/TransCora/blob/main/README_DE.md) for supported formats, setup and practical examples.
