"""FastAPI app. Route handlers are ≤5 lines: parse, call service, return."""

from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from chief.db import get_session, init_db
from chief.llm.factory import get_llm_provider
from chief.services import briefing


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok"}


@app.get("/briefing/today", response_class=HTMLResponse)
def briefing_today() -> str:
    with get_session() as session:
        row = briefing.get_or_create_briefing(session, get_llm_provider())
    return row.html


@app.get("/briefing/{for_date}", response_class=HTMLResponse)
def briefing_by_date(for_date: date) -> str:
    with get_session() as session:
        row = briefing.get_briefing_by_date(session, for_date)
    if row is None:
        raise HTTPException(status_code=404, detail="No briefing for that date")
    return row.html
