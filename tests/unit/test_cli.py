from typer.testing import CliRunner

import chief.cli as cli_module
from chief.fetch import FetchError
from chief.models import RoleKind
from chief.services import applications

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


def test_jd_show_renders_requirements(session):
    applications.add_application(
        session,
        "Acme",
        "SWE Intern",
        RoleKind.INTERN,
        location="Remote",
        requirements=["Python", "SQL"],
    )
    session.commit()

    result = runner.invoke(cli_module.app, ["jd", "show", "1"])

    assert result.exit_code == 0
    assert "Acme" in result.output
    assert "SWE Intern" in result.output
    assert "Python" in result.output
    assert "SQL" in result.output
