# TransCora 0.1.3

- Nach Doppelpunkten beginnen Programmtexte mit Großbuchstaben. Dateinamen,
  Pfade, technische Kennungen und Werte behalten ihre tatsächliche Schreibweise.
- Framerate-Zusätze heißen jetzt etwa `_30fps-tbh` und `_23.976fps-lrh`.
  Alte Zusätze werden weiterhin beim Erzeugen neuer Namen bereinigt.
- Der optionale Anaglyph-Modus heißt **Hohe Farbtiefe · 10 Bit / 4:4:4**.
- Ausgewählte Dateien behalten die goldene Markierung.
- Je Ausgabeordner bleiben die letzten zehn Laufprotokolle erhalten.
  **Logs löschen** im Logfenster ist nur bei ruhendem Programm verfügbar.
  Konvertierungsfehler werden auch im gespeicherten Laufprotokoll festgehalten.
- Die erste BD-3D-Strecke wird separat unter Windows geprüft: Portable FRIM-
  Software-Kodierung, AVC/MVC, tsMuxeR 2.6.12, UDF-2.50-ISO und SSIF.
  Die Vorbereitung unterstützt Full-/Half-SBS und Full-/Half-OU bei konstanten
  23,976 oder 24 fps. Bei 24 fps bleiben alle Bilder erhalten; Bild und Ton werden
  auf 23,976 fps verlangsamt. Noch kein BD-3D-Ziel in der Programmoberfläche.

Das Programm bleibt portabel. Die Windows-Teststrecke lädt Werkzeuge nur beim
Bauen; das gestartete Programm greift nicht auf das Netzwerk zu.
