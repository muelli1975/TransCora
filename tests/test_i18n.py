import re
import unittest
from transcora.i18n import EN, translate
from transcora.core.images import ImageOptions, resized_dimensions


class LocalisationTests(unittest.TestCase):
    def test_batch_status_and_audio_labels_are_english_without_translating_metadata(self):
        from transcora.core.audio import summary
        from transcora.core.model import Options
        self.assertEqual(translate('Test abgeschlossen: 5 bereit · 0 blockiert.','en'),
                         'Check finished: 5 ready · 0 blocked.')
        self.assertEqual(translate('2/5 · Restzeit etwa 31 s','en'),
                         '2/5 · Remaining approx. 31 s')
        info={'streams':[{'index':1,'codec_type':'audio','codec_name':'aac','channels':2,
                          'tags':{'language':'und','title':'Fertig · Wartet; Original'}},
                         {'index':2,'codec_type':'audio','codec_name':'aac','channels':6,
                          'tags':{'language':'deu','title':'Datei'}}]}
        result=summary(info,Options(target='bd3d',container='iso'),lambda s:translate(s,'en'))
        self.assertEqual(result,'Audio: Track 1: AAC → PCM_BLURAY · 2 channels · und · Fertig · Wartet; Original; Track 2: AAC → PCM_BLURAY · 6 channels · deu · Datei')
        self.assertEqual(translate(result,'en'),result)

    def test_bd_modes_and_file_batch_eta_have_english_labels(self):
        from transcora.core.bd3d import prepare
        from transcora.core.model import BD_MODES
        video=dict(index=0,width=128,height=64,r_frame_rate='25/1',avg_frame_rate='25/1',
                   pix_fmt='yuv420p',color_space='bt709',color_primaries='bt709',
                   color_transfer='bt709',color_range='tv')
        for mode in BD_MODES:
            for message in prepare(video,'full_sbs',mode=mode).warnings:
                result=translate(message,'en')
                self.assertIn('Duration and audio are retained',result)
                self.assertNotIn('Ganze',result)
                self.assertNotIn('59,94',result)
        self.assertEqual(translate('Restzeit: Datei ca. 01:10 · Stapel ca. 02:20','en'),
                         'Remaining: file approx. 01:10 · batch approx. 02:20')
        self.assertEqual(translate('Restzeit: Datei ca. 01:10 · Stapel —','en'),
                         'Remaining: file approx. 01:10 · batch —')

    def test_message_values_and_paths_remain_user_data(self):
        self.assertEqual(translate('1080p · 23,976 fps · AVC/MVC · Hohe Qualität.', 'en'),
                         '1080p · 23.976 fps · AVC/MVC · High quality.')
        self.assertEqual(translate('BD-3D: Nicht aufsteigende Bildzeit bei Bild 12: 7.040000 s nach 7.080000 s.', 'en'),
                         'BD-3D: non-increasing timestamp at frame 12: 7.040000 s after 7.080000 s.')
        self.assertEqual(translate('Dubois LCD (Sanders/McAllister) + rot', 'en'), 'Dubois LCD (Sanders/McAllister) + red')
        self.assertEqual(translate('Dubois grün/magenta (GM)', 'en'), 'Dubois green/magenta (GM)')
        self.assertEqual(translate('Dubois amber/blau (YB)', 'en'), 'Dubois amber/blue (YB)')
        self.assertEqual(translate('Voreinstellung geladen: Fertig', 'en'), 'Preset loaded: Fertig')
        self.assertEqual(translate(r'C:\Bilder\Wartet_full_sbs.png', 'en'), r'C:\Bilder\Wartet_full_sbs.png')
        self.assertEqual(translate('Einstellungen für 3 ausgewählte Datei(en). Leere Auswahlfelder bedeuten gemischte Werte.', 'en'),
                         'Settings for 3 selected file(s). Empty selection fields indicate mixed values.')
        self.assertEqual(translate('Ton passt nicht zum MP4-Ausgabeformat (pcm_bluray). Unter Erweitert AAC wählen oder MKV verwenden.', 'en'),
                         'Audio is incompatible with MP4 output (pcm_bluray). Select AAC under Advanced or use MKV.')
        self.assertIn('LPCM at 48 kHz', translate('BD-3D: LPCM mit 48 kHz und 24 Bit.', 'en'))
        for source, target in EN.items():
            self.assertEqual(set(re.findall(r'\{\d+\}', source)), set(re.findall(r'\{\d+\}', target)), source)

    def test_size_presets_match_existing_app_and_legacy_size_is_retained(self):
        source = (4000, 3000)
        for mode, expected in [('original', source), ('1080p', (1440, 1080)),
                               ('2160p', (2880, 2160)), ('2048', (2048, 1536))]:
            self.assertEqual(resized_dimensions(source, ImageOptions(size_mode=mode)), expected)
        self.assertEqual(resized_dimensions(source, ImageOptions(size_mode='custom', size_edge='short', size_pixels=600)), (800, 600))
        legacy = ImageOptions.from_dict({'long_edge': 1000})
        self.assertEqual(legacy.size_mode, 'custom')
        self.assertEqual(resized_dimensions(source, legacy), (1000, 750))
        with self.assertRaises(ValueError): ImageOptions.from_dict({'size_pixels': 0})
        with self.assertRaises(ValueError): ImageOptions.from_dict({'task': 'pairs'})
