# TransCora 1.1: finaler Umfang

Stand: 13. Oktober 2026. Entwicklungszweig `prepare/v1.1`.
Die Veröffentlichung erfolgt nach vollständiger Abnahme und ausdrücklicher Freigabe.
Das vorhandene Release v1.0 bleibt erhalten.

## Anwendung

- Gemeinsame Abschlussdaten für Videos und Bilder: feste, numerisch sortierbare
  Bearbeitungszeit hinter Status. Vorbereitung, Kodierung, Ton und Veröffentlichung
  zählen; Warteschlange und Pausen nicht.
- `TransCora-Journal.json` pro Ausgabeordner: unveränderte Quelle, wirksame
  Einstellungen und alle dokumentierten Ausgaben sind Voraussetzung für
  wiederhergestellten Fertigstatus. Keine Voll-Dekodierung oder Medien-Hashes beim
  Wiederimport. Journalfehler erhalten fertige Ausgaben; atomare und konkurrierende
  Schreiber verlieren keine fremden Abschlüsse. Listenentfernen löscht kein Journal.
- Fertige entfernen für Videos und Bilder. Entf/Entfernen folgt der sichtbaren
  Reihenfolge; Fokus und Sortierung bleiben erhalten.
- Nach Datei pausieren, Wunsch zurücknehmen und Fortsetzen. Pause erst nach
  Veröffentlichung und Journal; Abbruch und Schließen auch in der Pause.
- Mono-Video aus linkem oder rechtem Halbbild, mit `_mono_l`/`_mono_r`.
- Zeilenverschachtelte Bild-/Videoeingaben und Frame-sequential-Videos:
  zuerst Stereo-Zeilen trennen bzw. zeitliche Halbbilder paaren, anschließend
  skalieren/Bildrate ändern. L/R, Geometrie, Paarbildrate und Ton berücksichtigen;
  ungepaartes Schlussbild nicht verschweigen.
- HEIC/HEIF-SDR-Import einschließlich gekennzeichneter Stereo-HEIC/Spatial Photos.
  Separater gepackter Leser, Stereo-Gruppenzuordnung, Orientierung und ICC/NCLX.
  Tiefenkarten und Gainmaps sind keine zweiten Halbbilder; kein stilles HDR-zu-SDR.
- Dual als Ein-/Ausgabe: zwei eigenständige L/R-Videospuren in einer Datei.
  Ausgabe als MP4 (Standard) oder MKV; Größe je Halbbild, gemeinsame Bildrate,
  vorhandene Tonoptionen und `L/R tauschen`. `-dual` als Dateizusatz.
  Automatik erkennt `-dual`; unbenannte Mehrspurdateien erfordern die bewusste
  Wahl des Dual-Quelllayouts. Titel Left/Right bestimmen die Zuordnung, sonst L/R
  nach Spurreihenfolge. Synchronität wird während der tatsächlichen Dekodierung
  geprüft, ohne zusätzlichen vollständigen Vorab-Dekodierlauf.
- BD-3D-/Dual-Kontrollbild: Parallelblick L/R, Kreuzblick R/L oder Rot/Cyan-Anaglyph.
  Ansichtswahl ändert keine Exportoptionen.
- Neutrale Informationen und entfernte Duplikate. Gold/Fettschrift/Warndreieck
  nur für notwendige Klärung oder zu behebende Fehler. SDR-Annahmen und
  Untertitelverlust sind normale Hinweise.
- Player-Kennungen mit Herkunft in Klammern im Auswahlmenü. Im Dateinamen stehen
  nur die Zeichen der Kennung. Keine zusammengesetzten Kodi/Bino-Vorschläge;
  alte Dateinamen bleiben als Eingabe erkennbar und eigene Zusätze bleiben möglich.

## Bewusste Begrenzungen

MV-HEVC wird als Eingabe mit beiden gekennzeichneten Halbbildern unterstützt.

Die bestehende H.265-Ausgabe und die Bibliotheken des HEIF-Lesers behalten ihre
benötigten Komponenten, Quellarchive und Lizenznachweise.

Nicht enthalten: AVIF-Aktivierung, HDR-Tonemapping/volle HDR-Erhaltung, HEIC/AVIF-
Ausgabe, Spatial-Photo-Erstellung, separate L/R-Dateipaare, HDMI-Frame-Packing-
Export, RAW-Entwicklung oder Tiefenkarten-Synthese. Keine neuen Produkt-
Sperrprüfungen für gewöhnliche Quellen und keine vollständige Nachkontrolle
fertiger Medien.

## Abnahme und Veröffentlichung

Vollständige Kern-/GUI-Suite, native Windows-BD-3D/MVC/MV-HEVC-Eingabeprüfungen,
großes LPCM sowie echte HEIF- und Dual-Import-/Exportfälle in der gepackten Anwendung
auf Windows x64, Linux x64 und macOS Apple Silicon.

Version, Titel, Paket-Selbsttest, Dateinamen, Anleitungen und Release Notes verwenden
die gemeinsame Versionsquelle. Testbuilds sind Artefakte. Stabile Veröffentlichung
verwendet die geprüften Plattformpakete. Die bestehende Version 1.0 erhält
separat die Restzeitkorrektur bei unveränderter Versionsnummer.

Details: [TESTPLAN_1.1.md](TESTPLAN_1.1.md), [CHANGES_1.1_DE.md](CHANGES_1.1_DE.md)
und [TECHNICAL_REFERENCE.md](TECHNICAL_REFERENCE.md).

