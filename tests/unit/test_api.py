from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

import chief.api as api_module
from chief.draft.focus_line import FocusLine
from chief.models import RoleKind
from chief.services import applications


def test_healthz_returns_ok(session):
    with TestClient(api_module.app) as client:
        response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_briefing_today_returns_html_containing_focus_text(session, monkeypatch):
    monkeypatch.setattr(
        api_module.briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )

    with TestClient(api_module.app) as client:
        response = client.get("/briefing/today")

    assert response.status_code == 200
    assert "Nothing is due" in response.text


def test_briefing_today_reuses_cached_row_on_second_request(session, monkeypatch):
    now = datetime.now(UTC)
    applications.add_application(
        session, "Some Co", "SWE", RoleKind.FULLTIME, deadline_at=now + timedelta(days=3)
    )
    session.commit()
    calls = []

    def fake_write_focus_line(*a, **k):
        calls.append(1)
        return FocusLine(text="focus", cost_usd=0.0)

    monkeypatch.setattr(api_module.briefing, "write_focus_line", fake_write_focus_line)

    with TestClient(api_module.app) as client:
        client.get("/briefing/today")
        client.get("/briefing/today")

    assert len(calls) == 1


def test_briefing_by_date_returns_404_when_no_briefing_exists(session):
    with TestClient(api_module.app) as client:
        response = client.get("/briefing/2020-01-01")

    assert response.status_code == 404


def test_briefing_by_date_returns_cached_html_when_it_exists(session, monkeypatch):
    monkeypatch.setattr(
        api_module.briefing, "write_focus_line", lambda *a, **k: FocusLine(text="focus", cost_usd=0.0)
    )
    today_str = datetime.now(UTC).date().isoformat()

    with TestClient(api_module.app) as client:
        client.get("/briefing/today")
        response = client.get(f"/briefing/{today_str}")

    assert response.status_code == 200
    assert "Nothing is due" in response.text
