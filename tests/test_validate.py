import pytest

from pipeline.validate import validate_reports


def report(report_id="10001", receivedate="20260311", **extra):
    r = {"safetyreportid": report_id, "receivedate": receivedate}
    r.update(extra)
    return r


def test_valid_report_passes():
    r = report(serious="1")
    assert validate_reports([r]) == []  # DELIBERATELY BROKEN: CI block demo


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


@pytest.mark.xfail(
    strict=True,
    reason="Known gap: only the length is checked, so an 8-character non-date "
    "passes validation and would fail later at the SQL DATE insert.",
)
@pytest.mark.parametrize("bad_date", ["2026131X", "20261340"])
def test_eight_char_non_date_dropped(bad_date):
    good = report("10002")
    assert validate_reports([report("10001", bad_date), good]) == [good]
