from datetime import date, timedelta
from pipeline.ingest import fetch_date_range
from pipeline.validate import validate_reports, extract_drugs, extract_reactions
from pipeline.load import get_db_engine, get_last_loaded_date, load_report


def run_pipeline():
    engine = get_db_engine()

    last_loaded_date = get_last_loaded_date(engine)
    print("Last loaded date:", last_loaded_date)

    # Restart AT the watermark day, not the day after. If the last run died
    # partway through that day, it is only half loaded. load_report() deletes
    # and reinserts each report, so fetching the whole day again is safe and
    # fills the gap instead of skipping it.
    current = date.fromisoformat(last_loaded_date)
    fetch_end_date = date.today()  # exclusive: today's reports are still arriving

    # Fetch, validate and load one day at a time, so a crash costs at most
    # the day in flight rather than everything fetched so far.
    total_loaded = 0
    while current < fetch_end_date:
        next_day = current + timedelta(days=1)
        reports = fetch_date_range(current.isoformat(), next_day.isoformat())
        clean = validate_reports(reports)

        for report in clean:
            load_report(engine, report, extract_drugs(report), extract_reactions(report))
            total_loaded += 1
            if total_loaded % 1000 == 0:
                print(f"Loaded {total_loaded} reports so far...")

        current = next_day

    print(f"Loaded {total_loaded} reports")


if __name__ == "__main__":
    run_pipeline()
