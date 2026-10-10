"""Portable settings and lists; always re-probe restored jobs."""
from dataclasses import asdict
from pathlib import Path
import json
import os
import uuid

from .model import Job, Options


def write_json(path: Path, data: dict) -> None:
    temporary = path.with_name("." + path.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def save_list(path: Path, jobs: list[Job], output: Path) -> None:
    write_json(path, {"schema_version": 1, "output": str(output.resolve()),
                      "jobs": [job.serializable() for job in jobs]})


def load_list(path: Path) -> tuple[list[Job], Path | None]:
    if path.stat().st_size > 5_000_000:
        raise ValueError("Jobliste ist zu groß.")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        raise ValueError("Unbekanntes Joblistenformat.")
    entries = data.get("jobs")
    if not isinstance(entries, list) or len(entries) > 10000:
        raise ValueError("Ungültige oder zu große Jobliste.")
    output = data.get("output")
    if output is not None and not isinstance(output, str):
        raise ValueError("Ungültiger Ausgabeordner.")
    return [Job.from_dict(d) for d in entries], Path(output).expanduser().resolve() if output else None


def run_logs(folder: Path) -> list[Path]:
    import re
    if not folder.is_dir():
        return []
    return sorted(p for p in folder.iterdir() if p.is_file() and not p.is_symlink()
                  and re.fullmatch(r'\d{8}-\d{6}(?:-\d{6})?\.log', p.name))


def new_run_log(output: Path) -> Path:
    from datetime import datetime
    folder = output/'logs'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder/(datetime.now().strftime('%Y%m%d-%H%M%S-%f')+'.log')
    with path.open('x', encoding='utf-8') as log:
        log.write('TransCora: Laufprotokoll\n')
    # Delete only TransCora's own dated logs. Always preserve this running log.
    previous = [p for p in run_logs(folder) if p != path]
    for old in previous[:-9]:
        old.unlink()
    return path


def delete_run_logs(output: Path) -> int:
    paths = run_logs(output/'logs')
    for path in paths:
        path.unlink()
    return len(paths)


def preset_options(options: Options) -> dict:
    """Conversion choices only; a film title never follows a preset."""
    data = asdict(options)
    data.pop('disc_title', None)
    return data


def load_presets(path: Path) -> dict[str, Options]:
    if not path.exists():
        return {}
    if path.stat().st_size > 1_000_000:
        raise ValueError('Voreinstellungsdatei ist zu groß.')
    data = json.loads(path.read_text(encoding='utf-8'))
    if not isinstance(data, dict) or data.get('schema_version') != 1:
        raise ValueError('Unbekanntes Voreinstellungsformat.')
    entries = data.get('presets')
    if not isinstance(entries, dict) or len(entries) > 1000:
        raise ValueError('Ungültige Voreinstellungen.')
    result = {}
    for name, options in entries.items():
        validate_preset_name(name)
        result[name] = Options.from_dict(options)
        result[name].disc_title = None
    return result


def validate_preset_name(name: str) -> str:
    if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(ord(c) < 32 for c in name):
        raise ValueError('Name der Voreinstellung: 1 bis 80 Zeichen, ohne Steuerzeichen.')
    return name.strip()


def save_presets(path: Path, presets: dict[str, Options]) -> None:
    write_json(path, {'schema_version': 1, 'presets': {
        validate_preset_name(name): preset_options(options) for name, options in presets.items()}})
