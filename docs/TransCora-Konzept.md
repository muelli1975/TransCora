# TransCora – Entwicklungsgrundlage

Stand: 10. Oktober 2026. Planung, noch keine fertige Anwendung.

TransCora ist eine portable Python-GUI für batch-orientierte 3D-Video-, Bild- und Dateiformat-Konvertierung auf Basis bewährter FFmpeg-/FFBatch-Workflows. Das Projekt bleibt lokal, offline und portabel, ohne Cloud-/Account-Abhängigkeit, Tracking oder versteckte Online-Funktionen.

## Zuständigkeit

TransCora übersetzt Full-SBS-Material, Bildsequenzen, Einzelbilder, MPOs und L/R-Strukturen in praktische Zielformate. AnaChroma bleibt das Spezialwerkzeug für hochwertige Einzelbild-Anaglyphen und die große Verfahrensbibliothek. TransCora wird keine beliebige FFmpeg-GUI mit allen Schaltern.

FFmpeg ist die Haupt-Engine, ffprobe übernimmt die technische Analyse. ExifTool wird für spätere Bildfunktionen wie in der bestehenden Toolfamilie eingebunden. Pillow/OpenCV sind nur ergänzend für begründete Spezialfälle vorgesehen.

## Bedienung und verbindliche Ergänzungen

- Einzeldateien und frei zusammengestellte Dateilisten sind gleichwertige Eingabewege. Mehrfachauswahl und wiederholtes Hinzufügen aus unterschiedlichen Ordnern müssen möglich sein, etwa für gezielt ausgewählte Videos.
- Ordner und optional Unterordner werden in dieselbe Jobliste aufgelöst. Batchbetrieb setzt keinen Ordnerimport voraus.
- Technische Vorabprüfung, geplante Ausgabe, Warnungen, Jobstatus, Fortschritt, Abbruch und verständliches Log stehen im Mittelpunkt.
- Eine große visuelle Vorschau ist offen und kein Pflichtbestandteil.
- Die Oberfläche orientiert sich optisch und bedienlogisch an SplatTricia, StereoFine, AnaglyphBatch, Freeda und AnaChroma.
- Das gelieferte `transcora.ico` wird bytegetreu verwendet; geprüft sind 16, 24, 32, 40, 48, 64 und 256 Pixel. Der vorhandene Standardsound `assets/ready.wav` aus AnaChroma wird unverändert wiederverwendet.

Die Vorabprüfung zeigt unter anderem Container/Codec, Auflösung, SAR/DAR, Framerate, gewählten beziehungsweise belegten 3D-Typ, geplante Zielgröße, Container, Codec, Timing-Verhalten und technische Warnungen. Ein Job darf durch fehlende Angaben blockiert sein, ohne dass die gesamte Liste unbedienbar wird.

## Phasen

1. Vorhandene FFBatch-Parameter analysieren, feste und variable Parameter trennen, Presets und Jobmodell begründen.
2. Minimaler Video-Durchstich: Full-SBS zu Half-SBS/Half-OU/Mono, anschließend die 17 AnaglyphBatch-Verfahren ohne CIELab nach Referenzprüfung. Noch kein vorschneller Komplettcode.
3. Batchbetrieb vervollständigen: Dateilisten, Ordner, Rekursion, Strukturspiegelung, kollisionsfreie Namen, Abbruch, Fortschritt und Log.
4. Bild-/Dateiwerkzeuge: SBS-Konvertierung, MPO-Import/Split, L/R-Paarprüfung und Vorbereitung, ExifTool. MPO-Export hat keine Priorität.
5. Bildsequenzen, Diaschau-Workflows und zusätzliche Qualitäts-/Formatprofile nur bei begründetem Bedarf.
6. Blu-ray-3D/MVC als eigener Spezialmodus: FRIM, eventuell AviSynth und Authoring-/Muxing-Tooling prüfen; Timing, geeignete Frameraten und A/V-Synchronität sauber behandeln.

Die Grundfähigkeit zum Hinzufügen einzelner Dateien gehört bereits in das minimale GUI-Modell. Die Phasentrennung darf nicht dazu führen, dass zunächst ausschließlich ein Ordner-Workflow fest eingebaut wird.

## Formate und Timing

Die Oberfläche zeigt nur sinnvolle Kombinationen prominent. MP4/MKV und H.264 bilden die vorliegende Video-Referenz; H.265 und weitere Profile werden gesondert begründet. Übliche Bildformate, MPO-Split und eventuell HEIC/HEIF-Import gehören zu späteren Bildphasen. Moderne Formate wie AVIF/JPEG XL werden erst nach Prüfung des konkret verteilten Builds aufgenommen.

Framerate-Erhalt und jede spätere Konvertierung müssen ausdrücklich beschrieben werden. 24 fps ist kein globaler Zwang. 24/1 und 24000/1001 werden getrennt behandelt. Drop/Duplizieren, Geschwindigkeitsänderung und Interpolation sind unterschiedliche Methoden und dürfen nicht als versteckte Automatik vermischt werden.

Anaglyphenvideos benötigen ein bewusstes 4:4:4-Qualitätsprofil mit geprüftem Zielplayer. Höhere Bittiefe bleibt eine spätere offene Entscheidung. Pixelwandlung und Farbkennzeichnung müssen zusammenpassen.

## Portable Struktur und Entwicklung

Externe Programme werden klar getrennt unter dem obersten `tools/` geführt, zunächst `tools/ffmpeg/` mit ffmpeg/ffprobe und später `tools/exiftool/`. Interne Python-Module für Tool-Erkennung erhalten einen anderen Namen, zum Beispiel `core/toolchain.py`; ein zweiter gleichnamiger Binary-Ordner im Python-Paket ist unnötig. FRIM/AviSynth-Ordner werden erst bei der entsprechenden Phase angelegt.

GitHub ist der nachvollziehbare Entwicklungsstand. Änderungen werden mit konkreten Commits dokumentiert. Christoph soll möglichst wenig manuelle Arbeit an Dateien, Builds und Releases haben. Direkter Zugriff und tatsächliche Schreibresultate werden geprüft und nicht vorausgesetzt. Bei Einschränkungen werden vollständige Dateien beziehungsweise klare Patches geliefert. Builds/ZIPs/Releases erst nach verlässlicher Prüfung der Arbeitsumgebung.

AnaglyphBatch bestimmt die Verfahren, Matrizen, Berechnungsmodi, Kanal-LUTs und Suffixe; CIELab ist ausdrücklich ausgeschlossen. Bild- und Videoadapter verwenden dieselbe Verfahrensdefinition mit fachlich passender Transfer-/Farbwandlung. Alle Eingabewege nutzen dieselbe Job- und Konvertierungslogik. Originalparameter bleiben als Referenz erhalten. Die Analyse in `ffmpeg-Parameter-Auswertung.md` trennt die vorhandenen Workflows von vorgeschlagenen V1-Regeln. Es werden zunächst Dokumentation und Preset-Grundlage erstellt, noch keine Implementierung oder Release-Zusage.
