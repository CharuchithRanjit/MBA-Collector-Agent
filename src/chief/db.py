from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import event
from sqlmodel import Session, SQLModel, create_engine

from chief.config import settings


def make_engine(url: str, **kwargs):
    """Build an engine with our pragmas attached. Used by both app and tests."""
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        **kwargs,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    return engine


engine = make_engine(f"sqlite:///{settings.db_path}")


@contextmanager
def get_session() -> Iterator[Session]:
    """Commit on clean exit; roll back and re-raise on failure."""
    with Session(engine, expire_on_commit=False) as session:
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise


def init_db() -> None:
    Path(settings.db_path).parent.mkdir(parents=True, exist_ok=True)
    SQLModel.metadata.create_all(engine)