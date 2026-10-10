# FFmpeg / ffprobe

Portable Windows builds place FFmpeg, ffprobe and their runtime libraries here.
The application checks a deliberately configured tool directory first, otherwise
this directory and its bin subfolder, then PATH for development installations.
It never downloads tools at runtime. A missing custom tool directory is reported.

The Windows build script uses the checksum-pinned Gyan FFmpeg 9.0.2 full shared
build and retains the upstream license and documentation alongside the binaries.
