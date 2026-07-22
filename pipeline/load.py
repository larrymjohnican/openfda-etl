import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

load_dotenv()

def get_db_engine():
    conn = (
        "mssql+pyodbc://sa:" + os.environ["DB_PASSWORD"] +
        "@" + os.environ["DB_HOST"] + ":1433/FdaDB"
        "?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes"
    )
    return create_engine(conn)

def load_report(engine, report: dict, drugs: list[dict], reactions: list[dict]):
    """Insert one report and its child rows. Parent first, then children."""
    with engine.begin() as conn:
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
                drug  # already has exactly these keys, from extract_drugs
            )

        # Insert child rows for reactions
        for reaction in reactions:
            conn.execute(
                text("""
                    INSERT INTO Event_Reactions (safetyreportid, reactionmeddrapt, reactionoutcome)
                    VALUES (:safetyreportid, :reactionmeddrapt, :reactionoutcome)
                """),
                reaction  # already has exactly these keys, from extract_reactions
            )

if __name__ == "__main__":
    from pipeline.ingest import fetch_date_range
    from pipeline.validate import validate_reports, extract_drugs, extract_reactions

    reports = fetch_date_range("2024-01-01", "2024-01-02")
    clean = validate_reports(reports)

    engine = get_db_engine()
    for report in clean:
        load_report(engine, report, extract_drugs(report), extract_reactions(report))

    print(f"Loaded {len(clean)} reports")