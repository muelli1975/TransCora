"""Reader selection is independent of codec availability and storage order."""
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import unittest

spec = importlib.util.spec_from_file_location('transcora_heif_reader',
    Path(__file__).resolve().parents[1]/'native/heif/read_heif.py')
reader = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reader)


class Container(list):
    primary_index = 0


class HeifReaderTests(unittest.TestCase):
    def image(self, **info):
        return SimpleNamespace(info=info, size=(64, 64), mode='RGB')

    def test_tagged_group_order_wins_over_storage_order_and_other_images(self):
        images = Container([self.image(entity_groups=[
            {'type': 'altr', 'entities': [10, 11], 'images': [0, 1]},
            {'type': 'ster', 'entities': [12, 10], 'images': [2, 0]}]),
            self.image(aux={'gainmap': [11]}), self.image()])
        halves, entities = reader.selected_images(images)
        self.assertEqual(halves, [images[2], images[0]])
        self.assertEqual(entities, [12, 10])

    def test_untagged_multiple_images_do_not_become_a_stereo_pair(self):
        images = Container([self.image(aux={'depth': [11]}), self.image()])
        self.assertEqual(reader.selected_images(images), ([images[0]], []))

    def test_ambiguous_or_broken_stereo_groups_are_not_silently_replaced(self):
        for groups in ([{'type': 'ster', 'entities': [10, 11], 'images': [0, 9]}],
                       [{'type': 'ster', 'entities': [10, 11], 'images': [0, 1]},
                        {'type': 'ster', 'entities': [10, 12], 'images': [0, 2]}]):
            images = Container([self.image(entity_groups=groups), self.image(), self.image()])
            with self.assertRaises(ValueError):
                reader.selected_images(images)

    def test_sdr_light_level_metadata_is_not_misclassified_as_hdr(self):
        image = self.image(content_light_level={'max_content_light_level': 203},
                           nclx_profile={'transfer_characteristics': 13})
        self.assertFalse(reader.describe([image], [])['stereo'])
        for transfer in (16, 18):
            image.info['nclx_profile']['transfer_characteristics'] = transfer
            with self.assertRaisesRegex(ValueError, 'HDR'):
                reader.describe([image], [])
