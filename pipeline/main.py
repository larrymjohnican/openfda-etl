from datetime import date, timedelta
from pipeline.ingest import fetch_date_range
from pipeline.validate import validate_reports, extract_drugs, extract_reactions
from pipeline.load import get_db_engine, get_last_loaded_date, load_report


def run_pipeline():
    engine = get_db_engine()

    last_loaded_date = get_last_loaded_date(engine)
    print("Last loaded date:", last_loaded_date)

    fetch_start_date = date.fromisoformat(last_loaded_date) + timedelta(days=1)
    fetch_end_date = date.today()

    reports = fetch_date_range(fetch_start_date.isoformat(), fetch_end_date.isoformat())
    clean = validate_reports(reports)

    for report in clean:
        load_report(engine, report, extract_drugs(report), extract_reactions(report))

    print(f"Loaded {len(clean)} reports")


if __name__ == "__main__":
    run_pipeline()