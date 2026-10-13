from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from dataclasses import replace
import json
import multiprocessing
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from transcora.core.journal import Journal, JournalError, NAME, request, restore, processing_text
from transcora.core.model import Job


def save_receipt(root, wanted, output):
    Journal(root).complete(wanted, (Path(output),), 10.25)


class JournalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name).resolve()
        self.source = self.folder / 'source_full_sbs.mp4'
        self.source.write_bytes(b'original source')
        self.output = self.folder / 'out'
        self.output.mkdir()
        self.result = self.output / 'source_2_half_sbs.mp4'
        self.result.write_bytes(b'completed export')
        self.job = Job(self.source)
        self.journal = Journal(self.output)

    def tearDown(self):
        self.temp.cleanup()

    def complete(self, outputs=None):
        return self.journal.complete(request(self.job, 'video'), outputs or (self.result,), 3723.125,
            effective={'layout': 'full_sbs', 'swap': False}, tools={'video': 'test encoder'})

    def test_new_job_id_and_reload_restore_time_and_actual_numbered_path(self):
        self.complete()
        loaded = Job.from_dict(self.job.serializable())
        self.assertNotEqual(loaded.id, self.job.id)
        completion = restore(loaded, self.output, 'video')
        self.assertEqual(loaded.status, 'completed')
        self.assertEqual(completion.outputs, (self.result,))
        self.assertEqual(processing_text(completion), '01:02:03')
        self.assertEqual(completion.seconds, 3723.125)
        self.assertIsNone(Journal(self.folder).lookup(loaded, 'video'))
        self.assertIsNone(self.journal.lookup(loaded, 'image'))

    def test_changed_source_settings_or_relative_output_hierarchy_do_not_match(self):
        self.complete()
        other = Job(self.source, replace(self.job.options, swap=True))
        self.assertIsNone(self.journal.lookup(other, 'video'))
        other = Job(self.source, self.job.options, self.folder.parent)
        self.assertIsNone(self.journal.lookup(other, 'video'))
        self.source.write_bytes(b'changed input')
        self.assertIsNone(self.journal.lookup(self.job, 'video'))

    def test_same_size_changed_timestamp_is_detected_without_opening_media(self):
        self.complete()
        stat = self.result.stat()
        os.utime(self.result, ns=(stat.st_atime_ns, stat.st_mtime_ns + 10_000_000))
        self.assertIsNone(self.journal.lookup(self.job, 'video'))

    def test_every_file_of_multi_output_must_still_exist_unchanged(self):
        right = self.output / 'right.jpg'; right.write_bytes(b'right')
        self.complete((self.result, right))
        self.assertEqual(len(self.journal.lookup(self.job, 'video').outputs), 2)
        right.unlink()
        self.assertIsNone(self.journal.lookup(self.job, 'video'))

    def test_unknown_existing_output_is_not_adopted_or_overwritten(self):
        self.assertIsNone(self.journal.lookup(self.job, 'video'))
        from transcora.core.naming import reserve_output
        source = self.source
        first = reserve_output(source, self.output, self.job.options, 'test', set())
        first.write_bytes(b'existing file without journal')
        next_path = reserve_output(source, self.output, self.job.options, 'test', set())
        self.assertNotEqual(first, next_path)
        self.assertEqual(first.read_bytes(), b'existing file without journal')

    def test_deletion_resets_history_even_when_the_journal_object_remains_alive(self):
        self.complete()
        self.journal.path.unlink()
        self.assertIsNone(self.journal.lookup(self.job, 'video'))
        new_source = self.folder / 'next.mp4'; new_source.write_bytes(b'new source')
        job = Job(new_source)
        self.journal.complete(request(job, 'video'), (self.result,), 2)
        self.assertEqual(len(self.journal.read()['completed']), 1)
        self.assertIsNone(self.journal.lookup(self.job, 'video'))

    def test_bad_or_future_journal_is_not_overwritten_and_does_not_block_restore(self):
        for content in ('broken json', '{"schema_version": 22, "completed": {}}'):
            self.journal.path.write_text(content)
            messages = []
            self.assertIsNone(restore(self.job, self.output, 'video', messages.append))
            self.assertTrue(messages)
            with self.assertRaises(JournalError): self.complete()
            self.assertEqual(self.journal.path.read_text(), content)
            self.assertEqual(self.result.read_bytes(), b'completed export')

    def test_atomic_write_failure_preserves_previous_history_and_media(self):
        self.complete()
        before = self.journal.path.read_bytes()
        with patch('transcora.core.journal.write_json', side_effect=OSError('disk full')):
            with self.assertRaises(OSError): self.complete()
        self.assertEqual(self.journal.path.read_bytes(), before)
        self.assertTrue(self.result.is_file())

    def test_source_changed_during_encoding_is_not_recorded_as_new_source_success(self):
        wanted = request(self.job, 'video')
        self.source.write_bytes(b'replacement source')
        with self.assertRaises(JournalError):
            self.journal.complete(wanted, (self.result,), 1)
        self.assertFalse(self.journal.path.exists())

    def test_relative_paths_cannot_escape_output_folder(self):
        self.complete()
        data = self.journal.read()
        entry = next(iter(data['completed'].values()))
        entry['outputs'][0]['path'] = '../source_full_sbs.mp4'
        self.journal.path.write_text(json.dumps(data))
        self.assertIsNone(self.journal.lookup(self.job, 'video'))

    def test_thread_and_process_writes_merge_independent_completions(self):
        arguments = []
        for n in range(6):
            source = self.folder / f'{n}.mp4'; source.write_bytes(bytes([n]))
            output = self.output / f'{n}.mp4'; output.write_bytes(bytes([n]))
            arguments.append((self.output, request(Job(source), 'video'), output))
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(lambda args: save_receipt(*args), arguments[:3]))
        with ProcessPoolExecutor(max_workers=2, mp_context=multiprocessing.get_context('spawn')) as pool:
            futures = [pool.submit(save_receipt, *args) for args in arguments[3:]]
            for future in futures: future.result(timeout=20)
        self.assertEqual(len(self.journal.read()['completed']), 6)


if __name__ == '__main__': unittest.main()
