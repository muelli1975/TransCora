import re
import unittest
from transcora.i18n import EN, translate
from transcora.core.images import ImageOptions, resized_dimensions


class LocalisationTests(unittest.TestCase):
    def test_message_values_and_paths_remain_user_data(self):
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
