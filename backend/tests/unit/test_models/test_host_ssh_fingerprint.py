"""Tests unitaires du modèle HostSSHFingerprint (STORY-131.1).

Vérifie :
- la contrainte UNIQUE ``(host_id, hostname, port, key_type)`` : doublon
  exact → IntegrityError ; ``key_type`` différent → accepté (un hôte
  peut présenter plusieurs algorithmes de clé, spec 06) ;
- la cascade : suppression de la cible → empreintes purgées ;
- les défauts : ``accepted=False`` (TOFU non accepté à l'enregistrement),
  ``port=22``.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.models.host_ssh_fingerprint import HostSSHFingerprint
from app.models.host import Host


def _make_fingerprint(
    host_id: str,
    hostname: str = "192.0.2.10",
    port: int = 22,
    key_type: str = "ssh-ed25519",
    fingerprint: str = "SHA256:AAAA1111aaaa",
) -> HostSSHFingerprint:
    """Construit une empreinte valide pour une cible donnée."""
    return HostSSHFingerprint(
        host_id=host_id,
        hostname=hostname,
        port=port,
        key_type=key_type,
        fingerprint=fingerprint,
    )


class TestUniqueConstraint:
    """UNIQUE (host_id, hostname, port, key_type) — spec 06."""

    async def test_exact_duplicate_raises_integrity_error(
        self, db_session, test_organization
    ) -> None:
        """Deux lignes identiques (même algo) → IntegrityError."""
        target = Host(
            name="fp-target-1",
            host="192.0.2.10",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.flush()

        db_session.add(_make_fingerprint(target.id))
        await db_session.flush()
        db_session.add(_make_fingerprint(target.id))

        with pytest.raises(IntegrityError):
            await db_session.flush()
        await db_session.rollback()

    async def test_different_key_type_allowed(
        self, db_session, test_organization
    ) -> None:
        """Même hôte/port, algorithmes différents → 2 lignes (multi-
        algorithmes spec 06 : pas de collision)."""
        target = Host(
            name="fp-target-2",
            host="192.0.2.11",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.flush()

        db_session.add(_make_fingerprint(target.id, key_type="ssh-ed25519"))
        db_session.add(
            _make_fingerprint(
                target.id, key_type="ssh-rsa", fingerprint="SHA256:BBBB2222bbbb"
            )
        )
        await db_session.flush()

        rows = (await db_session.execute(select(HostSSHFingerprint))).scalars().all()
        assert len(rows) == 2
        assert {r.key_type for r in rows} == {"ssh-ed25519", "ssh-rsa"}

    async def test_different_port_allowed(self, db_session, test_organization) -> None:
        """Même hôte, ports différents → 2 lignes (contrainte inclut port)."""
        target = Host(
            name="fp-target-3",
            host="192.0.2.12",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.flush()

        db_session.add(_make_fingerprint(target.id, port=22))
        db_session.add(
            _make_fingerprint(target.id, port=2222, fingerprint="SHA256:CCCC3333cccc")
        )
        await db_session.flush()

        rows = (await db_session.execute(select(HostSSHFingerprint))).scalars().all()
        assert len(rows) == 2


class TestTargetDeletionCascades:
    """CASCADE : suppression de la cible → purge des empreintes."""

    async def test_target_deletion_purges_fingerprints(
        self, db_session, test_organization
    ) -> None:
        """Suppression de la cible → lignes host_ssh_fingerprints purgées."""
        target = Host(
            name="fp-target-4",
            host="192.0.2.13",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.flush()

        db_session.add(_make_fingerprint(target.id, key_type="ssh-ed25519"))
        db_session.add(
            _make_fingerprint(
                target.id, key_type="ssh-rsa", fingerprint="SHA256:DDDD4444dddd"
            )
        )
        await db_session.flush()

        count_before = (
            await db_session.execute(text("SELECT COUNT(*) FROM host_ssh_fingerprints"))
        ).scalar_one()
        assert count_before == 2

        await db_session.delete(target)
        await db_session.flush()

        count_after = (
            await db_session.execute(text("SELECT COUNT(*) FROM host_ssh_fingerprints"))
        ).scalar_one()
        assert count_after == 0, "les empreintes doivent être purgées"

    async def test_other_targets_fingerprints_preserved(
        self, db_session, test_organization
    ) -> None:
        """Isolation : la purge ne touche pas les empreintes des autres
        cibles."""
        target_a = Host(
            name="fp-target-5a",
            host="192.0.2.14",
            credentials={},
            organization_id=test_organization.id,
        )
        target_b = Host(
            name="fp-target-5b",
            host="192.0.2.15",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add_all([target_a, target_b])
        await db_session.flush()

        db_session.add(_make_fingerprint(target_a.id))
        db_session.add(_make_fingerprint(target_b.id))
        await db_session.flush()

        await db_session.delete(target_a)
        await db_session.flush()

        remaining = (
            (await db_session.execute(select(HostSSHFingerprint))).scalars().all()
        )
        assert len(remaining) == 1
        assert remaining[0].host_id == target_b.id


class TestDefaults:
    """Défauts TOFU (spec 06) : accepted=False, port=22."""

    async def test_defaults_accepted_false_port_22(
        self, db_session, test_organization
    ) -> None:
        """Empreinte fraîche : non acceptée, port par défaut 22."""
        target = Host(
            name="fp-target-6",
            host="192.0.2.16",
            credentials={},
            organization_id=test_organization.id,
        )
        db_session.add(target)
        await db_session.flush()

        row = _make_fingerprint(target.id)
        db_session.add(row)
        await db_session.flush()

        assert row.accepted is False, "TOFU : pas d'autorité sans acceptation"
        assert row.accepted_at is None
        assert row.port == 22
        assert row.created_at is not None
        assert len(row.id) == 36


class TestStructure:
    """Structure : table, contrainte nommée, index (metadata)."""

    def test_tablename(self) -> None:
        """__tablename__ == 'host_ssh_fingerprints' (convention spec 06)."""
        assert HostSSHFingerprint.__tablename__ == "host_ssh_fingerprints"

    def test_expected_columns(self) -> None:
        """Exactement les colonnes de la spec 06 § HostSSHFingerprint."""
        assert set(HostSSHFingerprint.__table__.columns.keys()) == {
            "id",
            "host_id",
            "hostname",
            "port",
            "key_type",
            "fingerprint",
            "accepted",
            "accepted_at",
            "created_at",
        }

    def test_unique_constraint_named(self) -> None:
        """Contrainte UNIQUE nommée uq_host_ssh_fp_identity (4 colonnes)."""
        constraints = {
            c.name: [col.name for col in c.columns]
            for c in HostSSHFingerprint.__table__.constraints
            if hasattr(c, "columns") and c.name
        }
        assert constraints.get("uq_host_ssh_fp_identity") == [
            "host_id",
            "hostname",
            "port",
            "key_type",
        ]

    def test_host_index_in_metadata(self) -> None:
        """Index idx_host_ssh_fp_host(host_id) présent (spec 06)."""
        indexes = {
            idx.name: [c.name for c in idx.columns]
            for idx in HostSSHFingerprint.__table__.indexes
        }
        assert indexes.get("idx_host_ssh_fp_host") == ["host_id"]
