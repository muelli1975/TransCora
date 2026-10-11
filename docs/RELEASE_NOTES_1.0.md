# TransCora 1.0

## RC5

- Lossless MPO splitting accepts the zero padding included in Fujifilm camera image sizes. Embedded JPEG pixels and compressed data remain unchanged; missing JPEG end markers or truncated ranges still fail.
- Lossless MPO splitting no longer requires matching dimensions or EXIF orientations. Those checks apply only when composing a stereo image.
- MPO splitting preserves each JPEG's original metadata without an unnecessary ExifTool rewrite; right-eye orientation and camera fields are no longer overwritten with left-eye values.
- Missing SDR colour descriptions use explicit existing hints or customary HD/PAL/NTSC defaults, with visible assumptions instead of rejecting usable sources. Full-OU defaults use the height of one eye.
- Explicit source layout selections override unsupported stereo metadata. Half-SBS/OU with matching stretched pixel ratios no longer requires redundant metadata.
- MV-HEVC checks the actual decoded eye pairs without rejecting them solely because of a container frame-count field. MVC no longer has an arbitrary two-million-frame input limit.
- BD-3D accepts any positive source frame rate that FFmpeg can convert. Conservative free-space estimates and missing duration metadata no longer block encoding; actual output validity checks remain.

## RC4

- BD-3D accepts valid variable frame timing and timestamp jitter. Complete stereo pairs are adjusted to the fixed output clock during the single encoding pass; long frame holds retain their presentation duration.
- Differing nominal and average source frame rates no longer trigger an automatic rejection. Constant 24 fps keeps the established 0.1% video/audio slowdown.
- Source checks reject missing, invalid or non-increasing timestamps. Fixed output timing, encoded pictures, muxed audio and both decoded MVC views remain verified.
- Removed the permanent technical frame-rate conversion sentence from the interface. File-specific conversion details remain under Test.
- BD-3D time remaining now refers explicitly to the current step. Encoding and final decoding use their own progress; estimates reset between steps instead of extrapolating from arbitrary overall percentage ranges.

## RC3

- Complete German/English interface with immediate switching and a saved language preference.
- Video/image tabs now use the shared Nachtgold palette, including selected, hover and disabled states.
- Images use the same `output` default, filename display, preset menu and selection scope as videos.
- Ctrl+A, Ctrl+click and Shift+click select all, individual entries and a range. Changes affect every selected entry.
- Image sizes follow AnaChroma: Original, 1080p, 2160p, 2048 long edge and Custom with long/short edge in pixels.
- Preview requires exactly one selected file. Video and image previews retain output-resolution pixels and offer fit or scrollable 1:1 display in a dark window.
- Keeping an image layout retains the source filename. Stereo and anaglyph conversions use descriptive suffixes; collisions never overwrite existing files.
- Removed L/R pair preparation. Lossless MPO splitting retains the embedded JPEG data, with `_l.jpg` and `_r.jpg` filenames.
- Temporary PNG compression and a second JPEG Huffman pass were removed to reduce avoidable preview/export work without changing decoded JPEG quality.
- Added cross-view video: Full-SBS with right half-image first, MKV StereoMode R/L and a `-rl` filename marker.
- Added image-only CIELAB Least Squares using AnaChroma's native, hash-pinned solver and recorded AnaglyphBatch reference checks. Lanczos resizing precedes the iterative solver; orientation, ICC and ExifTool handling remain shared.
- Regular image transformations retain the tested FFmpeg engine. A local 24 MP comparison showed different timing by method, rather than a general advantage for replacing it with Python/NumPy.

## Existing 1.0 features

- Eigene Bereiche **Videos** und **Bilder** mit unabhängigen Dateilisten,
  Auswahl-Einstellungen, Voreinstellungen, Kontrollbild, Testen, Start und Abbruch.
- Bilder: JPEG, PNG, TIFF, BMP, WebP, JPS/PNS und MPO als Quellen; JPEG, PNG,
  TIFF und verlustfreies WebP als Ausgabe. JPEG mit Qualität 90/95 und 4:4:4.
- MPO mit zwei Halbbildern verlustfrei in selbständige JPEGs teilen. Der
  obsolete MPO-Index wird entfernt, die komprimierten JPEG-Bilddaten bleiben erhalten.
- Stereo-Bilder: Full-/Half-SBS und Full-/Half-OU, Anaglyphen mit allen 17
  Batch-Verfahren sowie linkes/rechtes oder beide getrennte Halbbilder.
- Bildorientierung und ICC-Farbprofile werden vor einer Wandlung berücksichtigt.
  ExifTool übernimmt EXIF/XMP/IPTC, darunter Aufnahmezeiten, ohne eingebettete
  Vorschaubilder. Geänderte Bilder erhalten passende Orientierung; Dateizeiten bleiben erhalten.
- Videos zusätzlich als Full-SBS und Full-OU in rekonstruierter Quellauflösung ausgeben.
  Half → Full ist verfügbar und weist auf Hochskalierung ohne neue Bilddetails hin.
- Matroska-Half-Ausgaben erhalten neben StereoMode die korrekte Geometrie je
  Halbbild. Diese Ausgaben können erneut automatisch importiert werden.
- Weitere sView-Dateikürzel und WMV-Stereometadaten erkennen.
- MVC-Aufbereitung erhält native BT.709-/1080p-Halbbilder pixelgenau, ohne den
  bisherigen YUV/RGB/YUV-Umweg. Die abschließende Dekodierungsprüfung bleibt erhalten.
- MVC-Encoding: 40/40 Mbit/s, strikte GOP 24/4, CPB 3750 KB und maximal vier
  gepufferte Bilder; qualitätsorientierte FRIM-Stufe `-u 1`.
- Portable Ausgabe einschließlich passendem Anwendungscode und ExifTool samt
  Original-Supportdateien; Icon und Bereitschaftston bleiben unverändert.

## Grenzen

HDR, Interlaced-Quellen, animierte/mehrseitige Bilder, 16-Bit-Bilder und unabhängige
L/R-Videospuren sind nicht freigegeben. StereoMode enthält keine direkte
Full-/Half-Angabe; ohne eindeutige Metadaten oder Dateikürzel ist eine manuelle
Quellwahl nötig. Anaglyphen bekommen keine zusätzliche spezielle Stereo-Kennzeichnung.

Für eine 3D-Diaschau wurden Flackern und Kompressionsartefakte in der MVC-Ausgabe
gemeldet. Der Vergleich mit dem bereitgestellten Quellausschnitt läuft; eine
vollständige Fehlerbehebung ist noch nicht bestätigt. Die technische Abschlussprüfung
erkennt Dekodierungs-, Halbbild- und Verpackungsfehler, bewertet aber nicht die Bildqualität.
