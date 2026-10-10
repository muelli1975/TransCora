# TransCora 0.1.0

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
   **Ordner hinzufügen**, optional mit Unterordnern und gespiegelter Struktur.
2. Die gewünschten Listeneinträge auswählen. Einstellungen gelten für die Auswahl
   und als Vorgabe für neue Dateien. Leere Auswahlfelder bedeuten gemischte Werte;
   eine Änderung setzt nur dieses Feld für alle ausgewählten Jobs.
3. Für die bisherigen Workflows **Full-SBS** als Quelllayout wählen. Automatisch
   akzeptiert nur eindeutige unterstützte Dateikürzel, keine reine Auflösungsheuristik.
4. Ziel und Container wählen. **Prüfen** zeigt technische Daten, Ausgabe und Warnungen.
   **Starten** prüft erneut und verarbeitet alle noch offenen, gültigen Jobs.
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

Half-SBS/OU passen jedes Auge unter Erhalt seines Seitenverhältnisses in 1920 × 1080
ein, ergänzen bei Bedarf schwarze Ränder und halbieren danach die Packachse.
Full-/Half-SBS und Full-/Half-OU sind mögliche Quellen. MVC, Anaglyphen,
Frame-sequential und getrennte Videospuren sind keine unterstützten Quellen.

| Dateinamen-Auswahl für SBS/OU/Mono | Beispiele |
| --- | --- |
| Kein Layout-Zusatz | `Film.mkv` |
| Layout-Zusatz | `Film_half_sbs.mkv`, `Film_half_ou.mkv`, `Film_mono_l.mkv` |
| Player-Kürzel (Kodi/Bino) | `Film.3D.HSBS-lrh.mkv`, `Film.3D.HTAB-tbh.mkv`, `Film_mono_l-2d.mkv` |

Erkannte alte Stereo-Kürzel werden entfernt, unbekannte Zusätze bleiben erhalten.
Player-Kürzel helfen der Layout-Erkennung, garantieren jedoch keine Codec-Unterstützung.
Stereoscopic Player kann das Layout auch manuell wählen.

**Anaglyphen behalten die AnaglyphBatch-Zusätze**, etwa `Film_dubois_lcd.mkv`
oder `Film_rendepth2.mp4`, ohne zusätzliche `anaglyph`-, `2d`- oder Bit-Tiefen-Kürzel.
Vorhandene Dateien werden nicht überschrieben. Kollisionen werden vor dem Zusatz
nummeriert, z. B. `Film_2_dubois_lcd.mkv`; auch nachträglich angelegte Ziele sind geschützt.

## Qualität, Timing und Farbe

- Standard: **H.264 / MKV, CRF 18, slow**; alternativ MP4/H.264.
- Anaglyph-Standard: **8 Bit / 4:4:4**. Nicht alle Player/Hardwaredecoder unterstützen
  4:4:4. Optional **10 Bit / 4:4:4**, ebenfalls mit eingeschränkter Player-Unterstützung.
  Feinere Abstufungen machen eine 8-Bit-Quelle nicht zu HDR.
- **8 Bit / 4:2:0** ist der Anaglyph-Kompatibilitätsmodus. Die verringerte Farbauflösung
  kann die Qualität beeinträchtigen. Layout-/Mono-Ausgaben verwenden 8 Bit / 4:2:0.
- **Erweitert:** H.265/HEVC ausschließlich in MKV sowie frei einstellbare CRF oder
  durchschnittliche Zielbitrate in Mbit/s. CRF ist codecabhängig; Zielbitrate bedeutet
  kein garantiertes Dateigrößenlimit. Kein beliebiges Encoder-Menü.
- Quell-Timing bleibt erhalten, auch variable Framerate. Keine Umstellung,
  Interpolation oder bewusste Frame-Duplikation/-Auslassung. Container können
  Zeitstempel auf ihre eigene Genauigkeit runden.
- Unterstütztes SDR wird anhand seiner Farbkennzeichnung tatsächlich nach
  sRGB/16-Bit-RGB für die Batch-Verfahren umgerechnet und anschließend nach
  BT.709-YUV konvertiert und gekennzeichnet; keine bloße Änderung der Farb-Tags.
- Unvollständige Farbkennzeichnungen blockieren die Vorprüfung. Nach Quellenprüfung
  bewusst **Fehlende Farben: BT.709 SDR annehmen** einschalten; jede Annahme steht im
  Log. HDR wird nicht automatisch umgewandelt. Interlacing, nichtquadratische Pixel,
  Rotation und VR-Projektion werden in dieser Version mit Hinweis blockiert.
- Audio wird kopiert. Nicht zum MP4-Profil passende Audiospuren verlangen MKV.
  Untertitel, Kapitel, Daten und Anhänge werden in 0.1 nicht übernommen. Dateisystem-
  Zeitstempel werden noch nicht übertragen; ausgewählte globale Metadaten wie
  `creation_time` und Titel werden übernommen.

**Kontrollbild** zeigt optional einen Ausgabe-Frame derselben Filterkette: 8-Bit-Anzeige
vor Videokompression, kein Ersatz für den Test im Zielplayer. Der Fortschrittsbalken
kombiniert Dateifortschritt und Jobanzahl; unterschiedlich lange Videos haben gleiches
Gewicht. Meldungen und vollständige FFmpeg-Aufrufe stehen unter dem Ausgabeordner
in `logs`. Logs können lokale Pfade und Metadaten enthalten. Das vorhandene Icon und
der Windows-Abschlusssound bleiben unverändert.

## Entwicklung und Prüfung

Python 3.10 oder neuer mit Tk; die Engine verwendet nur die Standardbibliothek.
FFmpeg/ffprobe benötigen `libx264`, `zscale` und die geprüften Filter; `libx265` nur für
HEVC. Beide Programme unter `tools/ffmpeg` bzw. `tools/ffmpeg/bin` ablegen oder den
Ordner in der Oberfläche wählen. Für Entwicklung funktioniert auch die PATH-Installation.

```text
python run_transcora.py
python -m unittest discover -s tests -v
```

Unter Linux ohne Display: `xvfb-run -a python -m unittest discover -s tests -v`.
Tests vergleichen alle 17 sRGB-Composites pixelgenau mit der originalen Batch und
prüfen echte Exporte, Bit-Tiefen, Audio, variable Zeitstempel, L/R-Tausch, Kontrollbild,
Abbruch, Namenskollisionen und frei zusammengestellte Listen. Das Material ist
synthetisch; längere persönliche Videos und Zielplayer sind praktisch zu erproben.

Der Windows-Build läuft nach erfolgreichen Linux- und Windows-Tests. FFmpeg wird
nur beim Build aus einer mit SHA256 gepinnten Quelle geladen. Die Desktop-Anwendung
lädt keine Tools/Updates aus dem Netz. Siehe `requirements-build.txt` und
[Drittanbieter-Hinweise](THIRD_PARTY.md).

## Grundlagen

- [Konzept](docs/TransCora-Konzept.md)
- [FFBatch-Auswertung](docs/ffmpeg-Parameter-Auswertung.md)
- [Workflow, Player-Namen und Oberflächenplanung](docs/Video-Workflow-und-Oberflaeche.md)
- [Originale Parameter](reference/FFBatch-Presets.txt)
- [Unveränderte Batch-Referenz](reference/AnaglyphBatch_DE.bat)
- [Methodenkatalog](presets/anaglyph_methods.reference.json)

Projektlizenz: [MIT](LICENSE). Das Repository enthält keine externen Binärtools;
mitgelieferte Tools behalten ihre eigenen Lizenzen und Dokumente.
