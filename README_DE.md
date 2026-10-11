# TransCora 1.0

[English](README.md)

TransCora ist ein lokales Desktopprogramm zum Umwandeln stereoskopischer Videos und Bilder. Es unterstützt SBS, Over/Under, Kreuzblick, Anaglyphen und zeilenverschachtelte Ausgaben für Polfilter-Monitore. Unter Windows erstellt es außerdem Blu-ray-3D-ISOs und AVC/MVC-M2TS. MPO-Dateien lassen sich ohne JPEG-Neukodierung in ihre beiden Augenbilder aufteilen. Videos und Bilder haben eigene Stapellisten, Einstellungen und Kontrollbilder.

Alles läuft lokal, ohne Account, Cloud oder Tracking. Die Oberfläche lässt sich zwischen Deutsch und Englisch umschalten.

![TransCora 1.0 mit Videoliste und Ausgabeeinstellungen](docs/Screenshots/TransCora_DE.png)

## Schnellstart

1. Öffne **Videos** oder **Bilder** und füge Dateien oder einen Ordner hinzu. Aktiviere bei Bedarf **Unterordner**.
2. Markiere die gewünschten Dateien. Änderungen gelten für die markierten Einträge; ohne Auswahl bilden sie die Vorgabe für neue Dateien.
3. Wähle Quelllayout und Ziel. Mit **L/R tauschen** korrigierst du eine vertauschte Augenreihenfolge.
4. Wähle Größe und Ausgabeordner. **Kontrollbild** zeigt das Ergebnis vor der Kodierung, wahlweise ans Fenster angepasst oder in einer verschiebbaren 1:1-Pixelansicht.
5. **Testen** prüft den Stapel; **Start** verarbeitet ihn. Fortschritt, Dauer und Quellbildrate erscheinen im Fenster.

Standardmäßig landen Ergebnisse im Ordner `output` neben dem Programm. Bei Ordnerstapeln bleiben relative Unterordner erhalten. Vorhandene Dateien erhalten einen nummerierten Alternativnamen. Ein fehlerhafter Eintrag hält die übrigen gültigen Dateien nicht auf. **Abbrechen** beendet die aktuelle Verarbeitung; bereits fertige Dateien bleiben erhalten.

## Videoausgaben

| Ziel | Verwendung |
| --- | --- |
| Full-SBS / Full-OU | Zwei vollständige Augenbilder nebeneinander oder übereinander |
| Half-SBS / Half-OU | Kompakte Stereoformate für passende Player und Bildschirme |
| Kreuzblick · Full-SBS R/L | Freies Betrachten: rechtes Auge links, linkes Auge rechts |
| Anaglyph | Stereo mit Farbbrille; 17 Verfahren aus AnaglyphBatch |
| Mono | Linkes Auge als gewöhnliches Video ausgeben |
| Layout beibehalten | Anordnung erhalten und neu kodieren, optional mit anderer Bildrate |
| Zeilenverschachtelt | Direkte Ausgabe für einen passenden Polfilter-Monitor |
| BD-3D · 1080p | Blu-ray-3D-ISO oder AVC/MVC-M2TS mit 1920 × 1080 je Auge |

**MP4 ist voreingestellt; MKV bleibt wählbar**, auch für Kreuzblick. MKV erhält die passende Stereo-Kennzeichnung. Kreuzblick-MP4 behält die R/L-Anordnung ohne irreführenden L/R-Marker. Die Player-Unterstützung unterscheidet sich; prüfe die erste Ausgabe auf dem vorgesehenen Gerät.

### Auflösung und Kreuzblick

Wähle **Original**, **1080p**, **2160p** oder **Benutzerdefiniert**. Standard erhält bei vollständigen Layouts die rekonstruierte Quellgröße und verwendet bei Half-Layouts 1080p. Frei eingegebene Breite und Höhe bezeichnen immer das **gesamte Ausgabebild**. Das Seitenverhältnis bleibt erhalten; falls nötig entstehen Ränder.

| Beispiel | Gesamtes Bild | Gespeicherte Pixel je Auge |
| --- | --- | --- |
| Kreuzblick, 1080p je Auge | 3840 × 1080 | 1920 × 1080 |
| Kreuzblick, benutzerdefiniert 1920 × 540 | 1920 × 540 | 960 × 540 |
| Half-SBS in UHD | 3840 × 2160 | 1920 × 2160 |
| Full-SBS mit UHD je Auge | 7680 × 2160 | 3840 × 2160 |

Kreuzblick bleibt in jeder Größe Full-SBS: Beide Bilder werden proportional verkleinert, nicht auf halbe Breite gestaucht. Eine größere Ausgabe kann fehlende Quelldetails nicht zurückholen.

### Bildrate, Qualität und Ton

Normalerweise bleibt die Bildrate unverändert. Mit **Zielbildrate wählen** kannst du einen Wert eintragen, beispielsweise 23,976, 25, 30, 50, 59,94 oder 60 fps. Auflösung, Stereoformat und Bildrate lassen sich im selben Export ändern. Die Laufzeit bleibt erhalten; vollständige Stereobilder werden ausgelassen oder wiederholt, ohne künstliche Bewegungsinterpolation.

Zeitlich interlaced aufgenommene Videos werden progressiv ausgegeben, mit erhaltener Halbbildzeit: Aus 25 verschachtelten Vollbildern mit 50 Halbbildern werden beispielsweise 50 progressive Bilder pro Sekunde. Eine gewählte Zielbildrate kann diese Bildfolge anschließend anpassen.

Unter **Erweitert** wählst du H.264 oder H.265 (MKV), CRF-Qualität oder eine Zielbitrate. Anaglyphen bieten 4:4:4-Farbqualität und optional 4:2:0 für Player, die dies benötigen. Zeilenverschachtelte Videos verwenden 4:4:4, damit die Augenzeilen getrennt bleiben.

**Tonoptionen** übernehmen alle Spuren, ausgewählte Spuren oder keinen Ton. Du kannst Originalton beibehalten, nach AAC wandeln oder auf Stereo heruntermischen. BD-3D verwendet LPCM und fest 23,976 fps; die gemeinsame AVC/MVC-Zielbitrate ist zwischen 20 und 40 Mbit/s wählbar.

## Polfilter-Monitore

Wähle bei Bildern oder Videos **Zeilenverschachtelt**. Trage die native Monitorbreite und -höhe ein, zunächst 1920 × 1080, und bestimme das Auge für die erste Bildschirmzeile. Linke und rechte Bildzeilen wechseln sich ab.

Zeige das Ergebnis bildschirmfüllend in exakt nativer Auflösung, ohne Skalierung oder weitere Stereo-Umwandlung. Ist die Tiefe vertauscht, ändere das Auge der ersten Zeile. Für Bilder empfiehlt sich verlustfreies PNG. Ein vorhandenes Half-OU-/abq-Bild mit 1920 × 1080 enthält bereits 1920 × 540 Pixel je Auge und lässt sich für einen Full-HD-Monitor direkt verschachteln.

## Bilder und MPO

Öffne JPEG/JPS, PNG/PNS, TIFF, BMP, WebP und MPO mit zwei Augenbildern. Wandle in SBS, Over/Under, Anaglyphen, einzelne Augenbilder oder Zeilenverschachtelung um. Speichere JPEG, PNG, TIFF oder verlustfreies WebP. Bildgrößen: Original, 1080p, 2160p, 2048 Pixel an der langen Seite sowie frei wählbare lange/kurze Seite.

**MPO verlustfrei teilen** speichert die beiden Original-JPEGs als `_l.jpg` und `_r.jpg`, ohne Neukodierung. Auch die zusätzlichen Füllbytes von Fujifilm-Kameras werden berücksichtigt. Bildanaglyphen bieten neben den 17 Videoverfahren **CIELAB Least Squares**. JPEG verwendet normalerweise Qualität 90 mit 4:4:4, optional 95.

Bei Bildwandlungen werden Orientierung und Farbprofile angewendet. Die optionale Metadatenübernahme erhält Aufnahmezeiten und passende EXIF/XMP/IPTC-Felder. PNG, TIFF und WebP können beim Beibehalten des Layouts Transparenz erhalten.

## Quellen, Listen und Voreinstellungen

Gepacktes Full-/Half-SBS und Full-/Half-OU werden unterstützt. Die automatische Erkennung nutzt Stereo-Metadaten oder eindeutige Dateikürzel. Bei uneindeutigen Quellen wählst du das Layout selbst. Übliche Player-Kürzel sind `-lr`, `-rl`, `-lrh`, `-rlh`, `-ab`, `-ba`, `-abq` und `-baq`.

Windows liest außerdem unverschlüsseltes MVC/Blu-ray 3D und SDR-MV-HEVC. Bei einer Blu-ray-ISO wird die Haupt-Stereo-Playlist gewählt. Das Programm entfernt keinen Kopierschutz. HDR-Wandlung, animierte/mehrseitige Bilder und die Wandlung von 16-Bit-Bildern gehören nicht zu Version 1.0.

Speichere **Listen**, um einen Stapel mit seinen Einstellungen je Datei fortzusetzen. Listen enthalten Pfade und Einstellungen, nicht die Medien selbst. **Voreinstellungen** speichern wiederverwendbare Wandlungsoptionen. Sprache und gewählte Ordner werden lokal gemerkt.

Tastatur: **Strg+O** fügt Dateien hinzu; **Strg+A** markiert die Liste; **Strg+Klick** einzelne Einträge; **Umschalt+Klick** einen Bereich; **Entf** entfernt markierte Einträge; **Esc** bricht die aktive Verarbeitung ab. Unter macOS verwendest du **Command** zum Öffnen, Markieren aller Dateien und zur Einzelauswahl.

## Portable Pakete und Quellcode

Lade ein Paket unter [Releases](https://github.com/muelli1975/TransCora/releases/latest) herunter und entpacke das komplette Archiv in einen beschreibbaren Ordner.

| System | Paket | Start |
| --- | --- | --- |
| Windows x64 | `TransCora_1.0_Windows_x64.zip` | `TransCora.exe` |
| Linux x64 | `TransCora_1.0_Linux_x64.tar.gz` | `./TransCora` |
| macOS Apple Silicon | `TransCora_1.0_macOS_AppleSilicon.tar.gz` | `TransCora.app` |

Windows enthält Python, FFmpeg und die BD-3D-Werkzeuge. Linux und macOS enthalten die Programmlaufzeit und Bildwerkzeuge; **FFmpeg einschließlich ffprobe und System-Perl müssen separat installiert sein**. Unter Ubuntu/Debian: `sudo apt install ffmpeg perl`. Mit Homebrew unter macOS: `brew install ffmpeg@7`. Das macOS-Paket ist ad-hoc signiert und nicht notarisiert.

Halte den gesamten Programmordner zusammen. Eine eigene Python-Installation ist für diese Pakete nicht nötig. BD-3D-Kodierung ist im Windows-Paket verfügbar. Das Linux-Paket enthält zusätzlich den MVC-Decoder; das Apple-Silicon-Paket unterstützt derzeit gepacktes Stereo und normale Videos, ohne MVC-Decoder.

Die Pakete enthalten den zugehörigen Programmquellcode. Bauanleitung: [BUILD.md](BUILD.md). Ausführliche Formathinweise: [technische Referenz](docs/TECHNICAL_REFERENCE.md).

## Lizenz

Copyright Christoph Müller. TransCora steht unter der MIT-Lizenz; mitgelieferte Fremdwerkzeuge behalten ihre eigenen Lizenzen. Siehe [LICENSE](LICENSE) und [THIRD_PARTY.md](THIRD_PARTY.md).
