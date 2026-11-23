"""fetch_date_range must request every day from start (inclusive) to end
(exclusive) exactly once, as a single-day window, with no gaps or overlaps."""
from datetime import date, timedelta

import pytest

from pipeline import ingest


@pytest.fixture
def windows(monkeypatch):
    """Record every window fetch_date_range asks for instead of calling the API."""
    calls = []

    def fake_fetch_all_for_window(start_date, end_date):
        calls.append((start_date, end_date))
        return [{"safetyreportid": f"{start_date}-1", "receivedate": start_date}]

    monkeypatch.setattr(ingest, "fetch_all_for_window", fake_fetch_all_for_window)
    return calls


def expected_days(start: str, end: str) -> list[str]:
    d, stop = date.fromisoformat(start), date.fromisoformat(end)
    days = []
    while d < stop:
        days.append(d.strftime("%Y%m%d"))
        d += timedelta(days=1)
    return days


@pytest.mark.parametrize(
    "start, end",
    [
        ("2026-03-11", "2026-03-25"),  # the loaded demo range
        ("2026-01-30", "2026-03-02"),  # month ends, short February
        ("2025-12-30", "2026-01-03"),  # year boundary
        ("2028-02-27", "2028-03-02"),  # leap day
    ],
)
def test_every_day_once_as_single_day_window(windows, start, end):
    results = ingest.fetch_date_range(start, end)

    days = expected_days(start, end)
    # Each window starts and ends on the same day: no window spans two days.
    assert all(s == e for s, e in windows)
    # Exactly the expected days, in order: no gaps, no repeats.
    assert [s for s, _ in windows] == days
    # Results from every window are combined, nothing dropped.
    assert len(results) == len(days)


def test_start_inclusive_end_exclusive(windows):
    ingest.fetch_date_range("2026-03-11", "2026-03-13")
    assert [s for s, _ in windows] == ["20260311", "20260312"]


def test_empty_range_fetches_nothing(windows):
    assert ingest.fetch_date_range("2026-03-11", "2026-03-11") == []
    assert windows == []
