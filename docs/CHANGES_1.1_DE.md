# TransCora 1.1: Änderungen gegenüber 1.0

Stand: 13. Oktober 2026. Entwicklungszweig `prepare/v1.1`; noch keine veröffentlichte 1.1.

## In der Anwendung umgesetzt

| Bereich | Änderung |
| --- | --- |
| Bearbeitungszeit | Feste Spalte hinter Status für Videos und Bilder; HH:MM:SS und numerische Sortierung. Umfasst Vorbereitung, Kodierung, Ton und Veröffentlichung; Warteschlange und Pausen zählen nicht. |
| Abschlussjournal | TransCora-Journal.json pro Ausgabeordner. Erfolgreiche Aufträge werden nach Wiederimport anhand Quelle, wirksamer Einstellungen und aller unverändert vorhandenen Ausgaben wiedererkannt. Status, Ausgabepfade und Bearbeitungszeit werden wiederhergestellt. |
| Journalfehler | Fehlender, beschädigter oder nicht schreibbarer Journalnachweis blockiert den Medienimport nicht. Fertige Ausgaben bleiben erhalten; Schreibfehler werden gemeldet. Parallele Abschlüsse werden zusammengeführt. |
| Dateilisten | Fertige entfernen für Videos und Bilder; Medien und Journal bleiben erhalten. Nach Entfernen per Button oder Entf folgt die Auswahl der sichtbaren Reihenfolge. Sortierung und Fokus bleiben erhalten. |
| Pause | Start wird während der Konvertierung zu Nach Datei pausieren. Wunsch kann zurückgenommen werden. Pause erfolgt nach vollständigem Dateiabschluss und Journal; Fortsetzen beginnt beim nächsten Auftrag. Abbruch auch in der Pause. |
| Mono-Video | Linkes oder rechtes Halbbild direkt wählbar, mit _mono_l bzw. _mono_r. L/R-Tausch wird berücksichtigt. |
| Zeilenverschachtelte Eingaben | Videos und Bilder: Stereo-Zeilen werden getrennt rekonstruiert, bevor skaliert wird. Erste Zeile und L/R-Zuordnung werden berücksichtigt; keine Vermischung durch einen zeitlichen Deinterlacer. |
| Frame sequential | Video: benachbarte Halbbilder werden vor Größen-/Bildratenanpassung zu Stereopaaren verbunden. Laufzeit und Ton bleiben erhalten. Einzelbild- und Paarbildrate werden unterschieden; ungepaartes Schlussbild ist im Hinweis dokumentiert. |
| HEIC/HEIF | SDR-Import normaler Fotos und gekennzeichneter Stereo-/Apple-Spatial-Photos über separaten gepackten Leser. Stereo-Gruppe statt beliebiger erster zwei Bildobjekte; Orientierung und ICC/NCLX werden berücksichtigt. HDR wird erkannt und nicht still als gewöhnliches SDR ausgegeben. |
| Hinweise | Gewöhnliche Farbannahmen, Abläufe und Formatfolgen erscheinen neutral. Doppelte Hinweise entfallen. Gold/Fettschrift/Warndreieck nur für ausdrücklich zur Klärung eingestufte Hinweise und zu behebende Fehler. |
| Bedienung | Unverändert bestätigte Eingaben setzen fertige Aufträge nicht zurück. Spaltenbreiten und Pausenbeschriftungen berücksichtigen Deutsch/Englisch und neue Quelllayouts. |
| Paket-/Releaseweg | Gemeinsame Versionsquelle, Entwicklungsname 1.1-dev, gepackter HEIF-Leser mit Quellen und Lizenzen. Stabile Veröffentlichung über ausdrücklich ausgelösten Workflow; bestehendes v1.0 bleibt erhalten. |

## Ergebnis der Warnungsprüfung

In der veröffentlichten 1.0 wurden automatische SDR-Farbannahmen ausdrücklich in
`review_warnings` übernommen und deshalb gold/fett mit Warndreieck angezeigt.
Die bisherige 1.1 hatte dies bereits korrigiert. Die aktuelle Nachprüfung ergänzt:
Untertitelverlust ist ein neutraler Hinweis, da TransCora keine Untertitelübernahme
zur Auswahl anbietet. Pläne ohne ausdrückliche `review_warnings` stufen ihre Hinweise
nicht mehr pauschal als Warnung ein.

Neutral bleiben insbesondere SDR-Farbannahmen, Bildratenanpassung, Deinterlacing,
Half-/Full-Rekonstruktion, Zeilen-/Paarbildung, BD-3D-Verarbeitung, LPCM und die
automatische Wahl der längsten Blu-ray-Playlist. Auch der Hinweis auf die geringere
Farbauflösung des bereits gewählten Kompatibilitätsprofils bleibt neutral.

Hervorgehoben bleiben unbekanntes/widersprüchliches Quelllayout, zu prüfende
L/R-Zuordnung bei fehlenden MVC-Angaben, manuelle Interpretation gegen andere
Quellhinweise, 4:4:4-Playerkompatibilität sowie Fehler, die vor einem erneuten
Versuch behoben werden müssen.

Fünf gezielte Kern-/GUI-Regressionen für Einstufung, Deutsch/Englisch,
Warnsymbol, Formatierung und Duplikate bestehen lokal. Der letzte vollständige
Stand vor dieser kleinen Nachkorrektur bestand jeweils 159 Tests auf Windows,
Linux und macOS und alle Paketprüfungen:
https://github.com/muelli1975/TransCora/actions/runs/38356176846

## Technisch geprüft, noch kein neues Anwendungsausgabeziel

MV-HEVC mit x265 4.3 Multiview und FFmpeg 7.1.1: 36 pixelgleiche Bilder je View über
drei GOPs, L/R und R/L, Zeitstempel, Ton und getrennte hvcC/lhvC-Konfigurationen.
Gepacktes SBS über stdin sowie blockweise, atomare MP4-Containeranpassung sind
geprüft. Der Writer hält nur moov-Metadaten im Speicher und korrigiert stco/co64.
Lauf: https://github.com/muelli1975/TransCora/actions/runs/38356177448

Noch offen: Encoder-Paketierung mit Quellen/Lizenzen, Integration als Ausgabeziel,
Fortschritt, Abbruch, Tonoptionen, Einstellungen, Journal und Pakettests des Ziels.
Apple-Gerätewiedergabe ist ungeprüft; räumliche Kameradaten werden nicht erfunden.

AVIF ist derzeit nicht aktiviert. HDR-Tonemapping/volle HDR-Erhaltung,
HEIC/AVIF-Ausgabe und Spatial-Photo-Erstellung gehören nicht zum umgesetzten Umfang.

Details: [PLAN_1.1.md](PLAN_1.1.md) und [TESTPLAN_1.1.md](TESTPLAN_1.1.md).
