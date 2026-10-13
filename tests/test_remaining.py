import unittest
from transcora.gui.remaining import RemainingTime


class RemainingTests(unittest.TestCase):
    def test_duration_weighted_batch_keeps_estimate_without_updates(self):
        eta = RemainingTime([100, 200])
        eta.start(1, 100)
        eta.progress(150, 50)
        self.assertEqual(eta.remaining(150), (50, 250))
        # No new progress: slower measured throughput, rather than a blank ETA.
        self.assertEqual(eta.remaining(166), (66, 330))
        eta.complete(200)
        self.assertEqual(eta.remaining(200), (None, 200))
        eta.start(2, 300)
        self.assertEqual(eta.remaining(300), (200, 200))
        eta.progress(350, 25)
        # 150 video seconds processed in 150 seconds, across both files.
        self.assertEqual(eta.remaining(350), (150, 150))

    def test_average_is_weighted_by_processed_duration(self):
        eta = RemainingTime([100, 400, 200])
        eta.start(1, 0)
        eta.progress(10, 50)
        self.assertEqual(eta.remaining(10), (10, 130))
        eta.complete(40)
        eta.start(2, 1000)  # A pause between files is excluded.
        self.assertEqual(eta.remaining(1000), (160, 240))
        eta.progress(1060, 25)
        # 200 seconds of video processed in 100 seconds: 0.5 s per video second.
        self.assertEqual(eta.remaining(1060), (150, 250))
        eta.complete(1160)
        eta.start(3, 1200)
        self.assertEqual(eta.remaining(1200), (80, 80))
        eta.complete(1280)
        self.assertEqual(eta.remaining(1280), (None, 0))

    def test_long_first_file_does_not_wait_for_one_percent(self):
        eta = RemainingTime([10000, 10000])
        eta.start(1, 0)
        eta.progress(5, .05)
        self.assertEqual(eta.remaining(5), (9995, 19995))

    def test_multistage_export_learns_total_processing_time(self):
        eta = RemainingTime([100, 200])
        eta.start(1, 100)
        eta.progress(150, 37.5)
        self.assertAlmostEqual(eta.remaining(150)[0], 83.333333)
        eta.progress(200, 70)
        self.assertGreater(eta.remaining(202)[0], 0)
        eta.complete(220)  # Includes audio and muxing.
        eta.start(2, 300)
        self.assertEqual(eta.remaining(300), (240, 240))
        eta.progress(400, 37.5)
        self.assertAlmostEqual(eta.remaining(400)[0], 157.142857)
        eta.progress(550, 98, remaining=10)
        self.assertGreater(eta.remaining(550)[0], 9)
        self.assertLessEqual(eta.remaining(550)[0], 10)

    def test_explicit_stage_estimate_before_first_progress(self):
        eta = RemainingTime([100, 200])
        eta.start(1, 100)
        eta.progress(100, 94, remaining=120)
        self.assertEqual(eta.remaining(100), (120, 360))

    def test_mixed_settings_have_batch_estimate_and_failed_files_are_excluded(self):
        eta = RemainingTime([100, 100])
        eta.start(1, 0)
        eta.progress(10, 50)
        self.assertEqual(eta.remaining(10), (10, 30))
        eta.complete(12, success=False)
        self.assertEqual(eta.measured_time, 0)
        self.assertEqual(eta.measured_duration, 0)
        eta.start(2, 13)
        self.assertEqual(eta.remaining(14), (None, None))

    def test_zero_progress_and_duplicate_completion(self):
        eta = RemainingTime([100, 100])
        eta.start(1, 0)
        eta.progress(10, 0)
        self.assertEqual(eta.remaining(10), (None, None))
        eta.progress(20, 100)
        self.assertEqual(eta.remaining(20), (0, 20))
        eta.complete(20)
        eta.complete(30)
        self.assertEqual(eta.measured_time, 20)
        self.assertEqual(eta.measured_duration, 100)
        self.assertEqual(eta.remaining(30), (None, 20))
