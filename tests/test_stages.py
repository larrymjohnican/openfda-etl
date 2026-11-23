from datetime import date

import pytest

from pipeline import ingest, stages

DAY = date(2026, 3, 11)


def report(report_id, receivedate="20260311"):
    return {"safetyreportid": report_id, "receivedate": receivedate}


def test_stage_path_is_one_file_per_date(tmp_path):
    assert stages.stage_path(tmp_path, "raw", DAY) == tmp_path / "raw" / "2026-03-11.json.gz"


def test_ingest_day_fetches_only_that_day_and_stages_it(tmp_path, monkeypatch):
    calls = []

    def fake_fetch(start, end):
        calls.append((start, end))
        return [report("1"), report("2")]

    monkeypatch.setattr(stages, "fetch_all_for_window", fake_fetch)
    raw = stages.stage_path(tmp_path, "raw", DAY)

    assert stages.ingest_day(DAY, raw) == 2
    assert calls == [("20260311", "20260311")]
    assert stages.read_json(raw) == [report("1"), report("2")]


def test_ingest_day_with_no_reports_stages_an_empty_list(tmp_path, monkeypatch):
    monkeypatch.setattr(stages, "fetch_all_for_window", lambda s, e: [])
    raw = stages.stage_path(tmp_path, "raw", DAY)
    assert stages.ingest_day(DAY, raw) == 0
    assert stages.read_json(raw) == []


def test_rerunning_ingest_overwrites_the_staged_file(tmp_path, monkeypatch):
    raw = stages.stage_path(tmp_path, "raw", DAY)
    monkeypatch.setattr(stages, "fetch_all_for_window", lambda s, e: [report("1")])
    stages.ingest_day(DAY, raw)
    monkeypatch.setattr(stages, "fetch_all_for_window", lambda s, e: [report("1"), report("2")])
    stages.ingest_day(DAY, raw)
    assert len(stages.read_json(raw)) == 2


def test_validate_day_stages_only_valid_reports(tmp_path):
    raw = stages.stage_path(tmp_path, "raw", DAY)
    clean = stages.stage_path(tmp_path, "clean", DAY)
    stages.write_json_atomic(raw, [report("1"), report(None), report("1"), report("2", "20261340")])

    assert stages.validate_day(raw, clean) == {"raw": 4, "valid": 1, "dropped": 3}
    assert stages.read_json(clean) == [report("1")]


def test_failed_write_leaves_no_partial_file(tmp_path):
    path = tmp_path / "raw" / "2026-03-11.json.gz"
    with pytest.raises(TypeError):
        stages.write_json_atomic(path, [object()])  # not JSON-serializable
    assert not path.exists()


def test_load_day_loads_the_staged_file(tmp_path, monkeypatch):
    clean = stages.stage_path(tmp_path, "clean", DAY)
    stages.write_json_atomic(clean, [report("1"), report("2")])
    loaded = []
    monkeypatch.setattr(stages, "load_reports", lambda engine, reports: loaded.extend(reports) or len(reports))

    assert stages.load_day("engine", clean) == 2
    assert loaded == [report("1"), report("2")]


@pytest.mark.parametrize("key, expected", [("abc123", 1000), ("", 999)])
def test_page_limit_depends_on_api_key(monkeypatch, key, expected):
    monkeypatch.setenv("OPENFDA_API_KEY", key)
    assert ingest.page_limit() == expected


def test_fetch_reports_sends_key_only_when_set(monkeypatch):
    sent = []

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            pass

        def json(self):
            return {"meta": {"results": {"total": 0}}, "results": []}

    def fake_get(url, params, timeout):
        sent.append(dict(params))
        return FakeResponse()

    monkeypatch.setattr(ingest.requests, "get", fake_get)
    monkeypatch.delenv("OPENFDA_API_KEY", raising=False)
    ingest.fetch_reports("20260311", "20260311")
    monkeypatch.setenv("OPENFDA_API_KEY", "abc123")
    ingest.fetch_reports("20260311", "20260311")

    assert "api_key" not in sent[0]
    assert sent[1]["api_key"] == "abc123"
