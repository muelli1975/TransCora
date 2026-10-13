# TransCora 1.0

Portabler, lokaler Konverter für 3D-Videos und Bilder mit Python-Oberfläche und FFmpeg.
Videos und Bilder haben eigene Listen und Einstellungen. BD-3D-Ausgabe als ISO/M2TS,
MPO-Teilung und Bildkonvertierung sind enthalten.
Deutsch/English lässt sich in beiden Bereichen umschalten; die Sprachwahl wird gespeichert.
Kein Account, Tracking oder Netzwerkzugriff im Programm.

## Bilder verarbeiten

Im Bereich **Bilder** Dateien oder Ordner hinzufügen, gewünschte Einträge auswählen
und die Aufgabe festlegen. Einstellungen gelten für die markierten Dateien; ohne
Auswahl für neu hinzugefügte Dateien. Strg+A markiert alle Dateien, Strg+Klick einzelne
Dateien und Umschalt+Klick einen Bereich. **Testen** prüft den gesamten Stapel vor dem Start; **Details**
zeigt Quellinterpretation, Ausgabeziele und Hinweise. **Kontrollbild** hilft bei der
Prüfung der Halbbildreihenfolge und ist für genau eine Datei verfügbar. Die Kontrolle
zeigt das Exportergebnis mit Fensteranpassung oder scrollbarer 1:1-Ansicht. Beide Bereiche
verwenden standardmäßig `output`. Bei „Layout beibehalten“ bleibt der Dateiname erhalten;
Namenskonflikte bekommen eine Nummer. Listen und eigene Voreinstellungen sind speicherbar.

- **Bilder konvertieren:** JPEG/JPS, PNG/PNS, TIFF, BMP, WebP und MPO als Quellen;
  JPEG, PNG, TIFF oder verlustfreies WebP als Ausgabe. Layout beibehalten,
  Full-/Half-SBS, Full-/Half-OU, Anaglyph oder einzelne Halbbilder wählen.
- **MPO verlustfrei teilen:** Genau zwei JPEG-Halbbilder extrahieren, mit `_l`/`_r`
  benennen und den obsoleten MPO-Index entfernen. Keine JPEG-Neukodierung und
  keine Größenänderung; EXIF-Orientierung bleibt für die ungedrehten Pixel passend.
- **Größe:** Original, 1080p, 2160p, 2048 lange Seite oder Benutzerdefiniert mit
  langer/kurzer Seite in Pixeln, wie in AnaChroma. Das Seitenverhältnis bleibt erhalten.
  Beim Teilen gilt die Größe je Halbbild; bei SBS/OU für das gepackte Ausgabebild.
  Größere Vorgaben skalieren hoch, ohne neue Details zu erzeugen.
- **CIELAB Least Squares:** Zusätzliches Anaglyphenverfahren für Bilder, mit demselben
  nativen Werkzeug und Solver wie AnaChroma. Die Halbbilder werden in sRGB vorbereitet
  und bei Größenänderung mit Lanczos vor der iterativen Berechnung skaliert. Die
  iterative Berechnung kann deutlich länger dauern als die Matrixverfahren.
- JPEG: Qualität **90** (optional 95), **4:4:4**.
  PNG/TIFF/WebP erhalten Transparenz beim Beibehalten des Layouts. JPEG und
  Stereo-Transformationen setzen transparente Bereiche auf Weiß.
- Bei einer Wandlung EXIF-Orientierung anwenden und eingebettete ICC-Profile
  nach sRGB wandeln. Ohne Profil sRGB annehmen. Optional EXIF/XMP/IPTC mit
  ExifTool übernehmen, einschließlich Aufnahmezeiten, ohne eingebettete
  Vorschaubilder/Thumbnails oder veraltete Größen. Dateizeiten bleiben erhalten.
- JPS/PNS ohne eindeutiges Kürzel werden als Full-SBS mit rechtem Halbbild zuerst
  angenommen; MPO als erstes Halbbild links. Reihenfolge im Kontrollbild prüfen.
  Für gewöhnliche JPG/PNG mit Stereo-Inhalt das Quelllayout bewusst wählen.

Animierte/mehrseitige Bilder, MPO mit mehr als zwei Halbbildern sowie 16-Bit-/HDR-
Bilder sind nicht freigegeben. Bildsequenzen, Diaschau-Erstellung und L/R → SBS
sind spätere Erweiterungen.

## Windows starten

Der [GitHub-Build](https://github.com/muelli1975/TransCora/actions/workflows/build.yml)
testet die Anwendung und erstellt das Artefakt **TransCora-Windows** mit
`TransCora.zip` und SHA256-Prüfsumme. Actions-Downloads verlangen eine GitHub-Anmeldung;
das Programm selbst benötigt keine Anmeldung.

`TransCora.zip` vollständig entpacken und `TransCora/TransCora.exe` starten.
Python/Tk und die externen FFmpeg-Tools sind enthalten. Keine Installation nötig.
Der gesamte Ordner muss zusammenbleiben und sollte beschreibbar sein.

## Ein erster Job

1. **Dateien hinzufügen:** einzelne oder mehrere Videos auswählen. Wiederholtes
   Hinzufügen ermöglicht Listen aus unterschiedlichen Ordnern. Alternativ
   **Ordner hinzufügen**, optional mit **Unterordner mitverarbeiten**. Die relative
   Ordnerstruktur wird automatisch unter dem Ausgabeordner erhalten.
2. Die gewünschten Listeneinträge auswählen. Einstellungen gelten für die Auswahl
   und als Vorgabe für neue Dateien. Leere Auswahlfelder bedeuten gemischte Werte;
   eine Änderung setzt nur dieses Feld für alle ausgewählten Jobs.
3. Für die bisherigen Workflows **Full-SBS** als Quelllayout wählen. Automatisch
   akzeptiert eindeutige unterstützte Dateikürzel oder passende Stereo-Metadaten
   mit Full-/Half-Geometrie, keine reine Auflösungsheuristik.
4. Ziel und Container wählen. **Testen** zeigt technische Daten, Ausgabe und Warnungen.
   **Start** prüft erneut und verarbeitet alle noch offenen, gültigen Jobs.
   Blockierte Dateien erscheinen mit Fehlergrund; gültige Jobs laufen weiter.
5. Standardausgabe: `output` im TransCora-Ordner. Ein anderer gewählter Ordner wird
   gemerkt. **Abbrechen** beendet den Prozess und verwirft dessen begonnene Ausgabe.
   Bereits fertige Dateien bleiben erhalten.

**Liste speichern/laden** speichert Pfade und Jobeinstellungen, keine Videodateien.
Geladene Listen ergänzen die aktuelle Liste. Doppelte Quellen werden nicht erneut
hinzugefügt. Mehrere Ausgabevarianten derselben Quelle lassen sich in getrennten
Durchläufen erstellen. Fertige Jobs laufen erst nach bewusster Einstellungsänderung erneut.

## Ausgabe und optionale Namen

| Ziel | Verhalten |
| --- | --- |
| Full-SBS | Zwei vollständige Halbbilder nebeneinander, rekonstruierte Quellauflösung |
| Full-OU | Zwei vollständige Halbbilder übereinander, rekonstruierte Quellauflösung |
| Half-SBS | 1920 × 1080, links/rechts gepackt |
| Half-OU | 1920 × 1080, links oben/rechts unten |
| Anaglyph | Volle rekonstruierte Auflösung eines Halbbildes; 17 AnaglyphBatch-Verfahren |
| Mono | Linkes Halbbild; mit **L/R tauschen** das andere Halbbild |
| BD-3D · 1080p | AVC/MVC, 1920 × 1080 pro Halbbild, 23,976 fps; ISO oder M2TS |
| Layout beibehalten | Gepacktes Layout, Halbbildreihenfolge, Auflösung und YUV-Farbaufteilung erhalten; Bildrate optional ändern |
| Zeilenverschachtelt (Polfilter) | Exakte Monitorauflösung, abwechselnde Zeilen für linkes/rechtes Auge, 4:4:4 |

Standardmäßig passen Half-SBS/OU jedes Halbbild unter Erhalt seines Seitenverhältnisses in 1920 × 1080
ein, ergänzen bei Bedarf schwarze Ränder und halbieren danach die Packachse.
Full-Ausgaben erhalten die rekonstruierte Auflösung je Halbbild. Half → Full
skaliert die gestauchte Achse hoch und gewinnt keine verlorenen Bilddetails zurück.
Die Videogröße ist als **Standard / Original / 1080p / 2160p / Benutzerdefiniert** wählbar.
Standard behält die bisherigen Größen bei. Original verwendet die rekonstruierte
Quellgröße je Auge. Benutzerdefinierte Maße gelten bei allen Videoausgaben für
das Gesamtbild. Kreuzblick mit 1920 × 540 enthält zwei unverzerrte 960 × 540-Augenbilder. Half-SBS in UHD bedeutet
3840 × 2160 gesamt, Full-SBS mit UHD je Auge 7680 × 2160 gesamt.
Eine größere Ausgabe stellt keine verlorenen Quelldetails wieder her.

Full-/Half-SBS und Full-/Half-OU sind mögliche Quellen. Zusätzlich werden progressive
H.264-MVC- und SDR-MV-HEVC-Quellen mit zwei vollständigen Halbbildern verarbeitet.
Anaglyphen, Frame-sequential und unabhängige Videospuren sind keine unterstützten Quellen.

**Dateinamenszusatz · frei editierbar** bietet zum Ziel passende konkrete Zusätze,
**Keiner** und eigene Eingaben. Darunter steht unmittelbar der vollständige
**Ausgabename** der ausgewählten Datei; erkannte Kollisionen werden berücksichtigt.

| Ziel | Vorgegebene Zusätze (Auswahl) |
| --- | --- |
| Half-SBS | `_half_sbs`, `-lrh`, `-lrq`, `.3D.HSBS`, `.3D.HSBS-lrh` |
| Half-OU | `_half_ou`, `-tbh`, `-abq`, `.3D.HTAB`, `.3D.HTAB-tbh` |
| Anaglyph | Zusatz des gewählten Batch-Verfahrens, etwa `_dubois_lcd` |
| Mono | `_mono_l`, `-2d` |
| Layout beibehalten | Standard etwa `_30fps-tbh`; passende Layout-Kürzel und eigene Zusätze |

Erkannte alte Stereo-Kürzel werden entfernt, unbekannte Zusätze bleiben erhalten.
Auch TransCoras eigene `_full_sbs`, `_half_sbs`, `_full_ou` und `_half_ou` werden
beim Import erkannt. Player-Kürzel helfen der Layout-Erkennung, garantieren jedoch
keine Codec-Unterstützung. Stereoscopic Player kann das Layout auch manuell wählen.

Anaglyphen verwenden standardmäßig die **AnaglyphBatch-Zusätze**, etwa
`Film_dubois_lcd.mkv` oder `Film_rendepth2.mp4`. Eigene Zusätze sind möglich.
Vorhandene Dateien werden nicht überschrieben. Kollisionen werden vor dem Zusatz
nummeriert, z. B. `Film_2_dubois_lcd.mkv`; auch nachträglich angelegte Ziele sind geschützt.

## Qualität, Timing und Farbe

- Standard: **H.264 / MP4, CRF 18, slow**; alternativ MKV.
- Anaglyph-Standard: **8 Bit / 4:4:4**. Nicht alle Player/Hardwaredecoder unterstützen
  4:4:4. Optional **Hohe Farbtiefe · 10 Bit / 4:4:4**, ebenfalls mit eingeschränkter Player-Unterstützung.
  Feinere Abstufungen machen eine 8-Bit-Quelle nicht zu HDR.
- **8 Bit / 4:2:0** ist der Anaglyph-Kompatibilitätsmodus. Die verringerte Farbauflösung
  lässt Farbdetails und farbige Kanten sichtbar leiden. Für hochwertige Anaglyphen wird 4:4:4 empfohlen. Layout-/Mono-Ausgaben verwenden 8 Bit / 4:2:0.
- **Erweitert:** H.265/HEVC ausschließlich in MKV sowie frei einstellbare CRF oder
  durchschnittliche Zielbitrate in Mbit/s. CRF ist codecabhängig; Zielbitrate bedeutet
  kein garantiertes Dateigrößenlimit. Nur das zum gewählten Modus passende Feld ist
  sichtbar; beide Werte bleiben beim Umschalten erhalten. Startwert der Zielbitrate:
  **20 Mbit/s = 20.000 kbit/s**. Kein beliebiges Encoder-Menü.
- Bei Layout-/Anaglyph-/Mono-Konvertierungen bleibt das Quell-Timing erhalten,
  auch variable Framerate. Container können Zeitstempel auf ihre eigene Genauigkeit
  runden. Bei allen normalen Videozielen lässt sich optional eine konstante **Zielbildrate** wählen. Standard ist **Quelle beibehalten**; gültige variable Bildzeiten bleiben dann erhalten. Die Bildratenwahl und die Layout-/Größenwandlung erfolgen in einem Kodierdurchlauf. BD-3D verwendet weiterhin seine feste Bildrate.
  Eingaben `23,976`, `29,97` und `59,94` stehen für die exakten Brüche
  `24000/1001`, `30000/1001` und `60000/1001`; `24`, `30`, `60` bleiben ganze Raten.
  Andere Zahlen und Brüche sind frei eingebbar (1–240 fps).
- Eine Halbierung wie 60 → 30 oder 59,94 → 29,97 behält jedes zweite ganze Bild,
  beide Augen bleiben zeitlich zusammen. Andere Änderungen lassen Bilder aus oder
  wiederholen sie; keine Überblendung, Bewegungsinterpolation oder Tonverlangsamung.
  Wiedergabegeschwindigkeit und Audio-/Video-Versatz bleiben erhalten; die Enddauer
  kann um höchstens die Rasterung eines Zielbildes abweichen.
  Der Ton wird kopiert, das Video muss neu kodiert werden. Quell-YUV-Farbkennzeichnung,
  Farbaufteilung, Bit-Tiefe und Pixelseitenverhältnis bleiben erhalten, soweit der
  gewählte Encoder sie unterstützt. RGB benötigt eine gekennzeichnete YUV-Wandlung.
  Mono/2D ist für diesen Zweck als Quelllayout verfügbar.
- Unterstütztes SDR wird anhand seiner Farbkennzeichnung tatsächlich nach
  sRGB/16-Bit-RGB für die Batch-Verfahren umgerechnet und anschließend nach
  BT.709-YUV konvertiert und gekennzeichnet; keine bloße Änderung der Farb-Tags.
- Vorhandene Farbkennzeichnungen werden beachtet. Fehlende Farbangaben werden bei
  plausiblen HD-SDR-Quellen automatisch ergänzt (BT.709 für YUV, sRGB für RGB).
  SD/Legacy-Quellen mit unvollständigen Angaben und explizit nicht unterstützte
  Farbräume werden mit Hinweis blockiert. Der Wertebereich wird getrennt behandelt:
  vorhandene Angaben haben Vorrang, RGB/JPEG-YUV verwendet bei fehlender Kennzeichnung
  Vollbereich, gewöhnliches YUV den üblichen begrenzten Videobereich. Jede Annahme
  steht unter **Testen** und im Log. Eine fehlende Kennzeichnung lässt sich nicht
  anhand der Auflösung beweisen; die Kontrollbild-/Player-Prüfung bleibt sinnvoll.
  Erkannte HDR-Quellen werden nicht automatisch umgewandelt. Nicht unterstützte nichtquadratische Pixel,
  Rotation und VR-Projektion werden in dieser Version mit Hinweis blockiert.
- Unter **Erweitert → Tonoptionen** kann Ton im Original übernommen oder als AAC ausgegeben werden.
  Alle Tonspuren, ausgewählte Spurnummern oder kein Ton sind wählbar. Die Kanalzahl
  bleibt standardmäßig erhalten; Stereo-Downmix muss ausdrücklich gewählt werden.
  Für MP4 inkompatiblen Originalton unter Erweitert als AAC ausgeben oder MKV verwenden.
  Untertitel, Kapitel, Daten und Anhänge werden in 1.0 nicht übernommen. Dateisystem-
  Zeitstempel werden noch nicht übertragen; ausgewählte globale Metadaten wie
  `creation_time` und Titel werden übernommen.

Stereo-Ausgaben enthalten **MKV-StereoMode** bzw. die explizite **MP4-st3d**-Box.
H.264 verwendet zusätzlich Frame-Packing-SEI (3 für SBS, 4 für OU). Ein verlustfreier
MKV→MP4-Verpackungsschritt überträgt die Container-Kennzeichnung; das Video wird
nur einmal kodiert. Die fertige Ausgabe wird auf diese Kennzeichnungen geprüft.
Bei **Layout beibehalten** mit umgekehrter Halbbildreihenfolge speichert MKV die
passende Augenreihenfolge. MP4 bleibt wählbar und erhält keine irreführenden L/R-Flags,
weil st3d die Umkehrung nicht ausdrücken kann. Anaglyph-/Mono-Ausgaben erhalten keine SBS/OU-Flags.
**Testen** zeigt die Layout-Erkennung und die geplanten Kennzeichnungen.

**Kontrollbild** lädt das erste Bild automatisch und bietet einen Positionsregler und eine einzige editierbare Zeitangabe im Format mm:ss oder hh:mm:ss. Beim
Loslassen des Reglers oder mit Enter im Zeitfeld wird das Bild an der gewählten Stelle geladen. Es zeigt
optional einen Ausgabe-Frame derselben Filterkette: 8-Bit-Anzeige
vor Videokompression, kein Ersatz für den Test im Zielplayer. Der Fortschrittsbalken
kombiniert Dateifortschritt und Jobanzahl; unterschiedlich lange Videos haben gleiches
Gewicht. Vergangene Zeit und geschätzte Restzeit stehen nebeneinander. Bei Prüfungen
ohne belastbare Schätzung steht **Restzeit: —**; der Status nennt den laufenden
Arbeitsschritt. Meldungen, Phasendauern und vollständige FFmpeg-Aufrufe stehen im
Programmordner unter `logs`. Logs können lokale Pfade und Metadaten enthalten. Das vorhandene Icon und
der Windows-Abschlusssound bleiben unverändert.

## Einstellungen

TransCora merkt Ziel, Anaglyphenverfahren, Ausgabeprofil, Container, Codec,
Qualitätsmodus, CRF-/Bitratenwerte, Zielbildrate, Dateinamenszusatz, Eingabe-/Ausgabeordner und
Unterordneroption sowie Tonformat, Tonspurauswahl und Kanaleinstellung. Quelllayout beginnt beim nächsten Programmstart mit **Automatisch**,
**L/R tauschen** ist dann ausgeschaltet. Joblisten behalten ihre individuellen Angaben.
Dateiliste, Kontrollbildposition und Fenstergröße/-position werden nicht automatisch
wiederhergestellt. Einstellungen liegen lokal in `settings.json` im Programmordner.

**Standardeinstellungen** unter **Erweitert** stellt die Konvertierungsvorgaben für
neue Dateien wieder her. Bestehende Jobs, Ordnerpfade und Unterordneroption bleiben
erhalten. Alte Joblisten und Einstellungen aus 0.1.0 werden weiter gelesen; die
entfallenen Farbannahme-/FFmpeg-Pfad-/Struktur-Checkboxen werden nicht übernommen.

## Entwicklung und Prüfung

Python 3.10 oder neuer mit Tk; die Engine verwendet nur die Standardbibliothek.
FFmpeg/ffprobe benötigen `libx264`, `zscale` und die geprüften Filter; `libx265` nur für
HEVC. Beide Programme unter `tools/ffmpeg` bzw. `tools/ffmpeg/bin` ablegen.
Die portable EXE verwendet ausschließlich diese mitgelieferten Programme; nur beim
Start aus Python funktioniert als Entwicklungsfallback auch die PATH-Installation.

```text
python run_transcora.py
python -m unittest discover -s tests -v
```

Unter Linux ohne Display: `xvfb-run -a python -m unittest discover -s tests -v`.
Tests vergleichen alle 17 sRGB-Composites pixelgenau mit der originalen Batch und
prüfen echte Exporte, Bit-Tiefen, Audio, variable Zeitstempel, L/R-Tausch, Kontrollbild,
Abbruch, Namenskollisionen, 3D-Kennzeichnungen, Framerate-Änderungen samt Ton-Synchronität und frei zusammengestellte Listen. Das Material ist
synthetisch; längere persönliche Videos und Zielplayer sind praktisch zu erproben.

Der Windows-Build läuft nach erfolgreichen Linux- und Windows-Tests. FFmpeg wird
nur beim Build aus einer mit SHA256 gepinnten Quelle geladen. Die Desktop-Anwendung
lädt keine Tools/Updates aus dem Netz. Siehe `requirements-build.txt` und
[Drittanbieter-Hinweise](THIRD_PARTY.md).

## Grundlagen

- [Konzept](https://github.com/muelli1975/TransCora/blob/main/docs/TransCora-Konzept.md)
- [FFBatch-Auswertung](https://github.com/muelli1975/TransCora/blob/main/docs/ffmpeg-Parameter-Auswertung.md)
- [Workflow, Player-Namen und Oberflächenplanung](https://github.com/muelli1975/TransCora/blob/main/docs/Video-Workflow-und-Oberflaeche.md)
- [Originale Parameter](https://github.com/muelli1975/TransCora/blob/main/reference/FFBatch-Presets.txt)
- [Unveränderte Batch-Referenz](https://github.com/muelli1975/TransCora/blob/main/reference/AnaglyphBatch_DE.bat)
- [Methodenkatalog](presets/anaglyph_methods.reference.json)

Projektlizenz: [MIT](LICENSE). Das Repository enthält keine externen Binärtools;
mitgelieferte Tools behalten ihre eigenen Lizenzen und Dokumente.

## Laufprotokolle und BD-3D-Probelauf

Gespeicherte Laufprotokolle stehen im Programmordner von TransCora unter `logs`.
Beim Start eines neuen Laufs bleiben die letzten zehn TransCora-Protokolle erhalten.
**Logs löschen** im Logfenster löscht diese Protokolle und die angezeigten Meldungen;
die Schaltfläche ist während laufender Arbeit deaktiviert.

Der separate Workflow `Windows BD3D proof` prüft FRIM 1.31 x64 im Softwaremodus
und tsMuxeR 2.6.12 bis zur UDF-2.50-ISO mit SSIF. Er kodiert einen kurzen, gepackten
24-fps-Testfilm mit 240 Bildern nach AVC/MVC mit exakt 24000/1001 fps und passend
verlangsamtem LPCM-Ton. Er kontrolliert anschließend die ISO-Struktur, die
Bildanzahl, Zeitstempel, Farbangaben, Ton und beide wieder dekodierten Halbbilder.
Die daraus entwickelte Exportstrecke ist als **BD-3D · 1080p** integriert und wird
im Windows-Build zusätzlich als ISO und M2TS geprüft. Praktische Zielplayer-Tests
ergänzen die technischen Prüfungen.

## Voreinstellungen und Restzeit

**Voreinstellungen → Speichern unter …** merkt die Konvertierungseinstellungen
unter einem eigenen Namen im portablen Programmordner. **Laden** wendet sie auf
ausgewählte Dateien an; ohne Auswahl gelten sie für neue Dateien. **Löschen** entfernt
eine gespeicherte Voreinstellung. Dateiliste, Ordner und Disc-Titel sind nicht enthalten.
Ein schon vorhandener Name wird beim Speichern ersetzt.

Beim Fortschrittsbalken erscheinen **Vergangene Zeit** und die geschätzte Restzeit
für **Datei** und **Stapel**. Die vergangene Zeit bleibt nach dem Ende sichtbar.
Die Restzeit ergibt sich aus der verbleibenden Videodauer und dem nach Videodauer
gewichteten Verarbeitungsdurchschnitt des laufenden Stapels. Unterschiede bei
Auflösung, Bildrate oder Codec sperren die Schätzung nicht. Dateiwechsel und
verspätete Fortschrittsmeldungen lassen sie nicht verschwinden. Vor der ersten
Fortschrittsmessung steht ein Strich. Pausen zwischen Dateien zählen nicht zum
Durchschnitt; bei BD-3D zählen Ton und Multiplexing zur vollständigen Bearbeitungszeit.

## BD-3D-Ausgabe

**BD-3D · 1080p** bietet **Blu-ray-ISO** (Standard) oder eine einzelne **M2TS (AVC/MVC)**.
Beide enthalten zwei echte MVC-Halbbilder, kein SBS/OU-Video. ISO hat eine
UDF-2.50-Struktur mit SSIF und startet einen Film ohne Menü. Der **Disc-Titel** wird
vom Quellnamen abgeleitet und ist editierbar; er bestimmt auch den Ausgabenamen.
Bei M2TS gibt es kein Disc-Dateisystem; die Titelangabe benennt dort die Datei.
Ein Disc-Label wird je nach Player angezeigt, es ist keine eingeblendete Titelseite.

Der BD-3D-Export nimmt progressive SDR-Stereoquellen auch mit variablen Bildzeiten
an. Konstante **23,976 fps** bleiben unverändert; konstante **24 fps** werden um
0,1 % verlangsamt, der Ton wird unter Erhalt der Tonhöhe angepasst. Andere Raten
und variable Bildzeiten werden direkt vor der einzigen MVC-Kodierung anhand der
Quellzeitstempel auf die feste Bildrate angepasst: Ganze Stereobildpaare werden
bei Bedarf ausgelassen oder wiederholt. Lange Bildhaltezeiten bleiben erhalten,
statt die Laufzeit auf die Anzahl der Quellbilder zu verkürzen. Bei variablen
Quellbildzeiten bleiben Laufzeit und Ton erhalten; ein als 24 fps eingestufter
Stream verwendet weiterhin die oben beschriebene 0,1-%-Verlangsamung.
Bewegungen können bei einer Framerateänderung ungleichmäßiger werden; **Testen**
zeigt die konkrete Anpassung. Keine Bewegungsinterpolation. Verarbeitungsfehler werden mit den Meldungen der eingesetzten Werkzeuge angezeigt. Gültige variable Bildzeiten und Interlaced-Eingaben sind zulässig.
TransCora verwendet FFmpegs Zeitstempel-/Bildratenanpassung während der einzigen Kodierung.
Zusätzliche eigene Quellzeitstempel- und Ausgabekadenzprüfungen sperren den normalen Export nicht.

FRIM 1.31 verwendet das mitgelieferte Software-SDK; Intel-Grafik, Treiberinstallation,
AVISynth oder Netzwerkzugang werden für diesen FFmpeg-Eingabepfad nicht benötigt.
Der geprüfte Encoder verwendet hohe Qualität, eine wählbare gemeinsame AVC/MVC-Ziel-/Maximalrate von 20, 25, 30, 35 oder 40 Mbit/s (Standard 40),
AVC/MVC Level 4.1, strikte GOP 24/4, CPB 3750 KB, maximal vier gepufferte Bilder und
begrenztes 8-Bit-4:2:0-BT.709. Die qualitätsorientierte FRIM-Stufe `-u 1` bleibt erhalten. Für Blu-ray-Video ist dieses
Profil fest; das 4:4:4-Anaglyphenprofil ist davon unabhängig.

Die gewählten Audiospuren mit bekannter Mono-, Stereo-, 5.1- oder 7.1-Belegung werden
als 24-Bit-LPCM mit 48 kHz gespeichert. Alle Spuren und Originalkanäle sind Standard.
Stereo-Downmix und kein Ton sind ausdrückliche Optionen unter **Tonoptionen**.
Wave64 ersetzt das auf 4 GB begrenzte WAV-Zwischenformat, ohne zusätzliche
verlustbehaftete Tonkodierung. Untertitel werden noch nicht übernommen.

Rohbilder gehen direkt durch Pipes, nicht in riesige Zwischenvideodateien.
FFmpeg, FRIM und tsMuxeR melden tatsächliche Verarbeitungsfehler. Eine fehlende oder leere
Ausgabe wird nicht veröffentlicht; Originale und vorhandene Dateien werden nicht überschrieben.
Im normalen Export gibt es keinen Bilddatenvergleich, keine zusätzliche vollständige
Nachdekodierung und keine Sperre anhand einer eigenen Audio-/Videostarttoleranz.
Diese strukturellen und vollständigen Dekodierkontrollen laufen in den Entwicklungstests.
Temporäre Arbeitsdaten werden bei Erfolg/Abbruch entfernt. Knapp geschätzter Speicherplatz
führt zu einem Hinweis; es gibt keine automatische Disc-Aufteilung.



## MVC und MV-HEVC als Quelle

Automatisch erkennt MVC anhand der tatsächlichen NAL-Erweiterungen und MV-HEVC
anhand der beiden vom Decoder gemeldeten Halbbilder. Manuelle Einträge
**MVC / Blu-ray 3D** und **MV-HEVC** prüfen ebenfalls den Bitstream.

- MVC: Progressive 8-Bit-4:2:0-Stereoquellen in M2TS/TS/SSIF und einer kombinierten
  MKV/MP4-Videospur. Der portable edge264-mvc-Decoder benötigt keinen Frameserver;
  FRIM wird bei unterstützbaren Decoder-Lücken als geprüfter Windows-Fallback verwendet.
  Bei Blu-ray-ISO bestimmt die Playlist die linke/rechte Basis-Halbbild. Ohne diese
  Angabe wird links angenommen und ausdrücklich angezeigt; **L/R tauschen**
  bleibt für die Korrektur verfügbar. Zusätzliche eigene CFR-Paketzeit- und Paketanzahlprüfungen entfallen.
- Blu-ray-3D-ISO: Unverschlüsselte UDF-2.50-Discs mit einer vollständigen
  einzelnen SSIF-Filmdatei. Die längste Film-Playlist wird gewählt und genannt.
  Seamless Branching, alternative Blickwinkel und Clip-Ausschnitte bleiben blockiert.
- MV-HEVC: FFmpeg 7.1.1 dekodiert beide ausdrücklich als links/rechts
  gekennzeichneten Halbbildern. Das Basis-Halbbild kann rechts oder links sein.
  Beide Bildzeitfolgen müssen zusammenpassen. SDR einschließlich 10-Bit-Quellen
  folgt dem bestehenden Farbpfad; HDR und immersive Projektionen bleiben blockiert.

Die Ausgabe verwendet die vorhandenen SBS/OU-, Mono-, Anaglyphen- und BD-3D-Ziele.
Blu-ray-LPCM wird für MKV verlustfrei in FLAC gewandelt; andere freigegebene
Audiospuren werden gemäß den Tonoptionen übernommen. Für MP4 wird die
Kompatibilität des tatsächlich gewählten Tonformats geprüft. Layout beibehalten erhält weiterhin gepackte Quellen.

MV-HEVC-Ausgabe für Apple-Geräte ist ein späteres eigenes Ausgabeziel. Beliebigem
Stereomaterial werden keine erfundenen Spatial-Video-Kamerametadaten beigefügt.

## Matroska und 3D-Kennzeichnung

MKV-StereoMode kennzeichnet Anordnung und Reihenfolge: 1 = SBS L/R,
11 = SBS R/L, 3 = OU links oben und 2 = OU links unten. DisplayWidth/DisplayHeight
beschreiben die rekonstruierte Geometrie eines Halbbildes. Half-SBS-/Half-OU-MKV
setzt deshalb auch das entsprechende Pixelseitenverhältnis; Full-Ausgaben
behalten quadratische Pixel. StereoMode allein enthält keine Full-/Half-Angabe.
Anaglyphen erhalten keine besondere Anaglyph-StereoMode-Kennzeichnung.

Zusätzlich erkannt werden sView-Kürzel `-sbs`, `-hsbs`, `-hou`, `-half-sbs`,
`-half-ou` und WMV-Stereometadaten. Widersprüche zwischen Name und Metadaten
werden bei automatischer Erkennung gemeldet. `.mk3d`/`.mkv3d` sind MKV-Quellen.

Referenzen: [Matroska-Elemente](https://www.matroska.org/technical/elements.html)
und [sView-Stereoformate](https://github.com/gkv311/sview/blob/master/docs/stereoformats.md).

## Stand der MVC-Qualitätsprüfung

Native BT.709-/1080p-Halbbilder bleiben vor der MVC-Kodierung pixelgenau erhalten.
Der bisherige YUV/RGB/YUV-Umweg entfällt. Die FRIM-Grundeinstellungen bleiben
vorerst im dokumentierten Qualitätsprofil. Gemeldetes Flackern und Artefakte
bei Textüberblendungen einer Diaschau sind in Untersuchung; eine vollständige
Behebung ist noch nicht bestätigt. Technische Abschlussprüfungen bewerten
Integrität, Halbbilder und Verpackung, nicht die sichtbare Bildqualität.

Build-Anleitung: [BUILD.md](BUILD.md). Der passende Anwendungscode liegt im
portablen Paket unter `source/`.

## Kreuzblick-Video

**Kreuzblick · Full-SBS R/L** setzt das rechte Halbbild links und das linke rechts.
Die vollständige rekonstruierte Halbbildgröße bleibt standardmäßig erhalten. MP4 bleibt voreingestellt; MKV ist wählbar. MKV erhält StereoMode R/L. MP4 verwendet keine irreführende L/R-Kennzeichnung. Der Standardzusatz ist `-rl` (z. B. `Film-rl.mp4`). Die Halbbildreihenfolge einer R/L-
Quelle wird zuerst korrekt interpretiert; „L/R tauschen“ ändert die Quellzuordnung.


## Polfilter-Ausgabe für Bilder und Videos

**Zeilenverschachtelt (Polfilter)** legt linkes und rechtes Auge auf abwechselnde
Bildschirmzeilen. Monitorbreite und -höhe sind unabhängig von den sonstigen
Größenoptionen frei wählbar; voreingestellt sind 1920 × 1080. Die erste Zeile kann
dem linken oder rechten Auge zugeordnet werden. L/R tauschen bleibt die getrennte
Quellinterpretation. Jedes Auge wird vor der Verschachtelung mit Lanczos auf sein
Zielraster eingepasst; passende Half-OU/abq-Quellen werden nur zeilenweise umgeordnet.
Ein 1920 × 1080 großes abq-Bild liefert dabei unverändert 1920 × 540 Zeilen je Auge.
Bei abweichendem Seitenverhältnis bleiben schwarze Ränder innerhalb der exakten
Bildschirmmaße. Die fertigen Zeilen werden nicht nachträglich skaliert.

Bilder verwenden beim Wählen des Ziels zunächst verlustfreies PNG. JPEG bleibt mit
4:4:4 wählbar, kann aber durch seine verlustbehaftete Kompression Zeilen beeinflussen.
Videos verwenden 4:4:4, auch beim sonstigen Kompatibilitätsprofil, damit keine
vertikale Farbabtastung verschiedene Augen mischt. Den Zielplayer auf 4:4:4-Unterstützung
prüfen. MKV erhält den passenden nativen Row-Interleaved-StereoMode; linke erste Zeile
bei H.264 zusätzlich Frame-Packing 2. MP4 wird als normales Bildraster ohne unpassende
SBS/OU-Containerkennzeichnung ausgegeben. Dateizusätze sind `_rows_lr` oder `_rows_rl`.

Zur direkten Wiedergabe müssen Bildschirmauflösung und Ausgabemaße übereinstimmen.
Vollbild und Pixelzuordnung 1:1 verwenden; Skalierung, Overscan und eine erneute
3D-Umwandlung im Player/Monitor vermeiden. Das ist ein Bildschirmformat, keine
zeitliche 1080i-Ausgabe. Die Datei bleibt zeitlich progressiv. Native Augenreihenfolge
und Sitzposition müssen am tatsächlichen Monitor geprüft werden.

## Interlaced-Eingaben und Dateiliste

Zeitlich interlaced SBS/OU wird je Auge mit BWDIF und einem progressiven Bild pro
Halbbildzeit aufbereitet. Beispielsweise werden 25 interlaced Bilder mit 50
Halbbildzeitpunkten zu 50 progressiven Bildern pro Sekunde. Eine ausdrücklich
gewählte Zielbildrate beziehungsweise BD-3D passt die gemeinsame Bildfolge danach
an; Ton und Laufzeit bleiben erhalten. Zeitliche Interlaced-Ausgabe gehört nicht
zu diesem Release.

Die Videoliste zeigt Quell-fps und **Dauer** (HH:MM:SS) nach der Prüfung. Diese Werte
bleiben bei Änderungen der Ausgabeoptionen sichtbar; unbekannte Angaben erscheinen
als Strich. Die Oberfläche und das portable Paket tragen die Version **1.0**.
