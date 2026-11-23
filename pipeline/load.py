import logging
import os

from dotenv import load_dotenv
from sqlalchemy import create_engine, text

from pipeline.validate import extract_drugs, extract_reactions

load_dotenv()

log = logging.getLogger(__name__)

def get_db_engine():
    conn = (
        "mssql+pyodbc://sa:" + os.environ["DB_PASSWORD"] +
        "@" + os.environ["DB_HOST"] + ":1433/FdaDB"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    return create_engine(conn)

def load_report(engine, report: dict, drugs: list[dict], reactions: list[dict]):
    """Insert one report and its child rows in its own transaction (idempotent)."""
    with engine.begin() as conn:
        write_report(conn, report, drugs, reactions)


def load_reports(engine, reports: list[dict]) -> int:
    """Load one date's reports in a single transaction: the date lands whole or not at all.

    Each report is still deleted and reinserted, so loading a date twice
    leaves exactly one copy. If anything fails partway, the whole date rolls
    back, so a retry or rerun starts from a clean slate for that date.
    """
    with engine.begin() as conn:
        for i, report in enumerate(reports, start=1):
            write_report(conn, report, extract_drugs(report), extract_reactions(report))
            if i % 1000 == 0:
                log.info("Wrote %d/%d reports (uncommitted)", i, len(reports))
    log.info("Committed %d reports", len(reports))
    return len(reports)


def write_report(conn, report: dict, drugs: list[dict], reactions: list[dict]):
    """Delete any existing version of one report, then insert it, on an open connection."""
    report_id = report.get("safetyreportid")

    # Delete existing rows for this report ID first — children, then parent (FK order)
    conn.execute(
        text("DELETE FROM Event_Drugs WHERE safetyreportid = :id"),
        {"id": report_id}
    )
    conn.execute(
        text("DELETE FROM Event_Reactions WHERE safetyreportid = :id"),
        {"id": report_id}
    )
    conn.execute(
        text("DELETE FROM Adverse_Events WHERE safetyreportid = :id"),
        {"id": report_id}
    )

    # Insert parent row
    conn.execute(
        text("""
            INSERT INTO Adverse_Events (safetyreportid, receivedate, serious, seriousnessdeath,
                                          seriousnesshospitalization, primarysourcecountry,
                                          patientonsetage, patientsex)
            VALUES (:safetyreportid, :receivedate, :serious, :seriousnessdeath,
                    :seriousnesshospitalization, :primarysourcecountry,
                    :patientonsetage, :patientsex)
        """),
        {
            "safetyreportid": report.get("safetyreportid"),
            "receivedate": report.get("receivedate"),
            "serious": report.get("serious"),
            "seriousnessdeath": report.get("seriousnessdeath"),
            "seriousnesshospitalization": report.get("seriousnesshospitalization"),
            "primarysourcecountry": report.get("primarysourcecountry"),
            "patientonsetage": report.get("patient", {}).get("patientonsetage"),
            "patientsex": report.get("patient", {}).get("patientsex"),
        }
    )

    # Insert child rows for drugs
    for drug in drugs:
        conn.execute(
            text("""
                INSERT INTO Event_Drugs (safetyreportid, medicinalproduct, activesubstancename,
                                           drugcharacterization, drugindication)
                VALUES (:safetyreportid, :medicinalproduct, :activesubstancename,
                        :drugcharacterization, :drugindication)
            """),
            drug
        )

    # Insert child rows for reactions
    for reaction in reactions:
        conn.execute(
            text("""
                INSERT INTO Event_Reactions (safetyreportid, reactionmeddrapt, reactionoutcome)
                VALUES (:safetyreportid, :reactionmeddrapt, :reactionoutcome)
            """),
            reaction
        )

def get_last_loaded_date(engine) -> str:
    """Return the most recent receivedate in the Adverse_Events table, or a default start date if empty."""
    with engine.connect() as conn:
        result = conn.execute(text("SELECT MAX(receivedate) FROM Adverse_Events")).scalar()

    if result is None:
        return os.environ.get("FETCH_START_DATE", "2026-03-10")
    return result.strftime("%Y-%m-%d")
    
if __name__ == "__main__":
    engine = get_db_engine()
    print("Last loaded date:", get_last_loaded_date(engine))