import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from chief import db, models  # noqa: F401  registers tables on SQLModel.metadata
from chief.db import make_engine


@pytest.fixture()
def session(monkeypatch):
    engine = make_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    # Code under test may call get_session() itself (e.g. LoggingProvider) —
    # point the module-level engine at this same in-memory DB so those writes
    # land where the test can see them.
    monkeypatch.setattr(db, "engine", engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s
    engine.dispose()