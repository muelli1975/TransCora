# TransCora – Video-Workflow, Player-Konventionen und kompakte Oberfläche

Stand: 10. Oktober 2026. Recherche und Entwicklungsvorschlag, keine implementierte Funktion und keine Player-Zertifizierung. Christophs anschließende Präzisierung ist berücksichtigt: ausschließlich AnaglyphBatch-Verfahren; 4:4:4 als Standard mit Player-Hinweis; optional 4:2:0 mit Qualitätshinweis; zusätzlicher H.264-Modus mit 10 Bit/4:4:4 darf eingeplant werden. Zusätzliche Eingabelayouts und Oberflächendetails bleiben Vorschläge.

## 1. Empfehlung

TransCora bleibt ein kompakter Konverter mit einer gemeinsamen Jobliste für einzelne Dateien, frei zusammengestellte Listen und Ordnerimporte. Full-SBS bleibt der erste Referenzweg. Zusätzliche gepackte Eingaben werden als kleine Erweiterung derselben Verarbeitung geplant: Full/Half-SBS und Full/Half-OU, jeweils mit expliziter Augenreihenfolge.

Für Anaglyphen empfehlen sich zunächst MKV/H.264 mit 4:4:4 und 8 Bit sowie ein optionales, gesondert gekennzeichnetes Profil mit 4:4:4 und 10 Bit. Methoden folgen ausschließlich AnaglyphBatch ohne CIELab. Die alten Anaglyphenketten der Textdatei sind Beispiele; sie werden nicht als zusätzliche Produktvarianten oder auswählbarer Legacy-Modus übernommen. Die Bittiefe verändert die Ausgabequantisierung, nicht die Verfahrensdefinition.

Dateinamen sollen das tatsächliche Ergebnis beschreiben. Ein kombiniertes Namensschema verbindet Kodi-Marker mit einem abschließenden Bino-/Stereoscopic-Player-Hinweis. Es ersetzt weder korrekte Metadaten noch eine Wiedergabeprüfung. Eine optionale Standbildkontrolle ist sinnvoll, eine dauerhaft laufende Vorschau nicht erforderlich.

## 2. Bittiefe und Farbauflösung getrennt behandeln

8 Bit bieten rechnerisch 256, 10 Bit 1024 Codewerte pro Komponente; bei begrenztem Videobereich wird nur ein Teil davon genutzt. Eine höhere Ausgabebittiefe kann feinere Zwischenwerte aus Matrixrechnung, Transferwandlung, LUTs und Skalierung besser erhalten und zusätzliche Quantisierungsstufen beziehungsweise Banding reduzieren. Das ist eine technische Erwartung, noch kein gemessener Qualitätsgewinn an Christophs Material.

Wichtig ist eine durchgehend ausreichend genaue Filterkette. Erst eine bereits auf 8 Bit gerundete Ausgabe nachträglich in ein 10-Bit-Pixelformat zu verpacken erschließt nicht denselben Nutzen. Auch aus einer 8-Bit-Quelle können Berechnungen neue Zwischenwerte ergeben; ursprüngliches Quellenbanding, verlorene Details und verlorene Farbauflösung werden dadurch nicht rekonstruiert. 10 Bit sind außerdem weder HDR noch eine Korrektur von Ghosting, Brillenfiltern oder falschen Matrizen.

4:4:4 beschreibt die räumliche Farbauflösung. 4:2:0 reduziert die Chroma-Abtastung horizontal und vertikal. Bei Anaglyphen tragen Farbkanäle unterschiedliche Augeninformationen; zusätzliche Chroma-Reduktion kann Farbkanten und die Trennung dieser Informationen beeinträchtigen. Deshalb ist 10 Bit/4:2:0 kein allgemeiner Qualitätsersatz für 8 Bit/4:4:4. Bereits in der Quelle vorhandene 4:2:0-Verluste werden durch eine 4:4:4-Ausgabe nicht rückgängig gemacht.

| Vorgeschlagenes Profil | Container / Encoder | Ausgabeformat | Verwendung |
| --- | --- | --- | --- |
| Anaglyph Qualität | MKV / libx264 | yuv444p, 8 Bit | An die bisherigen Exporte angelehnt; Zielplayer muss 4:4:4 unterstützen |
| Anaglyph Qualität 10 Bit | MKV / libx264 | yuv444p10le, 10 Bit | Optional für passende Softwarewiedergabe und feinere Gradienten |
| Anaglyph kompatibel | MP4 / libx264 | yuv420p, 8 Bit | Optional, mit sichtbarem Hinweis auf Qualitätsverlust durch geringere Farbauflösung |

Die Methode bleibt in allen drei Profilen dieselbe AnaglyphBatch-Definition. Ein kompatibler Export ist keine andere Dubois-/LCD-Variante. Vorgeschlagene kurze GUI-Hinweise:

- **4:4:4:** „Hohe Farbauflösung. Nicht alle Player und Hardwaredecoder unterstützen dieses Format.“
- **4:2:0:** „Kompatibilitätsmodus mit geringerer Farbauflösung. Die Anaglyphenqualität kann darunter leiden.“
- **10 Bit/4:4:4:** „Feinere Tonwertabstufungen. Wiedergabe nur mit geeignetem Player/Decoder; kein HDR-Modus.“

Auch das 8-Bit-Qualitätsprofil ist kein universelles Hardwareprofil. 10-Bit- und 4:4:4-H.264 werden nicht allein deshalb unterstützt, weil ein Gerät H.264 oder MKV abspielen kann. Umgekehrt schafft der Wechsel zu MP4 keine neue Decoderfähigkeit. Profile brauchen eine Prüfung des konkret verteilten Windows-Builds und der gewünschten Player-/Decoderkombination.

FFmpeg dokumentiert 8–10 Bit für libx264, abhängig vom Build. x265 dokumentiert getrennte Profile für 10 Bit/4:2:0 und 10 Bit/4:4:4. H.265 ist damit eine mögliche spätere Erweiterung, aber für diesen Durchstich nicht erforderlich. 12-/16-Bit-Videoexport wird für V1 nicht vorgeschlagen. `gbrp16` aus den alten Filterketten bezeichnet die interne RGB-Präzision, keinen bisherigen 16-Bit-Export. [Q1, Q2]

Ein kurzer lokaler Machbarkeitstest hat die alte LCD-Anaglyphenkette mit ausschließlich geändertem abschließendem Pixelformat und explizitem `-pix_fmt yuv444p10le` erfolgreich ausgeführt. ffprobe meldete H.264, High 4:4:4 Predictive, 192 × 108, `yuv444p10le`, `bits_per_raw_sample=10`, BT.709-Kennzeichnungen und `24000/1001`. Die Quelle war das vorhandene synthetische Kurzvideo. Nachgewiesen ist diese Kombination auf FFmpeg 6.1.1-3ubuntu5 unter Linux; nicht nachgewiesen sind sichtbare Bandingverbesserung, Farbrichtigkeit der künftigen AnaglyphBatch-Adaption, große Auflösungen oder Windows-/Player-Kompatibilität.

Gleicher CRF bedeutet zwischen verschiedenen Bittiefen beziehungsweise Encodern weder identische Dateigröße noch garantiert identische Bildqualität. Das bisherige CRF-18/slow-Profil ist eine Vergleichsbasis. Es sollte anhand gleicher Szenen mit Farbverläufen, feinen Farbkanten und Bewegung überprüft werden. Dithering bei einer späteren Reduktion der Bittiefe gehört in eine explizite, reproduzierbare Ausgabeentscheidung.

## 3. Eingabecontainer und Stereo-Layout sind verschiedene Eigenschaften

MP4, MKV, MOV, M2TS/TS und AVI bleiben die sinnvollen Eingabecontainer. Ein Containername sagt noch nicht, wie die Augen darin angeordnet sind. `.mk3d` ist die offizielle Matroska-Endung für stereoskopisches Video und kann zusätzlich im Importfilter erscheinen; die Datei wird trotzdem technisch geprüft. Standardausgaben bleiben `.mkv` und `.mp4`. [Q3]

| Vorgeschlagene gepackte Eingabe | Reihenfolge | FFmpeg-Bezeichnung | Behandlung |
| --- | --- | --- | --- |
| Full-SBS | Links / rechts | sbsl | Erster Referenzweg |
| Full-SBS | Rechts / links | sbsr | Identischer Weg mit korrigierter Augenreihenfolge |
| Half-SBS | Links / rechts | sbs2l | Geometrie entzerren; verlorene Auflösung bleibt verloren |
| Half-SBS | Rechts / links | sbs2r | Wie zuvor, mit Tausch |
| Full-OU / TAB | Links oben | tbl / abl | Vertikal gepackte Augen trennen |
| Full-OU / TAB | Rechts oben | tbr / abr | Wie zuvor, mit Tausch |
| Half-OU / TAB | Links oben | tb2l / ab2l | Halbe vertikale Abtastung berücksichtigen |
| Half-OU / TAB | Rechts oben | tb2r / ab2r | Wie zuvor, mit Tausch |

Diese Layoutbezeichnungen sind durch die FFmpeg-Filterdokumentation belegt. Die technische Unterstützung des Filters ist noch kein fertiger Importadapter. [Q4]

In der GUI reichen vier Layouts plus „Augen tauschen“. Die Jobdaten speichern die tatsächliche Reihenfolge. Ein Standard für alle neu hinzugefügten Dateien ist möglich; abweichende Dateien erhalten eine eigene Einstellung. Eine gemischte Liste darf nicht unbemerkt als ein einziges Quelllayout behandelt werden.

Beispiel mit beabsichtigtem 16:9-Bild pro Auge und quadratischen Zielpixeln:

| Layout | Gepacktes Raster | Gespeicherte Pixel pro Auge | Gemeinte Geometrie pro Auge |
| --- | --- | --- | --- |
| Full-SBS | 3840 × 1080 | 1920 × 1080 | 16:9 |
| Half-SBS | 1920 × 1080 | 960 × 1080 | 16:9 nach horizontaler Entzerrung |
| Full-OU | 1920 × 2160 | 1920 × 1080 | 16:9 |
| Half-OU | 1920 × 1080 | 1920 × 540 | 16:9 nach vertikaler Entzerrung |

Die Beispiele sind keine universellen Erkennungsregeln. Filme können andere Bildverhältnisse, schwarze Balken, anamorphe Pixel oder spezielle Raster besitzen. Gerade ein 1920×1080-Video könnte normales 2D, Half-SBS oder Half-OU sein. Eine Auflösungsheuristik darf höchstens einen unbestätigten Hinweis liefern.

Vorerst zurückstellen: zwei getrennte Videodateien oder zwei unabhängige Videospuren, zeilen-/spaltenverschachtelte Quellen, Checkerboard, frame-sequentielle Eingaben, MVC/Blu-ray-3D und VR180/360-Projektionen. Sie benötigen zusätzliche Regeln für Synchronität, Rekonstruktion beziehungsweise Projektion. Bei frame-sequentiellen Quellen sind Framezahl und Stereo-Paarrate unterschiedliche Größen. Fertige Anaglyphenvideos sind kein verlustfreies Ausgangsformat zur Wiedergewinnung echter L/R-Ansichten.

`.ssif`, `.mvc`, `.264` und `.jsv` sind im Stereoscopic-Player-Kontext belegte Blu-ray-/Rohstrom-Sonderfälle, keine passenden normalen TransCora-Ausgabeendungen. `.svi` ist eine Metadatendatei des Players mit demselben Stammnamen wie das Video, kein Videocontainer. Einen entsprechenden Sidecar-Export können wir später gezielt prüfen. [Q5, Q6]

## 4. Dateinamenregeln der Player

Kodi dokumentiert zwei durch Punkt, Bindestrich, Unterstrich oder Leerzeichen abgegrenzte Marker: `3D` und `SBS`/`HSBS` beziehungsweise `TAB`/`HTAB`, ohne Beachtung der Groß-/Kleinschreibung. Eingebettete Streaminformationen stehen vor der Dateinamenheuristik. Die Wiki-Seite enthält zugleich einen ausdrücklichen Hinweis auf ältere Abschnitte; ihre Regeln sind eine Grundlage, keine Wiedergabegarantie für alle aktuellen Plattformen. [Q7]

Bino dokumentiert Layout-Hinweise als letzten Bestandteil vor der Dateiendung: `-lr`, `-lrh`, `-tb`, `-tbh`, die entsprechenden umgekehrten Reihenfolgen `-rl`, `-rlh`, `-bt`, `-bth` sowie `-2d`. Es versucht zuvor, Metadaten auszuwerten. [Q8]

Stereoscopic Player dokumentiert ausdrücklich `-lrh`, `-rlh`, `-tb`, `-bt`, `-tbh` und `-bth` seit Version 2.2.7; ältere Versionshinweise nennen TriDef-kompatible Suffix-Erkennung. Die englische Beschreibung von `-rlh` enthält offenbar einen Kopierfehler („left image first“). TransCora sollte auf rechts-zuerst-Ausgabe zunächst verzichten und diesen Sonderfall erst praktisch gegenprüfen. Die genaue heutige Interpretation der alten Full-SBS-Kürzel `-lr`/`-rl` ist anhand dieser Versionshinweise nicht vollständig belegt. [Q5]

### Kombiniertes Ausgabe-Namensschema – Vorschlag

| Tatsächliche Ausgabe | Beispielname | Dokumentierte Namensbasis |
| --- | --- | --- |
| Half-SBS, links zuerst | Film.3D.HSBS-lrh.mkv | Kodi + Bino + Stereoscopic Player |
| Half-OU, links oben | Film.3D.HTAB-tbh.mkv | Kodi + Bino + Stereoscopic Player |
| Full-SBS, links zuerst | Film.3D.SBS-lr.mkv | Kodi-Marker + Bino; genaue Full-Geometrie in Playern prüfen |
| Full-OU, links oben | Film.3D.TAB-tb.mkv | Kodi + Bino + Stereoscopic Player; genaue Full-Geometrie prüfen |
| Anaglyph, LCD-Methode | Film_anaglyph_dubois_lcd-2d.mkv | Methodenname aus AnaglyphBatch + Bino-Mono-Hinweis |
| Linkes Auge als 2D | Film_mono_l-2d.mp4 | Eigenes beschreibendes Suffix + Bino-Mono-Hinweis |

Diese Kombinationen sind eine eigene Ableitung aus den dokumentierten Regeln. Es wurden keine Wiedergabetests in Kodi, Bino oder Stereoscopic Player durchgeführt. Insbesondere Kodi-Marker allein kennzeichnen nicht verlässlich die Entzerrungsregeln für Full und Half in jeder Player-Version. Auflösung, Anzeigenmaße und Stereo-Metadaten müssen zusammenpassen.

Andere Container ändern nur die echte Endung: zum Beispiel `Film.3D.HSBS-lrh.mp4`. `.HSBS` wird keine erfundene Dateiendung. Für einen 10-Bit-Hinweis ist `Film_anaglyph_dubois_lcd_10bit-2d.mkv` möglich. Alle Qualitäts-/Auflösungshinweise müssen vor dem abschließenden Player-Suffix stehen. Standardmäßig sollte das kombinierte Schema automatisch verwendet werden, mit einer abschaltbaren Option „Stereo-Kürzel im Dateinamen“. Eine Liste aller historischen Player-Suffixvarianten in der Hauptoberfläche ist unnötig.

Ausgaben werden grundsätzlich links-zuerst beziehungsweise links-oben geschrieben. „Augen tauschen“ korrigiert die Quelle, es bedeutet nicht automatisch einen rechts-zuerst-Export.

Bei einer Umwandlung werden erkannte Layout-Marker des Eingabenamens gezielt ersetzt. Aus `Film.3D.HSBS-lrh.mkv` muss für Anaglyph beispielsweise `Film_anaglyph_dubois-2d.mkv` entstehen. Ein alter SBS-/TAB-Hinweis darf das fertige Anaglyphenbild nicht zu einer erneuten Stereotrennung veranlassen. Nicht blind jedes Vorkommen von „3D“ aus Filmtiteln entfernen. Kollisionen vorab erkennen; notwendige Unterscheidungszusätze stehen vor dem finalen Layout-Suffix.

## 5. Metadaten gehören zum Exportplan

Matroska spezifiziert `StereoMode` und die Beziehung zwischen gespeicherten Pixelmaßen und Anzeigenmaßen pro Ansicht. Bei Full-SBS beispielsweise unterscheiden sich das gepackte Raster und die einzelnen Ansichten. Ein gewöhnlicher Texttag namens „3D“ ist kein Ersatz. [Q9]

Der Exportplan muss Codec-Signalisierung, Container-Stereoangaben, Pixel-/Anzeigenmaße und Dateiname gemeinsam aus dem Ziel ableiten. Die bisherigen x264-Frame-Packing-Parameter sind eine relevante Referenz, aber keine Garantie universeller automatischer Erkennung. Nach Layoutwechseln dürfen alte Stereo- oder VR-Metadaten nicht einfach mitkopiert werden. Für fertige Anaglyphen erfolgt normale Wiedergabe eines bereits zusammengesetzten Bildes; insbesondere dürfen keine SBS-/TAB-Signale übrig bleiben. Matroska besitzt zwar auch spezielle Anaglyph-StereoMode-Werte, deren Verwendung müsste separat auf sinnvolles Playerverhalten geprüft werden. [Q9]

Die Bino-Metadatenhinweise empfehlen bei MKV gezielte Bearbeitung mit `mkvpropedit`. MKVToolNix dokumentiert sowohl das Setzen als auch das Entfernen von Trackeigenschaften. Wir nehmen deshalb zunächst eine Prüfung des FFmpeg-Muxergebnisses vor. Falls die benötigten Header nicht korrekt und reproduzierbar entstehen, kann `mkvpropedit` als begründete portable Ergänzung unter `tools/mkvtoolnix/` hinzukommen. Das ist eine offene Toolchain-Entscheidung, keine schon eingeführte Abhängigkeit. ExifTool-Unterstützung für bestimmte MP4-/VR-Metadaten rechtfertigt keine pauschale Zusage, es könne alle Stereoangaben in jedem Container schreiben. [Q10, Q11]

## 6. Ein gemeinsamer, reproduzierbarer Jobablauf

1. **Sammeln:** Mehrfachauswahl einzelner Dateien, wiederholtes Hinzufügen aus anderen Ordnern oder Ordnerimport. Alles endet in derselben Liste. Doppelte Quellen erkennen; gleiche Dateistämme verschiedener Ordner bleiben zulässig.
2. **Prüfen:** ffprobe erfasst Streams, Dauer, Timebase, CFR/VFR-Hinweise, Raster, Pixel-/Anzeigengeometrie, Farbraum, Transfer, Bereich und Stereo-/Projektionsinformationen. Frameratebrüche bleiben exakt gespeichert.
3. **Layout festlegen:** Manuelle Jobangabe gilt vor automatisch abgeleiteten Vorschlägen. Metadaten und Name werden gegeneinander geprüft. Widerspruch blockiert die automatische Freigabe. Reine Auflösungsheuristik bleibt unbestätigt. „Unbekannt“ wird niemals still zu Full-SBS. Ein bewusst gewählter Full-SBS-Standard für unmarkierte Bestände ist erlaubt und sichtbar.
4. **Plan erstellen:** Quelllayout in zwei eindeutig benannte Ansichten L/R überführen; native Abtastung, tatsächliches Bildverhältnis und nötige Entzerrung getrennt berücksichtigen. Die gemeinsame Methode arbeitet auf diesen Ansichten. Es ist keine zwischengespeicherte Full-SBS-Videodatei erforderlich. Die AnaglyphBatch-Matrizen, LUT-Reihenfolge und Clipregeln bleiben zentral definiert; Video-Farbadapter übernehmen die belegte Quellenfarbinterpretation und die korrekte Ausgabeübertragung.
5. **Ausgabe prüfen:** Profil, Raster, Bittiefe, Chroma, Rate, Audio-/Untertitelpolitik, Metadaten und vollständiger Zielname werden vor dem Start sichtbar. Keine automatische globale 24-fps-Wandlung. Half-Quellen erzeugen durch Hochskalierung keine echte Full-Auflösung. Für normale Exporte Zeitstempel erhalten; VFR-/A/V-Verhalten gesondert prüfen. Fehlende Farbangaben erfordern eine sichtbare Annahme oder Klärung; HDR-Quellen werden bis zu einem geprüften SDR-/HDR-Konzept nicht still durch SDR-Anaglyphenketten geschickt.
6. **Ausführen:** Zunächst seriell ein Job nach dem anderen. FFmpeg-Fortschrittsdaten liefern den Balken; die GUI bleibt bedienfähig. Ausgabe zunächst in eine eindeutig benannte temporäre Datei mit echter Container-Endung schreiben. Abbruch stoppt den Prozess kontrolliert; ein begonnenes Ergebnis wird nicht als erfolgreich ausgegeben. Einstellungen und Listenmutation bleiben während des Laufs gesperrt, Abbruch bleibt verfügbar.
7. **Abschließen:** ffprobe prüft das Ergebnis gegen den Plan. Erst dann wird es als erfolgreich markiert und in den endgültigen Namen überführt. Metadaten-Finalisierung gehört vor diesen Abschluss. Bei einem Fehler kann die Liste mit anderen freigegebenen Jobs weiterlaufen. Abschlussmeldung nennt erfolgreich/fehlerhaft/übersprungen/abgebrochen getrennt; der vorhandene Sound erklingt einmal am Ende des Laufs und verschleiert keine Fehler.

Zeitbasierter Fortschritt ist bei bekannter Dauer sinnvoll. Fehlende Dauer ergibt eine Aktivitätsanzeige, keine erfundene Prozentzahl. Gesamtfortschritt kann nach verarbeiteten Laufzeiten gewichtet werden; unterschiedliche Filter und Auflösungen machen dies noch nicht zu einer genauen Restzeitschätzung. Zusätzlich immer „Datei 2 von 7“ anzeigen. 100 % wird erst nach Muxing, Prüfung und Abschluss erreicht.

Eine frei zusammengestellte Jobliste sollte als kleine lokale TransCora-JSON-Datei gespeichert und wieder geladen werden können. Sie enthält Pfade und Jobentscheidungen, keine Videodaten. Fehlende beziehungsweise veränderte Dateien werden beim Wiederladen geprüft; die alte Analyse wird nicht ungeprüft wiederverwendet. Das ist für gezielt ausgewählte Videos nützlicher als ein Zwang, neue Quellordner anzulegen.

### Ergänzungen des internen Job-/Preset-Modells

| Bereich | Vorgeschlagene Daten |
| --- | --- |
| Quellinterpretation | layout, eye_order, provenance (manual/metadata/name/default), confirmed, native_view_size, view_display_aspect |
| Farbadapter | source_matrix, primaries, transfer, range, working_space, output_color_spec, assumptions |
| Methode | zentrale method_id und Revision; keine eigene Matrixkopie je Eingabeformat |
| Encodingprofil | codec, container, bit_depth, chroma_subsampling, pix_fmt, profile, CRF, encoder_preset |
| Geometrie / Timing | geplante gespeicherte Raster, Anzeigenmaße, Quelle-/Zielrate als Bruch, timestamp_policy |
| Namensplanung | sauberer Stamm, method_suffix, quality_hint, final_layout_hint, collision_resolution |
| Finalisierung | metadata_policy, expected_stream_properties, verification_result |

Nicht alle diese Felder gehören in die Hauptoberfläche. Sie verhindern intern, dass Liste, Ordnerimport, Vorschau oder neue Quelllayouts unterschiedliche Sonderlogik erhalten. Die technische Detailansicht macht den konkreten Plan und seine Annahmen nachvollziehbar.

## 7. Oberfläche: kompakter Konverter mit optionaler Kontrolle

Vorgeschlagenes Windows-Fenster: ungefähr 820 × 560 logische Pixel als Ausgangspunkt, größenveränderbar und bei DPI-Skalierung ohne abgeschnittene Beschriftungen. Kleine Programme müssen lesbar bleiben. Optik nach dem vorhandenen gemeinsamen Gestaltungsstandard: dunkle Flächen, zurückhaltende goldene Akzente, unverändertes Icon und Standardsound.

- **Oben:** „Dateien hinzufügen“, „Ordner hinzufügen“, Entfernen; „Liste speichern/laden“ als kompakte Nebenaktion.
- **Mitte:** Jobliste mit Datei, Quelllayout, Ziel/Preset und Status. Auswahl zeigt technische Angaben; Warnungen sind am betroffenen Job sichtbar. Alle Dateipfade sind zugänglich, auch wenn die Listenspalte nur den Dateinamen zeigt.
- **Darunter:** Quelllayout/„Augen tauschen“ für ausgewählte Jobs, Zielpreset, nur bei Anaglyphen die Methode, passendes Qualitätsprofil, Ausgabeordner und ein Beispiel des geplanten Zielnamens. Gemeinsame Einstellungen können bewusst auf die Auswahl beziehungsweise alle noch nicht gestarteten Jobs angewandt werden.
- **Unten:** Fortschrittsbalken, „Datei n von m“, aktueller Schritt, Geschwindigkeit und gegebenenfalls geschätzte Restzeit. „Starten“, während des Laufs „Abbrechen“. Technische Einzelheiten und Log sind aufklappbar.

Die Hauptansicht zeigt keine beliebige Codec-/Filter-/Formatliste. Presets kapseln kompatible Kombinationen. Sie blendet unpassende Felder aus oder deaktiviert sie nachvollziehbar. Quell- und Zielordner werden getrennt gemerkt. Das Quelllayout ist eine Interpretationsentscheidung pro Job; das Zielpreset ist eine Ausgabeentscheidung.

### Kontrollbild statt dauerhaftem Videoplayer

Reine Statusmeldungen erkennen einen vertauschten Blick oder geometrisch verzerrte Augen nicht ausreichend. Eine kleine **optionale Standbildkontrolle** ist deshalb fachlich sinnvoll:

- Aufruf für einen ausgewählten, noch nicht gestarteten Job; keine dauernde Dekodierung während des Batchlaufs.
- Gleicher Zeitpunkt für L, R und berechnetes Ergebnis; Zeitstelle wählbar, bei Bedarf vergrößern/1:1.
- Identische Methodendefinition, Farbwandlung und Reihenfolge wie im geplanten Export. Ein fachlich anderer „schneller Vorschaumodus“ wäre irreführend.
- Eindeutige Beschriftung von L/R, beabsichtigtem Bildverhältnis, Methode und Darstellung. Für SBS/OU gegebenenfalls zusätzlich das gepackte Zielraster ansehen.
- Ein kleines GUI-Bild ist keine Prüfung von 10-Bit-Wiedergabe, Decoderartefakten, Bewegung, langfristiger A/V-Synchronität oder der tatsächlichen Brillen-/Monitorwirkung. Für diese Fälle einen kurzen Testclip mit dem echten Ausgabeprofil erzeugen und im Zielplayer ansehen.

Im ersten technischen GUI-Durchstich können technische Prüfung, Liste und Fortschritt allein stehen. Die Standbildkontrolle sollte anschließend als kleiner zuschaltbarer Dialog folgen, vor einer breiten Freigabe zusätzlicher Layouts und Methoden. Eine Live-Vorschau und eingebettete Player-Engine gehören nicht zur V1-Empfehlung.

## 8. Konkrete Validierung vor Umsetzung/Freigabe

Die folgenden Prüfpunkte sichern tatsächlich verschiedene Anforderungen; sie sind keine bereits bestandenen Tests:

1. Gleiche L/R-Testbilder in Full/Half-SBS und Full/Half-OU; Augenmarkierungen, Kreise und Auflösungslinien. Reihenfolge, Zielraster und Geometrie überprüfen. Half gegen eine fachlich passende herunterabgetastete Referenz vergleichen, nicht verlustfreie Gleichheit behaupten.
2. Gleiche Farbtafeln korrekt als sRGB-Bild und BT.709-Video kodieren; zentralen AnaglyphBatch-Methodenadapter vergleichen. Clip- und LUT-Reihenfolge bewusst einbeziehen.
3. 8-/10-Bit-Anaglyphen mit Gradienten und Farbkanten in passenden Softwaredecodern vergleichen. Ausgabeformat und Farbkennzeichnungen per ffprobe prüfen; Qualität nicht aus dem Profilnamen ableiten.
4. Kombinierte Suffixe mit und ohne Container-Metadaten in den konkreten Windows-Versionen von Kodi, Bino und Stereoscopic Player prüfen. Widersprüchliche Alt-Tags als Negativfall testen. Full/Half, Augenreihenfolge und Anzeigengeometrie getrennt betrachten.
5. Gemischte Dateiliste aus mehreren Ordnern, gleichnamige Quellen, vorhandene Ausgaben, VFR, fehlende Dauer, Abbruch und Fehler prüfen. Keine unbeabsichtigte Framerate- oder Audioänderung.

Erst nach dem ersten Full-SBS-Referenzdurchstich weitere Adapter freigeben. So erweitern wir den Eingang, ohne verschiedene Methodenimplementierungen oder eine überladene Oberfläche einzuführen.

## Primärquellen

- **Q1 – FFmpeg, libx264 und unterstützte Pixelformate:** https://ffmpeg.org/ffmpeg-codecs.html#libx264_002c-libx264rgb
- **Q2 – x265, Profile und Bittiefen:** https://x265.readthedocs.io/en/master/cli.html
- **Q3 – Matroska, offizielle Dateiendungen:** https://www.matroska.org/index.html
- **Q4 – FFmpeg, stereo3d-Ein-/Ausgabelayouts:** https://ffmpeg.org/ffmpeg-filters.html#stereo3d
- **Q5 – Stereoscopic Player, Versionsgeschichte und Namenssuffixe:** https://www.3dtv.at/products/Player/History_en.aspx
- **Q6 – Stereoscopic Player, SVI-Metadaten:** https://www.3dtv.at/Products/Player/Metadata_en.aspx
- **Q7 – Kodi, 3D-Erkennung und Dateinamen:** https://kodi.wiki/view/3D
- **Q8 – Bino, File Name Conventions:** https://bino3d.org/bino-manual.html#file-name-conventions
- **Q9 – Matroska, Multi-planar and 3D Videos:** https://www.matroska.org/technical/notes.html
- **Q10 – Bino, Container-Metadatenhinweise:** https://bino3d.org/metadata-for-stereo-3d-and-surround-video.html
- **Q11 – MKVToolNix, Trackeigenschaften bearbeiten:** https://mkvtoolnix.download/doc/mkvpropedit.html

Alle Webquellen wurden am 10. Oktober 2026 gelesen. Belegte Player-Regeln, lokale FFmpeg-Ergebnisse und eigene TransCora-Vorschläge sind im Text getrennt ausgewiesen. Externe Webseiten werden zur Entwicklungsrecherche verwendet; die geplante Anwendung benötigt dadurch keine Onlinefunktion.
