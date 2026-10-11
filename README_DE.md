# TransCora 1.0

[English](README.md)

**3D-Videos und Stereobilder fÃ¼r deinen Bildschirm umwandeln.**

TransCora wandelt 3D-Videos und Stereobilder in SBS, Over/Under, Kreuzblick, Anaglyphen und zeilenverschachtelte Ausgaben fÃ¼r Polfilter-Monitore um. Es erstellt auÃŸerdem Blu-ray-3D-ISOs und teilt MPO-Dateien ohne JPEG-Neukodierung. Videos und Bilder haben eigene Stapellisten, Einstellungen und Kontrollbilder.

Alles lÃ¤uft lokal, ohne Account, Cloud oder Tracking. Die OberflÃ¤che lÃ¤sst sich zwischen Deutsch und Englisch umschalten.

## Herunterladen und starten

Lade ein Paket unter [Releases](https://github.com/muelli1975/TransCora/releases/latest) herunter und entpacke das komplette Archiv in einen beschreibbaren Ordner.

| System | Paket | Start |
| --- | --- | --- |
| Windows x64 | `TransCora_1.0_Windows_x64.zip` | `TransCora.exe` |
| Linux x64 | `TransCora_1.0_Linux_x64.tar.gz` | `./TransCora` |
| macOS Apple Silicon | `TransCora_1.0_macOS_AppleSilicon.tar.gz` | `TransCora.app` |

Windows enthÃ¤lt Python, FFmpeg und die BD-3D-Werkzeuge. Linux und macOS enthalten die Programmlaufzeit und Bildwerkzeuge; **FFmpeg einschlieÃŸlich ffprobe und System-Perl mÃ¼ssen separat installiert sein**. Unter Ubuntu/Debian: `sudo apt install ffmpeg perl`. Mit Homebrew unter macOS: `brew install ffmpeg-full`. Das macOS-Paket ist nicht notarisiert.

Halte den gesamten Programmordner zusammen. Eine eigene Python-Installation ist fÃ¼r diese Pakete nicht nÃ¶tig. BD-3D-Kodierung ist im Windows-Paket verfÃ¼gbar. Das Linux-Paket enthÃ¤lt zusÃ¤tzlich den MVC-Decoder; das Apple-Silicon-Paket unterstÃ¼tzt derzeit gepacktes Stereo und normale Videos, ohne MVC-Decoder.

## Schnellstart

1. Ã–ffne **Videos** oder **Bilder** und fÃ¼ge Dateien oder einen Ordner hinzu. Aktiviere bei Bedarf **Unterordner**.
2. Markiere die gewÃ¼nschten Dateien. Ã„nderungen gelten fÃ¼r die markierten EintrÃ¤ge; ohne Auswahl bilden sie die Vorgabe fÃ¼r neue Dateien.
3. WÃ¤hle Quelllayout und Ziel. Mit **L/R tauschen** korrigierst du eine vertauschte Augenreihenfolge.
4. WÃ¤hle GrÃ¶ÃŸe und Ausgabeordner. **Kontrollbild** zeigt das Ergebnis vor der Kodierung, wahlweise ans Fenster angepasst oder in einer verschiebbaren 1:1-Pixelansicht.
5. **Testen** prÃ¼ft den Stapel; **Start** verarbeitet ihn. Fortschritt, Dauer und Quellbildrate erscheinen im Fenster.

StandardmÃ¤ÃŸig landen Ergebnisse im Ordner `output` neben dem Programm. Bei Ordnerstapeln bleiben relative Unterordner erhalten. Vorhandene Dateien erhalten einen nummerierten Alternativnamen. Ein fehlerhafter Eintrag hÃ¤lt die Ã¼brigen gÃ¼ltigen Dateien nicht auf. **Abbrechen** beendet die aktuelle Verarbeitung; bereits fertige Dateien bleiben erhalten.

## Videoausgaben

| Ziel | Verwendung |
| --- | --- |
| Full-SBS / Full-OU | Zwei vollstÃ¤ndige Augenbilder nebeneinander oder Ã¼bereinander |
| Half-SBS / Half-OU | Kompakte Stereoformate fÃ¼r passende Player und Bildschirme |
| Kreuzblick Â· Full-SBS R/L | Freies Betrachten: rechtes Auge links, linkes Auge rechts |
| Anaglyph | Stereo mit Farbbrille; 17 Verfahren aus AnaglyphBatch |
| Mono | Linkes Auge als gewÃ¶hnliches Video ausgeben |
| Layout beibehalten | Anordnung erhalten und neu kodieren, optional mit anderer Bildrate |
| Zeilenverschachtelt | Direkte Ausgabe fÃ¼r einen passenden Polfilter-Monitor |
| BD-3D Â· 1080p | Blu-ray-3D-ISO oder AVC/MVC-M2TS mit 1920 Ã— 1080 je Auge |

**MP4 ist voreingestellt; MKV bleibt wÃ¤hlbar**, auch fÃ¼r Kreuzblick. MKV erhÃ¤lt die passende Stereo-Kennzeichnung. Kreuzblick-MP4 behÃ¤lt die R/L-Anordnung ohne irrefÃ¼hrenden L/R-Marker. Die Player-UnterstÃ¼tzung unterscheidet sich; prÃ¼fe die erste Ausgabe auf dem vorgesehenen GerÃ¤t.

### AuflÃ¶sung und Kreuzblick

WÃ¤hle **Original**, **1080p**, **2160p** oder **Benutzerdefiniert**. Standard erhÃ¤lt bei vollstÃ¤ndigen Layouts die rekonstruierte QuellgrÃ¶ÃŸe und verwendet bei Half-Layouts 1080p. Frei eingegebene Breite und HÃ¶he bezeichnen immer das **gesamte Ausgabebild**. Das SeitenverhÃ¤ltnis bleibt erhalten; falls nÃ¶tig entstehen RÃ¤nder.

| Beispiel | Gesamtes Bild | Gespeicherte Pixel je Auge |
| --- | --- | --- |
| Kreuzblick, 1080p je Auge | 3840 Ã— 1080 | 1920 Ã— 1080 |
| Kreuzblick, benutzerdefiniert 1920 Ã— 540 | 1920 Ã— 540 | 960 Ã— 540 |
| Half-SBS in UHD | 3840 Ã— 2160 | 1920 Ã— 2160 |
| Full-SBS mit UHD je Auge | 7680 Ã— 2160 | 3840 Ã— 2160 |

Kreuzblick bleibt in jeder GrÃ¶ÃŸe Full-SBS: Beide Bilder werden proportional verkleinert, nicht auf halbe Breite gestaucht. Eine grÃ¶ÃŸere Ausgabe kann fehlende Quelldetails nicht zurÃ¼ckholen.

### Bildrate, QualitÃ¤t und Ton

Normalerweise bleibt die Bildrate unverÃ¤ndert. Mit **Zielbildrate wÃ¤hlen** kannst du einen Wert eintragen, beispielsweise 23,976, 25, 30, 50, 59,94 oder 60 fps. AuflÃ¶sung, Stereoformat und Bildrate lassen sich im selben Export Ã¤ndern. Die Laufzeit bleibt erhalten; vollstÃ¤ndige Stereobilder werden ausgelassen oder wiederholt, ohne kÃ¼nstliche Bewegungsinterpolation.

Zeitlich interlaced aufgenommene Videos werden progressiv ausgegeben, mit erhaltener Halbbildzeit: Aus 25 verschachtelten Vollbildern mit 50 Halbbildern werden beispielsweise 50 progressive Bilder pro Sekunde. Eine gewÃ¤hlte Zielbildrate kann diese Bildfolge anschlieÃŸend anpassen.

Unter **Erweitert** wÃ¤hlst du H.264 oder H.265 (MKV), CRF-QualitÃ¤t oder eine Zielbitrate. Anaglyphen bieten 4:4:4-FarbqualitÃ¤t und optional 4:2:0 fÃ¼r Player, die dies benÃ¶tigen. Zeilenverschachtelte Videos verwenden 4:4:4, damit die Augenzeilen getrennt bleiben.

**Tonoptionen** Ã¼bernehmen alle Spuren, ausgewÃ¤hlte Spuren oder keinen Ton. Du kannst Originalton beibehalten, nach AAC wandeln oder auf Stereo heruntermischen. BD-3D verwendet LPCM und fest 23,976 fps; die gemeinsame AVC/MVC-Zielbitrate ist zwischen 20 und 40 Mbit/s wÃ¤hlbar.

## Polfilter-Monitore

WÃ¤hle bei Bildern oder Videos **Zeilenverschachtelt**. Trage die native Monitorbreite und -hÃ¶he ein, zunÃ¤chst 1920 Ã— 1080, und bestimme das Auge fÃ¼r die erste Bildschirmzeile. Linke und rechte Bildzeilen wechseln sich ab.

Zeige das Ergebnis bildschirmfÃ¼llend in exakt nativer AuflÃ¶sung, ohne Skalierung oder weitere Stereo-Umwandlung. Ist die Tiefe vertauscht, Ã¤ndere das Auge der ersten Zeile. FÃ¼r Bilder empfiehlt sich verlustfreies PNG. Ein vorhandenes Half-OU-/abq-Bild mit 1920 Ã— 1080 enthÃ¤lt bereits 1920 Ã— 540 Pixel je Auge und lÃ¤sst sich fÃ¼r einen Full-HD-Monitor direkt verschachteln.

## Bilder und MPO

Ã–ffne JPEG/JPS, PNG/PNS, TIFF, BMP, WebP und MPO mit zwei Augenbildern. Wandle in SBS, Over/Under, Anaglyphen, einzelne Augenbilder oder Zeilenverschachtelung um. Speichere JPEG, PNG, TIFF oder verlustfreies WebP. BildgrÃ¶ÃŸen: Original, 1080p, 2160p, 2048 Pixel an der langen Seite sowie frei wÃ¤hlbare lange/kurze Seite.

**MPO verlustfrei teilen** speichert die beiden Original-JPEGs als `_l.jpg` und `_r.jpg`, ohne Neukodierung. Auch die zusÃ¤tzlichen FÃ¼llbytes von Fujifilm-Kameras werden berÃ¼cksichtigt. Bildanaglyphen bieten neben den 17 Videoverfahren **CIELAB Least Squares**. JPEG verwendet normalerweise QualitÃ¤t 90 mit 4:4:4, optional 95.

Bei Bildwandlungen werden Orientierung und Farbprofile angewendet. Die optionale MetadatenÃ¼bernahme erhÃ¤lt Aufnahmezeiten und passende EXIF/XMP/IPTC-Felder. PNG, TIFF und WebP kÃ¶nnen beim Beibehalten des Layouts Transparenz erhalten.

## Quellen, Listen und Voreinstellungen

Gepacktes Full-/Half-SBS und Full-/Half-OU werden unterstÃ¼tzt. Die automatische Erkennung nutzt Stereo-Metadaten oder eindeutige DateikÃ¼rzel. Bei uneindeutigen Quellen wÃ¤hlst du das Layout selbst. Ãœbliche Player-KÃ¼rzel sind `-lr`, `-rl`, `-lrh`, `-rlh`, `-ab`, `-ba`, `-abq` und `-baq`.

Windows liest auÃŸerdem unverschlÃ¼sseltes MVC/Blu-ray 3D und SDR-MV-HEVC. Bei einer Blu-ray-ISO wird die Haupt-Stereo-Playlist gewÃ¤hlt. Das Programm entfernt keinen Kopierschutz. HDR-Wandlung, animierte/mehrseitige Bilder und die Wandlung von 16-Bit-Bildern gehÃ¶ren nicht zu Version 1.0.

Speichere **Listen**, um einen Stapel mit seinen Einstellungen je Datei fortzusetzen. Listen enthalten Pfade und Einstellungen, nicht die Medien selbst. **Voreinstellungen** speichern wiederverwendbare Wandlungsoptionen. Sprache und gewÃ¤hlte Ordner werden lokal gemerkt.

Tastatur: **Strg+O** fÃ¼gt Dateien hinzu; **Strg+A** markiert die Liste; **Strg+Klick** einzelne EintrÃ¤ge; **Umschalt+Klick** einen Bereich; **Entf** entfernt markierte EintrÃ¤ge; **Esc** bricht die aktive Verarbeitung ab. Unter macOS verwendest du **Command** zum Öffnen, Markieren aller Dateien und zur Einzelauswahl.

## Quellcode und Lizenz

Die Pakete enthalten den zugehÃ¶rigen Programmquellcode. Bauanleitung: [BUILD.md](BUILD.md). AusfÃ¼hrliche Formathinweise: [technische Referenz](docs/TECHNICAL_REFERENCE.md).

Copyright Christoph MÃ¼ller. TransCora steht unter der MIT-Lizenz; mitgelieferte Fremdwerkzeuge behalten ihre eigenen Lizenzen. Siehe [LICENSE](LICENSE) und [THIRD_PARTY.md](THIRD_PARTY.md).
