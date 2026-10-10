# TransCora: Auswertung der FFBatch-Parameter

Stand: 10. Oktober 2026. Phase 1, Entwicklungsgrundlage; noch keine fertige Anwendung.

Grundlage für die Video-Workflows ist Christophs `FFBatch-Presets.txt` mit zehn Parameterketten. Nach Christophs Präzisierung ist **ausschließlich AnaglyphBatch die Verfahrensreferenz**: 17 Verfahren ohne CIELab. Die FFBatch-Kommandos bleiben unverändert in `reference/FFBatch-Presets.txt` erhalten; ihre sieben Anaglyphenketten sind Analysebeispiele und keine zusätzlich beizubehaltenden Produktvarianten. Anaglyphen verwenden standardmäßig 4:4:4 mit Hinweis auf eingeschränkte Player-Unterstützung. Ein optionaler 4:2:0-Kompatibilitätsmodus muss den Qualitätsverlust anzeigen; ein zusätzlicher H.264-Modus mit 10 Bit/4:4:4 darf vorgesehen werden. Ergänzungen sind als Vorschläge oder offene Prüfungen gekennzeichnet.

## 1. Übersicht aller vorhandenen Kommandos

Die Datei enthält FFBatch-Parameterfragmente, keine vollständigen Shell-Kommandos: FFmpeg-Aufruf, Eingabedatei, Ausgabedatei und damit der Container fehlen. Alle zehn verwenden `-c:v libx264 -crf 18 -preset slow` und `-c:a copy`. Video wird neu kodiert; Audio soll ohne Neukodierung übernommen werden. Die Auswahl der Tonspuren ist damit noch nicht geregelt.

Alle Eingaben werden als Full-SBS mit dem linken Auge links behandelt. Die ersten sechs Ketten verwenden `stereo3d=sbsl:…`; die letzten vier teilen die Bildbreite mit `crop=iw/2`. Eine automatische Layout-Erkennung, Eingaben mit vertauschten Augen oder Half-SBS-Eingaben sind in den Fragmenten nicht vorgesehen.

| Nr. | Originaltitel | Verarbeitung | Größe laut Original | Besondere Parameter |
|---|---|---|---|---|
| 01 | FULL-SBS → TABH | `stereo3d=sbsl:tb2l`, danach Skalierung | Gepacktes Gesamtbild 1920 × 1080 | Lanczos, `frame-packing=4` |
| 02 | FULL-SBS → HSBS | `stereo3d=sbsl:sbs2l`, danach Skalierung | Gepacktes Gesamtbild 1920 × 1080 | Lanczos, `frame-packing=3` |
| 03 | FULL-SBS → Mono | `stereo3d=sbsl:ml` | Halbe Quellbreite, volle Quellhöhe | Nur linkes Auge, kein Größenlimit |
| 04 | FULL-SBS → Dubois rot/cyan | `stereo3d=sbsl:arcd` | Halbe Quellbreite, volle Quellhöhe | FFmpeg-Verfahren, keine explizite Transferkonvertierung |
| 05 | FULL-SBS → Dubois grün/magenta | `stereo3d=sbsl:agmd` | Halbe Quellbreite, volle Quellhöhe | FFmpeg-Verfahren, keine explizite Transferkonvertierung |
| 06 | FULL-SBS → Dubois amber/blau | `stereo3d=sbsl:aybd` | Halbe Quellbreite, volle Quellhöhe | FFmpeg bezeichnet das Filterpaar als gelb/blau |
| 07 | Full-SBS → Dubois LCD + rot | 16-Bit-RGB, L/R-Split, BT.709 → linear, Matrizen, Addition, linear → BT.709, Rotkorrektur | Halbe Quellbreite, volle Quellhöhe | Rotexponent 0,75; ausdrücklich `yuv444p` und BT.709-Tags |
| 08 | Full-SBS → iaian7 Anachrome | 16-Bit-RGB, getrennte Matrizen und LUTs, Addition, Nachmatrix | Halbe Quellbreite, volle Quellhöhe | Exponenten 0,87 / 1,176; `yuv444p`, BT.709-Tags |
| 09 | Full-SBS → Rendepth | 16-Bit-RGB, LCD-Matrizen, Clip-LUTs, Addition, Kanal-LUTs | Halbe Quellbreite, volle Quellhöhe | Rot 0,625, Grün 1,25, Blau unverändert; `yuv444p` |
| 10 | Full-SBS → Rendepth 2 | Wie 09 mit anderen L/R-Matrizen | Halbe Quellbreite, volle Quellhöhe | Gleiche Kanalexponenten; `yuv444p` |

`TABH` wird in der Oberfläche verständlich als **Half-Over-Under (links oben)** bezeichnet, `HSBS` als **Half-SBS (links links)**. Bei 1920 × 1080 sind die gespeicherten Teilbilder bei HSBS 960 × 1080 und bei Half-OU 1920 × 540. Die Entzerrung gehört zur stereoskopischen Wiedergabe. Die Einordnung der Filtercodes ist in der offiziellen Filterdokumentation beschrieben [1].

### Bedeutung der vier längeren Anaglyphenketten

**Dubois LCD + rot:** Nur diese Vorlage enthält ausdrücklich eine Linearisierung. Die Eingangs-Transferfunktion wird als BT.709 festgelegt. Die Matrixwerte sind genau die aus der Vorlage; sie werden nicht durch die Werte des kurzen FFmpeg-Dubois-Filters ersetzt. Nach der Addition folgt die Rückkonvertierung und dann die Rotkorrektur. Das ist eine eigene Referenzpipeline.

**iaian7:** Die linke Matrix erzeugt ausschließlich den Rotbeitrag, die rechte die Grün-/Blaubeteiligung. Danach werden die jeweiligen LUTs angewendet und die Ergebnisse addiert. Die abschließende Matrix korrigiert die Kanäle gemeinsam. Keine BT.709-Linearisierung in dieser Vorlage.

**Rendepth / Rendepth 2:** Keine explizite Linearisierung. Matrixbeiträge werden vor der Addition getrennt begrenzt; nach der Addition ändern sich Rot und Grün. Rendepth nutzt die Matrizen aus LCD + rot, Rendepth 2 andere. Das identische Gerüst macht sie nicht zu austauschbaren Verfahren.

Die Funktionen `gammaval(…)` sind Potenz-LUTs mit dem angegebenen Exponenten [1]. Diese Zahlen sind Bestandteil des Verfahrens, keine allgemeinen Qualitätsregler. Integer-`colorchannelmixer` begrenzt seine Ausgabe bereits; die zusätzliche Clip-LUT hebt diese Begrenzung nicht auf. Ein Wechsel zu Float und erst abschließendem Clipping könnte deshalb das Ergebnis verändern [4].

## 2. Aus FFBatch ableitbare Referenzpresets

Diese Tabelle bildet zunächst die zehn hochgeladenen Fragmente ab. Die drei `*_ffmpeg`-Dubois-IDs kennzeichnen historische Referenzen, keine zusätzlichen Standardverfahren im endgültigen Menü. Der maßgebliche 17er-Katalog folgt weiter unten. Anzeigenamen können übersetzt werden, ohne Jobdateien umzudeuten.

| Preset-ID | Anzeigename | Zielart | Auflösungsregel der Referenz | Verwendung |
|---|---|---|---|---|
| `video.hsbs.1080` | Half-SBS · 1080p | Stereo-Layout | Gesamtbild 1920 × 1080 | Hauptauswahl |
| `video.hou.1080` | Half-Over-Under · 1080p | Stereo-Layout | Gesamtbild 1920 × 1080 | Hauptauswahl |
| `video.mono.left` | Mono · linkes Auge | Mono | Augenauflösung erhalten | Hauptauswahl |
| `video.anaglyph.dubois_rc_ffmpeg` | Dubois · Rot/Cyan (FFmpeg) | Anaglyphe | Augenauflösung erhalten | Nur Analysebeispiel; kein Produktpreset |
| `video.anaglyph.dubois_gm_ffmpeg` | Dubois · Grün/Magenta (FFmpeg) | Anaglyphe | Augenauflösung erhalten | Nur Analysebeispiel; kein Produktpreset |
| `video.anaglyph.dubois_yb_ffmpeg` | Dubois · Amber/Blau (FFmpeg) | Anaglyphe | Augenauflösung erhalten | Nur Analysebeispiel; kein Produktpreset |
| `video.anaglyph.dubois_lcd_red` | Dubois LCD + Rotkorrektur | Anaglyphe | Augenauflösung erhalten | Vergleich; Produkt verwendet Batch-Definition |
| `video.anaglyph.iaian7` | iaian7 Anachrome | Anaglyphe | Augenauflösung erhalten | Vergleich; Produkt verwendet Batch-Definition |
| `video.anaglyph.rendepth` | Rendepth | Anaglyphe | Augenauflösung erhalten | Vergleich; Produkt verwendet Batch-Definition |
| `video.anaglyph.rendepth2` | Rendepth 2 | Anaglyphe | Augenauflösung erhalten | Vergleich; Produkt verwendet Batch-Definition |

Alle zehn Originalfragmente bleiben für Vergleiche erhalten. Im Produkt gibt es vier Ausgabearten mit einem Verfahren-Menü bei „Anaglyphe“. Dieses Menü orientiert sich an den 17 Batch-Verfahren; die drei historischen FFmpeg-Dubois-Kürzel werden nicht als weitere gleichnamige Varianten daneben gestellt. Ein bevorzugtes Verfahren wird erst nach Referenzvergleich festgelegt.

Container ist eine getrennte Entscheidung. Vorschlag: MP4/H.264 für übliche Stereo-/Mono-Wiedergabe, MKV/H.264 für hochwertige 4:4:4-Anaglyphen. Auch MP4 kann entsprechende H.264-Daten enthalten; ein Containerwechsel allein schafft jedoch keine Hardware-Kompatibilität. Zielgeräte müssen separat getestet werden. H.265 kommt in keiner Vorlage vor und erhält noch kein eigenes Qualitätsprofil.

## 3. Feste Parameter

### In den Originalen gemeinsam festgelegt

| Parameter | Wert | Behandlung für die erste Umsetzung |
|---|---|---|
| Encoder | `libx264` | Als H.264-Referenz übernehmen |
| Qualitätsmodus | `-crf 18` | Bewährter Standard; keine willkürliche CRF-Presetreihe |
| Encoder-Preset | `slow` | Bewährter Standard; Laufzeit offen anzeigen |
| Audio | `-c:a copy` | Kopieren nur nach Prüfung des Zielcontainers |
| Eingabelayout | Full-SBS, links links | Explizit bestätigen; nicht allein aus der Breite behaupten |

### An ein Verfahren gebunden

- Stereo-Ausgabecode und Augenreihenfolge.
- `frame-packing=3` für SBS beziehungsweise `4` für Top/Bottom. Diese Werte signalisieren die Anordnung im H.264-Stream [3]; sie sind kein MVC-Encoder und kein Blu-ray-Authoring.
- Matrixkoeffizienten, sämtliche LUT-Exponenten und ihre Reihenfolge.
- Position des Clippings und der Addition.
- `gbrp16` als Zwischenformat der vier langen Referenzketten.
- Die explizite BT.709-Linearisierung ausschließlich bei LCD + rot.
- Referenzskalierung `lanczos+accurate_rnd+full_chroma_int` bei HSBS/Half-OU. Die Flags beschreiben Skalierung und Chroma-Interpolation [2], nicht das Encoder-Ausgabeformat.
- Die Auflösung 1920 × 1080 ist fest im jeweiligen 1080p-Preset, kein globales Größenlimit für alle Verfahren.

Verbindliche Nutzervorgabe: Anaglyphen standardmäßig explizit mit 4:4:4 ausgeben und auf eingeschränkte Player-Unterstützung hinweisen. Ein optionaler Kompatibilitätsmodus darf 4:2:0 verwenden, mit sichtbarem Qualitätshinweis. Das bedeutet keine unbelegte Behauptung, die alten kurzen Dubois-Beispiele seien zuvor als 4:2:0 ausgegeben worden. Der ergänzende [Video-Workflow-Vorschlag](Video-Workflow-und-Oberflaeche.md) behandelt außerdem den optionalen H.264-Qualitätsmodus mit 10 Bit/4:4:4.

## 4. Variable Parameter

| Variable | Herkunft / Verhalten |
|---|---|
| Eingabedateien | Einzeldatei, Mehrfachauswahl, wiederholtes Hinzufügen aus verschiedenen Ordnern oder Ordnersuche |
| Quelleintrag | Herkunftspfad, optional gewählter Ordner als Spiegelungswurzel |
| Zielart / Verfahren | Auswahl eines der abgeleiteten Presets |
| Ausgabeordner | Vom Nutzer wählbar; außerhalb des Eingabebaums bevorzugt |
| Dateiname | Verfahrenssuffix, Quellname, festgelegte Konfliktregel |
| Container | Nur kuratierte passende Kombinationen; nicht automatisch aus dem Eingabecontainer übernehmen |
| Streamauswahl | Hauptvideo, gewünschte Tonspuren; Untertitel separat prüfen |
| Auflösung | Vorerst vom Preset oder Augenauflösung abgeleitet; Erweiterungen erst nach Festlegung |
| Quellenfarbdaten | Transferfunktion, Primärfarben, RGB/YUV-Matrix, Range und Chroma-Lage prüfen |
| Framerate / Timing | Aus der Quelle ermitteln; V1 ohne bewusste Framerate-Konvertierung |
| Verarbeitung | Einzeljob oder gesamte Liste, Reihenfolge, Abbruch, Wiederholung fehlgeschlagener Jobs |
| Ordnersuche | Unterordner optional, relative Struktur bei Ordnerimport erhalten |

Framerate, Quellenfarbraum und Pixelformat sind zunächst technische Eigenschaften, keine frei zugänglichen Schalter. Es gibt keine Grundlage für eine beliebige Matrixbearbeitung oder eine Vorschaufunktion in dieser Datei.

## 5. Vorschlag für Version 1

**V1 als Video-Batchwerkzeug mit den Layout-Workflows und dem AnaglyphBatch-Katalog:**

1. Dateien hinzufügen mit Mehrfachauswahl, auch über mehrere Hinzufüge-Vorgänge aus verschiedenen Ordnern. Eine einzelne Datei ist eine Liste mit einem Job.
2. Ordner hinzufügen, Unterordner optional. Beide Importwege erzeugen dieselben Jobs.
3. Technische Vorabprüfung mit ffprobe, sichtbaren Fehlern und geplantem Ausgabeformat.
4. Vier Ausgabearten: Half-SBS, Half-OU, Mono links und Anaglyphe mit 17 Batch-Verfahren ohne CIELab.
5. H.264 mit CRF 18 / slow; bestätigte Pixelformate und passende Container.
6. Audio zunächst kopieren, wenn möglich. Bei Inkompatibilität verständliche Meldung und bewusst gewählte Lösung; keine versteckte verlustbehaftete Neukodierung.
7. Fortschritt pro Datei und gesamte Liste, Protokoll, Abbrechen, Fehlerstatus. Zunächst sequenzielle Jobs als einfache robuste Ausführung.
8. Originaldateien erhalten, Ausgabekollisionen vor Start auflösen, temporäre Ausgabe erst nach erfolgreichem Abschluss zum endgültigen Ergebnis machen.

Der erste technische Durchstich darf zunächst die drei einfachen Layout-/Mono-Presets implementieren. Die 17 AnaglyphBatch-Verfahren werden innerhalb der V1-Entwicklung über gemeinsame Pipeline-Typen ergänzt und am ausgewählten portablen FFmpeg-Build geprüft. Das synthetische Laufresultat allein gilt nicht als Qualitätsfreigabe.

Bildfunktionen, MPO-Split, L/R-Dateiwerkzeuge, ExifTool und Bildsequenzen bleiben in den bereits vorgesehenen folgenden Phasen. Diese Parameterdatei enthält dafür keine ausgearbeiteten Kommandos. MVC/FRIM/AviSynth bleiben ein eigener späterer Bereich. Keine neue Spezialfunktion wird aus den zehn Fragmenten erfunden.

## 6. Internes Preset- und Jobmodell

Ein Preset beschreibt das Verfahren; ein Job bindet es an eine konkrete Datei; der Ausführungsplan enthält die nach Prüfung tatsächlich verwendeten Werte. Diese Trennung verhindert, dass ein Ordner-Batch ein anderer Verarbeitungspfad wird als die Dateiliste.

### Preset

| Gruppe | Felder |
|---|---|
| Identität | `id`, `revision`, `label`, `category`, `reference_command_index` |
| Voraussetzung | `media_kind`, `input_layout`, `eye_order`, benötigte Filter/Encoder, erlaubte Farbannahmen |
| Transformation | `pipeline_id`, Reihenfolge, festgelegte Koeffizienten/LUTs, Ausgabelayout |
| Geometrie | `resolution_policy`, gepackte Größe, Augenmaß, SAR-Regel |
| Kodierung | Encoder, CRF, Encoder-Preset, Pixelformat, Container-Auswahl |
| Timing | `frame_rate_policy`, Konvertierungsmethode, Zielrate gegebenenfalls als Bruch |
| Streams | Audio- und Untertitelregel, passende Metadatenregel |
| Nachweis | Originalkommando beziehungsweise Batch-Quellstand, Verfahrens-ID/Suffix, bekannte Einschränkungen, Status der Lauf-/Referenztests |

Ein verkürztes Modellbeispiel, noch kein ausführbares Schema:

```json
{
  "schema_version": 1,
  "id": "video.hsbs.1080",
  "revision": 1,
  "reference_command_index": 2,
  "input": {"media_kind": "video", "layout": "full_sbs", "eye_order": "left_right"},
  "transform": {"pipeline_id": "stereo3d_hsbs_1080_reference"},
  "output": {
    "layout": "half_sbs",
    "packed_size": [1920, 1080],
    "stored_eye_size": [960, 1080],
    "geometry_policy": "require_16_9_eyes_for_square_pixel_1080_preset",
    "codec": "libx264", "crf": 18, "encoder_preset": "slow",
    "pixel_format": "yuv420p", "container_choices": ["mp4", "mkv"],
    "h264_frame_packing": 3
  },
  "timing": {"policy": "preserve_source_timing", "target_rate": null},
  "audio": {"policy": "copy_if_container_compatible_else_require_decision"}
}
```

`yuv420p` und die Geometrieprüfung im Beispiel sind vorgeschlagene explizite V1-Regeln, nicht zusätzliche Parameter aus der Vorlage. Andere Seitenverhältnisse werden vor diesem 1080p-Profil angehalten, bis eine passende Größen-/Padding-Regel vereinbart ist.

### Job und Ausführungsplan

Ein Videojob enthält genau einen konkreten Quellpfad. `origin_kind` unterscheidet nur manuelle Dateiauswahl und Ordnerimport. `source_root` ist bei der Dateiauswahl optional; es wird nicht aus einem zufälligen gemeinsamen Ordner geraten. Zukünftige Paar-/Sequenzjobs können eine geordnete Quellenliste erhalten.

Gespeichert werden `job_id`, Quelle, Preset-ID und -Revision, Ausgabeziel, Zustandsdaten und Warnungen. Der Vorabcheck ergänzt Streamindices, Layoutbestätigung, Quell-/Zielgrößen, SAR/DAR, Farbdaten, Frameratenbrüche, Timing-Verhalten und konkrete Argumentliste. Presetänderungen dürfen bereits geplante Jobs nicht unbemerkt verändern.

Zustände: `queued`, `checking`, `ready`, `blocked`, `running`, `completed`, `failed`, `cancelled`. Blockierte Jobs starten nicht; andere gültige Jobs können weiterlaufen. Die Liste zeigt Datei, Preset, Ziel, Status und Warnungen. Entfernen löscht nur den Listeneintrag.

Dateien aus verschiedenen Ordnern dürfen gleiche Basenamen haben. Zielpfade werden über die ganze Liste geprüft, einschließlich Windows-Schreibweise ohne Groß-/Kleinschreibung. Eine gemeinsame Endung allein löst solche Kollisionen nicht. Ordnerimporte spiegeln ihre bewusst gewählte Wurzel; freie Dateilisten verwenden den Ausgabeordner und eine sichtbare eindeutige Namensregel. Bereits vorhandene Ergebnisse werden standardmäßig nicht überschrieben.

Der spätere Prozessaufruf verwendet eine Argumentliste ohne Shell. Das vermeidet eine erneute Interpretation von Leerzeichen, Umlauten und Shellzeichen in Pfaden. Originale FFBatch-Quotingregeln bleiben im Referenztext, werden aber nicht als Shellkommando aus Nutzerpfaden zusammengebaut.

## 7. Technische Risiken und erforderliche Entscheidungen

### Timing und Framerate

Die Vorlagen enthalten weder `-r` noch `fps`, `minterpolate` oder `setpts`. Sie definieren keine Wandlung nach 24 fps und keine Interpolation. Das Fehlen dieser Optionen allein garantiert noch nicht unverändertes VFR-Timing: FFmpeg wählt standardmäßig ein Sync-Verhalten nach Muxer. Die offizielle Dokumentation unterscheidet `passthrough`, `cfr` und `vfr`; CFR kann Frames duplizieren oder entfernen [5].

V1 soll Quell-Timing erhalten, soweit Encoder und Container es ermöglichen, und dies anhand von Zeitstempeln prüfen. `avg_frame_rate` und `r_frame_rate` reichen für eine sichere VFR-Erkennung nicht immer aus; bei Bedarf müssen Frame-/Packet-Zeitstempel untersucht werden. 24/1 und 24000/1001 bleiben unterschiedliche Raten. MVC/Blu-ray-Zielraten und Audioanpassung werden erst im Spezialmodus bewertet. Keine automatische „24 fps“-Option.

### Skalierung, SAR und Augenreihenfolge

Die 1080p-Profile sind unmittelbar passend für Full-SBS mit 16:9-Augen und quadratischen Quellpixeln. Bei 3840 × 1080 ergeben sich 1920 × 1080 gepackt; bei 7680 × 2160 werden zusätzlich die Augen verkleinert.

Eigenes Testresultat: `stereo3d=sbsl:sbs2l` verändert bei 384 × 108 zuerst den SAR zu 1:2, nicht schon die gespeicherte Breite. `tb2l` liefert 192 × 216 und SAR 2:1. Erst die folgende Skalierung liefert hier 1920 × 1080 mit SAR 1:1. Eine pauschale Aussage „stereo3d halbiert physisch die Breite/Höhe“ wäre für diese Ketten falsch.

Bei einer 320 × 120-Quelle mit 4:3-Augen ergeben beide Original-1080p-Ketten SAR 3:4 und DAR 4:3. Daher nicht einfach `setsar=1` anhängen: Das könnte den beabsichtigten Geometrieerhalt ändern. Für solche Quellen braucht es eine bewusst gewählte Ausgabegröße oder Padding pro Auge. Warnung vor Start statt stiller Dehnung. Getrennt prüfen: Rotation, geradzahlige Quellbreite, nötige Teilbild-Teilbarkeit und Encoderanforderungen. Auflösung allein beweist kein Full-SBS.

### Farbe und Anaglyphenqualität

Bei allen Anaglyphen soll 4:4:4 die Kanaltrennung schützen. Der Test erzeugte mit allen sieben bereits `yuv444p`; bei den kurzen Varianten war dies automatische Formatverhandlung. Zielgeräte müssen High-4:4:4-H.264 tatsächlich unterstützen. MKV oder MP4 im Dateinamen allein sagt dazu nichts.

`gbrp16` ist ein Zwischenformat, während `yuv444p` in diesen Ketten 8 Bit pro Komponente bedeutet. Die Vorlagen sind damit keine 16-Bit-Videoausgabe. Bereits verlorene Chroma-Information der Quelle wird durch 4:4:4 nicht zurückgewonnen.

LCD + rot nimmt BT.709 als Transferfunktion an. Das ist nicht die sRGB-Kurve für Standbilder. Ein identischer Matrixsatz beweist daher keine identische AnaChroma-Ausgabe. Für spätere Bilder wird das vorhandene sRGB-Modul der Toolfamilie verwendet; für Videos wird die tatsächliche Quelle geprüft.

BT.709-Ausgabetags ersetzen keine definierte RGB→YUV-Umrechnung oder Primärfarbenkonvertierung. Die vier langen Ketten setzen Tags, aber nicht alle Umrechnungsschritte ausdrücklich. Die kurzen Dubois-Ketten lieferten im Test keine explizite `color_space`-Angabe im Endstream. Vor Freigabe müssen Farbbalken-/Graurampen- und Referenzbildtests klären, welche Matrix und Range tatsächlich benutzt werden; dann Pixelwandlung und Tags konsistent festlegen. HDR/PQ/HLG, BT.2020 und unbekannte Farbangaben sind nicht durch diese SDR-Profile abgedeckt.

Bestehende Matrix- und Clip-Reihenfolge beibehalten. Änderungen an Genauigkeit, RGB-Konvertierung oder Skalierung vor/nach der Matrix brauchen einen dokumentierten Vergleich. Kein stiller „Qualitätsfix“, der bewährte Farben verändert.

### Codec, Container, Ton und Metadaten

CRF 18 ist der bewährte Referenzwert, kein festes Bitratenziel und keine Verlustlosigkeitsgarantie. `slow` ist das Encoder-Preset; es ist nicht mit einem TransCora-Ausgabe-Preset gleichzusetzen [3, 6].

Die Datei bestimmt keinen Container. `-c:a copy` allein übernimmt nicht automatisch sämtliche Audio-/Untertitelspuren. Die späteren Jobs brauchen ausdrücklich gewählte Streams und eine Kompatibilitätsprüfung. Bei einer Framerate-/Geschwindigkeitsänderung könnte reines Audiokopieren außerdem ungeeignet sein; das gehört zu einer bewusst definierten Wandlung.

Video-Metadaten nur passend übernehmen: alte Stereo-Layout- oder Rotationseinträge dürfen nach einer Transformation nicht falsch weitergetragen werden. Für Standbilder werden später ExifTool, Aufnahmedatum, Orientierung und Thumbnail-Regeln gesondert eingebunden. Diese zehn Video-Fragmente legen dafür noch keine Politik fest.

## 8. Durchgeführte Prüfung und Grenzen

Lokale Testumgebung: FFmpeg/ffprobe 6.1.1-3ubuntu5, Linux, mit libx264 und libzimg. Quelle: synthetisches Full-SBS 384 × 108, SAR 1:1, progressive Bilder, 24000/1001 fps, BT.709-Tags, FFV1/yuv420p und AAC-Audio. Ausgabecontainer für den Test: MKV. Jedes Originalfragment wurde mit unveränderter Transformations- und Codecparametrisierung ausgeführt; Prozess-/Filterthreads wurden für den Test auf eins begrenzt.

| Gruppe | Ergebnis | Größe | Pixelformat | Frames / Rate |
|---|---|---|---|---|
| Half-OU / Half-SBS | Beide erfolgreich | 1920 × 1080, SAR 1:1 | yuv420p, H.264 High | je 6, 24000/1001 |
| Mono links | Erfolgreich | 192 × 108, SAR 1:1 | yuv420p, H.264 High | 6, 24000/1001 |
| Drei kurze Dubois-Verfahren | Alle erfolgreich | 192 × 108, SAR 1:1 | yuv444p, High 4:4:4 Predictive | je 6, 24000/1001 |
| Vier lange Anaglyphenketten | Alle erfolgreich | 192 × 108, SAR 1:1 | yuv444p, High 4:4:4 Predictive | je 6, 24000/1001 |

AAC-Audio wurde jeweils übernommen. Die ersten Frames der zwei Stereo-Ausgaben enthalten Stereo-3D-Side-Data. Zusätzlicher Filtertest mit 4:3-Augen bestätigt den oben beschriebenen SAR 3:4 nach der Skalierung.

Nachgewiesen sind Syntax/Lauffähigkeit auf diesem Build, Ausgabemaße, ausgehandeltes Pixelformat und die Rate/Framezahl dieses kurzen CFR-Beispiels. Nicht nachgewiesen sind die Farbrichtigkeit aller Verfahren, Brillenwirkung, Langzeit-A/V-Synchronität, VFR-Verhalten, Gerätekompatibilität, Windows-Portable-Build oder beliebige Container-/Audio-Kombinationen. Diese Checks müssen gezielt vor Implementierungsfreigabe nachgeholt werden; sie erfordern keine vorschnelle GUI.


## 9. Verbindlicher Abgleich mit AnaglyphBatch

Christophs ergänzende Vorgabe vom 10. Oktober: Die Anaglyphen orientieren sich an AnaglyphBatch; CIELab entfällt. Geprüfte Quelle ist `AnaglyphBatch_DE.bat`, Git-Blob `f1e4bc892498055f999d8a41837a697fe68c9781`, im Quellstand `f073b9745d21eaa3f001b8fb14222b54cd34021d`. Eine Referenzkopie liegt unter `reference/AnaglyphBatch_DE.bat`. Das vorhandene AnaglyphBatch wird nicht geändert.

| Batch-Nr. | Verfahren | Verfahrens-ID / Suffix | Pipeline-Typ |
|---|---|---|---|
| 1 | Dubois LCD (Sanders/McAllister) + rot | `dubois_lcd` | linear + Rot-LUT |
| 2 | Dubois | `dubois` | linear |
| 3 | Optimized (Peter Wimmer) | `wimmer` | kodiertes RGB + Rot-LUT |
| 4 | Cosima AnaglyphType=3 (Gerhard P. Herbig) | `cosima3` | linear + Rot-LUT |
| 5 | Cosima AnaglyphType=4 (Gerhard P. Herbig) | `cosima4` | linear + Rot-LUT |
| 6 | Compromise (Jure Ahtik) | `compromise` | kodiertes RGB |
| 7 | iaian7 Anachrome (John Einselen) | `iaian7` | spezielle Zwei-Zweig-LUT/Nachmatrix |
| 8 | Rendepth (Andres Hernandez) | `rendepth` | kodiertes RGB + Clipping/Kanal-LUT |
| 9 | Rendepth 2 (Andres Hernandez) | `rendepth2` | kodiertes RGB + Clipping/Kanal-LUT |
| 10 | Color | `color` | kodiertes RGB |
| 11 | Half-Color | `halfcolor` | kodiertes RGB |
| 12 | Grey | `grey` | kodiertes RGB |
| 13 | Oldschool | `oldschool` | kodiertes RGB, Rot/Grün |
| 14 | Frans van den Poel | `vdp` | kodiertes RGB |
| 15 | John Wattie | `wattie` | kodiertes RGB |
| 17 | Dubois grün/magenta | `dubois_gm` | linear |
| 18 | Dubois amber/blau | `dubois_yb` | linear |

Batch-Nr. 16, CIELab, wird ausdrücklich ausgelassen. Die Nummern hier sind Herkunftsverweise und keine lückenhafte GUI-Nummerierung. Die restlichen 17 sind bereits in der Batch über FFmpeg realisiert. CIELab wird dort über ein separates Programm berechnet; wir planen dafür in TransCora keinen Nachbau. Daraus folgt keine allgemeine Behauptung, es könne prinzipiell niemals mit zusätzlichem Code umgesetzt werden.

Die Katalogdatei `presets/anaglyph_methods.reference.json` hält die Werte und Modusnamen der geprüften Batch unverändert fest. Sie ist ein Referenz-Datensatz, noch kein ausführbarer Preset-Compiler. Die iaian7-Spezialdefinition enthält ihre beiden Zweig-LUTs und ihre Nachmatrix ausdrücklich.

### Konsequenzen für die einheitliche Umsetzung

- Ein gemeinsamer Verfahrenskatalog liefert Namen, Suffixe, Matrizen, Rechenmodus und LUTs. Die vier Pipeline-Typen `linear`, `srgb`, `rendepth` und `iaian7` entsprechen der Referenz.
- Die drei kurzen FFBatch-Dubois-Aufrufe sind kein ungeprüfter Ersatz für die Batch-Definitionen. Insbesondere enthalten sie nicht die dort ausdrücklich vorgesehene Linearisierung.
- LCD + rot stimmt in Matrix und Rotexponent überein, verwendet im alten Video-Fragment jedoch BT.709 statt der sRGB-Transferfunktion der Bild-Batch. Diese Unterscheidung muss fachlich behandelt werden.
- iaian7 und beide Rendepth-Ketten entsprechen in ihren Matrix-/LUT-Angaben den jeweiligen Batch-Verfahren. Eingangsfarbraum, Endformat, Skalierung und Metadaten bleiben getrennte Adapteraufgaben.
- Alle Jobs verwenden dieselbe Aufbereitung, Transformationsdefinition, Größenregel und Ausgabeprüfung, unabhängig davon, ob die Datei aus Einzelwahl, einer freien Liste oder einem Ordner stammt.
- Bild- und Videoausgabe werden nicht durch blind identische Transfer-Tags „vereinheitlicht“. Die Methode hat einen definierten Arbeitsfarbraum; der Medienadapter wandelt passend hinein und heraus.

**Vorgeschlagene Farbregel für den Referenzvergleich:** Die Batch definiert ihre nichtlinearen Operationen im sRGB-Arbeitsraum. Ein BT.709-Video wird deshalb fachlich korrekt in diesen Arbeitsraum überführt; anschließend folgen die unveränderten Methodenoperationen und die Umrechnung zur gewählten Videoausgabe. Bei linearen Verfahren können äquivalente Schritte zusammengeführt werden, sofern auch der Raum einer nachfolgenden Kanal-LUT erhalten bleibt. Das soll Bild-/Video-Verfahren konsistent machen und wird zuerst anhand identischer Farbmuster in unterschiedlichen Quellkodierungen geprüft. Es ist noch keine implementierte oder freigegebene Pipeline.

Die alternative einfache Übertragung „alle sRGB-Stellen pauschal durch BT.709 ersetzen“ wird nicht ungeprüft zur Standardregel: Besonders nachgelagerte Kanalpotenzen und kodierte RGB-Matrizen könnten dadurch andere Farben ergeben. Bereits bewährte FFBatch-Ergebnisse bleiben zum Vergleich verfügbar. Korrekturen und begründete Unterschiede werden sichtbar dokumentiert.

Für die Entwicklungsstruktur kommt deshalb zu den allgemeinen Preset-Feldern eine `method_id` mit Verfahrensrevision sowie eine explizite `working_color_space`-Regel. Der spätere Compiler erzeugt daraus eine gemeinsame FFmpeg-Filterkette; Container, Kodierung, Ton, Dateinamenssuffix und Größenprofil werden anschließend angebunden. Keine siebzehn unabhängig gepflegten Sonderkommandozeilen.

### Asset- und Gestaltungsvorgaben

Geliefertes Icon: `assets/transcora.ico`, 128342 Bytes, SHA-256 `cc38e2de318e7ad95eb1060a079ae1dcec8b3fba08b52a8f502574e8347c3509`. Enthaltene Größen: 16, 24, 32, 40, 48, 64, 256 Pixel. Originalbytes bleiben unverändert.

Standardsound: `assets/ready.wav` aus AnaChroma, Git-Blob `260fb0d49982873a13dabd750b997448acb675ca`; SHA-256 laut dortigem Manifest `5eec8bd4c6cf509b57d2a0e39a87018f9523372112b5e66ded2f621f475c1119`. Keine Neusynthese oder Neukomprimierung.

Der gemeinsame Gestaltungsstandard Version 1.5 vom 9. Oktober 2026 wurde als Referenz gelesen. TransCora übernimmt dessen allgemeine Palette und Bedienzustände. Projektbesonderheiten wie eine optionale Vorschau werden nicht pauschal aus anderen GUIs übernommen. Für eine spätere Änderung des gemeinsamen Standards wäre der Abgleich der bestehenden fünf Repositories erforderlich; in dieser Analyse werden sie nicht verändert.

### Ergänzende Referenz

[AnaglyphBatch_DE.bat, geprüfter Quellstand](https://github.com/muelli1975/AnaglyphBatch/blob/f073b9745d21eaa3f001b8fb14222b54cd34021d/AnaglyphBatch_DE.bat)


## Quellen

Die zehn Video-Referenzketten stammen aus Christophs Datei; der verbindliche 17er-Verfahrenskatalog aus AnaglyphBatch. Externe Quellen dienen nur zur Bedeutung der verwendeten Optionen und zur Prüfung der Implementierung.

1. [FFmpeg-Filterdokumentation: stereo3d, zscale, lutrgb](https://ffmpeg.org/ffmpeg-filters.html)
2. [FFmpeg-Scaler: Lanczos und Chroma-Flags](https://ffmpeg.org/ffmpeg-scaler.html)
3. [x264-Quelltext: Hilfe zu frame-packing und CRF](https://github.com/mirror/x264/blob/master/x264.c)
4. [FFmpeg 6.1: colorchannelmixer_template.c, Integer-Clipping](https://ffmpeg.org/doxygen/6.1/colorchannelmixer__template_8c_source.html)
5. [FFmpeg: fps_mode und Stream-Auswahl](https://ffmpeg.org/ffmpeg.html)
6. [FFmpeg: libx264](https://ffmpeg.org/ffmpeg-codecs.html)
