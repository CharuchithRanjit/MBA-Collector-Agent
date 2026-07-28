"""Database tables. Hand-written — the schema is the expensive thing to change."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, Relationship, SQLModel


def utcnow() -> datetime:
    """Always use this. Never datetime.now()."""
    return datetime.now(UTC)


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes. Re-attach UTC on read."""
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class RoleKind(StrEnum):
    INTERN = "intern"
    FULLTIME = "fulltime"


class AppStatus(StrEnum):
    INTERESTED = "interested"
    APPLIED = "applied"
    OA = "oa"
    PHONE = "phone"
    ONSITE = "onsite"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class Company(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    domain: str | None = None
    tier: int = Field(default=2)          # 1 = dream, 3 = safety
    notes: str | None = None
    created_at: datetime = Field(default_factory=utcnow)

    roles: list["Role"] = Relationship(back_populates="company")


class Role(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    company_id: int = Field(foreign_key="company.id", index=True)
    title: str
    kind: RoleKind
    location: str | None = None
    jd_url: str | None = None
    jd_raw_text: str | None = None        # always keep the source
    deadline_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)
    requirements: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    company: Company = Relationship(back_populates="roles")
    application: Optional["Application"] = Relationship(back_populates="role")


class Application(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    role_id: int = Field(foreign_key="role.id", index=True, unique=True)
    status: AppStatus = Field(default=AppStatus.INTERESTED, index=True)
    applied_at: datetime | None = None
    next_action: str | None = None
    next_action_due_at: datetime | None = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=utcnow)

    role: Role = Relationship(back_populates="application")

class LLMCall(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=utcnow, index=True)
    purpose: str = Field(index=True)
    provider: str
    model: str
    prompt_version: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    success: bool = True
    error: str | None = None