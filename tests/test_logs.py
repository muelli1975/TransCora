from pathlib import Path
import tempfile
import unittest

from transcora.core.storage import new_run_log, delete_run_logs, run_logs


class LogTests(unittest.TestCase):
    def test_keep_ten_and_delete_only_transcora_logs(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp)
            folder = output/'logs'
            folder.mkdir()
            for number in range(15):
                (folder/f'20250101-0000{number:02}.log').write_text('old')
            foreign = folder/'important.log'
            foreign.write_text('keep')
            current = new_run_log(output)
            self.assertEqual(len(run_logs(folder)), 10)
            self.assertTrue(current.exists())
            self.assertTrue(foreign.exists())
            self.assertEqual(delete_run_logs(output), 10)
            self.assertEqual(foreign.read_text(), 'keep')
