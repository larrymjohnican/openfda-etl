import logging
import os
from datetime import date, timedelta

import requests
from dotenv import load_dotenv
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

load_dotenv()

log = logging.getLogger(__name__)

def is_retryable(exception: BaseException) -> bool:
    """Decide whether a given exception is worth retrying."""
    # Connection drops, DNS failures, timeouts — always worth retrying
    if isinstance(exception, (requests.ConnectionError, requests.Timeout)):
        return True

    if isinstance(exception, requests.HTTPError):
        if exception.response is None:
            return False
        status_code = exception.response.status_code
        return 500 <= status_code < 600

    return False


@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    retry=retry_if_exception(is_retryable),
    before_sleep=before_sleep_log(log, logging.WARNING),
)
def fetch_reports(start_date: str, end_date: str, skip: int = 0, limit: int = 1000) -> dict:
    """Fetch FAERS adverse-event reports received between two dates (YYYYMMDD)."""
    url = "https://api.fda.gov/drug/event.json"
    params = {
        "search": f"receivedate:[{start_date} TO {end_date}]",
        "limit": limit,
        "skip": skip,
    }
    api_key = os.environ.get("OPENFDA_API_KEY")
    if api_key:
        params["api_key"] = api_key
    resp = requests.get(url, params=params, timeout=30)

    if resp.status_code == 404:
        # No results found for this date range
        return {"meta": {"results": {"total": 0}}, "results": []}
    resp.raise_for_status()
    return resp.json()


def page_limit() -> int:
    """Largest page openFDA will serve: 1,000 with an API key, 999 without.

    Without a key, limit=1000 is rejected with 403 API_KEY_MISSING.
    """
    return 1000 if os.environ.get("OPENFDA_API_KEY") else 999


def fetch_all_for_window(start_date: str, end_date: str) -> list[dict]:
    """Fetch every report in a date window, paging past the per-call limit."""
    all_results = []
    skip = 0
    limit = page_limit()

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
    
    current = date.fromisoformat(start)   
    end_date = date.fromisoformat(end)

    while current < end_date:
        window_str = current.strftime("%Y%m%d")

        day_results = fetch_all_for_window(window_str, window_str)
        all_results.extend(day_results)
        print(f"Collected {len(day_results)} reports for {current}")

        current += timedelta(days=1)

    return all_results


if __name__ == "__main__":
    results = fetch_date_range("2024-01-01", "2024-01-04")
    print("Total collected:", len(results))