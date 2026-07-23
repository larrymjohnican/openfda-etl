import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from datetime import date

load_dotenv()

def get_db_engine():
    conn = (
        "mssql+pyodbc://sa:" + os.environ["DB_PASSWORD"] +
        "@" + os.environ["DB_HOST"] + ":1433/FdaDB"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    return create_engine(conn)

def load_report(engine, report: dict, drugs: list[dict], reactions: list[dict]):
    """Insert one report and its child rows. Deletes any existing version first (idempotent)."""
    report_id = report.get("safetyreportid")

    with engine.begin() as conn:
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
        return "2024-01-01"  # default start date if table is empty
    return result.strftime("%Y-%m-%d")  # return as "YYYY-MM-DD" string
    
if __name__ == "__main__":
    engine = get_db_engine()
    print("Last loaded date:", get_last_loaded_date(engine))

    # --- full ingest/load loop, re-enable once dedup logic (Piece 2) is in place ---
    from pipeline.ingest import fetch_date_range
    from pipeline.validate import validate_reports, extract_drugs, extract_reactions
    reports = fetch_date_range("2024-01-01", "2024-01-02")
    clean = validate_reports(reports)
    for report in clean:
        load_report(engine, report, extract_drugs(report), extract_reactions(report))
    print(f"Loaded {len(clean)} reports")