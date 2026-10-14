"""Successful export receipts; matching uses file stats, never media rescans."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
import threading
import time

from transcora import __version__
from .storage import write_json

NAME = 'TransCora-Journal.json'
_locks = {}
_guard = threading.Lock()


class JournalError(ValueError):
    pass


@dataclass(frozen=True)
class Completion:
    outputs: tuple[Path, ...]
    seconds: float
    record: dict


def stamp(path):
    path = Path(path).resolve()
    if not path.is_file():
        raise OSError('Keine reguläre Datei: ' + str(path))
    stat = path.stat()
    return {'path': os.path.normcase(str(path)), 'size': stat.st_size,
            'mtime_ns': stat.st_mtime_ns}


def request(job, kind):
    source = job.source.resolve()
    # Relative output hierarchy participates in matching, independently of GUI IDs.
    destination = source.parent.relative_to(job.source_root.resolve()).as_posix() if job.source_root else '.'
    options = asdict(job.options)
    if kind == 'image' and 'size_fit' in options:
        from .images import fixed_image_size
        if not fixed_image_size(job.options):
            # Default/inactive fitting must still match existing image receipts.
            options.pop('size_fit', None)
    return {'kind': kind, 'source': stamp(source), 'destination': destination,
            'options': options}


def key(value):
    data = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False)
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


@contextmanager
def locked(root):
    """Cooperative thread/process locking outside the user's output directory."""
    identity = hashlib.sha256(os.path.normcase(str(root)).encode()).hexdigest()
    with _guard:
        lock = _locks.setdefault(identity, threading.RLock())
    with lock, (Path(tempfile.gettempdir()) / ('transcora-journal-' + identity + '.lock')).open('a+b') as handle:
        handle.seek(0, 2)
        if not handle.tell():
            handle.write(b'0'); handle.flush()
        acquired = False
        until = time.monotonic() + 5
        try:
            while not acquired:
                try:
                    handle.seek(0)
                    if os.name == 'nt':
                        import msvcrt
                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl
                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except (OSError, BlockingIOError):
                    if time.monotonic() >= until:
                        raise JournalError('Journal wird von einem anderen Lauf geschrieben.')
                    time.sleep(.05)
            yield
        finally:
            if acquired:
                handle.seek(0)
                if os.name == 'nt':
                    import msvcrt
                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


class Journal:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.path = self.root / NAME

    def read(self):
        try:
            if not self.path.exists():
                return {'schema_version': 1, 'completed': {}}
            if self.path.stat().st_size > 20_000_000:
                raise JournalError('Journal ist zu groß.')
            data = json.loads(self.path.read_text(encoding='utf-8'))
            if not isinstance(data, dict) or data.get('schema_version') != 1 or not isinstance(data.get('completed'), dict):
                raise JournalError('Unbekanntes Journalformat.')
            return data
        except (OSError, ValueError) as error:
            raise JournalError('Journal konnte nicht gelesen werden: ' + str(error)) from error

    def lookup(self, job, kind):
        try:
            wanted = request(job, kind)
        except (OSError, ValueError):
            return None
        entry = self.read()['completed'].get(key(wanted))
        if not isinstance(entry, dict) or entry.get('request') != wanted:
            return None
        if not isinstance(entry.get('effective'), dict):
            return None
        try:
            seconds = entry['processing_seconds']
            if isinstance(seconds, bool) or not isinstance(seconds, (int, float)) or not math.isfinite(seconds) or seconds < 0:
                return None
            outputs = entry['outputs']
            if not isinstance(outputs, list) or not outputs:
                return None
            paths = []
            for result in outputs:
                relative = Path(result['path'])
                if relative.is_absolute():
                    return None
                path = (self.root / relative).resolve()
                path.relative_to(self.root)
                current = stamp(path)
                if (current['size'], current['mtime_ns']) != (result['size'], result['mtime_ns']):
                    return None
                paths.append(path)
            return Completion(tuple(paths), float(seconds), entry)
        except (KeyError, TypeError, ValueError, OSError):
            return None

    def complete(self, wanted, outputs, seconds, *, effective=None, tools=None):
        if not math.isfinite(seconds) or seconds < 0:
            raise JournalError('Ungültige Bearbeitungszeit.')
        if stamp(Path(wanted['source']['path'])) != wanted['source']:
            raise JournalError('Quelle wurde während der Verarbeitung geändert; Abschluss nicht zugeordnet.')
        files = []
        for output in outputs:
            path = Path(output).resolve()
            info = stamp(path)
            info['path'] = path.relative_to(self.root).as_posix()
            files.append(info)
        if not files:
            raise JournalError('Keine fertigen Ausgaben für das Journal.')
        entry = {'request': wanted, 'effective': effective or {}, 'outputs': files,
                 'processing_seconds': seconds, 'completed_at': datetime.now(timezone.utc).isoformat(),
                 'transcora_version': __version__, 'tools': tools or {}}
        # Reread under the lock: deletion resets history; concurrent writes merge.
        with locked(self.root):
            data = self.read()
            data['completed'][key(wanted)] = entry
            write_json(self.path, data)
        return Completion(tuple(Path(p).resolve() for p in outputs), seconds, entry)


def restore(job, root, kind, notify=lambda message: None):
    try:
        completion = Journal(root).lookup(job, kind)
    except (OSError, JournalError) as error:
        notify('Journal: ' + str(error))
        completion = None
    if completion:
        job.result = completion
        job.status = 'completed'
        job.detail = 'Bereits verarbeitet.\nGespeichert: ' + '\n'.join(map(str, completion.outputs))
        metadata = completion.record.get('effective', {})
        if hasattr(job, 'source_fps'):
            rate = metadata.get('source_fps')
            duration = metadata.get('source_duration')
            job.source_fps = rate if isinstance(rate, str) else None
            job.source_duration = duration if isinstance(duration, (int, float)) and math.isfinite(duration) and duration >= 0 else None
    elif job.status == 'completed':
        job.result = None
        job.status = 'queued'
        job.detail = 'Noch nicht geprüft'
        if hasattr(job, 'plan'):
            job.plan = None
    return completion


def processing_text(result):
    if result is None:
        return '—'
    seconds = int(result.seconds)
    return f'{seconds // 3600:02}:{seconds // 60 % 60:02}:{seconds % 60:02}'

