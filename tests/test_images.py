from dataclasses import replace
from pathlib import Path
import hashlib
import json
import os
import tempfile
import threading
import unittest
from PIL import Image
from transcora.core.images import (ImageJob, ImageOptions, plans, execute_image, mpo_jpegs,
                                   save_images, load_images, exiftool)
from transcora.core.engine import capture
from transcora.core.toolchain import Toolchain


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.folder = Path(self.temp.name).resolve()
        self.tools = Toolchain.find(); self.cancel = threading.Event()
        left = Image.new('RGB', (128, 72), (210, 30, 10)); right = Image.new('RGB', left.size, (10, 50, 210))
        left.paste((255, 255, 255), (20, 20, 60, 24)); right.paste((255, 255, 255), (15, 20, 55, 24))
        self.left, self.right = left, right
        self.source = self.folder/'test_full_sbs.png'
        packed = Image.new('RGB', (256, 72)); packed.paste(left); packed.paste(right, (128, 0)); packed.save(self.source)

    def tearDown(self): self.temp.cleanup()

    def run_job(self, source, options):
        plan = plans([ImageJob(source, options)], self.folder/'out', self.cancel)[0]
        execute_image(self.tools, plan, self.cancel, lambda *a: None, self.folder/'log.jsonl')
        return plan

    def test_layout_dimensions_and_left_right_order_for_real_outputs(self):
        for target, size in [('full_sbs', (256, 72)), ('full_ou', (128, 144)), ('half_sbs', (128, 72)),
                             ('half_ou', (128, 72)), ('left', (128, 72)), ('right', (128, 72)), ('split', (128, 72))]:
            plan = self.run_job(self.source, ImageOptions(target=target, format='png', metadata=False))
            for output in plan.outputs:
                with Image.open(output) as image: self.assertEqual(image.size, size)
            if target == 'split':
                with Image.open(plan.outputs[0]) as left, Image.open(plan.outputs[1]) as right:
                    self.assertEqual(left.convert('RGB').tobytes(), self.left.tobytes())
                    self.assertEqual(right.convert('RGB').tobytes(), self.right.tobytes())
        swapped = self.run_job(self.source, ImageOptions(target='left', swap=True, format='png', metadata=False))
        with Image.open(swapped.outputs[0]) as image: self.assertEqual(image.convert('RGB').tobytes(), self.right.tobytes())
        for method in __import__('transcora.core.engine', fromlist=['methods']).methods():
            plan = self.run_job(self.source, ImageOptions(target='anaglyph', method=method, format='png', metadata=False))
            with Image.open(plan.outputs[0]) as image: self.assertEqual(image.size, (128, 72))

    def test_mpo_split_preserves_jpeg_pixels_quantization_and_orientation(self):
        source = self.folder/'stereo.mpo'; exif = Image.Exif(); exif[274] = 6
        self.left.save(source, format='MPO', save_all=True, append_images=[self.right], quality=90, exif=exif)
        originals = mpo_jpegs(source)
        plan = self.run_job(source, ImageOptions(task='mpo', metadata=False))
        self.assertEqual(len(plan.outputs), 2)
        for expected, output in zip(originals, plan.outputs):
            self.assertEqual(expected, output.read_bytes())
            with Image.open(output) as image: self.assertEqual(image.format, 'JPEG'); self.assertNotEqual(image.format, 'MPO')
        tagged = self.run_job(source, ImageOptions(task='mpo', metadata=True))
        for expected, output in zip(originals, tagged.outputs):
            actual = output.read_bytes()
            self.assertEqual(actual[actual.index(b'\xff\xda'):], expected[expected.index(b'\xff\xda'):])
            with Image.open(output) as image: self.assertEqual(image.getexif().get(274), 6)
        converted = self.run_job(source, ImageOptions(target='full_ou', format='png', metadata=False))
        with Image.open(converted.outputs[0]) as image: self.assertEqual(image.size, (72, 256))

    def test_orientation_dates_icc_jpeg_sampling_and_lossless_formats(self):
        source = self.folder/'photo.jpg'; exif = Image.Exif(); exif[274] = 6; exif[36867] = '2016:08:19 22:10:11'
        self.left.save(source, exif=exif, quality=95)
        for format in ('jpeg', 'png', 'tiff', 'webp'):
            plan = self.run_job(source, ImageOptions(format=format, layout='mono', long_edge=64))
            with Image.open(plan.outputs[0]) as image:
                self.assertEqual(image.size, (36, 64)); self.assertTrue(image.info.get('icc_profile'))
                self.assertEqual(image.getexif().get(274), 1)
                if format == 'jpeg':
                    from PIL.JpegImagePlugin import get_sampling
                    self.assertEqual(get_sampling(image), 0)
            tags = json.loads(capture(exiftool()+['-j', '-DateTimeOriginal', '-ThumbnailImage', '-PreviewImage', str(plan.outputs[0])]))[0]
            self.assertEqual(tags.get('DateTimeOriginal'), '2016:08:19 22:10:11')
            self.assertNotIn('ThumbnailImage', tags); self.assertNotIn('PreviewImage', tags)
            self.assertEqual(plan.outputs[0].stat().st_mtime_ns, source.stat().st_mtime_ns)

    def test_pair_validation_numbering_lists_collision_and_cancel(self):
        left, right = self.folder/'photo_l.jpg', self.folder/'photo_r.jpg'
        self.left.save(left); self.right.save(right)
        os.utime(right, ns=(right.stat().st_atime_ns, left.stat().st_mtime_ns - 10_000_000_000))
        opts = ImageOptions(task='pairs'); jobs = [ImageJob(left, opts), ImageJob(right, replace(opts))]
        with self.assertRaises(ValueError): plans(jobs[:1], self.folder/'pairs', self.cancel)
        prepared = plans(jobs, self.folder/'pairs', self.cancel)
        execute_image(self.tools, prepared[0], self.cancel, lambda *a: None, self.folder/'pairs.log')
        self.assertEqual(prepared[0].outputs[0].name, '0001_l.jpg')
        for source, output in zip(prepared[0].sources, prepared[0].outputs):
            self.assertEqual(hashlib.sha256(source.read_bytes()).digest(), hashlib.sha256(output.read_bytes()).digest())
            self.assertEqual(source.stat().st_mtime_ns, output.stat().st_mtime_ns)
        next_plan = plans(jobs, self.folder/'pairs', self.cancel)[0]
        self.assertNotEqual(next_plan.outputs, prepared[0].outputs)
        listing = self.folder/'list.json'; save_images(listing, jobs); restored = load_images(listing)
        self.assertEqual(restored[0].serializable(), jobs[0].serializable())
        self.cancel.set()
        with self.assertRaises(__import__('transcora.core.engine', fromlist=['Cancelled']).Cancelled):
            execute_image(self.tools, next_plan, self.cancel, lambda *a: None, self.folder/'pairs.log')
        self.assertFalse(any(p.exists() for p in next_plan.outputs))

