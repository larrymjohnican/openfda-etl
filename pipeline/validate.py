import logging
from pipeline.ingest import fetch_date_range
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

def extract_drugs(report: dict) -> list[dict]:
    """Extract every drug entry from a report into flat rows for event_drugs."""
    report_id = report.get("safetyreportid")
    drug_list = report.get("patient", {}).get("drug", [])

    rows = []
    for drug in drug_list:
        rows.append({
            "safetyreportid": report_id,
            "medicinalproduct": drug.get("medicinalproduct"),
            "activesubstancename": drug.get("activesubstance", {}).get("activesubstancename"),
            "drugcharacterization": drug.get("drugcharacterization"),
            "drugindication": drug.get("drugindication"),
        })

    return rows

def extract_reactions(report: dict) -> list[dict]:
    """Extract every reaction entry from a report into flat rows for event_reactions."""
    report_id = report.get("safetyreportid")
    reaction_list = report.get("patient", {}).get("reaction", [])

    rows = []
    for reaction in reaction_list:
        rows.append({
            "safetyreportid": report_id,
            "reactionmeddrapt": reaction.get("reactionmeddrapt"),
            "reactionoutcome": reaction.get("reactionoutcome"),
        })

    return rows

def validate_reports(reports: list[dict]) -> list[dict]:
    """Validate a list of reports and return only those that are valid."""
    log = logging.getLogger(__name__)
    seen_ids = set()
    valid_reports = []

    for report in reports:
        report_id = report.get("safetyreportid")
        received = report.get("receivedate")

        if not report_id:
            log.warning("Dropped report with missing safetyreportid")
            continue

        if report_id in seen_ids:
            log.warning("Dropped duplicate safetyreportid: %s", report_id)
            continue

        if not received or len(received) != 8:
            log.warning("Dropped report %s with bad receivedate: %r", report_id, received)
            continue

        seen_ids.add(report_id)
        valid_reports.append(report)

    log.info("Validated %d reports, %d are valid.", len(reports), len(valid_reports))
    return valid_reports

if __name__ == "__main__":
    reports = fetch_date_range("2024-01-01", "2024-01-04")
    clean = validate_reports(reports)
    print("Sample drugs:", extract_drugs(clean[0]))
    print("Sample reactions:", extract_reactions(clean[0]))