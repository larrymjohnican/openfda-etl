import pytest

from pipeline.validate import validate_reports


def report(report_id="10001", receivedate="20260311", **extra):
    r = {"safetyreportid": report_id, "receivedate": receivedate}
    r.update(extra)
    return r


def test_valid_report_passes():
    r = report(serious="1")
    assert validate_reports([r]) == [r]


@pytest.mark.parametrize("bad_id", [None, ""])
def test_missing_safetyreportid_dropped(bad_id):
    good = report("10001")
    assert validate_reports([report(bad_id), good]) == [good]


def test_absent_safetyreportid_key_dropped():
    good = report("10001")
    assert validate_reports([{"receivedate": "20260311"}, good]) == [good]


def test_duplicate_id_dropped_first_kept():
    first = report("10001", serious="1")
    second = report("10001", serious="2")
    assert validate_reports([first, second]) == [first]


@pytest.mark.parametrize("bad_date", [None, "", "2026-03-11", "2026031", "202603110"])
def test_bad_receivedate_dropped(bad_date):
    good = report("10002")
    assert validate_reports([report("10001", bad_date), good]) == [good]


def test_absent_receivedate_key_dropped():
    good = report("10002")
    assert validate_reports([{"safetyreportid": "10001"}, good]) == [good]


def test_dropped_bad_date_does_not_block_same_id_later():
    # A report rejected for its date is not marked as seen, so a later valid
    # copy with the same id still gets through.
    good = report("10001", "20260311")
    assert validate_reports([report("10001", "bad"), good]) == [good]


@pytest.mark.parametrize(
    "bad_date",
    [
        "20261340",  # month 13, day 40
        "20260230",  # February 30
        "20250229",  # leap day in a non-leap year
        "20260300",  # day 0
        "2026131X",  # non-digit
        " 2026031",  # padded, 8 chars
        "２０２６０３１１",  # full-width digits: isdigit() alone would accept these
        20260311,  # an int, not a string
    ],
)
def test_eight_char_non_date_dropped(bad_date):
    good = report("10002")
    assert validate_reports([report("10001", bad_date), good]) == [good]


def test_bad_date_does_not_crash_and_good_reports_survive():
    # The regression: 20261340 used to pass validation and crash the SQL load.
    batch = [report("1", "20260311"), report("2", "20261340"), report("3", "20260312")]
    assert [r["safetyreportid"] for r in validate_reports(batch)] == ["1", "3"]


@pytest.mark.parametrize("good_date", ["20260311", "20280229", "19991231"])
def test_real_dates_pass(good_date):
    r = report("10001", good_date)
    assert validate_reports([r]) == [r]
