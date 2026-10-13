# TransCora 1.1: Änderungen gegenüber 1.0

Stand: 13. Oktober 2026. Testfassung im Zweig `prepare/v1.1`; noch keine öffentliche Veröffentlichung.

| Bereich | Änderung |
| --- | --- |
| Dual | Ein- und Ausgabe mit zwei getrennten L/R-Videospuren. MP4 voreingestellt, MKV wählbar; Größe je Halbbild, L/R-Tausch, Tonoptionen, Fortschritt und Abbruch. `-dual` ermöglicht automatische Erkennung; sonst Quelllayout ausdrücklich wählen. Zeitlich abweichende Spuren werden gemeldet. |
| Kontrollbild | BD-3D und Dual zeigen beide Halbbilder als Parallelblick, Kreuzblick oder Rot/Cyan-Anaglyph. Die Ansicht verändert keine Ausgabeoptionen. |
| Dateinamenszusätze | Playernamen in Klammern im Auswahlmenü: Kodi, Bino bzw. Bino/Stereoscopic Player. Dateinamen enthalten nur die Kennung. Zusammengesetzte Vorschläge wie `.3D.HTAB-tbh` entfallen; bestehende Namen bleiben lesbar. |
| Restzeit | Gemeinsamer, nach Videodauer gewichteter Verarbeitungsdurchschnitt für den Stapel. Die Schätzung bleibt bei Dateiwechseln und verspäteten Meldungen erhalten; unterschiedliche Auflösungen und Bildraten sperren sie nicht. |
| Bearbeitungszeit | Feste Spalte hinter Status, numerisch sortierbar. Warteschlange und Pausen zählen nicht mit. |
| Abschlussjournal | `TransCora-Journal.json` je Ausgabeordner erkennt unveränderte erfolgreiche Aufträge wieder und stellt Zeit und Ergebnisse wieder her. Parallele Abschlüsse werden zusammengeführt. |
| Journalfehler | Beschädigte oder fehlende Nachweise verhindern keinen Import. Schreibfehler werden gemeldet; fertige Medien bleiben erhalten. |
| Dateilisten | Fertige entfernen für Videos/Bilder. Entfernen per Button oder Entf folgt der sichtbaren Sortierreihenfolge und erhält den Fokus. |
| Pause | Nach Datei pausieren, Wunsch zurücknehmen, Fortsetzen und Abbrechen. Pause nach vollständigem Export und Journaleintrag. |
| Mono-Video | Linkes oder rechtes Halbbild direkt wählen; L/R-Tausch wird berücksichtigt. |
| Zeilenquellen | Stereo-Zeilen werden vor Skalierung getrennt rekonstruiert. Erste Zeile und L/R-Zuordnung bleiben erhalten. |
| Frame sequential | Aufeinanderfolgende Halbbilder werden vor Größen-/Bildratenanpassung zu Paaren verbunden. Einzelbildrate und Paarbildrate werden unterschieden; Ton und Laufzeit bleiben erhalten. |
| HEIC/HEIF | SDR-Fotos, gekennzeichnete Stereo-HEIC und Spatial Photos. Stereo-Gruppe bestimmt L/R; Orientierung und ICC/NCLX werden berücksichtigt. Zusatzbilder werden nicht als zweites Halbbild gewählt. |
| Hinweise | Farbannahmen, Abläufe und Formatfolgen neutral. Gold/Fettschrift/Warndreieck nur für erforderliche Klärung oder zu behebende Fehler. Doppelte Hinweise und pauschale Warnungseinstufung entfallen. |
| Bedienung | Unveränderte Eingaben setzen fertige Aufträge nicht zurück. Beschriftungen und Spalten berücksichtigen Deutsch/Englisch. |
| Bereinigung | Zusätzlicher MV-HEVC-Encoderprototyp, zugehörige Prüfungen und überholte Planungsdokumente entfernt. MV-HEVC-Dekodierung bleibt erhalten. Versionsquelle vereinheitlicht. |

## Warnungsprüfung

In 1.0 wurden automatische SDR-Farbannahmen als Benutzerwarnungen dargestellt.
In 1.1 bleiben sie neutral, ebenso Untertitelverlust, Bildratenanpassung,
Deinterlacing, Stereo-Rekonstruktion, LPCM und Blu-ray-Playlistwahl.
Hervorgehoben bleiben unbekannte oder widersprüchliche Quelllayouts,
zu klärende MVC-L/R-Zuordnung, manuelle Interpretation gegen Quellhinweise,
4:4:4-Playerkompatibilität und zu behebende Fehler.

Bei unbekannter MVC-Reihenfolge dient das Kontrollbild zum Prüfen der Tiefe:
Parallelblick, Kreuzblick oder Rot/Cyan-Brille verwenden und bei umgekehrter
Tiefe L/R tauschen. Die Anwendung erfindet keine fehlenden Quellangaben.

## Umfang

MV-HEVC ist ausschließlich Eingabe, kein Ausgabeziel. HDR-Tonemapping,
HEIC/AVIF-Ausgabe, Spatial-Photo-Erstellung und AVIF-Import gehören nicht zu 1.1.
Die bestehende Veröffentlichung 1.0 wird nicht überschrieben.

Prüfungen und Paketstatus: [TESTPLAN_1.1.md](TESTPLAN_1.1.md).

