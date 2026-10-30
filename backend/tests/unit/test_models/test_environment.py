"""Tests unitaires du modèle ``Environment`` (STORY-166.4).

Couvre (cf. story § Tests à écrire) :
- ``UNIQUE(organization_id, name)`` : doublon dans la même organisation →
  ``IntegrityError`` ; même nom dans 2 organisations différentes → OK
  (isolation organisationnelle) ;
- FK ``organizations.id`` ``ON DELETE CASCADE`` : la suppression de
  l'organisation purge ses environnements ;
- défauts : ``is_active`` ``True``, ``configuration`` ``{}`` ;
- rattachements : ``Stack.environment_id`` / ``Host.environment_id`` FK
  ``SET NULL`` (suppression de l'environnement → entités conservées,
  colonne NULL) — spec 06, A14.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import Base
from app.models.environment import Environment
from app.models.organization import Organization
from app.models.stack import Stack


def _make_org(org_id: str, name: str) -> Organization:
    return Organization(id=org_id, name=name, slug=name.lower().replace(" ", "-"))


def _make_environment(name: str = "production", org_id: str = "org-1") -> Environment:
    return Environment(id=f"env-{name}-{org_id}", name=name, organization_id=org_id)


@pytest.fixture()
def engine():
    """Engine in-memory avec les tables du périmètre (pattern test_host).

    ``PRAGMA foreign_keys=ON`` : SQLite n'active pas les FK par défaut —
    requis pour tester ``ON DELETE CASCADE`` / ``SET NULL`` au niveau SQL.
    """
    from sqlalchemy import event

    engine = create_engine("sqlite://")
    event.listen(
        engine,
        "connect",
        lambda dbapi_con, _: dbapi_con.execute("PRAGMA foreign_keys=ON"),
    )
    Base.metadata.create_all(
        engine,
        tables=[
            Organization.__table__,
            Environment.__table__,
            Stack.__table__,
        ],
    )
    yield engine
    engine.dispose()


@pytest.fixture()
def seeded_orgs(engine):
    """Deux organisations (isolation inter-org)."""
    with Session(engine) as session:
        session.add_all([_make_org("org-1", "Org One"), _make_org("org-2", "Org Two")])
        session.commit()
    yield engine


class TestUniqueOrgName:
    """``UNIQUE(organization_id, name)`` — contrainte ``uq_environment_org_name``."""

    def test_constraint_is_declared(self) -> None:
        """La contrainte nommée existe sur la table."""
        names = {c.name for c in Environment.__table_args__ if hasattr(c, "name")}
        assert "uq_environment_org_name" in names

    def test_duplicate_org_name_raises_integrity_error(self, seeded_orgs) -> None:
        """AC 2 — doublon (même org, même nom) → IntegrityError."""
        with Session(seeded_orgs) as session:
            session.add(_make_environment("production", "org-1"))
            session.commit()

            session.add(
                Environment(id="env-dup", name="production", organization_id="org-1")
            )
            with pytest.raises(IntegrityError):
                session.commit()

    def test_same_name_across_organizations_is_allowed(self, seeded_orgs) -> None:
        """AC 2 — isolation : même nom dans 2 orgs différentes → OK."""
        with Session(seeded_orgs) as session:
            session.add(_make_environment("production", "org-1"))
            session.add(_make_environment("production", "org-2"))
            session.commit()  # ne doit pas lever

            envs = session.execute(select(Environment)).scalars().all()
            assert len(envs) == 2


class TestOrganizationCascade:
    """FK ``organizations.id`` ON DELETE CASCADE."""

    def test_org_deletion_purges_environments(self, seeded_orgs) -> None:
        with Session(seeded_orgs) as session:
            session.add(_make_environment("staging", "org-1"))
            session.add(_make_environment("production", "org-1"))
            session.commit()

            # Delete SQL direct : teste le ON DELETE CASCADE de la FK
            # (le delete ORM cascaderait via la relation, pas la FK).
            from sqlalchemy import delete

            session.execute(delete(Organization).where(Organization.id == "org-1"))
            session.commit()

            remaining = session.execute(select(Environment)).scalars().all()
            assert remaining == []


class TestDefaults:
    """Défauts canoniques (spec 06) — appliqués au flush."""

    def test_defaults_is_active_true_configuration_empty(self, seeded_orgs) -> None:
        with Session(seeded_orgs) as session:
            env = _make_environment("dev", "org-1")
            session.add(env)
            session.flush()

            assert env.is_active is True
            assert env.configuration == {}
            assert env.type == "development"


class TestStackEnvironmentSetNull:
    """``stacks.environment_id`` FK SET NULL (Tâche 2 de la story)."""

    def test_stack_defaults_origin_managed_git_url_nullable(self, seeded_orgs) -> None:
        """AC 1 — défaut ``managed`` ; ``git_url`` nullable persisté."""
        with Session(seeded_orgs) as session:
            stack = Stack(
                id="stk-1",
                name="my-stack",
                template={"version": "3.8", "services": {}},
                variables={},
                tags=[],
                target_type="docker",
                organization_id="org-1",
                screenshots=[],
            )
            session.add(stack)
            session.flush()

            assert stack.origin == "managed"
            assert stack.git_url is None

    def test_deleting_environment_keeps_stack_with_null_fk(self, seeded_orgs) -> None:
        """Suppression environnement → stack conservée, colonne NULL."""
        with Session(seeded_orgs) as session:
            env = _make_environment("production", "org-1")
            session.add(env)
            session.flush()

            stack = Stack(
                id="stk-2",
                name="stack-attached",
                template={},
                variables={},
                tags=[],
                target_type="docker",
                organization_id="org-1",
                environment_id=env.id,
                screenshots=[],
            )
            session.add(stack)
            session.commit()

            # Delete SQL direct : teste le ON DELETE SET NULL de la FK
            # (le delete ORM cascaderait via la relation, pas la FK).
            from sqlalchemy import delete

            session.execute(delete(Environment).where(Environment.id == env.id))
            session.commit()

            reloaded = session.get(Stack, "stk-2")
            assert reloaded is not None  # conservée
            assert reloaded.environment_id is None  # déréférencée

    def test_git_url_is_persisted(self, seeded_orgs) -> None:
        """AC 2 — ``Stack.git_url`` optionnel persisté."""
        url = "https://git.example.com/org/repo.git"
        with Session(seeded_orgs) as session:
            stack = Stack(
                id="stk-3",
                name="git-stack",
                template={},
                variables={},
                tags=[],
                target_type="docker",
                organization_id="org-1",
                git_url=url,
                screenshots=[],
            )
            session.add(stack)
            session.commit()

            reloaded = session.get(Stack, "stk-3")
            assert reloaded is not None
            assert reloaded.git_url == url


class TestReprSecurity:
    """Règle 40 — ``__repr__`` sans ``configuration`` (variables partagées
    potentiellement sensibles)."""

    def test_repr_does_not_expose_configuration(self) -> None:
        env = _make_environment("prod")
        env.configuration = {"shared_secret": "s3cr3t"}
        assert "s3cr3t" not in repr(env)
        assert "configuration" not in repr(env)
