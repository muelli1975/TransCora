"""German source messages with a local English catalogue; never translate user data."""
import re
LANGUAGES = {'de': 'Deutsch', 'en': 'English'}
EN = {'\nFehler: {0}\n{1}\n': '\nError: {0}\n{1}\n',
 '\nGespeichert: ': '\nSaved: ',
 ' Bildprotokoll: {0}': ' Image log: {0}',
 ' H.265: MKV, längere Rechenzeit und Zielplayer prüfen; CRF ist codecabhängig.': ' H.265: MKV, longer '
                                                                                  'processing time; check '
                                                                                  'your target player. CRF '
                                                                                  'depends on the codec.',
 ' M2TS enthält beide Halbbilder, jedoch keine Blu-ray-Disc-Struktur.': ' M2TS contains both half-images, '
                                                                        'without a Blu-ray disc structure.',
 ' Zielbitrate = Videodurchschnitt, kein festes Dateigrößenlimit.': ' Target bitrate = average video '
                                                                    'bitrate, without a fixed file-size '
                                                                    'limit.',
 ' ausgewählt.': ' selected.',
 ' → 23,976 fps (24000/1001) · ': ' → 23.976 fps (24000/1001) · ',
 ' → {0} fps ({1}) · Laufzeit unverändert': ' → {0} fps ({1}) · Duration unchanged',
 '). Unter Erweitert AAC wählen oder MKV verwenden.': '). Select AAC under Advanced or use MKV.',
 '-Halbbild: ': ' half-image: ',
 '10 Bit: Feinere Abstufungen; kein HDR-Modus.': '10 bit: finer gradations; no HDR mode.',
 '1080p · 23,976 fps · AVC/MVC · Hohe Qualität. Andere konstante Quellbildraten werden direkt angepasst.': '1080p '
                                                                                                           '· '
                                                                                                           '23.976 '
                                                                                                           'fps '
                                                                                                           '· '
                                                                                                           'AVC/MVC '
                                                                                                           '· '
                                                                                                           'High '
                                                                                                           'quality. '
                                                                                                           'Other '
                                                                                                           'constant '
                                                                                                           'source '
                                                                                                           'frame '
                                                                                                           'rates '
                                                                                                           'are '
                                                                                                           'adjusted '
                                                                                                           'directly.',
 '16-Bit-/Fließkommabilder sind noch nicht freigegeben; 8-Bit-Kopie verwenden.': '16-bit/floating-point '
                                                                                 'images are not yet '
                                                                                 'supported; use an 8-bit '
                                                                                 'copy.',
 '1:1 · Originalpixel': '1:1 · Original pixels',
 '24 → 23,976 fps: Alle Bilder bleiben erhalten; Ton wird um 0,1 % verlangsamt.': '24 → 23.976 fps: all '
                                                                                  'frames are retained; '
                                                                                  'audio is slowed by 0.1%.',
 '3D-Kennzeichnung: AVC-Basis + zweites MVC-Halbbild · Linkes Halbbild zuerst': '3D metadata: AVC base + '
                                                                                'second MVC half-image · '
                                                                                'Left half-image first',
 '3D-Kennzeichnung: Keine SBS/OU-Kennzeichnung': '3D metadata: no SBS/OU flag',
 '3D-Kennzeichnung: {0}': '3D metadata: {0}',
 '4:2:0 benötigt gerade Ausgabemaße; diese Quelle muss zuerst passend vorbereitet werden.': '4:2:0 requires '
                                                                                            'even output '
                                                                                            'dimensions; '
                                                                                            'prepare this '
                                                                                            'source '
                                                                                            'accordingly '
                                                                                            'first.',
 '4:4:4 wird nicht von allen Playern/Hardwaredecodern unterstützt.': '4:4:4 is not supported by all '
                                                                     'players/hardware decoders.',
 '4:4:4: Nicht alle Player und Hardwaredecoder unterstützen dieses Format.': '4:4:4: not all players and '
                                                                             'hardware decoders support this '
                                                                             'format.',
 'AAC wird neu kodiert. Stereo mischt vorhandene Kanäle zusammen.': 'AAC is re-encoded. Stereo mixes the '
                                                                    'existing channels together.',
 'AAC · Hohe Kompatibilität': 'AAC · High compatibility',
 'Abbrechen': 'Cancel',
 'Abbruch angefordert …': 'Cancellation requested …',
 'Abbruch angefordert; laufenden Prozess beenden …': 'Cancellation requested; stopping the running process …',
 'Abgebrochen': 'Cancelled',
 'Abgebrochen.': 'Cancelled.',
 'Abschließen': 'Finish',
 'Aktuelle Einstellungen speichern …': 'Save current settings …',
 'Alle Bilder bleiben erhalten': 'All frames are retained',
 'Alle Bilder sind bereits fertig.': 'All images are already complete.',
 'Alle Dateien': 'All files',
 'Alle übernehmen': 'Copy all',
 'An Fenster anpassen': 'Fit to window',
 'Anaglyph-Ausgabeprofil': 'Anaglyph output profile',
 'Anaglyphenverfahren': 'Anaglyph method',
 'Anaglyphenverfahren der Voreinstellung ist nicht verfügbar.': 'Preset anaglyph method is not available.',
 'Anaglyphenverfahren nicht im geprüften Batch-Katalog.': 'Anaglyph method is not in the verified batch '
                                                          'catalogue.',
 'Aufgabe': 'Task',
 'Auflösung, Bildrate und Tonoptionen prüfen': 'Check resolution, frame rate and audio options',
 'Ausgabe geprüft · ': 'Output checked · ',
 'Ausgabe prüfen': 'Check output',
 'Ausgabemaße oder Pixelformat entsprechen nicht dem geprüften Plan.': 'Output dimensions or pixel format do '
                                                                       'not match the verified plan.',
 'Ausgabemaße stimmen nicht mit dem Bildplan überein.': 'Output dimensions do not match the image plan.',
 'Ausgabename: ': 'Output name: ',
 'Ausgabename: Nach Auswahl einer Datei': 'Output name: select a file first',
 'Ausgabename: Quelllayout prüfen': 'Output name: check source layout',
 'Ausgabeordner': 'Output folder',
 'Ausgabeordner auswählen.': 'Choose an output folder.',
 'Ausgabeordner wählen': 'Choose output folder',
 'Ausgabeziel geändert; erneut prüfen.': 'Output destination changed; check again.',
 'Ausgewählte Spuren': 'Selected tracks',
 'Automatisch': 'Automatic',
 'BD-3D benötigt ISO oder M2TS mit AVC/MVC.': 'BD-3D requires ISO or M2TS with AVC/MVC.',
 'BD-3D ist in der portablen Windows-Version verfügbar.': 'BD-3D is available in the portable Windows '
                                                          'version.',
 'BD-3D-Werkzeuge fehlen. TransCora.zip vollständig entpacken.': 'BD-3D tools are missing. Extract '
                                                                 'TransCora.zip completely.',
 'BD-3D: AVC-Basis oder zweites MVC-Halbbild fehlt im Multiplex.': 'BD-3D: AVC base or second MVC half-image '
                                                                   'is missing from the multiplex.',
 'BD-3D: Audio und Video beginnen nicht synchron.': 'BD-3D: audio and video do not start in sync.',
 'BD-3D: Audiospur mit nicht freigegebener Kanalbelegung; Mono, Stereo, 5.1 oder 7.1 verwenden.': 'BD-3D: '
                                                                                                  'unsupported '
                                                                                                  'audio '
                                                                                                  'channel '
                                                                                                  'layout; '
                                                                                                  'use mono, '
                                                                                                  'stereo, '
                                                                                                  '5.1 or '
                                                                                                  '7.1.',
 'BD-3D: Ausgaberaster, Farbauflösung oder AVC-Level falsch.': 'BD-3D: incorrect output dimensions, chroma '
                                                               'resolution or AVC level.',
 'BD-3D: BT.709-Farbkennzeichnung in beiden Bildspuren setzen': 'BD-3D: set BT.709 colour metadata in both '
                                                                'image tracks',
 'BD-3D: Beide Halbbilder fehlen in der fertigen Ausgabe.': 'BD-3D: both half-images are missing from the '
                                                            'finished output.',
 'BD-3D: Beide Halbbilder in hoher Qualität kodieren': 'BD-3D: encode both half-images at high quality',
 'BD-3D: Beschädigte UDF-Dateiallokation.': 'BD-3D: damaged UDF file allocation.',
 'BD-3D: Bildrate oder Farbkennzeichnung falsch.': 'BD-3D: incorrect frame rate or colour metadata.',
 'BD-3D: Bildzeiten und beide Halbbilder werden beim Export vollständig geprüft. Gewählter Ton wird als LPCM gespeichert.': 'BD-3D: '
                                                                                                                            'frame '
                                                                                                                            'timing '
                                                                                                                            'and '
                                                                                                                            'both '
                                                                                                                            'half-images '
                                                                                                                            'are '
                                                                                                                            'fully '
                                                                                                                            'checked '
                                                                                                                            'during '
                                                                                                                            'export. '
                                                                                                                            'Selected '
                                                                                                                            'audio '
                                                                                                                            'is '
                                                                                                                            'saved '
                                                                                                                            'as '
                                                                                                                            'LPCM.',
 'BD-3D: Blu-ray-Struktur ungültig.': 'BD-3D: invalid Blu-ray structure.',
 'BD-3D: Blu-ray-Struktur unvollständig.': 'BD-3D: incomplete Blu-ray structure.',
 'BD-3D: Der Disc-Titel wurde nicht korrekt gespeichert.': 'BD-3D: disc title was not saved correctly.',
 'BD-3D: Die Dekodierung beider Halbbilder enthält nicht die erwartete Bildanzahl.': 'BD-3D: decoding both '
                                                                                     'half-images did not '
                                                                                     'produce the expected '
                                                                                     'frame count.',
 'BD-3D: Die native Bildfolge wurde unerwartet verändert.': 'BD-3D: the native image sequence was '
                                                            'unexpectedly changed.',
 'BD-3D: Die tatsächliche Bildfolge entspricht nicht der angegebenen konstanten Framerate.': 'BD-3D: the '
                                                                                             'actual frame '
                                                                                             'sequence does '
                                                                                             'not match the '
                                                                                             'declared '
                                                                                             'constant frame '
                                                                                             'rate.',
 'BD-3D: Disc-Titel ist für das UDF-Feld zu lang.': 'BD-3D: disc title is too long for the UDF field.',
 'BD-3D: Eindeutige SBS/OU-Quelle erforderlich.': 'BD-3D: an unambiguous SBS/OU source is required.',
 'BD-3D: Eine konstante, progressive Quellbildrate zwischen 1 und 240 fps ist erforderlich.': 'BD-3D: a '
                                                                                              'constant, '
                                                                                              'progressive '
                                                                                              'source frame '
                                                                                              'rate from 1 '
                                                                                              'to 240 fps is '
                                                                                              'required.',
 'BD-3D: Fehlende Bildzeit in der Quelle.': 'BD-3D: missing source frame timestamp.',
 'BD-3D: Fertige Ausgabe und Blu-ray-Struktur prüfen': 'BD-3D: check finished output and Blu-ray structure',
 'BD-3D: Fertige Ausgabe vollständig dekodieren und beide Halbbilder prüfen': 'BD-3D: fully decode the '
                                                                              'finished output and check '
                                                                              'both half-images',
 'BD-3D: Für Ausgabe und Prüfdaten werden ungefähr {0} GB freier Platz benötigt.': 'BD-3D: output and '
                                                                                   'verification data '
                                                                                   'require approximately '
                                                                                   '{0} GB of free space.',
 'BD-3D: ISO-Beschriftungsstruktur fehlt.': 'BD-3D: ISO label structure is missing.',
 'BD-3D: ISO-Datei abgeschnitten.': 'BD-3D: truncated ISO file.',
 'BD-3D: ISO-Datei nicht vollständig lesbar.': 'BD-3D: ISO file could not be read completely.',
 'BD-3D: ISO-Deskriptorbereich ungültig.': 'BD-3D: invalid ISO descriptor area.',
 'BD-3D: In der ISO fehlt {0}': 'BD-3D: ISO is missing {0}',
 'BD-3D: Interlaced-Quellen sind noch nicht freigegeben.': 'BD-3D: interlaced sources are not yet supported.',
 'BD-3D: Kodierte Bilddaten für den Ausgabevergleich erfassen': 'BD-3D: record encoded image data for output '
                                                                'comparison',
 'BD-3D: Kodierte Bilddaten mit der fertigen Ausgabe vergleichen': 'BD-3D: compare encoded image data with '
                                                                   'the finished output',
 'BD-3D: Kodierte Bilder oder Parameter fehlen.': 'BD-3D: encoded frames or parameters are missing.',
 'BD-3D: Kodierte Halbbilder oder Bildparameter wurden beim Verpacken verändert.': 'BD-3D: encoded '
                                                                                   'half-images or image '
                                                                                   'parameters were changed '
                                                                                   'during packaging.',
 'BD-3D: Kodierung fehlgeschlagen · {0}': 'BD-3D: encoding failed · {0}',
 'BD-3D: LPCM mit 48 kHz und 24 Bit.': 'BD-3D: LPCM at 48 kHz and 24 bit.',
 'BD-3D: Laufzeit für die Platzprüfung fehlt.': 'BD-3D: duration is missing for the disk-space check.',
 'BD-3D: Leere NAL-Einheit in der Bildspur.': 'BD-3D: empty NAL unit in image track.',
 'BD-3D: Nicht unterstützte UDF-Dateiallokation.': 'BD-3D: unsupported UDF file allocation.',
 'BD-3D: Nicht unterstützte UDF-Fortsetzungsallokation.': 'BD-3D: unsupported UDF continuation allocation.',
 'BD-3D: Nicht unterstützte UDF-Partitionskarte.': 'BD-3D: unsupported UDF partition map.',
 'BD-3D: Quellbildrate fehlt oder ist ungültig.': 'BD-3D: source frame rate is missing or invalid.',
 'BD-3D: UDF 2.50 fehlt.': 'BD-3D: UDF 2.50 is missing.',
 'BD-3D: UDF-Adresse außerhalb der Partition.': 'BD-3D: UDF address is outside the partition.',
 'BD-3D: UDF-Dateidaten fehlen.': 'BD-3D: UDF file data is missing.',
 'BD-3D: UDF-Deskriptor beschädigt.': 'BD-3D: damaged UDF descriptor.',
 'BD-3D: UDF-Metadatenspiegel ungültig.': 'BD-3D: invalid UDF metadata mirror.',
 'BD-3D: UDF-Metadatenspiegel unvollständig.': 'BD-3D: incomplete UDF metadata mirror.',
 'BD-3D: UDF-Metadatenzuordnung ungültig.': 'BD-3D: invalid UDF metadata mapping.',
 'BD-3D: UDF-Partitionskarte ungültig.': 'BD-3D: invalid UDF partition map.',
 'BD-3D: UDF-Prüfsumme ungültig.': 'BD-3D: invalid UDF checksum.',
 'BD-3D: UDF-Verzeichnis abgeschnitten.': 'BD-3D: truncated UDF directory.',
 'BD-3D: UDF-Verzeichnis zu groß.': 'BD-3D: UDF directory is too large.',
 'BD-3D: Unerwartet unterschiedliche NAL-/VCL-HRD-Parameter.': 'BD-3D: unexpectedly different NAL/VCL HRD '
                                                               'parameters.',
 'BD-3D: Unerwartete ISO-Struktur.': 'BD-3D: unexpected ISO structure.',
 'BD-3D: Ungültige Bildzeit in der Quelle.': 'BD-3D: invalid source frame timestamp.',
 'BD-3D: Ungültige HRD-Pufferbeschreibung.': 'BD-3D: invalid HRD buffer description.',
 'BD-3D: Ungültige UDF-Allokationsfortsetzung.': 'BD-3D: invalid UDF allocation continuation.',
 'BD-3D: Ungültige UDF-Partition.': 'BD-3D: invalid UDF partition.',
 'BD-3D: Ungültige oder unteilbare Stereo-Auflösung.': 'BD-3D: invalid or indivisible stereo resolution.',
 'BD-3D: Ungültiger Disc-Titel.': 'BD-3D: invalid disc title.',
 'BD-3D: Ungültiger Pfad für die Multiplexer-Datei.': 'BD-3D: invalid path for the multiplexer file.',
 'BD-3D: Ungültiger UDF-Dateieintrag.': 'BD-3D: invalid UDF file entry.',
 'BD-3D: Ungültiger UDF-Dateiname.': 'BD-3D: invalid UDF filename.',
 'BD-3D: Variable Bildzeiten oder Bildlücken sind noch nicht freigegeben.': 'BD-3D: variable frame timing or '
                                                                            'gaps are not yet supported.',
 'BD-3D: Verlustfreie Audioübernahme stimmt nicht mit der Quelle überein.': 'BD-3D: lossless audio transfer '
                                                                            'does not match the source.',
 'BD-3D: Werkzeugfehler · {0}': 'BD-3D: tool error · {0}',
 'BD-3D: Zu große UDF-Allokationsfortsetzung.': 'BD-3D: oversized UDF allocation continuation.',
 'BD-3D: Zu wenige Bilder für eine verlässliche Timing-Prüfung.': 'BD-3D: too few frames for a reliable '
                                                                  'timing check.',
 'Begonnene Ausgabe verworfen': 'Incomplete output discarded',
 'Beide Halbbilder teilen': 'Split both half-images',
 'Beispiel-Ausgabename: ': 'Example output name: ',
 'Bereit': 'Ready',
 'Bereit.': 'Ready.',
 'Beschädigter MPO-Index oder unvollständiges JPEG-Halbbild.': 'Damaged MPO index or incomplete JPEG '
                                                               'half-image.',
 'Bild lässt sich nicht in zwei gleich große Halbbilder teilen.': 'Image cannot be divided into two equal '
                                                                  'half-images.',
 'Bild mit FFmpeg verarbeiten': 'Process image with FFmpeg',
 'Bild orientieren und Farbprofil lesen': 'Apply image orientation and read colour profile',
 'Bilddetails': 'Image details',
 'Bilder': 'Images',
 'Bilder hinzufügen': 'Add images',
 'Bilder konvertieren': 'Convert images',
 'Bilder und Halbbilder im Stapel verarbeiten': 'Batch processing of images and half-images',
 'Bildformat': 'Image format',
 'Bildformat und Metadaten schreiben': 'Write image format and metadata',
 'Bildkontrolle · L/R-Reihenfolge und Details prüfen': 'Image preview · Check L/R order and detail',
 'Bildliste': 'Image list',
 'Bildpaare auslassen/wiederholen': 'Drop/repeat image pairs',
 'Bildprotokoll: {0}': 'Image log: {0}',
 'Bildquelle wurde seit dem Test verändert: ': 'Image source changed since the test: ',
 'Bildquelle während der Verarbeitung verändert.': 'Image source changed during processing.',
 'Bildstapel abgebrochen.': 'Image batch cancelled.',
 'Bildstapel abgeschlossen.': 'Image batch complete.',
 'Bildstapel prüfen …': 'Check image batch …',
 'Bildvoreinstellung': 'Image preset',
 'Blu-ray-Filmdatei für die Prüfung lesen': 'Read Blu-ray movie file for verification',
 'Blu-ray-ISO erstellen': 'Create Blu-ray ISO',
 'Blu-ray-ISO: Längste Film-Playlist ': 'Blu-ray ISO: longest movie playlist ',
 'Blu-ray-PlayItem ist abgeschnitten.': 'Truncated Blu-ray PlayItem.',
 'Blu-ray-Playlist ist abgeschnitten.': 'Truncated Blu-ray playlist.',
 'Blu-ray-Playlist ist zu groß.': 'Blu-ray playlist is too large.',
 'Blu-ray-Playlist prüfen': 'Check Blu-ray playlist',
 'Blu-ray: AppInfoPlayList fehlt.': 'Blu-ray: AppInfoPlayList is missing.',
 'Blu-ray: AppInfoPlayList ist abgeschnitten.': 'Blu-ray: truncated AppInfoPlayList.',
 'Breitere Player-Unterstützung, jedoch mit deutlich geringerer Farbauflösung. Farbdetails und farbige Kanten können sichtbar leiden. Für hochwertige Anaglyphen wird 4:4:4 empfohlen.': 'Wider '
                                                                                                                                                                                         'player '
                                                                                                                                                                                         'support, '
                                                                                                                                                                                         'but '
                                                                                                                                                                                         'significantly '
                                                                                                                                                                                         'lower '
                                                                                                                                                                                         'chroma '
                                                                                                                                                                                         'resolution. '
                                                                                                                                                                                         'Colour '
                                                                                                                                                                                         'detail '
                                                                                                                                                                                         'and '
                                                                                                                                                                                         'coloured '
                                                                                                                                                                                         'edges '
                                                                                                                                                                                         'may '
                                                                                                                                                                                         'suffer '
                                                                                                                                                                                         'visibly. '
                                                                                                                                                                                         '4:4:4 '
                                                                                                                                                                                         'is '
                                                                                                                                                                                         'recommended '
                                                                                                                                                                                         'for '
                                                                                                                                                                                         'high-quality '
                                                                                                                                                                                         'anaglyphs.',
 'CRF muss zwischen 1 und 51 liegen.': 'CRF must be between 1 and 51.',
 'Das Ausgabeziel wurde zwischenzeitlich angelegt; es wird nicht überschrieben.': 'The output destination '
                                                                                  'was created in the '
                                                                                  'meantime; it will not be '
                                                                                  'overwritten.',
 'Das Pixelseitenverhältnis wurde unerwartet geändert.': 'Pixel aspect ratio was unexpectedly changed.',
 'Das gepackte Raster lässt sich nicht in zwei gleich große Halbbilder teilen.': 'The packed image cannot be '
                                                                                 'divided into two equal '
                                                                                 'half-images.',
 'Datei': 'File',
 'Datei fehlt: {0}': 'File is missing: {0}',
 'Datei {0} von {1} · {2}': 'File {0} of {1} · {2}',
 'Dateien hinzufügen': 'Add files',
 'Dateien hinzufügen oder eine gespeicherte Liste laden.': 'Add files or load a saved list.',
 'Dateiname und Stereo-Metadaten widersprechen sich. Quelllayout bewusst auswählen.': 'Filename and stereo '
                                                                                      'metadata conflict. '
                                                                                      'Select the source '
                                                                                      'layout explicitly.',
 'Dateinamenszusatz · frei editierbar': 'Filename suffix · editable',
 'Dateinamenszusatz: Höchstens 80 Zeichen, ohne Pfad- oder ungültige Dateizeichen.': 'Filename suffix: up to '
                                                                                     '80 characters, without '
                                                                                     'path separators or '
                                                                                     'invalid filename '
                                                                                     'characters.',
 'Dauer unbekannt': 'Unknown duration',
 'Der Encoder unterstützt das gewählte Pixelformat nicht.': 'The encoder does not support the selected pixel '
                                                            'format.',
 'Der FFmpeg-Build enthält keinen H.264-Encoder libx264.': 'FFmpeg build has no H.264 encoder libx264.',
 'Der Programmordner ist schreibgeschützt; Einstellungen konnten nicht gespeichert werden.': 'The program '
                                                                                             'folder is '
                                                                                             'read-only; '
                                                                                             'settings could '
                                                                                             'not be saved.',
 'Der portable MVC-Decoder fehlt. TransCora vollständig entpacken.': 'Portable MVC decoder is missing. '
                                                                     'Extract TransCora completely.',
 'Die Audioübernahme stimmt nicht mit der Quelle überein.': 'Audio transfer does not match the source.',
 'Die Ausgabe ist leer.': 'Output is empty.',
 'Die Blu-ray-Playlist verwendet einen Ausschnitt. Clip-Trimmen ist noch nicht freigegeben.': 'Blu-ray '
                                                                                              'playlist uses '
                                                                                              'an excerpt. '
                                                                                              'Clip trimming '
                                                                                              'is not yet '
                                                                                              'supported.',
 'Die Farbkennzeichnung der Ausgabe stimmt nicht mit dem Plan überein.': 'Output colour metadata does not '
                                                                         'match the plan.',
 'Die H.264-Frame-Packing-Kennzeichnung fehlt oder ist falsch.': 'H.264 frame-packing metadata is missing or '
                                                                 'incorrect.',
 'Die Kanalzahl des ausgegebenen Tons stimmt nicht mit dem Plan überein.': 'Output audio channel count does '
                                                                           'not match the plan.',
 'Die MP4-Bildzeiten entsprechen nicht der exakten Zielbildrate: ': 'MP4 frame timing does not match the '
                                                                    'exact target frame rate: ',
 'Die Quelldatei wurde während der Prüfung geändert.': 'Source file changed during verification.',
 'Die Quelldatei wurde während der Verarbeitung geändert.': 'Source file changed during processing.',
 'Die Quelle enthält nicht das gewählte Multiview-Format.': 'Source does not contain the selected multiview '
                                                            'format.',
 'Die Stereo-Kennzeichnung der Ausgabe stimmt nicht mit dem Plan überein: ': 'Output stereo metadata does '
                                                                             'not match the plan: ',
 'Die Zielbildrate wurde nicht korrekt gespeichert: ': 'Target frame rate was not saved correctly: ',
 'Die Zielbitrate muss größer als 0 und höchstens 1000 Mbit/s sein.': 'Target bitrate must be greater than 0 '
                                                                      'and no more than 1000 Mbit/s.',
 'Die explizite MP4-st3d-Kennzeichnung fehlt oder ist falsch.': 'Explicit MP4-st3d metadata is missing or '
                                                                'incorrect.',
 'Die mitgelieferten Programme ffmpeg und ffprobe fehlen. TransCora.zip vollständig entpacken und den gesamten Programmordner zusammenhalten.': 'Bundled '
                                                                                                                                                'ffmpeg '
                                                                                                                                                'and '
                                                                                                                                                'ffprobe '
                                                                                                                                                'are '
                                                                                                                                                'missing. '
                                                                                                                                                'Extract '
                                                                                                                                                'TransCora.zip '
                                                                                                                                                'completely '
                                                                                                                                                'and '
                                                                                                                                                'keep '
                                                                                                                                                'the '
                                                                                                                                                'entire '
                                                                                                                                                'program '
                                                                                                                                                'folder '
                                                                                                                                                'together.',
 'Die technische Prüfung hat zu lange gedauert.': 'Technical verification took too long.',
 'Diese Blu-ray verwendet mehrere Clips pro Film. Seamless Branching ist noch nicht freigegeben.': 'This '
                                                                                                   'Blu-ray '
                                                                                                   'uses '
                                                                                                   'several '
                                                                                                   'clips '
                                                                                                   'per '
                                                                                                   'movie. '
                                                                                                   'Seamless '
                                                                                                   'branching '
                                                                                                   'is not '
                                                                                                   'yet '
                                                                                                   'supported.',
 'Diese Quelle enthält echte Multiview-Halbbilder. Automatisch oder das passende Multiview-Format wählen.': 'This '
                                                                                                            'source '
                                                                                                            'contains '
                                                                                                            'genuine '
                                                                                                            'multiview '
                                                                                                            'half-images. '
                                                                                                            'Select '
                                                                                                            'Automatic '
                                                                                                            'or '
                                                                                                            'the '
                                                                                                            'matching '
                                                                                                            'multiview '
                                                                                                            'format.',
 'Dieser FFmpeg-Build enthält keinen H.265-Encoder.': 'This FFmpeg build has no H.265 encoder.',
 'Dieses Stereo-Layout ist noch nicht freigegeben. SBS/OU-Quelle verwenden.': 'This stereo layout is not yet '
                                                                              'supported. Use an SBS/OU '
                                                                              'source.',
 'Dieses Ziel benötigt zwei Halbbilder: ': 'This target requires two half-images: ',
 'Disc-Titel': 'Disc title',
 'Disc-Titel: Höchstens 62 Unicode-Zeichen, ohne ungültige Dateizeichen.': 'Disc title: up to 62 Unicode '
                                                                           'characters, without invalid '
                                                                           'filename characters.',
 'Doppeltes {0}-Halbbild: {1}': 'Duplicate {0} half-image: {1}',
 'Ein Bild in der Liste auswählen.': 'Select an image in the list.',
 'Ein vorhandener Name ersetzt die gespeicherte Voreinstellung.': 'An existing name replaces the saved '
                                                                  'preset.',
 'Einstellungen': 'Settings',
 'Einstellungen für {0} ausgewählte Datei(en). Leere Auswahlfelder bedeuten gemischte Werte.': 'Settings for '
                                                                                               '{0} selected '
                                                                                               'file(s). '
                                                                                               'Empty '
                                                                                               'selection '
                                                                                               'fields '
                                                                                               'indicate '
                                                                                               'mixed '
                                                                                               'values.',
 'Einstellungen gelten für neu hinzugefügte Bilder.': 'Settings apply to newly added images.',
 'Einstellungen gelten für neu hinzugefügte Dateien.': 'Settings apply to newly added files.',
 'Einstellungen gelten für {0} ausgewählte Bilder.': 'Settings apply to {0} selected images.',
 'Einstellungen geändert; erneut prüfen.': 'Settings changed; check again.',
 'Einstellungen geändert; erneut testen.': 'Settings changed; test again.',
 'Einstellungen werden sofort übernommen.': 'Settings are applied immediately.',
 'Einstellungen übernommen. Vor dem Start wird erneut geprüft.': 'Settings applied. Verification runs again '
                                                                 'before starting.',
 'Entfernen': 'Remove',
 'Erweitert ▸': 'Advanced ▸',
 'ExifTool fehlt. TransCora.zip vollständig entpacken.': 'ExifTool is missing. Extract TransCora.zip '
                                                         'completely.',
 'Exportgröße: {0} × {1} Pixel': 'Export size: {0} × {1} pixels',
 'Externes Tool meldet einen Fehler.': 'An external tool reported an error.',
 'FFmpeg konnte nicht gestartet werden.': 'FFmpeg could not be started.',
 'FFmpeg-Build ungeeignet; fehlende Filter: {0}': 'Unsuitable FFmpeg build; missing filters: {0}',
 'FRIM: Keine vollständige dekodierte Stereobildfolge.': 'FRIM: no complete decoded stereo image sequence.',
 'Farbangaben unvollständig; keine eindeutige HD-SDR-Annahme möglich. Quelle prüfen und fehlende Farbangaben vor dem Import ergänzen.': 'Incomplete '
                                                                                                                                        'colour '
                                                                                                                                        'metadata; '
                                                                                                                                        'no '
                                                                                                                                        'unambiguous '
                                                                                                                                        'HD-SDR '
                                                                                                                                        'assumption '
                                                                                                                                        'is '
                                                                                                                                        'possible. '
                                                                                                                                        'Check '
                                                                                                                                        'the '
                                                                                                                                        'source '
                                                                                                                                        'and '
                                                                                                                                        'add '
                                                                                                                                        'missing '
                                                                                                                                        'colour '
                                                                                                                                        'metadata '
                                                                                                                                        'before '
                                                                                                                                        'importing.',
 'Farbannahme {0}={1} (fehlende HD-SDR-Angabe)': 'Colour assumption {0}={1} (missing HD SDR tag)',
 'Fehler': 'Error',
 'Fehler: {0}': 'Error: {0}',
 'Fertig': 'Done',
 'Full-OU · Quellauflösung': 'Full-OU · Source resolution',
 'Full-SBS · Quellauflösung': 'Full-SBS · Source resolution',
 'Full/Half-Layout nicht eindeutig erkennbar. Quelllayout für diese Datei auswählen.': 'Full/Half layout is '
                                                                                       'ambiguous. Select '
                                                                                       'the source layout '
                                                                                       'for this file.',
 'Für das Kontrollbild genau eine Datei auswählen.': 'Select exactly one file for the preview.',
 'Ganze Bilder werden ausgelassen/wiederholt; keine Überblendung oder Bewegungsinterpolation. Video wird neu kodiert; Ton und Wiedergabegeschwindigkeit bleiben erhalten.': 'Whole '
                                                                                                                                                                            'frames '
                                                                                                                                                                            'are '
                                                                                                                                                                            'dropped/repeated; '
                                                                                                                                                                            'no '
                                                                                                                                                                            'blending '
                                                                                                                                                                            'or '
                                                                                                                                                                            'motion '
                                                                                                                                                                            'interpolation. '
                                                                                                                                                                            'Video '
                                                                                                                                                                            'is '
                                                                                                                                                                            're-encoded; '
                                                                                                                                                                            'audio '
                                                                                                                                                                            'and '
                                                                                                                                                                            'playback '
                                                                                                                                                                            'speed '
                                                                                                                                                                            'are '
                                                                                                                                                                            'retained.',
 'Gedrehte oder VR-projizierte Quelle: In dieser Version bitte vorher als normales SBS/OU vorbereiten.': 'Rotated '
                                                                                                         'or '
                                                                                                         'VR-projected '
                                                                                                         'source: '
                                                                                                         'prepare '
                                                                                                         'it '
                                                                                                         'as '
                                                                                                         'standard '
                                                                                                         'SBS/OU '
                                                                                                         'before '
                                                                                                         'using '
                                                                                                         'this '
                                                                                                         'version.',
 'Geschwindigkeit {0}': 'Speed {0}',
 'Geschwindigkeit: {0}': 'Speed: {0}',
 'Gleiche Exportgröße und Kompression wie im Export.': 'Same output size and compression as export.',
 'Gleiche Filterkette wie im Export · 8-Bit-Anzeige, ohne Videokompression': 'Same filter chain as export · '
                                                                             '8-bit display, without video '
                                                                             'compression',
 'H.265 ist in dieser Version nur mit MKV freigegeben.': 'H.265 is only supported with MKV in this version.',
 'HDR-Quelle: Diese Version verarbeitet geprüftes SDR, ohne automatische HDR-/SDR-Wandlung.': 'HDR source: '
                                                                                              'this version '
                                                                                              'supports '
                                                                                              'verified SDR, '
                                                                                              'without '
                                                                                              'automatic '
                                                                                              'HDR/SDR '
                                                                                              'conversion.',
 'Half → Full skaliert die gestauchte Achse; keine zusätzlichen Bilddetails.': 'Half → Full upscales the '
                                                                               'compressed axis; no '
                                                                               'additional image detail.',
 'Half → Full: Die gestauchte Achse wird hochskaliert. Verlorene Bilddetails werden nicht wiederhergestellt.': 'Half '
                                                                                                               '→ '
                                                                                                               'Full: '
                                                                                                               'the '
                                                                                                               'compressed '
                                                                                                               'axis '
                                                                                                               'is '
                                                                                                               'upscaled. '
                                                                                                               'Lost '
                                                                                                               'image '
                                                                                                               'detail '
                                                                                                               'cannot '
                                                                                                               'be '
                                                                                                               'restored.',
 'Helligkeitswertebereich fehlt und ist für dieses Pixelformat nicht bestimmbar.': 'Luminance range is '
                                                                                   'missing and cannot be '
                                                                                   'determined for this '
                                                                                   'pixel format.',
 'Hohe Farbtiefe · 10 Bit / 4:4:4': 'High colour depth · 10 bit / 4:4:4',
 'ISO/M2TS ist nur für BD-3D verfügbar.': 'ISO/M2TS is available only for BD-3D.',
 'In Stereo umwandeln': 'Convert to stereo',
 'Interlaced-Quelle: Eine geprüfte Deinterlacing-Regel ist noch nicht verfügbar.': 'Interlaced source: a '
                                                                                   'verified deinterlacing '
                                                                                   'rule is not yet '
                                                                                   'available.',
 'JPEG-Qualität': 'JPEG quality',
 'JPEG-Qualität: 90/95. Lange Kante: 0 (Original) bis 20000 Pixel.': 'JPEG quality: 90/95. Long edge: 0 '
                                                                     '(original) to 20000 pixels.',
 'JPS/PNS: Full-SBS mit rechtem Halbbild zuerst angenommen; Reihenfolge kontrollieren.': 'JPS/PNS: Full-SBS '
                                                                                         'with right '
                                                                                         'half-image first '
                                                                                         'is assumed; check '
                                                                                         'order.',
 'Jobliste ergänzt. Alle Quellen werden vor dem Start neu geprüft.': 'Job list appended. All sources will be '
                                                                     'checked again before starting.',
 'Jobliste gespeichert; enthalten sind Pfade und Einstellungen, keine Videos.': 'Job list saved; it contains '
                                                                                'paths and settings, without '
                                                                                'video files.',
 'Jobliste ist zu groß.': 'Job list is too large.',
 'Jobliste laden': 'Load job list',
 'Jobliste speichern': 'Save job list',
 'Kein Layout-Zusatz': 'No layout suffix',
 'Keine Film-Playlist in der Blu-ray-ISO.': 'No movie playlist in the Blu-ray ISO.',
 'Keine TransCora-Bildliste.': 'Not a TransCora image list.',
 'Keine gespeicherten Voreinstellungen': 'No saved presets',
 'Keine gültige Videoauflösung.': 'No valid video resolution.',
 'Keine noch offenen Dateien in der Liste.': 'No unfinished files in the list.',
 'Keine nutzbare Videospur gefunden.': 'No usable video track found.',
 'Keine technischen Meldungen.': 'No technical messages.',
 'Keiner': 'None',
 'Kompatibel · 8 Bit / 4:2:0': 'Compatible · 8 bit / 4:2:0',
 'Kontrollbild': 'Preview',
 'Kontrollbild berechnen': 'Calculate preview',
 'Kontrollbild berechnen …': 'Calculate preview …',
 'Kontrollbild bereit.': 'Preview ready.',
 'Kontrollbild wird berechnet …': 'Calculating preview …',
 'Kontrollbild · vor der Kodierung': 'Preview · before encoding',
 'Kontrollbild · {0} × {1} Pixel': 'Preview · {0} × {1} pixels',
 'Kontrollbild: ': 'Preview: ',
 'Kontrollbild: Dekodierung dauert zu lange.': 'Preview: decoding took too long.',
 'Kontrollbild: {0}': 'Preview: {0}',
 'L/R tauschen': 'Swap L/R',
 'L/R-Ordner und Nummerierung; Bilddateien werden unverändert kopiert.': 'L/R folders and numbering; image '
                                                                         'files are copied unchanged.',
 'L/R-Paar: Maße und Einstellungen müssen übereinstimmen.': 'L/R pair: dimensions and settings must match.',
 'L/R-Paar: Namen mit _l/_r oder Ordner L/R erforderlich: ': 'L/R pair: names with _l/_r or L/R folders are '
                                                             'required: ',
 'L/R-Paare vorbereiten': 'Prepare L/R pairs',
 'L/R-Vorbereitung benötigt einzelne Halbbilder; MPO zuerst teilen.': 'L/R preparation requires individual '
                                                                      'half-images; split MPO first.',
 'L/R-Vorbereitung kopiert Dateien unverändert. Mit Testen die Paare prüfen.': 'L/R preparation copies files '
                                                                               'unchanged. Use Test to check '
                                                                               'pairs.',
 'LPCM · 24 Bit': 'LPCM · 24 bit',
 'Laden': 'Load',
 'Lange Kante · 0 = Original': 'Long edge · 0 = original',
 'Laufende Arbeit abbrechen und TransCora schließen?': 'Cancel running work and close TransCora?',
 'Laufzeit erhalten': 'Retain duration',
 'Layout beibehalten': 'Keep layout',
 'Layout, Auflösung und Halbbildreihenfolge bleiben erhalten. Video wird neu kodiert; Ton gemäß Erweitert.': 'Layout, '
                                                                                                             'resolution '
                                                                                                             'and '
                                                                                                             'half-image '
                                                                                                             'order '
                                                                                                             'are '
                                                                                                             'retained. '
                                                                                                             'Video '
                                                                                                             'is '
                                                                                                             're-encoded; '
                                                                                                             'audio '
                                                                                                             'as '
                                                                                                             'set '
                                                                                                             'under '
                                                                                                             'Advanced.',
 'Linkes Halbbild': 'Left half-image',
 'Linkes Halbbild zuerst': 'Left half-image first',
 'Liste laden': 'Load list',
 'Liste speichern': 'Save list',
 'Logs löschen': 'Delete logs',
 'Logs löschen: {0}': 'Delete logs: {0}',
 'Lokale 3D-Video-Konvertierung': 'Local 3D video conversion',
 'Läuft': 'Running',
 'Löschen': 'Delete',
 'M2TS erstellen': 'Create M2TS',
 'MP4-3D-Kennzeichnung schreiben': 'Write MP4 3D metadata',
 'MP4-Bildzeiten schreiben': 'Write MP4 frame timing',
 'MPO mit genau zwei Halbbildern erforderlich.': 'An MPO with exactly two half-images is required.',
 'MPO verlustfrei teilen': 'Split MPO losslessly',
 'MPO-Extraktion ergibt kein selbständiges JPEG.': 'MPO extraction does not produce a standalone JPEG.',
 'MPO-Halbbilder haben unterschiedliche Maße oder Orientierung.': 'MPO half-images have different dimensions '
                                                                  'or orientations.',
 'MPO-Teilung und L/R-Vorbereitung erhalten die komprimierten Bilddaten unverändert.': 'MPO splitting and '
                                                                                       'L/R preparation '
                                                                                       'preserve compressed '
                                                                                       'image data '
                                                                                       'unchanged.',
 'MPO: Erstes Halbbild als links angenommen; L/R-Reihenfolge kontrollieren.': 'MPO: first half-image assumed '
                                                                              'to be left; check L/R order.',
 'MV-HEVC: Ein Halbbild fehlt oder bleibt zurück.': 'MV-HEVC: a half-image is missing or falling behind.',
 'MV-HEVC: Eine Ansicht fehlt oder bleibt zurück.': 'MV-HEVC: a half-image is missing or falling behind.',
 'MV-HEVC: Fehlende Bildzeit eines Halbbildes.': 'MV-HEVC: missing timestamp for a half-image.',
 'MV-HEVC: Halbbilder sind zeitlich nicht synchron.': 'MV-HEVC: half-images are not synchronised in time.',
 'MV-HEVC: Unvollständige Stereobildfolge.': 'MV-HEVC: incomplete stereo image sequence.',
 'MV-HEVC: Zwei eindeutig als links/rechts gekennzeichnete Halbbilder sind erforderlich.': 'MV-HEVC: two '
                                                                                           'half-images '
                                                                                           'explicitly '
                                                                                           'labelled '
                                                                                           'left/right are '
                                                                                           'required.',
 'MVC-Decoder an beiden Halbbildern testen': 'Test MVC decoder with both half-images',
 'MVC-Kennzeichnung der Quelle prüfen': 'Check MVC source metadata',
 'MVC: Basis-Halbbild als links angenommen. Reihenfolge im Kontrollbild prüfen; L/R tauschen ist verfügbar.': 'MVC: '
                                                                                                              'base '
                                                                                                              'half-image '
                                                                                                              'assumed '
                                                                                                              'to '
                                                                                                              'be '
                                                                                                              'left. '
                                                                                                              'Check '
                                                                                                              'order '
                                                                                                              'in '
                                                                                                              'the '
                                                                                                              'preview; '
                                                                                                              'Swap '
                                                                                                              'L/R '
                                                                                                              'is '
                                                                                                              'available.',
 'MVC: Basis-Halbbild laut Blu-ray-Playlist ': 'MVC: base half-image according to Blu-ray playlist ',
 'MVC: Beide Halbbilder dekodieren · ': 'MVC: decode both half-images · ',
 'MVC: Beschädigter oder verschlüsselter Transportstrom.': 'MVC: damaged or encrypted transport stream.',
 'MVC: Decoder beendet sich nach dem letzten Bild nicht.': 'MVC: decoder does not exit after the last frame.',
 'MVC: Decoder-Geometrie stimmt nicht mit der Quelle überein.': 'MVC: decoder geometry does not match the '
                                                                'source.',
 'MVC: Dekodierung fehlgeschlagen · {0}': 'MVC: decoding failed · {0}',
 'MVC: Eine der beiden Videospuren fehlt.': 'MVC: one of the two video tracks is missing.',
 'MVC: Fehlende Paketbildzeit. CFR-Quelle mit vollständigen Zeitstempeln verwenden.': 'MVC: missing packet '
                                                                                      'timestamp. Use a CFR '
                                                                                      'source with complete '
                                                                                      'timestamps.',
 'MVC: Kein unterstützter MPEG-Transportstrom.': 'MVC: unsupported MPEG transport stream.',
 'MVC: Keine eindeutige AVC/MVC-Spurkombination.': 'MVC: no unambiguous AVC/MVC track combination.',
 'MVC: Komprimierte Eingabespuren vorbereiten': 'MVC: prepare compressed input tracks',
 'MVC: Letztes PES-Paket ist abgeschnitten.': 'MVC: last PES packet is truncated.',
 'MVC: Mehr als zwei Millionen Bilder sind noch nicht freigegeben.': 'MVC: more than two million frames are '
                                                                     'not yet supported.',
 'MVC: PES-Paket ist unvollständig.': 'MVC: incomplete PES packet.',
 'MVC: Paketbildzeiten und dekodierte Bildzahl stimmen nicht überein.': 'MVC: packet timestamps and decoded '
                                                                        'frame count do not match.',
 'MVC: Paketlücke im Transportstrom.': 'MVC: packet gap in transport stream.',
 'MVC: Transportstrom ist abgeschnitten.': 'MVC: truncated transport stream.',
 'MVC: Transportstrom-Synchronisation verloren.': 'MVC: transport-stream synchronisation lost.',
 'MVC: Ungültige PES-Länge.': 'MVC: invalid PES length.',
 'MVC: Ungültiger PES-Kopf.': 'MVC: invalid PES header.',
 'MVC: Ungültiger Transportstrom-Paketkopf.': 'MVC: invalid transport-stream packet header.',
 'MVC: Ungültiges Adaptationsfeld.': 'MVC: invalid adaptation field.',
 'MVC: Ursprüngliche Bildzeiten prüfen': 'MVC: check original frame timing',
 'MVC: Verlässliche Quellframerate fehlt.': 'MVC: reliable source frame rate is missing.',
 'MVC: Vollständige Basis- und Zusatzansicht fehlen.': 'MVC: complete base and dependent half-images are '
                                                       'missing.',
 'MVC: Vollständiges Basis- und Zusatzhalbbild fehlen.': 'MVC: complete base and dependent half-images are '
                                                         'missing.',
 'Manuell gewähltes Layout/L/R weicht vom Dateinamen ab.': 'Manually selected layout/L/R differs from the '
                                                           'filename.',
 'Manuelle Quellinterpretation ersetzt abweichende Stereo-Metadaten.': 'Manual source interpretation '
                                                                       'overrides conflicting stereo '
                                                                       'metadata.',
 'Manuelle Quellinterpretation verwendet.': 'Manual source interpretation used.',
 'Mehrere Videospuren: Getrennte L/R-Spuren sind in dieser Version noch nicht freigegeben.': 'Multiple video '
                                                                                             'tracks: '
                                                                                             'separate L/R '
                                                                                             'tracks are not '
                                                                                             'yet supported '
                                                                                             'in this '
                                                                                             'version.',
 'Mehrere unabhängige Videospuren oder keine gültige Videoauflösung.': 'Multiple independent video tracks or '
                                                                       'no valid video resolution.',
 'Mehrere unabhängige Videospuren sind noch nicht freigegeben.': 'Multiple independent video tracks are not '
                                                                 'yet supported.',
 'Metadaten übernehmen': 'Copy metadata',
 'Modell: {0}': 'Model: {0}',
 'Mono / 2D': 'Mono / 2D',
 'Mono · linkes Halbbild': 'Mono · left half-image',
 'Mono/2D ist als Quelle für ‚Nur Framerate ändern‘ verfügbar; andere Ziele benötigen SBS/OU.': 'Mono/2D is '
                                                                                                'available '
                                                                                                'as a source '
                                                                                                'for ‘Change '
                                                                                                'frame rate '
                                                                                                'only’; '
                                                                                                'other '
                                                                                                'targets '
                                                                                                'require '
                                                                                                'SBS/OU.',
 'Name der Voreinstellung': 'Preset name',
 'Name der Voreinstellung:': 'Preset name:',
 'Name der Voreinstellung: 1 bis 80 Zeichen, ohne Steuerzeichen.': 'Preset name: 1 to 80 characters, without '
                                                                   'control characters.',
 'Nicht mehr gestartet': 'Not started',
 'Nicht unterstütztes Bildformat: ': 'Unsupported image format: ',
 'Nicht unterstütztes Blu-ray-PlayItem.': 'Unsupported Blu-ray PlayItem.',
 'Nichtquadratische Pixel (SAR {0}): Quelllayout und Stereo-Metadaten prüfen.': 'Non-square pixels (SAR '
                                                                                '{0}): check source layout '
                                                                                'and stereo metadata.',
 'Noch keine technischen Meldungen.': 'No technical messages yet.',
 'Noch nicht geprüft': 'Not yet checked',
 'Nur Framerate ändern': 'Change frame rate only',
 'Nur Framerate ändern erhält die Halbbildreihenfolge. L/R tauschen ausschalten.': 'Change frame rate only '
                                                                                   'retains half-image '
                                                                                   'order. Disable Swap L/R.',
 'Nur Framerate ändern erhält gepackte SBS/OU-Quellen. Für MVC/MV-HEVC zuerst das gewünschte Ausgabe-Layout wählen.': 'Change '
                                                                                                                      'frame '
                                                                                                                      'rate '
                                                                                                                      'only '
                                                                                                                      'retains '
                                                                                                                      'packed '
                                                                                                                      'SBS/OU '
                                                                                                                      'sources. '
                                                                                                                      'For '
                                                                                                                      'MVC/MV-HEVC, '
                                                                                                                      'select '
                                                                                                                      'the '
                                                                                                                      'required '
                                                                                                                      'output '
                                                                                                                      'layout '
                                                                                                                      'first.',
 'Nur einzelne Bilder oder MPO mit genau zwei Halbbildern werden unterstützt.': 'Only single images or MPO '
                                                                                'files with exactly two '
                                                                                'half-images are supported.',
 'Ohne Ton': 'No audio',
 'Ordner durchsuchen': 'Scan folder',
 'Ordner hinzufügen': 'Add folder',
 'Original beibehalten': 'Keep original',
 'Originalton wird kopiert. Blu-ray-LPCM wird in MKV verlustfrei als FLAC gespeichert.': 'Original audio is '
                                                                                         'copied. Blu-ray '
                                                                                         'LPCM is saved '
                                                                                         'losslessly as FLAC '
                                                                                         'in MKV.',
 'Player-Kürzel (Kodi/Bino)': 'Player flags (Kodi/Bino)',
 'Protokoll': 'Log',
 'Prüfen!': 'Check!',
 'Prüfung': 'Checking',
 'Prüfung abgebrochen': 'Verification cancelled',
 'Prüfung bestanden; bereit für Start.': 'Verification passed; ready to start.',
 'Qualität (CRF)': 'Quality (CRF)',
 'Qualität · 8 Bit / 4:4:4': 'Quality · 8-bit / 4:4:4',
 'Qualitätssteuerung': 'Rate control',
 'Quelle': 'Source',
 'Quelle beibehalten': 'Keep source',
 'Quelle liegt nicht unter der gespeicherten Ordnerwurzel.': 'Source is not under the saved root folder.',
 'Quelle seit der Prüfung geändert. Erneut prüfen.': 'Source changed since verification. Check again.',
 'Quelllayout': 'Source layout',
 'R/L-Quelle: Für unveränderte Halbbildreihenfolge MKV wählen; MP4-st3d unterstützt diese Umkehrung nicht.': 'R/L '
                                                                                                             'source: '
                                                                                                             'select '
                                                                                                             'MKV '
                                                                                                             'to '
                                                                                                             'retain '
                                                                                                             'half-image '
                                                                                                             'order; '
                                                                                                             'MP4-st3d '
                                                                                                             'does '
                                                                                                             'not '
                                                                                                             'support '
                                                                                                             'this '
                                                                                                             'reversal.',
 'Rechtes Halbbild': 'Right half-image',
 'Rechtes Halbbild zuerst': 'Right half-image first',
 'Restzeit: ca. {0}': 'Remaining: approx. {0}',
 'Restzeit: {0}': 'Remaining: {0}',
 'Restzeit: —': 'Remaining: —',
 'Schließen': 'Close',
 'Speichern': 'Save',
 'Speichern unter …': 'Save as …',
 'Sprache / Language': 'Sprache / Language',
 'Spur {0}: {1} → {2} · {3} Kanäle': 'Track {0}: {1} → {2} · {3} channels',
 'Spurnummern · z. B. 1, 3 oder 2-4': 'Track numbers · e.g. 1, 3 or 2-4',
 'Standardeinstellungen': 'Default settings',
 'Standardeinstellungen für neue Dateien wiederhergestellt. Bestehende Jobs behalten ihre Einstellungen.': 'Default '
                                                                                                           'settings '
                                                                                                           'for '
                                                                                                           'new '
                                                                                                           'files '
                                                                                                           'restored. '
                                                                                                           'Existing '
                                                                                                           'jobs '
                                                                                                           'retain '
                                                                                                           'their '
                                                                                                           'settings.',
 'Start': 'Start',
 'Stereo-Kennzeichnung an einer als Mono/2D gewählten Quelle; Quelllayout prüfen.': 'Stereo metadata on a '
                                                                                    'source selected as '
                                                                                    'Mono/2D; check source '
                                                                                    'layout.',
 'Stereo-Metadaten: Gestauchte Achse wird je Halbbild rekonstruiert.': 'Stereo metadata: the compressed axis '
                                                                       'is reconstructed for each '
                                                                       'half-image.',
 'Stereo-Quelllayout nicht eindeutig. Layout auswählen: ': 'Stereo source layout is ambiguous. Select a '
                                                           'layout: ',
 'Technische Prüfung': 'Technical verification',
 'Testen': 'Test',
 'Testen: ': 'Check: ',
 'Testen: Datei {0} von {1} · {2}': 'Test: file {0} of {1} · {2}',
 'Testen: Mitgelieferte Videowerkzeuge prüfen': 'Test: check bundled video tools',
 'Ton passt nicht zum MP4-Ausgabeformat (': 'Audio is incompatible with MP4 output (',
 'Ton passt nicht zum MP4-Ausgabeformat ({0}). Unter Erweitert AAC wählen oder MKV verwenden.': 'Audio is '
                                                                                                'incompatible '
                                                                                                'with MP4 '
                                                                                                'output '
                                                                                                '({0}). '
                                                                                                'Select AAC '
                                                                                                'under '
                                                                                                'Advanced or '
                                                                                                'use MKV.',
 'Ton: ': 'Audio: ',
 'Ton: Ohne Ton': 'Audio: no audio',
 'Ton: Quelle enthält keinen Ton': 'Audio: source has no audio',
 'Ton: Verlässliche Kanalzahl von 1 bis 8 erforderlich.': 'Audio: a reliable channel count from 1 to 8 is '
                                                          'required.',
 'Tonkanäle': 'Audio channels',
 'Tonoptionen …': 'Audio options …',
 'Tonspuren': 'Audio tracks',
 'Tonspuren: Aufsteigende Nummern von 1 bis 1000 verwenden.': 'Audio tracks: use ascending numbers from 1 to '
                                                              '1000.',
 'Tonspuren: Gewählte Spur fehlt; die Quelle enthält {0} Audiospur(en).': 'Audio tracks: selected track is '
                                                                          'missing; the source contains {0} '
                                                                          'audio track(s).',
 'Tonspuren: Nummern wie 1, 3 oder 2-4 eingeben.': 'Audio tracks: enter numbers such as 1, 3 or 2-4.',
 'TransCora · Log': 'TransCora · Log',
 'TransCora-Jobliste': 'TransCora job list',
 'TransCora: Laufprotokoll': 'TransCora: run log',
 'Unbekannte Einstellungen in der Jobliste.': 'Unknown settings in the job list.',
 'Unbekanntes Anaglyphenverfahren in der Jobliste.': 'Unknown anaglyph method in the job list.',
 'Unbekanntes Joblistenformat.': 'Unknown job-list format.',
 'Unbekanntes Voreinstellungsformat.': 'Unknown preset format.',
 'Unerwarteter Ausgabecodec.': 'Unexpected output codec.',
 'Ungültige Bild-, Metadaten- oder Anaglypheneinstellung.': 'Invalid image, metadata or anaglyph setting.',
 'Ungültige Bildeinstellung: ': 'Invalid image setting: ',
 'Ungültige Bildeinstellungen.': 'Invalid image settings.',
 'Ungültige Blu-ray-Playlist.': 'Invalid Blu-ray playlist.',
 'Ungültige Eingabe.': 'Invalid input.',
 'Ungültige Einstellung: {0}.': 'Invalid setting: {0}.',
 'Ungültige Farbeinstellung in der Jobliste.': 'Invalid colour setting in the job list.',
 'Ungültige JPEG-Segmentlänge.': 'Invalid JPEG segment length.',
 'Ungültige Jobeinstellungen.': 'Invalid job settings.',
 'Ungültige L/R-Einstellung.': 'Invalid L/R setting.',
 'Ungültige MP4-Box-Größe.': 'Invalid MP4 box size.',
 'Ungültige MP4-Box-Verschachtelung.': 'Invalid MP4 box nesting.',
 'Ungültige MP4-st3d-Kennzeichnung.': 'Invalid MP4-st3d metadata.',
 'Ungültige Ordnerwurzel.': 'Invalid root folder.',
 'Ungültige Toneinstellung: ': 'Invalid audio setting: ',
 'Ungültige Voreinstellungen.': 'Invalid presets.',
 'Ungültige Zielbildrate.': 'Invalid target frame rate.',
 'Ungültige oder zu große Jobliste.': 'Invalid or oversized job list.',
 'Ungültiger Ausgabeordner.': 'Invalid output folder.',
 'Ungültiger Bildeintrag.': 'Invalid image entry.',
 'Ungültiger Bildordner.': 'Invalid image folder.',
 'Ungültiger Dateieintrag.': 'Invalid file entry.',
 'Ungültiger JPEG-Marker im MPO.': 'Invalid JPEG marker in MPO.',
 'Ungültiges Anaglyphenverfahren.': 'Invalid anaglyph method.',
 'Unterordner mitverarbeiten': 'Include subfolders',
 'Unterordner mitverarbeiten und Struktur beibehalten': 'Include subfolders and retain folder structure',
 'Untertitel werden nicht übernommen.': 'Subtitles are not copied.',
 'Unvollständige MP4-Box-Größe.': 'Incomplete MP4 box size.',
 'Unvollständige MP4-Box.': 'Incomplete MP4 box.',
 'Unvollständiges L/R-Paar: ': 'Incomplete L/R pair: ',
 'Verarbeitung': 'Processing',
 'Vergangene Zeit: {0}': 'Elapsed: {0}',
 'Verlustfreies Teilen benötigt eine MPO-Datei: ': 'Lossless splitting requires an MPO file: ',
 'Video und Tonspuren analysieren': 'Analyse video and audio tracks',
 'Videocodec': 'Video codec',
 'Videodauer wird ermittelt …': 'Determining video duration …',
 'Videoordner hinzufügen': 'Add video folder',
 'Videos': 'Videos',
 'Videos hinzufügen': 'Add videos',
 'Vollbereich für RGB/JPEG-YUV': 'Full range for RGB/JPEG-YUV',
 'Voreinstellung geladen: {0}': 'Preset loaded: {0}',
 'Voreinstellung geladen; erneut prüfen.': 'Preset loaded; check again.',
 'Voreinstellung gelöscht: ': 'Preset deleted: ',
 'Voreinstellung gelöscht: {0}': 'Preset deleted: {0}',
 'Voreinstellung gespeichert: {0}': 'Preset saved: {0}',
 'Voreinstellung geändert.': 'Preset changed.',
 'Voreinstellung speichern': 'Save preset',
 'Voreinstellungen': 'Presets',
 'Voreinstellungen: {0}': 'Presets: {0}',
 'Voreinstellungsdatei ist zu groß.': 'Preset file is too large.',
 'Wartet': 'Queued',
 'WebP (verlustfrei)': 'WebP (lossless)',
 'Widersprüchliche Stereo-Kürzel im Dateinamen.': 'Conflicting stereo flags in the filename.',
 'Widersprüchliche Stereo-Kürzel im Dateinamen. Namen beziehungsweise Quelllayout klären.': 'Conflicting '
                                                                                            'stereo flags in '
                                                                                            'the filename. '
                                                                                            'Resolve the '
                                                                                            'name or source '
                                                                                            'layout.',
 'Wählen': 'Choose',
 'Zeitposition': 'Time position',
 'Zeitstelle liegt außerhalb des Videos oder ist ungültig.': 'Time position is outside the video or invalid.',
 'Zeitstelle liegt außerhalb des Videos.': 'Time position is outside the video.',
 'Ziel': 'Target',
 'Zielbildrate (fps) · Zahl oder Bruch': 'Target frame rate (fps) · Number or fraction',
 'Zielbildrate: 1 bis 240 fps, als Zahl oder Bruch (z. B. 24000/1001).': 'Target frame rate: 1 to 240 fps, '
                                                                         'as a number or fraction (e.g. '
                                                                         '24000/1001).',
 'Zielbitrate (Durchschnitt)': 'Target bitrate (average)',
 'Zum Speichern Dateien mit gleichen Einstellungen auswählen.': 'Select files with matching settings to save '
                                                                'a preset.',
 'Zwei vollständige Multiview-Halbbilder werden dekodiert.': 'Two complete multiview half-images will be '
                                                             'decoded.',
 'erkannt am Dateizusatz in {0}': 'detected from the filename suffix in {0}',
 'erkannt an Stereo-Metadaten und Halbbildgeometrie': 'detected from stereo metadata and half-image geometry',
 'manuell gewählt': 'selected manually',
 '{0} Laufprotokolle gelöscht.': '{0} run logs deleted.',
 '{0} Listeneinträge entfernt; Quelldateien bleiben erhalten.': '{0} list entries removed; source files are '
                                                                'retained.',
 '{0} erfolgreich · {1} Fehler · {2} blockiert · {3} abgebrochen. Log: {4}': '{0} successful · {1} errors · '
                                                                             '{2} blocked · {3} cancelled. '
                                                                             'Log: {4}',
 '{0} hinzugefügt · {1} Dateien insgesamt.': '{0} added · {1} files in total.',
 '{0} · Zwei vollständige Halbbilder aus dem Bitstream': '{0} · Two complete half-images from the bitstream',
 '{0} → 23,976 fps: Ganze Stereobildpaare werden ausgelassen oder wiederholt. Laufzeit und Ton bleiben erhalten; Bewegungen können ungleichmäßiger werden. Keine Bewegungsinterpolation; Video wird nur einmal kodiert.': '{0} '
                                                                                                                                                                                                                          '→ '
                                                                                                                                                                                                                          '23.976 '
                                                                                                                                                                                                                          'fps: '
                                                                                                                                                                                                                          'complete '
                                                                                                                                                                                                                          'stereo '
                                                                                                                                                                                                                          'image '
                                                                                                                                                                                                                          'pairs '
                                                                                                                                                                                                                          'are '
                                                                                                                                                                                                                          'dropped '
                                                                                                                                                                                                                          'or '
                                                                                                                                                                                                                          'repeated. '
                                                                                                                                                                                                                          'Duration '
                                                                                                                                                                                                                          'and '
                                                                                                                                                                                                                          'audio '
                                                                                                                                                                                                                          'are '
                                                                                                                                                                                                                          'retained; '
                                                                                                                                                                                                                          'motion '
                                                                                                                                                                                                                          'may '
                                                                                                                                                                                                                          'become '
                                                                                                                                                                                                                          'less '
                                                                                                                                                                                                                          'even. '
                                                                                                                                                                                                                          'No '
                                                                                                                                                                                                                          'motion '
                                                                                                                                                                                                                          'interpolation; '
                                                                                                                                                                                                                          'video '
                                                                                                                                                                                                                          'is '
                                                                                                                                                                                                                          'encoded '
                                                                                                                                                                                                                          'only '
                                                                                                                                                                                                                          'once.',
 'üblicher begrenzter YUV-Videobereich; Quelle bei abweichendem Kontrast prüfen': 'standard limited YUV '
                                                                                  'video range; check '
                                                                                  'sources with different '
                                                                                  'contrast'}

EN.update({
    'Dubois LCD (Sanders/McAllister) + rot': 'Dubois LCD (Sanders/McAllister) + red',
    'Dubois grün/magenta (GM)': 'Dubois green/magenta (GM)',
    'Dubois amber/blau (YB)': 'Dubois amber/blue (YB)',
    'Kreuzblick · Full-SBS R/L': 'Cross-view · Full-SBS R/L',
    'Kreuzblick-Ausgabe benötigt MKV für die eindeutige R/L-Kennzeichnung.': 'Cross-view output requires MKV for unambiguous R/L metadata.',
    'Kreuzblick: Full-SBS mit rechtem Halbbild zuerst. MKV erhält die passende R/L-Kennzeichnung.': 'Cross-view: Full-SBS with the right half-image first. MKV receives matching R/L metadata.',
    'CIELAB fehlt. TransCora.zip vollständig entpacken.': 'CIELAB is missing. Extract TransCora.zip completely.',
    'CIELAB-Werkzeug stimmt nicht mit dem geprüften Build überein.': 'CIELAB tool does not match the verified build.',
    'CIELAB: Halbbilder iterativ berechnen': 'CIELAB: calculate half-images iteratively',
    'CIELAB liefert unerwartete Bildmaße oder ein falsches Farbformat.': 'CIELAB returned unexpected image dimensions or colour format.',
    'Tonoptionen': 'Audio options', 'Bildeinstellungen': 'Image settings',
    'Größe': 'Size', '2048 lange Seite': '2048 long edge', 'Benutzerdefiniert': 'Custom',
    'lange Seite': 'long edge', 'kurze Seite': 'short edge',
    'Eine positive Pixelzahl bis 20000 und lange/kurze Seite wählen.': 'Choose a positive pixel count up to 20000 and a long/short edge.',
    'MPO-Teilung erhält die komprimierten Bilddaten unverändert.': 'MPO splitting preserves the compressed image data unchanged.',
    'Ausgabe: {0} × {1} Pixel je Datei': 'Output: {0} × {1} pixels per file',
    'Qualität': 'Quality', 'Hohe Farbtiefe': 'High colour depth', 'Kompatibel': 'Compatible',
    '3D-Kennzeichnung: {0} · {1} · {2}': '3D metadata: {0} · {1} · {2}',
})
for source, target in list(EN.items()):
    if source.endswith('…'):
        EN[source] = target.removesuffix(' .')+' …' if target.endswith(' .') else target
    if source.startswith('Erweitert') and source != 'Erweitert':
        EN[source] = source.replace('Erweitert', 'Advanced')
    if source.endswith('.') and target.endswith('.'):
        EN.setdefault(source[:-1], target[:-1])
    if source != source.strip():
        EN.setdefault(source.strip(), target.strip())

# Long messages win over prefix fragments. Captures retain filenames and values.
PATTERNS = []
for source, target in EN.items():
    parts = re.split(r"(\{\d+\})", source)
    if len(parts) > 1:
        pattern = ''.join('(.*?)' if re.fullmatch(r"\{\d+\}", part) else re.escape(part) for part in parts)
        PATTERNS.append((re.compile('^'+pattern+'$', re.S), target))
PATTERNS.sort(key=lambda item: len(item[0].pattern), reverse=True)

def translate(text, language='de'):
    text = str(text)
    if language != 'en' or not text:
        return text
    if text in EN:
        return EN[text]
    if '\n' in text:
        return '\n'.join(translate(line, language) for line in text.split('\n'))
    if re.match(r'^(?:[A-Za-z]:[\\/]|\\\\|/)', text):
        return text
    for pattern, target in PATTERNS:
        match = pattern.fullmatch(text)
        if match:
            return target.format(*match.groups())
    for source, target in EN.items():
        if source.endswith(': ') and text.startswith(source):
            return target + text[len(source):]
    if '. ' in text:
        return '. '.join(translate(part, language) for part in text.split('. '))
    if ' · ' in text:
        return ' · '.join(translate(part, language) for part in text.split(' · '))
    if text != text.strip() and text.strip() in EN:
        start = len(text)-len(text.lstrip()); end = len(text.rstrip())
        return text[:start]+EN[text.strip()]+text[end:]
    return text
