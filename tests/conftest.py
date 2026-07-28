import pytest
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

from chief import models  # noqa: F401  registers tables on SQLModel.metadata
from chief.db import make_engine


@pytest.fixture()
def session():
    engine = make_engine("sqlite://", poolclass=StaticPool)
    SQLModel.metadata.create_all(engine)
    with Session(engine, expire_on_commit=False) as s:
        yield s
    engine.dispose()