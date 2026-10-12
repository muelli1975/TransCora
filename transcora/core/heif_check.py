"""Development package check through the real image import/export path."""
import hashlib
from pathlib import Path
import tempfile
import threading


def check(folder):
    from PIL import Image
    from .images import ImageJob, ImageOptions, plans, execute_image, inspect
    from .toolchain import Toolchain
    tools = Toolchain.find()
    checks = []
    with tempfile.TemporaryDirectory(prefix='transcora-heif-check-') as tmp:
        output = Path(tmp)
        for filename, blue_left in [('stereo_pair.heic', False), ('entity_groups.heic', True)]:
            for swap in (False, True):
                plan = plans([ImageJob(folder/filename, ImageOptions(
                    target='split', format='png', metadata=True, swap=swap))], output, threading.Event())[0]
                execute_image(tools, plan, threading.Event(), lambda *a: None, output/'check.log')
                for index, path in enumerate(plan.outputs):
                    with Image.open(path) as image:
                        image.load()
                        assert image.size == (64, 64)
                        pixel = image.convert('RGB').getpixel((32, 32))
                        blue = blue_left ^ swap ^ bool(index)
                        assert pixel[2 if blue else 0] > 240 and pixel[0 if blue else 2] < 10
                        assert image.info.get('icc_profile')
                checks.append({'source': filename, 'swap': swap, 'result': 'passed'})
        source = folder/'spatial_photo.heic'
        plan = plans([ImageJob(source, ImageOptions(target='split', format='png', metadata=False,
                       size_mode='custom', size_pixels=128, size_edge='long'))], output, threading.Event())[0]
        assert plan.size == (5120, 2560)
        execute_image(tools, plan, threading.Event(), lambda *a: None, output/'check.log')
        hashes = []
        for path in plan.outputs:
            with Image.open(path) as image:
                image.load()
                assert image.size == (128, 128)
                assert image.info.get('icc_profile')
                hashes.append(hashlib.sha256(image.tobytes()).hexdigest())
        assert hashes[0] != hashes[1]
        checks.append({'source': source.name, 'result': 'passed', 'pixel_sha256': hashes})
        source = folder/'arrow.heic'
        assert inspect(source) == ((3024, 4032), False)
        plan = plans([ImageJob(source, ImageOptions(target='keep', format='png', metadata=True,
                       size_mode='custom', size_pixels=128, size_edge='long'))], output, threading.Event())[0]
        execute_image(tools, plan, threading.Event(), lambda *a: None, output/'check.log')
        with Image.open(plan.outputs[0]) as image:
            assert image.size == (96, 128)
            assert image.getexif().get(274) == 1
            assert image.info.get('icc_profile')
        checks.append({'source': source.name, 'result': 'passed'})
    return {'ok': True, 'checks': checks}
