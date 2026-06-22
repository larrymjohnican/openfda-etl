import os
import json
import requests
from dotenv import load_dotenv

load_dotenv()

def fetch_reports(start_date: str, end_date: str, skip: int = 0, limit: int = 1000) -> dict:
    """Fetch FAERS adverse-event reports received between two dates (YYYYMMDD)."""
    url = "https://api.fda.gov/drug/event.json"
    params = {
        "search": f"receivedate:[{start_date} TO {end_date}]",
        "limit": limit,
        "skip": skip,
        "api_key": os.environ["OPENFDA_API_KEY"],
    }
    resp = requests.get(url, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


if __name__ == "__main__":
    data = fetch_reports("20240101", "20240102")
    print("Total hits:", data["meta"]["results"]["total"])
    print("First record keys:", list(data["results"][0].keys()))
    print(json.dumps(data["results"][0]["patient"], indent=2)[:1500])