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
    def test_actual_heif_import_exports_the_tagged_half_images_and_respects_swap(self):
        import importlib.util
        import tempfile
        import threading
        from PIL import Image
        from transcora.core.model import app_root
        from transcora.core.images import ImageJob, ImageOptions, plans, execute_image
        from transcora.core.toolchain import Toolchain
        binaries = [app_root()/'tools/heif/TransCora-HEIF.exe', app_root()/'tools/heif/TransCora-HEIF']
        if not any(path.is_file() for path in binaries) and not importlib.util.find_spec('pillow_heif'):
            self.skipTest('Separate HEIF development reader is unavailable')
        tools = Toolchain.find()
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            for filename, blue_left in [('stereo_pair.heic', False), ('entity_groups.heic', True)]:
                source = Path(__file__).parent/'fixtures/heif'/filename
                for swap in (False, True):
                    plan = plans([ImageJob(source, ImageOptions(target='split', format='png', metadata=False, swap=swap))],
                                 folder, threading.Event())[0]
                    self.assertEqual(plan.layout, 'full_sbs')
                    self.assertEqual(plan.size, (128, 64))
                    self.assertEqual(plan.warnings, ('HEIF: Halbbilder anhand der Stereo-Gruppe links/rechts zugeordnet.',))
                    execute_image(tools, plan, threading.Event(), lambda *a: None, folder/'heif.log')
                    for index, output in enumerate(plan.outputs):
                        with Image.open(output) as half:
                            self.assertEqual(half.size, (64, 64))
                            pixel = half.convert('RGB').getpixel((32, 32))
                            blue = blue_left ^ swap ^ bool(index)
                            self.assertGreater(pixel[2 if blue else 0], 240)
                            self.assertLess(pixel[0 if blue else 2], 10)
                with self.assertRaisesRegex(ValueError, 'MPO'):
                    plans([ImageJob(source, ImageOptions(task='mpo'))], folder, threading.Event())

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
