# TransCora 1.1 — development

[Deutsch](README_DE.md)

TransCora is a local desktop program for converting stereoscopic videos and images. It supports SBS, over/under, cross-view, anaglyphs and row-interleaved output for polarised monitors. On Windows, it also creates Blu-ray 3D ISO and AVC/MVC M2TS files. MPO files can be split into their two half-images without JPEG recompression. Videos and images have separate batch lists, settings and previews.

Everything runs locally, without an account, cloud or tracking. The interface can be switched between German and English.

![TransCora 1.0 video batch and output settings](docs/TransCora-1.0.png)

Row-interleaved image/video inputs and **Frame sequential** video inputs can now
be converted to the existing stereo or mono targets. L/R swap determines the first
half-image. Frame sequential pairs consecutive half-images before frame-rate
conversion; 120 individual frames/s represent 60 stereo pairs/s. An unpaired final
half-image is omitted. Choose an output layout for frame-sequential input.

The 1.1 development build reads **HEIC/HEIF** SDR images, including tagged stereo
HEIC and Spatial Photos. Stereo groups determine left/right assignment; depth
maps and gainmaps are not selected as a second half-image. Orientation and colour
profiles are respected. The existing image outputs and preview are available.
HDR tone mapping, HEIC output and MV-HEVC output are not released yet.

## Quick start

1. Open **Videos** or **Images** and add files or a folder. Enable **Include subfolders** if needed.
2. Select the files you want to process. Changes apply to the selected entries; without a selection, they set the defaults for new files.
3. Choose the source layout and output. Use **Swap L/R** if the half-images are reversed.
4. Choose the size and output folder. Use **Preview** to check the result before encoding; the preview has a fit view and a scrollable 1:1 pixel view.
5. Use **Test** to check the batch or **Start** to process it. Progress, duration and source frame rate are shown in the window.

The default output folder is `output` beside the program. Folder batches preserve relative subfolders. Existing files receive a numbered alternative name. A failed entry does not stop the remaining valid entries. **Cancel** stops the current operation; completed files remain available.

Video status shows estimated remaining time for the **file** and **batch**. Estimates use live progress and durations of comparable completed files. BD-3D also learns audio and mux finishing times; the first title has a coarser estimate. A dash indicates an unmeasured format or missing progress.

Videos and images share **Source**, **Output**, **Format** and **Save** sections. **Output size** shows dimensions beside the size menu. Video dimensions describe the complete output picture; BD-3D shows dimensions per half-image. Images can be scaled proportionally by their long or short edge.

**Advanced** expands additional settings inside the window. **Default settings** restores defaults for new files; existing entries keep their settings. In smaller windows, settings scroll while the file list, information area and processing buttons retain their space. Use **Choose** to select the output folder.

The current file remains visible beside progress information when the processing phase changes. Long filenames are shortened in the middle to fit the window.

Click a column heading to sort the file list in ascending or descending order. Frame rate and duration sort numerically; the visible order also applies to the next processing run. Input and output folders may be identical. Recursive imports skip a nested output subfolder.

## Video output

| Output | Use |
| --- | --- |
| Full-SBS / Full-OU | Two complete half-images, beside or above each other |
| Half-SBS / Half-OU | Compact stereo formats for compatible players and displays |
| Cross-view · Full-SBS R/L | Free-viewing: right half-image on the left, left half-image on the right |
| Anaglyph | Stereo through coloured glasses; 17 AnaglyphBatch methods |
| Mono | Export the selected left or right half-image as an ordinary video |
| Keep layout | Re-encode with the existing arrangement, optionally changing frame rate |
| Row-interleaved | Direct output for a compatible polarised monitor |
| BD-3D | Blu-ray 3D ISO or AVC/MVC M2TS: 1080p at 23.976 fps or 720p at 50/59.94 fps per half-image |

**MP4 is the default; MKV is selectable**, including cross-view. MKV carries the appropriate stereo metadata. Cross-view MP4 keeps the R/L picture arrangement without a misleading L/R marker. Player support varies; check the first output on the intended device.

### Resolution and cross-view

Choose **Original**, **1080p**, **2160p** or **Custom**. Automatic retains the reconstructed source size for full layouts and uses 1080p for half layouts. Custom width and height always describe the **complete output picture**. The aspect ratio is preserved, with borders when necessary.

| Example | Complete picture | Stored pixels per half-image |
| --- | --- | --- |
| Cross-view, 1080p per half-image | 3840 × 1080 | 1920 × 1080 |
| Cross-view, custom 1920 × 540 | 1920 × 540 | 960 × 540 |
| Half-SBS in UHD | 3840 × 2160 | 1920 × 2160 |
| Full-SBS with UHD per half-image | 7680 × 2160 | 3840 × 2160 |

Cross-view stays Full-SBS at every size: the half-images are scaled proportionally rather than squeezed to half width. A larger output cannot restore details missing from the source. For free cross-viewing, show both images together in ordinary 2D mode; disable any automatic stereo conversion in the player.

### Frame rate, quality and audio

Frame rate normally stays unchanged. Choose **Target frame rate** to enter a value, including 23.976, 25, 30, 50, 59.94 or 60 fps. Resolution, stereo conversion and frame rate can be changed in the same export. Duration is retained; this duplicates or removes complete stereo frames rather than generating interpolated motion.

Temporal interlaced sources are converted to progressive pictures while retaining field timing: for example, 25 interlaced frames / 50 fields become 50 progressive frames per second. An explicit target rate can then change that rate.

Under **Advanced**, select H.264 or H.265 (MKV), CRF quality or a target bitrate. Anaglyph quality modes use 4:4:4 colour; a 4:2:0 compatibility mode is available for players that need it. Row-interleaved video uses 4:4:4 to preserve the separate rows of the half-images.

**Audio options** select all tracks, individual tracks or no audio. Keep the original audio, convert to AAC, or downmix to stereo. For BD-3D, audio options and bitrate are grouped under **Advanced**, in separate video and audio rows. BD-3D uses LPCM audio; **Output size per half-image** selects 1080p/23.976, 720p/50 or 720p/59.94. The 720p modes offer smoother motion from suitable sources at lower spatial resolution. Complete stereo pairs are dropped or repeated as needed, without motion interpolation; duration and audio are retained (only 24 → 23.976 is slowed by 0.1%). Its selectable total AVC/MVC target bitrate is 20–40 Mbit/s, with a factory default of 40 Mbit/s.

## Polarised monitors

Choose **Row-interleaved** for either videos or images. Enter the monitor's native width and height, initially 1920 × 1080, and select which half-image supplies the first screen row. Rows from the left and right half-images alternate.

Display the result at the exact native resolution, full screen, with no scaling or second stereo conversion. If depth is reversed, switch the half-image assigned to the first row. Lossless PNG is recommended for images. An existing 1920 × 1080 Half-OU/abq image already has 1920 × 540 pixels per half-image and can be woven directly for a Full-HD monitor.

## Images and MPO

Read JPEG/JPS, PNG/PNS, TIFF, BMP, WebP and MPO containing two half-images. Convert to SBS, over/under, anaglyphs, individual half-images or row-interleaved output. Save JPEG, PNG, TIFF or lossless WebP. Image sizes include Original, 1080p, 2160p, 2048 pixels on the long edge and custom long/short edge.

**Split MPO losslessly** writes the two original JPEG half-images as `_l.jpg` and `_r.jpg`, without recompression. This also handles Fujifilm camera padding. Image anaglyphs offer the 17 video methods plus **CIELAB Least Squares**. JPEG normally uses quality 90 with 4:4:4, optionally 95.

Orientation and colour profiles are applied when converting images. Optional metadata copying retains capture dates and suitable EXIF/XMP/IPTC fields. PNG, TIFF and WebP can retain transparency when keeping the layout.

## Sources, lists and presets

Packed Full/Half SBS and OU are supported. Automatic source detection uses stereo metadata or an unambiguous filename marker. If the source is ambiguous, choose its layout manually. Common player suffixes include `-lr`, `-rl`, `-lrh`, `-rlh`, `-ab`, `-ba`, `-abq` and `-baq`.

Windows can also read unencrypted MVC/Blu-ray 3D and SDR MV-HEVC sources. Reading a Blu-ray ISO selects its main stereoscopic playlist. The program does not remove copy protection. HDR conversion, animated/multipage images and 16-bit image conversion are outside version 1.0.

Save lists to resume a batch with its per-file settings. Lists contain paths and settings, not the media itself. Save **Presets** to reuse conversion settings. Language and chosen folders are remembered locally.

Shortcuts: **Ctrl+O** adds files; **Ctrl+A** selects the list; **Ctrl+click** selects individual entries; **Shift+click** selects a range; **Delete** removes selected entries; **Esc** cancels the active operation. On macOS use **Command** for opening files, selecting all and selecting individual entries.

## Portable builds and source

Download a package from [Releases](https://github.com/muelli1975/TransCora/releases/latest) and extract the complete archive into a writable folder.

| System | Package | Start |
| --- | --- | --- |
| Windows x64 | `TransCora_1.0_Windows_x64.zip` | `TransCora.exe` |
| Linux x64 | `TransCora_1.0_Linux_x64.tar.gz` | `./TransCora` |
| macOS Apple Silicon | `TransCora_1.0_macOS_AppleSilicon.tar.gz` | `TransCora.app` |

Windows includes Python, FFmpeg and the BD-3D tools. Linux and macOS include the application runtime and image tools; **FFmpeg with ffprobe and system Perl must be installed separately**. On Ubuntu/Debian: `sudo apt install ffmpeg perl`. On macOS with Homebrew: `brew install ffmpeg@7`. macOS packages are ad-hoc signed and not notarised.

Keep the supplied application files and tools together. No separate Python installation is needed for these packages. Blu-ray 3D encoding is available in the Windows package. The Linux package also includes the MVC reader; the Apple Silicon package currently supports packed stereo and ordinary video input, without an MVC reader.

Release packages include the matching application source. Build instructions: [BUILD.md](BUILD.md). Detailed format notes: [technical reference](docs/TECHNICAL_REFERENCE.md).

## License

Copyright Christoph Müller. TransCora uses the MIT License; supplied third-party tools retain their own licences. See [LICENSE](LICENSE) and [THIRD_PARTY.md](THIRD_PARTY.md).
