import os
import json
import requests
from dotenv import load_dotenv
from datetime import date, timedelta

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



def fetch_all_for_window(start_date: str, end_date: str) -> list[dict]:
    """Fetch every report in a date window, paging past the 1,000-record limit."""
    all_results = []
    skip = 0
    limit = 1000

    while True:
        data = fetch_reports(start_date, end_date, skip=skip, limit=limit)
        all_results.extend(data["results"])
        total = data["meta"]["results"]["total"]
        if len(all_results) >= total:
            break
        skip += limit

    return all_results

def fetch_date_range(start: str, end: str) -> list[dict]:
    """Walk a date range one day at a time, paginating each day, and combine results."""
    all_results = []
    
    current = date.fromisoformat(start)   # expects "YYYY-MM-DD"
    end_date = date.fromisoformat(end)

    while current < end_date:
        window_start = current.strftime("%Y%m%d")
        next_day = current + timedelta(days=1)
        window_end = next_day.strftime("%Y%m%d")

        # TODO (you): call fetch_all_for_window for this single-day window,
        # extend all_results with what comes back, log the day + count,
        # then advance `current` to the next day

    return all_results

if __name__ == "__main__":
    results = fetch_all_for_window("20240101", "20240102")
    print("Collected:", len(results))