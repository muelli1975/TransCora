# TransCora 1.1: vereinbarter Umfang und Umsetzung

Stand: 12. Oktober 2026. Entwicklungszweig: `prepare/v1.1`.

Diese Datei beschreibt den vereinbarten Umfang. Journal, Bearbeitungszeit,
Listenaktionen und die Bereinigung doppelter Hinweise sind als erster
Entwicklungsstand implementiert. Pausensteuerung und Mono-Halbbildwahl sind
ebenfalls umgesetzt. Zeilenverschachtelte und Frame-sequential-Eingaben sind
integriert. HEIF-Bildimport nutzt den separaten Leser; die plattformübergreifende
Paketabnahme läuft. MV-HEVC-Encoding wird separat erprobt.
Die Abnahme ist im Testplan dokumentiert. Grundlage ist `main` bei
`7ef801f8aff9697ecd40882a763fdac0cdd2d3fe`; die veröffentlichte 1.0 wurde aus
`c3f23155db3c56da8377bc7e4dd7bf9bc1eb35e8` gebaut. Die Vorbereitung ändert
weder die ausgelieferten Funktionen noch das Release `v1.0`; Anwendungscode von
1.1 bleibt bis zur Freigabe ausschließlich auf dem Entwicklungszweig.

## 1. Dateiliste und Bedienung

- Feste Spalte **Bearbeitungszeit / Processing time** unmittelbar hinter Status,
  bei Videos und Bildern. Gemessen vom Beginn der eigentlichen Verarbeitung bis
  zur vollständigen Veröffentlichung aller Ausgaben, einschließlich Vorbereitung,
  Ton und Verpackung. Vorprüfung, Warteschlange und Pausen zählen nicht dazu.
- Anzeige bei erfolgreichem Abschluss als `HH:MM:SS`, intern Sekunden mit
  Nachkommastellen für numerische Sortierung. Ohne bekannten Abschlusswert `—`.
  Nach einem fehlgeschlagenen neuen Versuch bleibt kein alter Erfolgswert stehen.
- Datei, Quelle und FPS dürfen schmaler werden. FPS bleibt präzise wie in 1.0;
  Werte wie `29,973` werden weder gerundet noch abgeschnitten. Breiten anhand
  tatsächlicher Schriftmaße für beide Sprachen, Sortierpfeile und längere Ziele
  prüfen. Frame sequential muss als Quelllayout lesbar bleiben.
- **Fertige entfernen / Remove completed** links neben Standardeinstellungen.
  Entfernt nur erfolgreich abgeschlossene Einträge, ohne Medien oder Journal zu
  löschen. Deaktiviert, wenn es keine fertigen Einträge gibt oder ein Stapel läuft.
- Entfernen per Entf und per Entfernen-Button wählt anschließend den nächsten
  verbliebenen Eintrag in der sichtbaren Reihenfolge. Am Listenende den vorherigen
  wählen. Bei Mehrfachauswahl den ersten verbliebenen Eintrag hinter dem aktiven
  gelöschten Eintrag wählen, ersatzweise davor. Fokus bleibt in der Liste; leerer
  oder unverändert gelassener Liste keine künstliche Auswahl hinzufügen.
- Videos und Bilder verwenden dieselbe Auswahlregel. Sortierung und Tastatur-
  Bedienung dürfen nicht durch eine spätere Aktualisierung zurückgesetzt werden.
- Konsequent **Halbbild/Halbbilder** in deutschen Oberflächentexten und Anleitungen.
  Technische Bezeichnungen wie **Frame sequential** bleiben in beiden Sprachen.
- Hinweise nur einmal über alle Infobereiche hinweg anzeigen. Gold, Fettschrift
  und Warndreieck ausschließlich bei erforderlicher Benutzerhandlung. Übliche
  SDR-Farbannahmen, Ablaufhinweise und normale Statusmeldungen bleiben neutral.

Betroffene Stellen: `gui/window.py`, `gui/images_panel.py`, `gui/file_list.py`,
Jobmodelle in `core/model.py` und `core/images.py`, vorhandene GUI-Übersetzungen.

## 2. Abschlussjournal

Dateiname: **`TransCora-Journal.json`**, einmal pro gewähltem Ausgabeordner.
Das Journal enthält erfolgreiche Abschlüsse, keine Medien und keinen gespeicherten
Fortschritt innerhalb einer teilweise kodierten Datei.

Ein Abschlussdatensatz enthält:

| Feld | Inhalt |
| --- | --- |
| `schema_version` | Version des Journalformats |
| Quelle | Normalisierter Pfad, Dateigröße, Änderungsdatum in Nanosekunden |
| Einstellungen | Vollständige wirksame Ausgabeoptionen und erkannte L/R-Zuordnung |
| Ergebnisse | Tatsächliche relative Ausgabepfade, Größe und Änderungsdatum jeder Datei |
| Abschluss | UTC-Zeitpunkt und gemessene Bearbeitungszeit in Sekunden |
| Herkunft | TransCora- und Werkzeugversionen zur Nachvollziehbarkeit |

Der Wiedererkennungsschlüssel basiert auf Quelle und wirksamen Einstellungen,
nicht auf der bei jedem Import neu erzeugten GUI-Job-ID. Bei ISO-/Ordnerquellen
auch die tatsächlich benutzten Playlist-/Quelldateiinformationen berücksichtigen.
Ausgabeunterordner, Suffix, Disc-Titel, Größe, Bildrate, Halbbildreihenfolge,
Codec-/Ton-/Metadatenoptionen und neue Optionen gehören zur Zuordnung.

Vorhandene Einträge beim Import, Listenladen und Start abgleichen. Automatisch
erledigt ist ein Auftrag nur bei passenden Quelldaten und Einstellungen und wenn
**alle** dokumentierten Ausgaben unverändert vorhanden sind. Bilder können mehrere
Ausgaben erzeugen, etwa beide Halbbilder einer MPO-Datei. Fehlende oder veränderte
Dateien machen den Nachweis unbrauchbar; keine zusätzliche inhaltliche Medien-
Prüfung, vollständige Dekodierung oder Hash-Berechnung großer Dateien einführen.

Fertigstatus, Ausgabepfade und Bearbeitungszeit in der Liste wiederherstellen.
Änderungen an Quelle, Einstellungen oder Ausgabeordner lösen den Abgleich erneut
aus. Eine bereits erfolgreich erledigte Datei wird nicht nochmals kodiert.
Unvollständige Dateien werden nach einem Neustart von Anfang an verarbeitet.
Offene Aufträge bleiben über die vorhandene Funktion Liste speichern/laden
transportierbar; das Journal ersetzt die gespeicherte Jobliste nicht.

Nach jedem vollständigen Erfolg atomar schreiben, nach dem Muster von
`core/storage.py:write_json`. Erst nach Veröffentlichung aller Ausgabedateien
einen Abschluss eintragen. Fehler und Abbruch erzeugen keinen Erledigt-Nachweis.
Ein Schreibfehler darf eine fertige Ausgabe nicht löschen oder als Kodierfehler
ausgeben; Status/Log nennen dann den fehlenden Journalnachweis. Parallele
Schreiber müssen ihre Datensätze zusammenführen, ohne fremde Abschlüsse zu verlieren.

Entf, Entfernen und Fertige entfernen ändern das Journal nicht. Kein automatisches
Ablaufdatum und kein zusätzlicher Löschbutton. Löschen der Journaldatei reicht.
Nach einem späteren Erfolg kann eine neue Journaldatei entstehen; vorherige
Datensätze dürfen dabei nicht aus einem alten Speicherstand zurückgeschrieben werden.
Eine beschädigte oder unbekannte Journalversion darf den Medienimport nicht sperren
und soll nicht still überschrieben werden.

Dateien ohne Journaleintrag werden nicht übernommen oder allein anhand ihres Namens
als fertig erkannt. Die vorhandene Vergabe nummerierter Alternativnamen bleibt.
Es gibt keine neue Aktion „Als erledigt markieren“.

Umsetzung: gemeinsames `core/journal.py`, gemeinsame Ergebnisdaten in beiden
Jobmodellen, Abgleich vor der Namensreservierung, Abschluss im jeweiligen Worker.

## 3. Nach aktueller Datei pausieren

Der bestehende Start-Button wechselt während der Verarbeitung zu
**Nach Datei pausieren / Pause after file**. Keine zusätzliche Schaltfläche.
Buttonbreite und gesamte untere Leiste mit den längeren Beschriftungen auf beiden
Sprachen prüfen; keine abgeschnittene Beschriftung oder Überlappung zulassen.
Erneuter Klick auf **Pause vorgemerkt / Pause requested** hebt den Wunsch auf.
Nach vollständig abgeschlossener Datei einschließlich Journal wird der Stapel
pausiert: **Fortsetzen / Resume**, Status **Stapel pausiert / Batch paused**.
Der letzte Auftrag erhält seinen normalen Fertigstatus.

Fortsetzen verwendet denselben geordneten Auftragssnapshot. Es startet weder
fertige Dateien erneut noch den aktuellen Auftrag mitten in einer Kodierung.
Abbrechen bleibt jederzeit erreichbar, auch während einer Pause; Beenden der
Anwendung darf nicht an einem wartenden Worker hängen. Wenn nach der aktuellen
Datei kein Auftrag mehr folgt, endet der Stapel regulär statt in einer leeren Pause.
Pausenzeit verfälscht keine Bearbeitungszeit oder Restzeitschätzung. Parameter-
und Listenänderungen bleiben während eines aktiven Stapels wie bisher gesperrt.

Umsetzung: gemeinsame Pausensteuerung für Video- und Bildworker, sauber getrennt
vom bestehenden Cancel-Event; GUI-Zustand aus Worker-Ereignissen aktualisieren.

## 4. Mono und neue Stereo-Eingaben

- Mono-Ausgabe bei Videos: **Linkes Halbbild / Rechtes Halbbild** direkt wählbar.
  Entsprechende Ausgabesuffixe `_mono_l` und `_mono_r`; keine zweite L/R-Vertauschung
  versteckt anwenden. Die Bildausgabe bietet diese Ziele bereits.
- Zeilenverschachtelte Eingaben für Videos und Bilder: erste Zeile und L/R-
  Zuordnung beachten; zunächst gespeicherte Halbbildzeilen getrennt rekonstruieren.
  Zeilenverschachtelung ist keine zeitliche Interlace-Aufnahme. Kein Deinterlacer
  darf linke/rechte Zeilen vermischen. Geometrie und fehlende räumliche Details
  korrekt behandeln; Vorschaubild und alle bestehenden Ziele weiterverwenden.
- **Frame sequential** bei Videos: zuerst benachbarte L/R-Einzelbilder zu
  Stereopaaren zusammenführen, erst danach Größe oder Zielbildrate ändern.
  Beispielsweise 120 Einzelbilder/s ergeben 60 Stereopaare/s. Laufzeit und Ton
  erhalten. Erste Halbbildzuordnung, ungerade Bildanzahl und variable Zeitstempel
  ausdrücklich testen und einen einzelnen ungepaarten Rest nicht verschweigen.
  Präzise Quell-FPS-Anzeige erhalten; Einzelbildrate und Stereopaar-Rate in den
  Details unterscheiden. Alte Listen behalten ihre bisherigen Layouts und Optionen.

Gemeinsame Quellnormalisierung vor `core/engine.py:build_graph` und der BD-
Vorbereitung verwenden. `LAYOUTS`, Namens-/Stereo-Metadaten-Erkennung, Vorschaubild,
Größenanzeige und BD-3D müssen dieselbe Geometrie und Paar-Zeitbasis benutzen.
Keine zusätzliche selbst entwickelte Sperrprüfung einführen.

## 5. Aktuelle Bildformate

HEIF/HEIC als Eingabe, einschließlich korrekt gekennzeichneter Stereo-HEIC/Apple
Spatial Photos. Beide Halbbilder aus der Stereo-Gruppe zuordnen; nicht blind die
ersten zwei Bildobjekte nehmen. Vorschaubilder, Alpha, Tiefenkarten und HDR-Gainmaps
sind keine zweiten Halbbilder. Ein normales HEIC bleibt ein normales Foto.

Zunächst klar definierte SDR-Ausgabe über die bestehenden Bildziele. Orientierung,
ICC/NCLX-Farbkennzeichnung und L/R-Zuordnung beachten. HDR-Dateien brauchen eine
bewusste SDR-Behandlung; die bloße Reduktion auf 8 Bit ist kein vollständiges
Tonemapping. Keine vollständige HDR-Erhaltung in 1.1 versprechen.

`pillow-heif`/`libheif` als zusätzliche Bildleser prüfen, einschließlich tatsächlicher
Stereo-Gruppen-Unterstützung der verwendeten Wheels. Auf Windows x64, Linux x64 und
macOS Apple Silicon testen; anschließend exakte Abhängigkeiten festlegen und native
Bibliotheken, Lizenzdateien und Herkunftsnachweise in den Paketbau aufnehmen.
Die bloße Unterstützung in einer neueren Dokumentation ist noch kein Paketnachweis.

AVIF-Eingabe ergänzen, wenn die Paketprüfung unkompliziert gelingt. Statische SDR-
Einzelbilder sowie explizites SBS/OU; Animationen und beliebige Mehrbilddateien nicht
stillschweigend auf das erste Bild reduzieren. HEIC-/AVIF-Ausgabe und Spatial-Photo-
Erstellung sind kein vereinbartes neues Ausgabeziel.

## 6. MV-HEVC-Ausgabe: frühe Machbarkeitsprüfung

Geplantes eigenständiges Stereo-Ausgabeziel mit zwei Halbbildern, zunächst SDR.
Kein gewöhnliches gepacktes H.265 als MV-HEVC ausgeben. Keine erfundenen räumlichen
Kamerametadaten hinzufügen.

Zuerst einen festgelegten x265-Build mit Multiview-Unterstützung, zwei Eingabeströmen
und wiederholbarem Build prüfen. Danach passenden Container mit vollständigen Layer-
und L/R-Informationen erzeugen. Mit FFmpeg beide Views ausdrücklich dekodieren:
Halbbildzuordnung, Bildzahl, Zeitstempel, Laufzeit, Ton und sichtbare Qualität prüfen.
Eine erfolgreiche Basis-Layer-Dekodierung allein reicht nicht. Vor Freigabe Build-
Herkunft, Quellen und Lizenzhinweise der zusätzlichen Werkzeuge dokumentieren.

Ohne Test auf einem Apple-Gerät nur die technisch geprüfte Stereo-Kompatibilität
angeben, keine bestätigte Vision-Pro-Wiedergabe behaupten. Fehlt ein funktionierender
Encoder-/Container-Weg, die Entscheidung offen dokumentieren, bevor ein sichtbares
Ausgabeziel oder eine Versionsfreigabe erfolgt.

## 7. Reihenfolge und Freigabe

1. Journal/Ergebnisdaten, Bearbeitungszeit, Sortierung und Listenaktionen.
2. Pausensteuerung und Mono-Halbbildwahl.
3. Neue Stereo-Eingaben und Vorschau einschließlich BD-3D.
4. HEIC/HEIF und Paketprüfung; AVIF bei unkompliziertem Ergebnis.
5. MV-HEVC-Prototyp bereits zu Beginn der technischen Vorbereitung prüfen;
   Ergebnis vor Integration bewerten.
6. Testbuild, vollständige bestehende Regressionen und neue Tests auf allen
   unterstützten Systemen; kurze sachliche Release Notes erst für fertige Funktionen.

Die Testfälle stehen in [TESTPLAN_1.1.md](TESTPLAN_1.1.md). Bestehende 1.0-Vorgaben
(insbesondere BD-3D 1080p/23,976 und 40 Mbit/s), Ordnerimport, Warnfarben, Log,
Sprachwechsel und präzise FPS bleiben durch Regressionen abgesichert.

Vor dem ersten 1.1-Paket alle hart kodierten 1.0-Paketnamen in `scripts/build_windows.py`
und `.github/workflows/build.yml` auf eine gemeinsame Versionsquelle umstellen.
Der bisherige Publish-Job aktualisiert `v1.0` automatisch bei Push auf `main`.
Diesen Pfad **vor einem Merge von 1.1-Anwendungscode** ersetzen: Testbuilds erzeugen
nur Artefakte, die Veröffentlichung von 1.1 erhält einen eigenen ausdrücklich
ausgelösten Release-Lauf und darf `v1.0` nicht verschieben oder überschreiben.

Zur späteren Versionierung gehören `transcora/__init__.py`, Fenstertitel,
Paket-Selbsttest, Dokumentation, Downloadnamen und Release Notes. Der Entwicklungsstand verwendet
`1.1-dev`; Downloadlinks verweisen weiterhin auf die veröffentlichte stabile 1.0.

Nicht vorgesehen: HDMI-Frame-Packing-Dateiexport, fertige Ausgaben in TransCora
nachträglich kontrollieren, Übernahme alter Ausgaben ohne Journal, Journal-
Löschbutton, RAW-Entwicklung, Tiefenkarten-zu-Stereo-Synthese, weitere exotische
Layouts oder vollständige HDR-Pipeline. Separate L/R-Dateipaare sind ein späterer
größerer Schritt.

## Primärquellen der Vorbereitung

- [FFmpeg stereo3d](https://ffmpeg.org/ffmpeg-filters.html#stereo3d)
- [x265 4.1: Multiview encoding](https://x265.readthedocs.io/en/4.1/cli.html#multiview-encoding)
- [Apple: Writing spatial photos](https://developer.apple.com/documentation/imageio/writing-spatial-photos)
- [pillow-heif: Bildobjekte und Stereo-Gruppen](https://pillow-heif.readthedocs.io/en/stable/reference/HeifImage.html)
- [Pillow: AVIF](https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html#avif)
- [Android: Ultra HDR](https://developer.android.com/media/platform/hdr-image-format)
