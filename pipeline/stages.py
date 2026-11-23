"""One-date pipeline stages for an orchestrator such as Airflow.

Each stage handles a single date and hands its output to the next stage as a
file, not in memory. That lets each stage run as its own task, fail and retry
on its own, and be rerun later without repeating the stages before it:
rerunning only `load` reloads the staged file without calling the API again.

    ingest_day    API -> data/raw/<date>.json.gz     (every report for the date)
    validate_day  raw -> data/clean/<date>.json.gz   (rejects dropped and logged)
    load_day      clean -> SQL Server                (one transaction per date)
"""
import gzip
import json
import os
from datetime import date
from pathlib import Path

from pipeline.ingest import fetch_all_for_window
from pipeline.load import load_reports
from pipeline.validate import validate_reports


def stage_path(data_dir, stage: str, day: date) -> Path:
    return Path(data_dir) / stage / f"{day.isoformat()}.json.gz"


def write_json_atomic(path, data) -> None:
    """Write to a temp file, then rename, so a crash never leaves a half-written
    file for the next stage to read."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(data, f)
    os.replace(tmp, path)


def read_json(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def ingest_day(day: date, raw_path) -> int:
    """Fetch every report received on `day` and stage it. Returns the count."""
    yyyymmdd = day.strftime("%Y%m%d")
    reports = fetch_all_for_window(yyyymmdd, yyyymmdd)
    write_json_atomic(raw_path, reports)
    return len(reports)


def validate_day(raw_path, clean_path) -> dict:
    """Validate a staged day and stage the survivors. Returns the counts."""
    reports = read_json(raw_path)
    clean = validate_reports(reports)
    write_json_atomic(clean_path, clean)
    return {"raw": len(reports), "valid": len(clean), "dropped": len(reports) - len(clean)}


def load_day(engine, clean_path) -> int:
    """Load a staged, validated day in one transaction. Returns the count."""
    return load_reports(engine, read_json(clean_path))
