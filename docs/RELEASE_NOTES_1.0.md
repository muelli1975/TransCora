# TransCora 1.0

- Eigene Bereiche **Videos** und **Bilder** mit unabhängigen Dateilisten,
  Auswahl-Einstellungen, Voreinstellungen, Kontrollbild, Testen, Start und Abbruch.
- Bilder: JPEG, PNG, TIFF, BMP, WebP, JPS/PNS und MPO als Quellen; JPEG, PNG,
  TIFF und verlustfreies WebP als Ausgabe. JPEG mit Qualität 90/95 und 4:4:4.
- MPO mit zwei Halbbildern verlustfrei in selbständige JPEGs teilen. Der
  obsolete MPO-Index wird entfernt, die komprimierten JPEG-Bilddaten bleiben erhalten.
- Stereo-Bilder: Full-/Half-SBS und Full-/Half-OU, Anaglyphen mit allen 17
  Batch-Verfahren sowie linkes/rechtes oder beide getrennte Halbbilder.
- L/R-Paare anhand von _l/_r beziehungsweise Ordnern L/R prüfen und unverändert
  in nummerierte L/R-Ausgabeordner kopieren. Fehlende oder doppelte Halbbilder blockieren den Start.
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
