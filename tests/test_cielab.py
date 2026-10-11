import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
from PIL import Image, ImageChops
from transcora.core.cielab import executable
from transcora.core.images import ImageJob, ImageOptions, plans, execute_image
from transcora.core.toolchain import Toolchain
from transcora.core.engine import Cancelled


class CielabTests(unittest.TestCase):
    def test_native_matches_recorded_anaglyphbatch_with_same_image_pipeline(self):
        try: executable()
        except ValueError: self.skipTest('Build native CIELAB first')
        fixture = json.loads((Path(__file__).parent/'fixtures/cielab_reference.json').read_text(encoding='utf-8'))
        with tempfile.TemporaryDirectory() as value:
            root = Path(value); cancel = threading.Event(); tools = Toolchain.find()
            for name in ('random', 'gray', 'colors', 'demo'):
                images = {}
                for side, item in fixture['cases'][name].items():
                    data = base64.b64decode(item['png_base64'])
                    self.assertEqual(hashlib.sha256(data).hexdigest(), item['sha256'])
                    with Image.open(io.BytesIO(data)) as image: images[side] = image.convert('RGB')
                left, right = images['left'], images['right']
                packed = Image.new('RGB', (left.width*2, left.height)); packed.paste(left); packed.paste(right, (left.width, 0))
                source = root/(name+'_full_sbs.png'); packed.save(source)
                options = ImageOptions(target='anaglyph', method='cielab', format='png', metadata=False)
                plan = plans([ImageJob(source, options)], root/'out', cancel)[0]
                self.assertEqual(plan.outputs[0].name, name+'_cielab.png')
                execute_image(tools, plan, cancel, lambda *a: None, root/'log')
                with Image.open(plan.outputs[0]) as actual:
                    difference = ImageChops.difference(actual.convert('RGB'), images['reference'])
                    self.assertLessEqual(max(maximum for minimum, maximum in difference.getextrema()), 2, name)
                    self.assertTrue(actual.info['icc_profile'])
            options.size_mode = 'custom'; options.size_edge = 'short'; options.size_pixels = 6; options.format = 'jpeg'; options.metadata = True
            resized = plans([ImageJob(source, options)], root/'out', cancel)[0]
            execute_image(tools, resized, cancel, lambda *a: None, root/'log')
            from PIL.JpegImagePlugin import get_sampling
            with Image.open(resized.outputs[0]) as actual:
                self.assertEqual(min(actual.size), 6)
                self.assertEqual(get_sampling(actual), 0)
                self.assertTrue(actual.info['icc_profile'])
            cancel.set()
            with self.assertRaises(Cancelled): execute_image(tools, resized, cancel, lambda *a: None, root/'log')
