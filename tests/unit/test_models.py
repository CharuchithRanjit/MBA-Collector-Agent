import pytest
from sqlalchemy.exc import IntegrityError

from chief.models import Company, Role, RoleKind


def test_role_relationship_resolves_to_company(session):
    company = Company(name="Acme")
    session.add(company)
    session.commit()
    session.refresh(company)

    role = Role(company_id=company.id, title="Software Engineer Intern", kind=RoleKind.INTERN)
    session.add(role)
    session.commit()
    session.refresh(role)

    fetched_role = session.get(Role, role.id)

    assert fetched_role.company.id == company.id
    assert fetched_role.company.name == "Acme"

def test_orphan_role_rejected(session):
    """Proves PRAGMA foreign_keys=ON is actually active."""
    session.add(Role(company_id=9999, title="Ghost PM", kind=RoleKind.INTERN))
    with pytest.raises(IntegrityError):
        session.commit()