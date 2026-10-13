# TransCora 1.1: Abnahme

Die Testfassung wird aus `prepare/v1.1` gebaut. Eine Veröffentlichung erfolgt
erst nach den Anwendungstests und den Prüfungen der tatsächlich gepackten Programme.

| Bereich | Abnahme |
| --- | --- |
| Dual | MP4 und MKV, beide unabhängig dekodierte Spuren, L/R und Tausch, gleiche Bildzahl und Bildrate, Ton, Wiederimport, ungleiche Geometrie, abweichende Zeitstempel, Abbruch ohne Veröffentlichung. |
| Stereo-Kontrollbild | BD-3D/Dual: Parallelblick, Kreuzblick, Rot/Cyan; beide Halbbilder und richtige Geometrie. Zieloptionen unverändert. |
| Dateinamenszusätze | Klammerzuordnung in DE/EN, nur rohe Kennung im Dateinamen, eigene Zusätze bleiben unverändert; alte zusammengesetzte Namen weiter erkennen. |
| Warnungen | Gewöhnliche Hinweise neutral; nur Klärung/Fehler gold/fett mit Dreieck; keine Duplikate. |
| Zeit/Journal | Video und Bilder, numerische Sortierung, Wiederimport unveränderter Abschlüsse, mehrere Ausgaben, geänderte Quelle/Optionen/Ergebnisse, beschädigte und nicht schreibbare Journale, parallele Schreiber. |
| Listen/Pause | Sichtbare Reihenfolge und Fokus nach Entfernen; Fertige entfernen; Pause nach Dateiabschluss/Journal, Fortsetzen, Wunsch zurücknehmen, Abbruch auch während Pause. |
| Mono/Zeilen | Asymmetrische Halbbilder, beide Zuordnungen, Tausch; Stereo-Zeilen vor Skalierung trennen, kein zeitlicher Deinterlacer. |
| Frame sequential | 48/50/59,94/120 Einzelbilder/s, Paarbildrate, letzte Paare, ungepaartes Schlussbild, variable Zeitstempel und Ton. |
| HEIF | Normales/gedrehtes Foto, gekennzeichnete Stereo-Gruppe, echte Spatial Photo, vertauschte Item-Reihenfolge, ICC/NCLX, Zusatzdaten und HDR-Erkennung. |
| Native Medien | Tatsächliche BD-3D-ISO/M2TS, alle BD-Modi, Zeitstempeljitter, großes LPCM, MVC und MV-HEVC-Eingaben mit beiden Views, originales Fujifilm-MPO. |
| Pakete | Windows x64, Linux x64, macOS Apple Silicon: vollständige Suite, Start des gefrorenen Programms, HEIF und Dual durch das tatsächlich gepackte Programm; Quellen/Lizenzen vollständig. |

## Prüfstand

Der vorherige Stand `6b8e071` bestand die vollständige CI und Paketprüfung:
https://github.com/muelli1975/TransCora/actions/runs/38369823814

Die ergänzten lokalen Dual- und Menütests sind bestanden. Die vollständige
Abnahme des abschließenden Standes und die Paketprüfungen laufen nach dem Commit.
Ergebnisse werden hier mit dem zugehörigen Lauf dokumentiert.

Auf dem lokalen Windows-Testhost verhindern zwei ExifTool-Starts einen vollständigen
Bildmetadatentest (WinError 623). Dafür sind die unabhängigen CI- und Paketläufe maßgeblich.

## Wiederholbare Prüfungen

```text
python -m unittest discover -s tests -v
python scripts/multiview_test.py
python scripts/check_dual_package.py --application dist/TransCora/TransCora.exe
```

Unter Linux GUI-Tests mit `xvfb-run -a` starten. Die Paketprüfung verwendet
unter Linux/macOS den ausführbaren Pfad ohne `.exe`. Kleine synthetische
Testmedien werden erzeugt; echte Kamera-Fixtures haben dokumentierte Herkunft.

MV-HEVC-Encoding und Geräte-Zertifizierung gehören nicht zu dieser Abnahme.
