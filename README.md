# TransCora 0.1.3

Portabler, lokaler 3D-Video-Konverter mit kompakter Python-Oberfläche und FFmpeg.
**Erste Testversion:** Video-Konvertierung ist umgesetzt; Bild-/MPO-Werkzeuge und
Blu-ray-3D/MVC folgen später. Kein Account, Tracking oder Netzwerkzugriff im Programm.

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
   akzeptiert nur eindeutige unterstützte Dateikürzel, keine reine Auflösungsheuristik.
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
| Half-SBS | 1920 × 1080, links/rechts gepackt |
| Half-OU | 1920 × 1080, links oben/rechts unten |
| Anaglyph | Volle rekonstruierte Auflösung eines Auges; 17 AnaglyphBatch-Verfahren |
| Mono | Linkes Auge; mit **L/R tauschen** das andere Auge |
| Nur Framerate ändern | Auflösung, gepacktes Layout, Augenreihenfolge und YUV-Farbaufteilung bleiben erhalten |

Half-SBS/OU passen jedes Auge unter Erhalt seines Seitenverhältnisses in 1920 × 1080
ein, ergänzen bei Bedarf schwarze Ränder und halbieren danach die Packachse.
Full-/Half-SBS und Full-/Half-OU sind mögliche Quellen. MVC, Anaglyphen,
Frame-sequential und getrennte Videospuren sind keine unterstützten Quellen.

**Dateinamenszusatz · frei editierbar** bietet zum Ziel passende konkrete Zusätze,
**Keiner** und eigene Eingaben. Darunter steht unmittelbar der vollständige
**Ausgabename** der ausgewählten Datei; erkannte Kollisionen werden berücksichtigt.

| Ziel | Vorgegebene Zusätze (Auswahl) |
| --- | --- |
| Half-SBS | `_half_sbs`, `-lrh`, `-lrq`, `.3D.HSBS`, `.3D.HSBS-lrh` |
| Half-OU | `_half_ou`, `-tbh`, `-abq`, `.3D.HTAB`, `.3D.HTAB-tbh` |
| Anaglyph | Zusatz des gewählten Batch-Verfahrens, etwa `_dubois_lcd` |
| Mono | `_mono_l`, `-2d` |
| Nur Framerate ändern | Standard etwa `_30fps-tbh`; passende Layout-Kürzel und eigene Zusätze |

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
  kann die Qualität beeinträchtigen. Layout-/Mono-Ausgaben verwenden 8 Bit / 4:2:0.
- **Erweitert:** H.265/HEVC ausschließlich in MKV sowie frei einstellbare CRF oder
  durchschnittliche Zielbitrate in Mbit/s. CRF ist codecabhängig; Zielbitrate bedeutet
  kein garantiertes Dateigrößenlimit. Nur das zum gewählten Modus passende Feld ist
  sichtbar; beide Werte bleiben beim Umschalten erhalten. Startwert der Zielbitrate:
  **20 Mbit/s = 20.000 kbit/s**. Kein beliebiges Encoder-Menü.
- Bei Layout-/Anaglyph-/Mono-Konvertierungen bleibt das Quell-Timing erhalten,
  auch variable Framerate. Container können Zeitstempel auf ihre eigene Genauigkeit
  runden. **Nur Framerate ändern** erzeugt dagegen die gewählte konstante Bildrate.
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
  Erkannte HDR-Quellen werden nicht automatisch umgewandelt. Interlacing, nichtquadratische Pixel,
  Rotation und VR-Projektion werden in dieser Version mit Hinweis blockiert.
- Audio wird kopiert. Nicht zum MP4-Profil passende Audiospuren verlangen MKV.
  Untertitel, Kapitel, Daten und Anhänge werden in 0.1 nicht übernommen. Dateisystem-
  Zeitstempel werden noch nicht übertragen; ausgewählte globale Metadaten wie
  `creation_time` und Titel werden übernommen.

Stereo-Ausgaben enthalten **MKV-StereoMode** bzw. die explizite **MP4-st3d**-Box.
H.264 verwendet zusätzlich Frame-Packing-SEI (3 für SBS, 4 für OU). Ein verlustfreier
MKV→MP4-Verpackungsschritt überträgt die Container-Kennzeichnung; das Video wird
nur einmal kodiert. Die fertige Ausgabe wird auf diese Kennzeichnungen geprüft.
Bei **Nur Framerate ändern** mit umgekehrter Augenreihenfolge ist MKV erforderlich:
st3d kann R/L nicht ausdrücken. Anaglyph-/Mono-Ausgaben erhalten keine SBS/OU-Flags.
**Testen** zeigt die Layout-Erkennung und die geplanten Kennzeichnungen.

**Kontrollbild** lädt das erste Bild automatisch und bietet einen Positionsregler und eine genaue Sekundenangabe. Beim
Loslassen des Reglers oder mit Enter im Sekundenfeld wird das Bild an der gewählten Stelle geladen. Es zeigt
optional einen Ausgabe-Frame derselben Filterkette: 8-Bit-Anzeige
vor Videokompression, kein Ersatz für den Test im Zielplayer. Der Fortschrittsbalken
kombiniert Dateifortschritt und Jobanzahl; unterschiedlich lange Videos haben gleiches
Gewicht. Meldungen und vollständige FFmpeg-Aufrufe stehen unter dem Ausgabeordner
in `logs`. Logs können lokale Pfade und Metadaten enthalten. Das vorhandene Icon und
der Windows-Abschlusssound bleiben unverändert.

## Einstellungen

TransCora merkt Ziel, Anaglyphenverfahren, Ausgabeprofil, Container, Codec,
Qualitätsmodus, CRF-/Bitratenwerte, Zielbildrate, Dateinamenszusatz, Eingabe-/Ausgabeordner und
Unterordneroption. Quelllayout beginnt beim nächsten Programmstart mit **Automatisch**,
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

Gespeicherte Laufprotokolle stehen im gewählten Ausgabeordner unter `logs`.
Beim Start eines neuen Laufs bleiben die letzten zehn TransCora-Protokolle erhalten.
**Logs löschen** im Logfenster löscht diese Protokolle und die angezeigten Meldungen;
die Schaltfläche ist während laufender Arbeit deaktiviert.

Der separate Workflow `Windows BD3D proof` prüft FRIM 1.31 x64 im Softwaremodus
und tsMuxeR 2.6.12 bis zur UDF-2.50-ISO mit SSIF. Er kodiert einen kurzen, gepackten
24-fps-Testfilm mit 240 Bildern nach AVC/MVC mit exakt 24000/1001 fps und passend
verlangsamtem LPCM-Ton. Er kontrolliert anschließend die ISO-Struktur, die
Bildanzahl, Zeitstempel, Farbangaben, Ton und beide wieder dekodierten Augenbilder.
Die experimentelle Vorbereitung ist noch kein Ziel in der Programmoberfläche.
Ein Abspieltest auf realer Blu-ray-3D-Hardware steht zusätzlich zur technischen
Prüfung aus.
