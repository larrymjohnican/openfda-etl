"""openFDA adverse events -> SQL Server, one DAG run per day of data.

    ingest  >>  validate  >>  load

Every run works on exactly one date: the start of its data interval. A run
whose interval is 2026-09-24 00:00 to 2026-09-25 00:00 UTC fetches, validates
and loads the reports openFDA received on 2026-09-24, and nothing else. It is
started just after 2026-09-25 00:00, once that day is complete. That
is what makes backfills and reruns simple. A backfill is just one run per past
date, and rerunning a date replaces that date's rows instead of adding to them.

Retries happen at two levels:
  * inside ingest, each HTTP call retries transient errors (timeouts, 5xx)
    with exponential backoff (tenacity, see pipeline/ingest.py);
  * Airflow retries a whole failed task (default_args below), for failures
    that outlast that, such as the database being down.

Tasks hand data to each other through files under DATA_DIR, one per stage per
date. Only the file path travels through XCom. Thousands of reports would be
far too big for XCom, which lives in Airflow's own metadata database.
"""
from datetime import timedelta

import pendulum
from airflow.sdk import CronDataIntervalTimetable, dag, task

DATA_DIR = "/opt/airflow/data"


def _day(data_interval_start):
    if data_interval_start is None:
        raise ValueError("This DAG needs a data interval; trigger it with a logical date.")
    return data_interval_start.date()


@dag(
    dag_id="openfda_daily",
    description="openFDA adverse events for one received date -> SQL Server",
    # Each run covers one whole day, [D 00:00, D+1 00:00) UTC, and is only
    # started once that day is over. In Airflow 3 a bare "@daily" means
    # something else: a zero-length interval at the moment the run fires, so
    # the midnight run would fetch the day that had only just started.
    schedule=CronDataIntervalTimetable("@daily", timezone="UTC"),
    start_date=pendulum.datetime(2026, 1, 1, tz="UTC"),
    # Don't create a run for every day since start_date when the DAG is first
    # unpaused. Past dates are loaded deliberately, with a backfill.
    catchup=False,
    # One date at a time for scheduled runs: each load holds a single large
    # transaction, and keyless openFDA access has a low rate limit. Backfills
    # have their own limit, so pass --max-active-runs 1 to those as well.
    max_active_runs=1,
    default_args={
        "retries": 2,
        "retry_delay": timedelta(minutes=1),
        "retry_exponential_backoff": True,  # waits about 1 min, then about 2 min
    },
    tags=["openfda", "etl"],
)
def openfda_daily():
    @task
    def ingest(data_interval_start=None) -> str:
        """Fetch every report openFDA received on this run's date and stage it raw."""
        from pipeline.stages import ingest_day, stage_path

        day = _day(data_interval_start)
        raw = stage_path(DATA_DIR, "raw", day)
        count = ingest_day(day, raw)
        print(f"{day}: fetched {count} reports -> {raw}")
        return str(raw)

    @task
    def validate(raw_path: str, data_interval_start=None) -> str:
        """Drop reports that fail the quality rules and stage the rest."""
        from pipeline.stages import stage_path, validate_day

        clean = stage_path(DATA_DIR, "clean", _day(data_interval_start))
        counts = validate_day(raw_path, clean)
        print(f"validated: {counts} -> {clean}")
        return str(clean)

    @task
    def load(clean_path: str) -> int:
        """Replace this date's reports in SQL Server, all in one transaction."""
        from pipeline.load import get_db_engine
        from pipeline.stages import load_day

        count = load_day(get_db_engine(), clean_path)
        print(f"loaded {count} reports from {clean_path}")
        return count

    load(validate(ingest()))


openfda_daily()
