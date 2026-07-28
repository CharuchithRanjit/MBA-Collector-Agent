from typer.testing import CliRunner

import chief.cli as cli_module
from chief.fetch import FetchError

runner = CliRunner()


def test_jd_add_prints_paste_hint_on_fetch_error(session, monkeypatch):
    def fake_ingest_jd(*args, **kwargs):
        raise FetchError("Could not fetch https://example.com/job (403)")

    monkeypatch.setattr(cli_module.jobs, "ingest_jd", fake_ingest_jd)

    result = runner.invoke(cli_module.app, ["jd", "add", "https://example.com/job"])

    assert result.exit_code == 1
    assert "Could not fetch https://example.com/job (403)" in result.output
    assert "chief jd add --paste" in result.output
    assert "Traceback" not in result.output
