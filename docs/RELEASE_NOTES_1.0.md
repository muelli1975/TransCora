# TransCora 1.0

## Video export

- MP4 remains the default. Cross-view Full-SBS R/L can use MP4 or MKV; MKV stores native right-eye-first StereoMode. MP4 omits stereo flags that would misidentify the eye order.
- Size selection: Standard, Original, 1080p, 2160p and Custom. Full layouts retain reconstructed source size by default. Custom width and height describe the complete output picture for every layout. Cross-view 1080p is 3840 Ã— 1080 total; custom 1920 Ã— 540 preserves two proportional 960 Ã— 540 eyes. Actual MP4/MKV raster, square pixels, eye order and round-circle geometry are tested.
- Optional frame-rate conversion is available with every regular video target, in the same encoding pass as layout and resizing. Source timing is preserved by default. The former standalone frame-rate target is now Keep layout. Earlier saved frame-rate jobs retain their selected conversion.
- Frame-rate changes drop or repeat complete stereo pairs without blending or motion interpolation. Audio and playback duration remain unchanged. Fractional NTSC choices use exact rational rates.
- Interlaced sources are deinterlaced per eye with BWDIF at field rate. 25 interlaced frames/50 fields can become 50 progressive frames. Explicit target rates and BD-3D adapt the common pair sequence afterwards.
- MKV writes native stereo arrangement/order and appropriate eye-display geometry. H.264 L/R SBS and OU also carry Frame-Packing SEI 3 and 4. MP4 SBS/OU uses an explicit st3d box.
- Source fps and duration columns remain visible after output-option changes. Updated status border and version display.

## Polarised monitor output

- Row-interleaved output is available for both images and videos. Default screen dimensions are 1920 Ã— 1080; width, height and first-row eye assignment are adjustable and saved per job/preset.
- Each eye is fitted to its final per-eye screen grid before weaving. Matching 1920 Ã— 1080 Half-OU/abq images are reordered without resampling or pixel changes. Other sizes use Lanczos, with aspect-preserving borders.
- Images initially use lossless PNG; videos use 4:4:4 colour to keep adjacent eye rows separate. MKV writes native row-interleaved StereoMode; H.264 left-first also writes Frame-Packing 2. MP4 preserves the physical rows without misleading SBS/OU metadata.
- Direct playback requires native screen resolution, full screen and no rescaling, overscan or second stereo conversion. Actual monitor eye order must be checked on the device. Row weaving is separate from temporal interlacing.

## Blu-ray 3D and practical validation

- BD-3D exports 1080p AVC/MVC at 24000/1001 fps to ISO or M2TS with LPCM audio. Constant 24 fps uses the established 0.1% video/audio slowdown.
- Select aggregate AVC/MVC target/max bitrate: 20, 25, 28, 30, 35 or 40 Mbit/s; default 40. The quality-oriented FRIM stage, strict GOP 24/4, CPB 3750 KB and bounded DPB remain.
- Valid variable source timing, timestamp jitter, differing nominal/average rates, missing duration and uncertain free-space estimates do not alone block usable sources. Output timing and stereo-pair synchronisation remain checked.
- Concrete missing/non-finite/non-increasing source timestamps, decoder errors or invalid generated output still fail with a specific reason. Generated-output cadence errors are distinguished from source timing.
- Final validation checks encoded pictures, ISO/M2TS structure, muxed audio and both decoded MVC views. Time remaining refers to the current export phase.
- The previously pinned tsMuxeR remains. Version 2.7.0 passed variable-timing trials but failed the independent ISO structure check in the comparison workflow; it is not substituted without a passing full export check.

## Images and existing features

- Separate video/image lists, selected-job settings, saved presets, preview, test, start and cancellation. German/English switching and saved language preference; shared Nachtgold styling.
- Image inputs include JPEG, PNG, TIFF, BMP, WebP, JPS/PNS and two-eye MPO. Outputs include JPEG at quality 90/95 with 4:4:4, PNG, TIFF and lossless WebP.
- Full/Half SBS and OU, anaglyphs using all 17 AnaglyphBatch methods, image-only native CIELAB Least Squares, and separate eye exports. Original, 1080p, 2160p, 2048-long-edge and custom image sizing.
- Lossless MPO splitting follows actual JPEG frame boundaries, tolerates Fujifilm zero padding and inaccurate size fields, and preserves each eye's compressed pixels and original metadata. Only genuinely truncated data fails. MPO-only batches need no FFmpeg.
- Image batches isolate file errors and continue with valid entries while retaining collision-free output names.
- Orientation and ICC profiles are handled before conversion. ExifTool retains relevant EXIF/XMP/IPTC and capture dates; output orientation and filesystem times are preserved.
- MVC and SDR MV-HEVC decode both actual views. No arbitrary MVC frame-count limit or rejection based only on an unreliable container count. Explicit packed layouts override unsuitable stereo metadata; ordinary missing SDR tags use visible colour assumptions.
- Portable Windows package contains application code, verified tools and ExifTool support files. The application works locally without an account, tracking or runtime network access.

## Platform packages

Windows x64 includes all required runtimes and the BD-3D encoder. Linux x64 and macOS Apple Silicon include the application runtime, CIELAB and ExifTool; FFmpeg/ffprobe and Perl are installed separately. Linux includes the independent MVC decoder. Apple Silicon currently supports packed stereo and ordinary video input without an MVC decoder. Native Linux/macOS BD-3D encoding is not released; this is a limitation of the current FRIM integration, not a general restriction of Blu-ray 3D.

## Limits

HDR conversion, animated/multipage images, 16-bit image inputs, temporal interlaced export and independent L/R video tracks are outside this release. Ambiguous packed layouts require an explicit source selection. Higher output sizes cannot recreate details missing from Half sources. Hardware support for 4:4:4 video varies.

Reported flicker/compression artefacts in a 3D slideshow remain a visual-quality investigation. Structural verification detects decoding, view and packaging failures; it does not measure perceived image quality or certify playback on every monitor/player.
