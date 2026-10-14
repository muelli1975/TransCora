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
                                   save_images, load_images, exiftool, ImagePlan, image_graph)
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

    def test_fixed_image_fitting_preserves_half_image_shape_borders_and_order(self):
        halves = []
        for colour in ((210, 30, 10), (10, 50, 210)):
            half = Image.new('RGB', (160, 120), colour)
            half.paste('white', (60, 40, 100, 80))
            half.paste('green', (0, 0, 160, 12))
            half.paste('green', (0, 108, 160, 120))
            halves.append(half)
        source = self.folder/'four_three_full_sbs.png'
        packed = Image.new('RGB', (320, 120))
        for i, half in enumerate(halves): packed.paste(half, (160*i, 0))
        packed.save(source)
        for target in ('half_sbs', 'half_ou'):
            for mode in ('pad', 'crop'):
                with self.subTest(target=target, mode=mode):
                    plan = self.run_job(source, ImageOptions(target=target, size_mode='1080p',
                        size_fit=mode, format='png', metadata=False))
                    self.assertIn('1920 × 1080', plan.summary)
                    with Image.open(plan.outputs[0]) as image:
                        self.assertEqual(image.size, (1920, 1080))
                        boxes = ((0, 0, 960, 1080), (960, 0, 1920, 1080)) if target == 'half_sbs' else (
                            (0, 0, 1920, 540), (0, 540, 1920, 1080))
                        for i, box in enumerate(boxes):
                            half = image.crop(box).resize((1920, 1080), Image.Resampling.NEAREST).convert('RGB')
                            self.assertEqual(half.getpixel((20, 540)), (0, 0, 0) if mode == 'pad' else halves[i].getpixel((0, 60)))
                            white = half.point(lambda p: 255 if p > 245 else 0)
                            r, g, b = white.split()
                            from PIL import ImageChops
                            bounds = ImageChops.multiply(ImageChops.multiply(r, g), b).getbbox()
                            self.assertIsNotNone(bounds)
                            self.assertLessEqual(abs((bounds[2]-bounds[0])-(bounds[3]-bounds[1])), 3)
                            self.assertAlmostEqual((bounds[0]+bounds[2])/2, 960, delta=2)
                            self.assertAlmostEqual((bounds[1]+bounds[3])/2, 540, delta=2)
                            if mode == 'crop':
                                self.assertEqual(half.getpixel((960, 5)), halves[i].getpixel((0, 60)))
        swapped = self.run_job(source, ImageOptions(target='half_sbs', size_mode='1080p',
            size_fit='pad', swap=True, format='png', metadata=False))
        with Image.open(swapped.outputs[0]) as image:
            self.assertEqual(image.getpixel((200, 540)), (10, 50, 210))

    def test_fixed_image_fitting_handles_wide_portrait_ou_and_split_sources(self):
        for eye_size in ((240, 90), (90, 160)):
            left = Image.new('RGB', eye_size, 'red'); right = Image.new('RGB', eye_size, 'blue')
            source = self.folder/f'wide_{eye_size[0]}_full_ou.png'
            image = Image.new('RGB', (eye_size[0], eye_size[1]*2))
            image.paste(left); image.paste(right, (0, eye_size[1])); image.save(source)
            plan = self.run_job(source, ImageOptions(target='half_sbs', size_mode='1080p',
                size_fit='pad', format='png', metadata=False))
            with Image.open(plan.outputs[0]) as result:
                self.assertEqual(result.size, (1920, 1080))
                self.assertEqual(result.getpixel((480, 540)), (255, 0, 0))
                self.assertEqual(result.getpixel((1440, 540)), (0, 0, 255))
                self.assertEqual(result.getpixel((0, 0)), (0, 0, 0))
        plan = self.run_job(source, ImageOptions(target='split', size_mode='1080p',
            size_fit='crop', format='png', metadata=False))
        for i, output in enumerate(plan.outputs):
            with Image.open(output) as result:
                self.assertEqual(result.size, (1920, 1080))
                self.assertEqual(result.getpixel((0, 0)), ((255, 0, 0), (0, 0, 255))[i])

    def test_fixed_image_fitting_2160p_and_inactive_modes_keep_existing_geometry(self):
        for target in ('keep', 'full_sbs', 'full_ou', 'half_sbs', 'half_ou', 'left', 'right', 'split', 'anaglyph'):
            opts = ImageOptions(target=target, size_mode='2160p', size_fit='pad', metadata=False)
            plan = ImagePlan((self.source,), (), opts, 'full_sbs', False, (320, 120), (), ())
            graph, size = image_graph(plan)
            self.assertEqual(size, (7680, 2160) if target == 'split' else (3840, 2160))
            self.assertIn('pad=', graph)
            for mode in ('original', '2048', 'custom'):
                original = replace(plan, options=replace(opts, size_mode=mode, size_fit='scale'))
                inactive = replace(original, options=replace(original.options, size_fit='crop'))
                self.assertEqual(image_graph(original), image_graph(inactive))
        old = ImageOptions.from_dict({'target': 'half_sbs', 'size_mode': '1080p'})
        self.assertEqual(old.size_fit, 'scale')
        with self.assertRaises(ValueError): ImageOptions.from_dict({'size_fit': 'stretch'})
        listing = self.folder/'fitting-list.json'
        save_images(listing, [ImageJob(self.source, opts)])
        self.assertEqual(load_images(listing)[0].options.size_fit, 'pad')

    def test_fixed_image_fitting_cielab_matches_the_planned_canvas(self):
        from transcora.core.cielab import executable
        if not executable().is_file(): self.skipTest('CIELAB not available')
        source = self.folder/'cielab_full_sbs.png'
        image = Image.new('RGB', (160, 60), 'white'); image.save(source)
        for mode in ('pad', 'crop'):
            plan = self.run_job(source, ImageOptions(target='anaglyph', method='cielab',
                size_mode='1080p', size_fit=mode, format='png', metadata=False))
            with Image.open(plan.outputs[0]) as result:
                self.assertEqual(result.size, (1920, 1080))
                self.assertEqual(result.getpixel((0, 540)), (0, 0, 0) if mode == 'pad' else (255, 255, 255))

    def test_fixed_image_fitting_preserves_old_completion_receipts_and_distinguishes_new_modes(self):
        from dataclasses import asdict
        from transcora.core.journal import Journal, request
        job = ImageJob(self.source, ImageOptions(target='half_sbs', size_mode='1080p'))
        folder = self.folder/'history'; folder.mkdir()
        output = folder/'finished.png'; self.left.save(output)
        journal = Journal(folder)
        legacy = request(job, 'image')
        legacy['options'] = asdict(job.options); legacy['options'].pop('size_fit')
        journal.complete(legacy, (output,), 12.5)
        self.assertEqual(journal.lookup(job, 'image').seconds, 12.5)
        job.options = replace(job.options, size_fit='pad')
        self.assertIsNone(journal.lookup(job, 'image'))
        journal.complete(request(job, 'image'), (output,), 15)
        self.assertEqual(journal.lookup(job, 'image').seconds, 15)
        job.options = replace(job.options, size_fit='crop')
        self.assertIsNone(journal.lookup(job, 'image'))

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
        capture(exiftool()+['-overwrite_original', '-EXIF:ColorSpace#=65535',
                            '-EXIF:ExifImageWidth=128', '-EXIF:ExifImageHeight=72', str(source)])
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
            dimensions = json.loads(capture(exiftool()+['-j', '-n', '-EXIF:ColorSpace',
                '-ExifImageWidth', '-ExifImageHeight', str(plan.outputs[0])]))[0]
            self.assertEqual(dimensions['ColorSpace'], 1)
            self.assertEqual((dimensions['ExifImageWidth'], dimensions['ExifImageHeight']), (36, 64))
            self.assertEqual(plan.outputs[0].stat().st_mtime_ns, source.stat().st_mtime_ns)

    def test_image_lists_collision_and_cancel(self):
        options = ImageOptions(target='keep', format='png', metadata=False)
        jobs = [ImageJob(self.source, options)]
        prepared = plans(jobs, self.folder/'out', self.cancel)[0]
        self.assertEqual(prepared.outputs[0].name, self.source.name)
        execute_image(self.tools, prepared, self.cancel, lambda *a: None, self.folder/'log')
        next_plan = plans(jobs, self.folder/'out', self.cancel)[0]
        self.assertNotEqual(next_plan.outputs, prepared.outputs)
        self.assertNotIn('converted', next_plan.outputs[0].name)
        listing = self.folder/'list.json'; save_images(listing, jobs); restored = load_images(listing)
        self.assertEqual(restored[0].serializable(), jobs[0].serializable())
        self.cancel.set()
        with self.assertRaises(__import__('transcora.core.engine', fromlist=['Cancelled']).Cancelled):
            execute_image(self.tools, next_plan, self.cancel, lambda *a: None, self.folder/'log')
        self.assertFalse(any(p.exists() for p in next_plan.outputs))

