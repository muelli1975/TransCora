import unittest
from transcora.gui.remaining import RemainingTime


class RemainingTests(unittest.TestCase):
    def test_duration_weighted_batch_and_stalled_encoder(self):
        eta = RemainingTime([(100, 'h264', False), (200, 'h264', False)])
        eta.start(1, 100)
        eta.progress(150, 50)
        self.assertEqual(eta.remaining(150), (50, 250))
        self.assertEqual(eta.remaining(166), (None, None))
        eta.complete(200)
        eta.start(2, 300)
        eta.progress(350, 25)
        self.assertEqual(eta.remaining(350), (150, 150))

    def test_bd_estimate_learns_actual_audio_and_mux_overhead(self):
        eta = RemainingTime([(100, 'bd', True), (200, 'bd', True)])
        eta.start(1, 100)
        eta.phase(100)
        eta.progress(150, 37.5, 50)
        file_left, batch_left = eta.remaining(150)
        self.assertGreater(file_left, 50)  # Includes finishing work.
        self.assertGreater(batch_left, file_left)
        eta.end_encoding(200)
        eta.phase(201)
        self.assertIsNotNone(eta.remaining(202)[0])
        eta.complete(220)  # 100 seconds encoding, 20 seconds finishing.
        eta.start(2, 300)
        eta.phase(300)
        eta.progress(400, 37.5, 50)
        self.assertEqual(eta.remaining(400), (140, 140))
        eta.end_encoding(500)
        self.assertEqual(eta.remaining(501), (39, 39))
        self.assertEqual(eta.remaining(541), (None, None))

    def test_mixed_unmeasured_formats_and_failed_files_are_not_guessed(self):
        eta = RemainingTime([(100, 'h264', False), (100, 'h265', False)])
        eta.start(1, 0)
        eta.progress(10, 50)
        self.assertEqual(eta.remaining(10), (10, None))
        eta.complete(12, success=False)
        self.assertEqual(eta.history, {})
        eta.start(2, 13)
        self.assertEqual(eta.remaining(14), (None, None))
