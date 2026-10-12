# TransCora 1.1: Testplan und Voraussetzungen

Dies ist die geplante Abnahme, keine Behauptung bereits bestandener Anwendungstests.
Die Umsetzung steht in [PLAN_1.1.md](PLAN_1.1.md).

## Erster Implementierungsstand

Journal, Ergebniszeiten, numerische Zeitsortierung, Fertige entfernen und die
Tastaturauswahl sind implementiert. Zusätzlich erscheinen gleiche Hinweise nur
einmal; übliche SDR-Farbannahmen sind neutrale Informationen. Unverändertes
Übernehmen eines Eingabefelds setzt fertige Aufträge nicht mehr zurück.

Vollständige CI des ersten Entwicklungsstands (`53191f2`): **132 Tests auf
Windows, Linux und macOS bestanden**, einschließlich 43 GUI-Tests. Die nativen
BD-3D-/MVC-/MV-HEVC-/MPO-Prüfungen und die gestarteten gepackten Anwendungen
waren erfolgreich. Ein vorausgehender Lauf scheiterte am HTTP-504 beim Download
der CIELAB-Abhängigkeit; der wiederholte Lauf war vollständig erfolgreich.

Pausensteuerung und Mono-Halbbildwahl: **85 lokale Regressionen bestanden**.
Die Tests verarbeiten echte Video- und MPO-Dateien, pausieren nach Veröffentlichung
und Journaleintrag, prüfen Fortsetzen/Abbrechen und die eingefrorene Zeitmessung.
Unterschiedliche farbige Halbbilder prüfen beide Mono-Auswahlen und L/R-Tausch.

Die echte 20-Dateien-GUI-Konvertierung wurde um Entfernen/Wiederhinzufügen und
Erledigt-Erkennung ohne erneute Kodierung erweitert. Mehrteiliger MPO-Export,
Journalverlust, beschädigtes Journal, Schreibfehler sowie konkurrierende Thread-
und Prozessschreiber sind erfasst. Bei Journal-Schreibfehler bleiben Ausgaben
und Erfolgsstatus erhalten; die Abschlussmeldung weist auf fehlende Einträge hin.

Die plattformübergreifenden Pakettests für den erweiterten Stand mit Pause und
Mono-Auswahl werden gesondert ausgeführt.

## Wiederaufgenommener Stand vom 12. Oktober

Commit `7b82b3d` enthält die erhaltenen neueren lokalen HEIF-Änderungen und die
Reparaturen der Spaltenbreite sowie der x265-Quellvorbereitung. **148 Tests auf
Windows, Linux und macOS bestanden**, einschließlich des echten HEIF-Stereopaarimports.
Alle drei Pakete starten erfolgreich. Ihre eingefrorenen HEIF-
Leser bestehen vier Proben; zusätzlich bestehen die sechs Import-/Exportfälle
in der gestarteten gepackten TransCora-Anwendung (inklusive Metadaten).
Lauf: https://github.com/muelli1975/TransCora/actions/runs/38281236329

Die lokale Windows-Quelle bestand 146 von 148 Tests. Zwei ExifTool-Starts wurden
vom lokalen Testhost mit WinError 623 (DLL-Ladefehler) verhindert; diese beiden
Tests bestehen in den unabhängigen Läufen aller drei Systeme. Die abschließende
Windows-Paketprüfung war erfolgreich, einschließlich echter BD-3D-ISO/M2TS-
Ausgaben, Bildzeiten, großem LPCM, MVC/MV-HEVC-Eingaben und gefrorener EXE.

Die korrigierte x265-Probe lässt sich bauen und kodiert zwei Views. Das Ergebnis
ist dennoch **blocked**, nicht candidate: View 1 ist in der verlustfreien Probe
nicht pixelgleich mit ihrer Quelle; eindeutige L/R-Positionen fehlen. Rohes HEVC,
MP4/hev1 und MP4/hvc1 bestehen deshalb die Abnahme nicht. Der technische Lauf
selbst war erfolgreich und hat diese Einschränkungen gemeldet. Es wird kein
MV-HEVC-Ausgabeziel freigegeben. Vollständiger Bericht:
[1.1-mvhevc-probe.json](verification/1.1-mvhevc-probe.json).

Gezielte Wiederholung mit `-fps_mode passthrough` (keine vom Test hinzugefügten
Bilder) bestätigt die Einschränkung: View 0 liefert 12 pixelgleiche Bilder,
View 1 nur 11 statt 12 und abweichende Pixel. Dies betrifft rohes HEVC und beide
MP4-Varianten mit x265 4.3 und dem festgelegten FFmpeg 7.1.1. Die Zuordnung zum
Encoder oder Decoder ist damit noch nicht geklärt. Encoderlog und synthetische
Ausgaben sind im gesonderten Codec-Artefakt gesichert. Kein neues Ausgabeziel
und keine zusätzliche Produkt-Sperrprüfung werden daraus abgeleitet.

AVIF bleibt optional und ist für diesen Stand nicht aktiviert: Der Pillow-Leser
liefert hier keine NCLX-/HDR-Transferkennzeichnung an die vorhandene Bildpipeline.
Die Ausgabe darf nicht still eine HDR-Datei als gewöhnliches SDR behandeln.

## Neue Stereo-Eingaben und HEIF-Prototyp

Zeilenverschachtelte Bilder/Videos und Frame sequential sind in den Import und die
vorhandenen Ausgabeziele integriert. Tests mit unabhängig erzeugten Halbbildern
prüfen L/R und R/L, richtige Geometrie, 48/50/59,94/120 Einzelbilder/s, vollständiges
letztes Paar, ungepaartes Schlussbild, unveränderten Ton und variable Bildzeiten.
Alle drei BD-Vorbereitungsgraphen wurden mit FFmpeg tatsächlich ausgeführt.
Zusammen mit bestehenden GUI-/Kern-/Journal-Regressionen: **94 lokale Tests bestanden**. Die
Liste bietet Platz für Frame sequential in DE/EN; normale Erklärungen bleiben neutral.

Bei Frame sequential erfordert die Ausgabe derzeit ein gewähltes Stereo-/Mono-
Layout. Ein alternierender Export über FFmpegs `stereo3d=sbsl:al` verlor in der
Vorbereitung das letzte Paar; dieser Weg wird nicht als Layout-beibehalten angeboten.
Die Zielbildrate gilt nach der Paarbildung für vollständige Stereobildpaare.

Der separate HEIF-Leserprototyp bestand vier lokale Proben mit pillow-heif 1.8.1:
Stereo-Paar, vertauschte Item-Reihenfolge, upstream Spatial Photo (beide 2560×2560-
Halbbilder einschließlich ICC) und gedrehtes Hauptfoto. Quellen, SHA-256, gewählte
Item-IDs und Pixelprüfsummen stehen in `verification/1.1-heif-probe.json`. Zusätzliche
Tests verhindern, dass Tiefenkarten/Gainmaps/andere Bilder als zweites Halbbild
gewählt werden. HDR wird anhand PQ/HLG erkannt, nicht allein an Lichtpegel-Metadaten.

**HEIF ist in den Entwicklungs-Bildimport integriert.** Der separate Windows-Leser
wurde gebaut und bestand alle vier ursprünglichen Proben auch als EXE. Der Paketbau
enthält die passenden nativen Quellarchive, Bauanleitungen und Lizenznachweise.
Die erweiterten Pakettests starten zusätzlich die gepackte TransCora-Anwendung:
Stereo-Gruppen/L/R-Tausch, normales gedrehtes Foto, Spatial Photo, ICC und Metadaten.
Die Prüfung aller drei Systeme ist für diesen Stand noch ausstehend. Die öffentliche
Upstream-Fixture wurde zur Prüfung heruntergeladen; Fotos werden nicht ins Repository
kopiert. Der MV-HEVC-Prototyp baut x265 mit echtem ENABLE_MULTIVIEW und prüft beide
expliziten Views, MP4-Container, Zeitstempel und Ton in einem getrennten CI-Lauf.
Ein erfolgreich ausgeführter Probelauf bedeutet nicht automatisch einen brauchbaren
Codec: dessen JSON-Ergebnis kann `blocked` oder `candidate` sein.

## Bereits geprüft bei der Vorbereitung

- 1.0-Basis: veröffentlichter Build `c3f2315`, aktueller Dokumentationsstand `7ef801f`.
- Derzeitiger Paketbau: Pillow **11.3.0**, kein `pillow-heif` in den festgelegten
  Abhängigkeiten; keine HEIC/HEIF/AVIF-Endungen im aktuellen Bildimport.
- Lokaler Python-Testhost: Pillow **12.1.0** mit AVIF; kein `pillow-heif`.
  Diese Hostausstattung beweist keine Unterstützung im ausgelieferten Paket.
- 1.0-Listen speichern nur Quellpfade und Einstellungen; 1.1 ergänzt das Journal.
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
