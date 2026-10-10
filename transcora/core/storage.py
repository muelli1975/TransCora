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
