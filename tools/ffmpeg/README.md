# FFmpeg / ffprobe

Portable Windows builds place FFmpeg, ffprobe and their runtime libraries here.
The portable application locates this directory and its bin subfolder relative
to its executable. No external tool selection or saved absolute path is required.
Only Python source runs may fall back to PATH for development installations.
It never downloads tools at runtime. Missing bundled tools are reported as an
incomplete installation.

The Windows build script uses the checksum-pinned Gyan FFmpeg 9.0.2 full shared
build and retains the upstream license and documentation alongside the binaries.
