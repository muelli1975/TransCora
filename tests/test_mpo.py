import io
from pathlib import Path
import struct
import tempfile
import threading
import unittest

from PIL import Image
from transcora.core.images import ImageJob, ImageOptions, inspect, mpo_jpegs, plans, execute_image


class MpoTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.source = self.folder/'camera.mpo'
        left = Image.new('RGB', (64, 48), 'red')
        right = Image.new('RGB', (64, 48), 'blue')
        left.save(self.source, format='MPO', save_all=True, append_images=[right], quality=90)
        self.original = mpo_jpegs(self.source)

    def padded_mpo(self, left_padding, right_padding):
        data = bytearray(self.source.read_bytes())
        tiff = data.index(b'MPF\0')+4
        endian = '<' if data[tiff:tiff+2] == b'II' else '>'
        ifd = tiff+struct.unpack_from(endian+'I', data, tiff+4)[0]
        count = struct.unpack_from(endian+'H', data, ifd)[0]
        for i in range(count):
            field = ifd+2+12*i
            if struct.unpack_from(endian+'H', data, field)[0] == 0xB002:
                entries = tiff+struct.unpack_from(endian+'I', data, field+8)[0]
                break
        else:
            self.fail('Missing MP entries in test fixture')
        left_size = struct.unpack_from(endian+'I', data, entries+4)[0]
        right_size, right_offset = struct.unpack_from(endian+'II', data, entries+20)
        struct.pack_into(endian+'I', data, entries+4, left_size+len(left_padding))
        struct.pack_into(endian+'II', data, entries+20, right_size+len(right_padding),
                         right_offset+len(left_padding))
        data = data[:left_size]+left_padding+data[left_size:]+right_padding
        self.source.write_bytes(data)
        return left_size, entries, endian

    def test_camera_padding_passes_test_and_lossless_export(self):
        self.padded_mpo(b'\0'*45, b'\0'*17)
        self.assertEqual(inspect(self.source), ((64, 48), True))
        self.assertEqual(mpo_jpegs(self.source), self.original)
        for swap in (False, True):
            with self.subTest(swap=swap):
                options = ImageOptions(task='mpo', metadata=False, swap=swap)
                cancel = threading.Event()
                plan = plans([ImageJob(self.source, options)], self.folder/'out', cancel)[0]
                execute_image(None, plan, cancel, lambda *args: None, self.folder/'log.jsonl')
                expected = self.original[::-1] if swap else self.original
                self.assertEqual(tuple(p.read_bytes() for p in plan.outputs), expected)
                for output in plan.outputs:
                    with Image.open(output) as image:
                        self.assertEqual(image.format, 'JPEG')
                        image.load()

    def test_missing_container_padding_does_not_block_complete_jpegs(self):
        self.padded_mpo(b'\0'*45, b'\0'*17)
        self.source.write_bytes(self.source.read_bytes()[:-1])
        self.assertEqual(mpo_jpegs(self.source), self.original)

    def test_inaccurate_index_sizes_do_not_block_complete_jpegs(self):
        left_size, entries, endian = self.padded_mpo(b'\0'*45, b'')
        data = bytearray(self.source.read_bytes())
        # Ignore inaccurate lengths when both actual JPEGs are complete.
        struct.pack_into(endian+'I', data, entries+4, left_size-2)
        right_size = struct.unpack_from(endian+'I', data, entries+20)[0]
        struct.pack_into(endian+'I', data, entries+20, right_size+30)
        self.source.write_bytes(data)
        self.assertEqual(inspect(self.source), ((64, 48), True))
        self.assertEqual(mpo_jpegs(self.source), self.original)

    def test_actually_truncated_jpeg_is_rejected(self):
        self.source.write_bytes(self.source.read_bytes()[:-2])
        with self.assertRaisesRegex(ValueError, 'JPEG-Halbbild'):
            mpo_jpegs(self.source)

    def test_non_padding_trailer_is_rejected(self):
        self.padded_mpo(b'\0'*44+b'X', b'')
        with self.assertRaisesRegex(ValueError, 'MPO-Index'):
            mpo_jpegs(self.source)

    def test_lossless_split_does_not_require_matching_dimensions_or_orientation(self):
        exif = Image.Exif()
        exif[274] = 6
        left = Image.new('RGB', (64, 48), 'red')
        right = Image.new('RGB', (48, 32), 'blue')
        right.encoderinfo = {'exif': exif}
        left.save(self.source, format='MPO', save_all=True, append_images=[right])
        originals = mpo_jpegs(self.source)
        self.assertEqual(inspect(self.source, require_equal_size=False), ((64, 48), True))
        cancel = threading.Event()
        plan = plans([ImageJob(self.source, ImageOptions(task='mpo'))],
                     self.folder/'out', cancel)[0]
        execute_image(None, plan, cancel, lambda *args: None, self.folder/'log.jsonl')
        self.assertEqual(tuple(p.read_bytes() for p in plan.outputs), originals)
        with Image.open(plan.outputs[1]) as image:
            self.assertEqual(image.size, (48, 32))
            self.assertEqual(image.getexif().get(274), 6)
