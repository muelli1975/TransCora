# FFmpeg / ffprobe

Portable Windows builds place FFmpeg, ffprobe and their runtime libraries here.
The application first checks this directory, then the configured tool directory,
then PATH for development installations. It never downloads tools at runtime.

The Windows build script uses the checksum-pinned Gyan FFmpeg 9.0.2 full shared
build and retains the upstream license and documentation alongside the binaries.
