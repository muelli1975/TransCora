# TransCora 1.1

- Image fitting for 1080p/2160p: proportional scaling, black bars or a centred crop, applied equally to both half-images and shown in the control preview.

- Dual video input/output: separate left/right tracks in MP4 or MKV, with size per half-image, audio options and L/R swap.
- BD-3D and Dual control previews show both half-images as parallel, cross-view or red/cyan anaglyph.
- Filename suffix menus identify Kodi, Bino and Stereoscopic Player. Labels stay out of filenames; combined suffix suggestions have been removed.
- Batch remaining time uses a duration-weighted processing average, including mixed settings, file transitions and delayed progress updates.
- Completed-job processing times, completion journal, remove-completed actions and pause-after-file control.
- Optional close or computer shutdown after a successful video/image batch; cancellable 30-second shutdown countdown and session-only selection.
- Neutral control-preview hint for both BD-3D and Dual.
- Completed-file details display stereo information and the output path once.
- The information field omits the inapplicable "no SBS/OU flag" note for outputs such as anaglyph and mono.
- Row-interleaved output labels the first-row selection as "Left half-image" or "Right half-image" in both video and image tabs.
- Selectable mono half-image, row-interleaved inputs and frame-sequential half-image pairing.
- SDR HEIC/HEIF input, including tagged stereo images and Spatial Photos, with orientation and colour-profile handling.
- Neutral routine messages; highlighted warnings reserved for required decisions and errors.
- MV-HEVC input decodes both half-images.

Platform capabilities and external FFmpeg requirements are described in the README.

