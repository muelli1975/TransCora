# TransCora 1.1: Testplan und Voraussetzungen

Dies ist die geplante Abnahme, keine Behauptung bereits bestandener Anwendungstests.
Die Umsetzung steht in [PLAN_1.1.md](PLAN_1.1.md).

## Bereits geprüft bei der Vorbereitung

- 1.0-Basis: veröffentlichter Build `c3f2315`, aktueller Dokumentationsstand `7ef801f`.
- Derzeitiger Paketbau: Pillow **11.3.0**, kein `pillow-heif` in den festgelegten
  Abhängigkeiten; keine HEIC/HEIF/AVIF-Endungen im aktuellen Bildimport.
- Lokaler Python-Testhost: Pillow **12.1.0** mit AVIF; kein `pillow-heif`.
  Diese Hostausstattung beweist keine Unterstützung im ausgelieferten Paket.
- Journal fehlt; Listen speichern bisher nur Quellpfade und Einstellungen.
- Das aktuelle `libx265`-Ziel kodiert gepacktes H.265; MV-HEVC-Ausgabe fehlt.
- FFmpeg-Voraussetzung mit `scripts/probe_1_1_inputs.py` reproduzierbar prüfen.
  Der Bericht enthält genaue Werkzeugversion und tatsächliche Ergebnisse. Die Probe
  ist kein Importtest und hat keinen Einfluss auf Annahme oder Sperrung von Medien.
- Ausgeführt am 12. Oktober 2026 mit dem Windows-FFmpeg 7.1.1: **sechs Proben
  bestanden** (`irl`, `irr`, `al`, `ar`, `ml`, `mr`). Unabhängig erzeugte verlustfreie
  Eingaben liefern genau die erwarteten L/R-Pixel. Zeilenquellen erhalten Bildzahl
  und Rate; sechs Frame-sequential-Einzelbilder mit 48 fps werden zu drei Paaren
  mit 24 fps bei gleicher Laufzeit. Bericht: [1.1-input-probe.json](verification/1.1-input-probe.json).

Aufruf mit FFmpeg/ffprobe auf PATH:

```text
python scripts/probe_1_1_inputs.py --report input-probe.json
```

Alternativ `--ffmpeg` und optional `--ffprobe` angeben. Ohne explizites ffprobe
wird die zum FFmpeg-Pfad gehörende Nachbardatei benutzt. Ein beschreibbares TEMP-
Verzeichnis verwenden. Die Probe erzeugt kurze verlustfreie YUV-4:4:4-Dateien mit
unterschiedlichen Halbbildern, Zeilen, Spalten und Bildfolgen; sie räumt diese auf.

## Funktionale Abnahme

| Bereich | Fälle und erwartetes Ergebnis |
| --- | --- |
| Zeitspalte | Videos/Bilder, kurze/lange Dauer, BD-Vorbereitung und Muxing; nur vollständige Erfolge erhalten Zeitwerte. Zahlen statt Anzeigezeichenfolgen sortieren; unbekannte Werte bleiben hinten. |
| Standardfenster | DE/EN, Sortierpfeile, lange Dateinamen, Frame sequential, BD-3D 720p/59,94, 100/125/150-%-DPI; neue Spalte ohne abgeschnittene FPS, überlappende Anzeigen oder nötiges horizontales Scrollen bei Standardgröße. |
| Entfernen | Anfang/Mitte/Ende, leere Liste, Einzel-/Mehrfachauswahl, auf-/absteigend sortierte Liste; nächster sichtbarer Eintrag markiert, Fokus erhalten, Entf mehrfach nutzbar. In Video- und Bildtab identisch. |
| Fertige entfernen | Gemischte Fertig/Fehler/Offen-Liste; nur Fertige verschwinden. Journal, Quelle und Ausgabe bleiben erhalten. Keine Aktion während Verarbeitung. |
| Journal-Erfolg | Echter Video-/Bildexport, alternative nummerierte Namen, Unterordner und mehrere Ausgaben; vollständiger Erfolg wird sofort atomar gespeichert und nach Neustart erkannt. |
| Journal-Abgleich | Quelle, Größe, Zeitstempel, Einstellung oder Ausgabeordner geändert; eine von mehreren Ausgaben fehlt/geändert; kein automatischer Fertigstatus. Unveränderte Abschlüsse erhalten Zeit und Ausgabezuordnung zurück. |
| Journal-Fehler | Unterbrochenes Schreiben, beschädigtes/unbekanntes JSON, schreibgeschützter Ordner, parallele Schreiber; keine verlorenen fremden Datensätze und kein Löschen fertiger Medien. Speichern ohne neuen Erledigt-Nachweis klar melden. |
| Journal-Löschen | Liste leeren/Fertige entfernen lässt Nachweise bestehen. Journal manuell löschen; Import erkennt keine alten Abschlüsse. Nächster Erfolg erzeugt nur den neuen Nachweis, keine Wiederherstellung gelöschter Historie. |
| Alte Dateien/Listen | 1.0-Listen weiterhin laden. Vorhandene Ausgabe ohne Journal wird nicht als fertig übernommen; nummerierter Alternativname bleibt. Fehler/Abbruch werden nach Neustart erneut von Anfang an verarbeitet. |
| Pause | Wunsch an/aus, zwischen zwei Dateien, BD-Mux fertigstellen, Fortsetzen, Abbrechen/Schließen während Pause und Wunsch beim letzten Auftrag; kein Doppelstart oder hängender Worker. Zeit/ETA ohne Pausenanteil. |
| Mono | Asymmetrische markierte Halbbilder, beide Auswahlmöglichkeiten, L/R tauschen, passende Suffixe; Bildziel bereits vorhanden, Videoziel korrekt erweitern. |
| Zeilenquelle | L/R und R/L, feine Zeilenmuster, Bild/Video, Vorschau, SBS/OU/Anaglyph/BD-Ziele; Zeilen zuerst trennen, kein zeitlicher Deinterlacer auf Stereo-Zeilen, richtige Halbbildgeometrie. |
| Frame sequential | Beide Erst-Halbbildzuordnungen, 48/50/59,94/120 Einzelbilder/s, ungerade Schlussbildzahl, variable Zeitstempel, Ton; korrekte Paar-Rate, Laufzeit und Synchronität auch bei BD-3D. |
| HEIC normal | Echtes Gerätefoto, gedrehte Orientierung, ICC/NCLX, Alpha, Vorschauen/Zusatzbilder; Hauptfoto korrekt lesen und nach bestehendem Ziel ausgeben. |
| Stereo-HEIC | Originale Spatial Photo plus synthetisches Paar mit eindeutig unterschiedlichem L/R, vertauschte Speicherreihenfolge, zusätzliche Bilder; Stereo-Gruppe bestimmt die Zuordnung. Vorschau und beide Halbbilder korrekt. |
| HEIF-Zusatzdaten | Tiefenkarte/HDR-Gainmap werden nicht zum zweiten Halbbild. HDR zu SDR bewusst prüfen, Farb-/Helligkeitsfehler nicht durch bloße 8-Bit-Konvertierung verdecken. |
| AVIF optional | Statisches SDR, SBS/OU, ICC/Alpha, Animation/Mehrbilddatei; korrekter Import oder verständliche Meldung statt stiller Auswahl des ersten Bildes. |
| MV-HEVC-Prototyp | Echter Multiview-Encoder, Container und zwei explizit dekodierte Views; L/R, Anzahl, Zeitstempel, Audio und Bildqualität. Basis-Layer allein genügt nicht. |
| Paket | Windows x64, Linux x64, macOS Apple Silicon; tatsächlich gepackte HEIF-Bibliotheken und Lizenznachweise, Programm ohne Entwicklungs-PYTHONPATH starten, neue Formate im gefrorenen Paket lesen. |
| Regression | Bisherige vollständige Suite und native Integrationen einschließlich aller BD-Modi; Ordnerimport, Sortierung, Warnklassifikation, Logauswahl/Kopieren und DE/EN prüfen. |
| Veröffentlichung | Testbuild überschreibt weder Dateien noch Tag von v1.0. Erst fertige getestete Funktionen in kurze sachliche 1.1-Release-Notes aufnehmen. |

## Testmaterial

Synthetische Fixtures klein und reproduzierbar erzeugen. Für HEIC/Spatial Photos
zusätzlich echte Geräteoriginale mit dokumentierter Herkunft verwenden: Eine selbst
erzeugte Datei beweist nicht die Kompatibilität mit Geräte-Metadaten. Nicht heimlich
private Fotos in das öffentliche Repository übernehmen. Wiederverteilbare Fixtures
mit Quelle, Lizenz und SHA-256 festlegen; private Vergleichsdateien bleiben lokal.

Die bestehenden MVC-/MV-HEVC-/MPO-Fixtures und Integrationstests weiterverwenden.
Neue Stereo-HEIC-Fixtures, ein MV-HEVC-Encoderbuild und dessen Container-Prototyp
sind noch offen. Ohne tatsächlich ausgeführte Prüfung weder HEIC-Paketunterstützung
noch MV-HEVC-Ausgabe oder Vision-Pro-Wiedergabe als bestanden kennzeichnen.

Ausgabe-Roundtrips bleiben Entwicklungs-/CI-Tests. Keine neue vollständige
Nachkontrolle, Hash-Prüfung oder selbst entwickelte Annahmesperre im Produkt.
