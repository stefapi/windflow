"""Tests unitaires du helper TOFU ``ssh_connection`` (STORY-131.3, famille 5).

Couverture des deux politiques (mock asyncssh — pas de réseau réel,
rules 35) :

- **STRICT** : sans ligne d'empreinte → ligne PENDING ``accepted=False``
  créée + ``SSHHostKeyNotAcceptedError`` + event PENDING ; ligne non
  acceptée → idem ; divergence vs acceptée → ``SSHHostKeyMismatchError``
  + event DIVERGENCE + audit + **aucun écrasement** de l'empreinte
  acceptée ; acceptée + matching → session OK ; sans cible persistée
  → blocage systématique sans persistance ;
- **COLLECT** : empreinte retournée au caller, **rien persisté**
  (aucune ligne — AC « jamais d'ajout silencieux ») ; statut
  ``mismatch`` détecté sans écriture ;
- **Résolution d'authentification** : ``ssh_key_id`` → ``client_keys``
  importé depuis la clé déchiffrée + ``last_used_at`` mis à jour ;
  fallback credentials password ; matériau PEM explicite ;
  ``passphrase`` explicitement ``None`` pour asyncssh quand absente.
"""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import EventType
from app.core.exceptions import (
    SSHHostKeyMismatchError,
    SSHHostKeyNotAcceptedError,
)
from app.models.audit_log import AuditLog
from app.models.host_ssh_fingerprint import HostSSHFingerprint
from app.models.organization import Organization
from app.models.ssh_key import SSHKey
from app.models.host import Host
from app.services.ssh_connection import (
    HostKeyCapture,
    HostKeyPolicy,
    build_ssh_kwargs,
)

HOST = "prod-vm01.example.com"
FP_A = "SHA256:" + "A" * 43
FP_B = "SHA256:" + "B" * 43


def _make_host_key(fingerprint: str = FP_A, key_type: str = "ssh-ed25519"):
    """Clé d'hôte asyncssh factice (méthodes get_fingerprint/get_algorithm)."""
    key = MagicMock()
    key.get_fingerprint.return_value = fingerprint
    key.get_algorithm.return_value = key_type
    return key


async def _call_verify(
    kwargs: dict[str, Any],
) -> Any:
    """Invoque le callback ``server_host_key_verify`` construit."""
    return await kwargs["server_host_key_verify"](
        HOST, "203.0.113.10", 22, _make_host_key(), "ssh-ed25519"
    )


async def _seed_target(db: AsyncSession, organization_id: str) -> Target:
    """Cible distante minimale (credentials chiffrées password)."""
    from app.models.host import encrypt_credentials_for_storage

    target = Host(
        name="tofu-target",
        host=HOST,
        port=22,
        credentials=encrypt_credentials_for_storage(
            {"auth_method": "password", "username": "deploy", "password": "s3cr3t"}
        ),
        organization_id=organization_id,
    )
    db.add(target)
    await db.commit()
    await db.refresh(target)
    return target


async def _seed_fingerprint(
    db: AsyncSession,
    target_id: str,
    *,
    fingerprint: str = FP_A,
    accepted: bool = False,
) -> HostSSHFingerprint:
    """Ligne d'empreinte (PENDING par défaut)."""
    fp = HostSSHFingerprint(
        host_id=target_id,
        hostname=HOST,
        port=22,
        key_type="ssh-ed25519",
        fingerprint=fingerprint,
        accepted=accepted,
    )
    if accepted:
        fp.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
    db.add(fp)
    await db.commit()
    return fp


async def _rows(db: AsyncSession) -> list[HostSSHFingerprint]:
    """Toutes les lignes d'empreintes (assertion de persistance)."""
    return list((await db.execute(select(HostSSHFingerprint))).scalars().all())


@pytest.fixture(autouse=True)
def _audit_db(monkeypatch, test_session_factory) -> None:
    """Redirige les sessions courtes d'audit vers la base de test
    (pattern test_targets_fingerprints.py)."""
    import app.services.audit_service as audit_service_module

    monkeypatch.setattr(audit_service_module, "AsyncSessionLocal", test_session_factory)


@pytest.fixture(autouse=True)
def _quiet_events(monkeypatch):
    """Capture les émissions du bus (pas de handlers réels)."""
    emitted: list[tuple[Any, dict]] = []
    from app.core import events as events_module

    async def _capture(event_type, data):
        emitted.append((event_type, data))

    monkeypatch.setattr(events_module.event_bus, "emit", _capture)
    return emitted


class TestStrictPolicy:
    """Politique STRICT — sessions opérationnelles (scan/discovery)."""

    async def test_unknown_creates_pending_and_blocks(
        self, db_session: AsyncSession, test_organization
    ):
        """Empreinte inconnue → ligne PENDING accepted=False + exception + event."""
        target = await _seed_target(db_session, test_organization.id)
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
            password="s3cr3t",
        )
        with pytest.raises(SSHHostKeyNotAcceptedError):
            await _call_verify(kwargs)

        rows = await _rows(db_session)
        assert len(rows) == 1
        assert rows[0].host_id == target.id
        assert rows[0].accepted is False
        assert rows[0].accepted_at is None
        assert rows[0].fingerprint == FP_A

    async def test_pending_line_does_not_make_authority(
        self, db_session: AsyncSession, test_organization, _quiet_events
    ):
        """Ligne existante accepted=False → blocage, pas d'autorité, pas de doublon."""
        target = await _seed_target(db_session, test_organization.id)
        await _seed_fingerprint(db_session, target.id, accepted=False)

        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
            password="s3cr3t",
        )
        with pytest.raises(SSHHostKeyNotAcceptedError):
            await _call_verify(kwargs)

        # Aucune ligne dupliquée, empreinte d'origine intacte.
        rows = await _rows(db_session)
        assert len(rows) == 1
        assert rows[0].fingerprint == FP_A

    async def test_mismatch_blocks_without_overwrite(
        self, db_session: AsyncSession, test_organization, _quiet_events
    ):
        """Divergence → SSHHostKeyMismatchError + event DIVERGENCE + empreinte
        acceptée jamais écrasée."""
        target = await _seed_target(db_session, test_organization.id)
        await _seed_fingerprint(db_session, target.id, accepted=True)

        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
            password="s3cr3t",
        )
        # L'hôte présente FP_B alors que FP_A est acceptée.
        with pytest.raises(SSHHostKeyMismatchError):
            await kwargs["server_host_key_verify"](
                HOST, "203.0.113.10", 22, _make_host_key(FP_B), "ssh-ed25519"
            )

        rows = await _rows(db_session)
        assert len(rows) == 1
        assert rows[0].fingerprint == FP_A  # jamais écrasée
        assert rows[0].accepted is True

        # Event DIVERGENCE émis (payload sans secret).
        divergences = [
            d
            for (t, d) in _quiet_events
            if t is EventType.HOST_SSH_FINGERPRINT_DIVERGENCE
        ]
        assert len(divergences) == 1
        assert divergences[0]["fingerprint"] == FP_B
        assert divergences[0]["expected_fingerprint"] == FP_A

    async def test_mismatch_writes_audit(
        self, db_session: AsyncSession, test_organization
    ):
        """Divergence → ligne d'audit target.fingerprint_divergence persistée."""
        target = await _seed_target(db_session, test_organization.id)
        await _seed_fingerprint(db_session, target.id, accepted=True)

        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
            password="s3cr3t",
        )
        with pytest.raises(SSHHostKeyMismatchError):
            await kwargs["server_host_key_verify"](
                HOST, "203.0.113.10", 22, _make_host_key(FP_B), "ssh-ed25519"
            )

        audits = list(
            (
                await db_session.execute(
                    select(AuditLog).where(
                        AuditLog.action == "target.fingerprint_divergence"
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(audits) == 1
        assert audits[0].resource_type == "host_ssh_fingerprint"

    async def test_accepted_matching_allows_session(
        self, db_session: AsyncSession, test_organization
    ):
        """Acceptée + matching → callback True (session établie)."""
        target = await _seed_target(db_session, test_organization.id)
        await _seed_fingerprint(db_session, target.id, accepted=True)

        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
            password="s3cr3t",
        )
        assert await _call_verify(kwargs) is True

    async def test_no_target_blocks_without_persisting(
        self, db_session: AsyncSession, _quiet_events
    ):
        """Sans cible persistée (scan ad hoc) → blocage systématique,
        aucune ligne créée (le TOFU vit sur targets.id)."""
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            password="s3cr3t",
        )
        with pytest.raises(SSHHostKeyNotAcceptedError):
            await _call_verify(kwargs)

        assert await _rows(db_session) == []
        # Event PENDING émis avec target_id=None (observabilité).
        pendings = [
            d for (t, d) in _quiet_events if t is EventType.HOST_SSH_FINGERPRINT_PENDING
        ]
        assert len(pendings) == 1
        assert pendings[0]["target_id"] is None


class TestCollectPolicy:
    """Politique COLLECT — test-connection uniquement."""

    async def test_collect_returns_capture_without_persisting(
        self, db_session: AsyncSession, test_organization
    ):
        """COLLECT → empreinte retournée au caller, aucune ligne en base."""
        target = await _seed_target(db_session, test_organization.id)
        captures: list[HostKeyCapture] = []
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.COLLECT,
            host_model=target,
            password="s3cr3t",
            capture_out=captures,
        )
        assert await _call_verify(kwargs) is True

        assert len(captures) == 1
        assert captures[0].fingerprint == FP_A
        assert captures[0].key_type == "ssh-ed25519"
        assert captures[0].status == "unknown"
        assert await _rows(db_session) == []  # jamais silencieux

    async def test_collect_status_accepted_on_match(
        self, db_session: AsyncSession, test_organization
    ):
        """COLLECT avec ligne acceptée matching → status accepted."""
        target = await _seed_target(db_session, test_organization.id)
        await _seed_fingerprint(db_session, target.id, accepted=True)

        captures: list[HostKeyCapture] = []
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.COLLECT,
            host_model=target,
            password="s3cr3t",
            capture_out=captures,
        )
        assert await _call_verify(kwargs) is True
        assert captures[0].status == "accepted"

    async def test_collect_mismatch_refuses_and_reports(
        self, db_session: AsyncSession, test_organization, _quiet_events
    ):
        """COLLECT mismatch → connexion refusée (False) + event DIVERGENCE,
        rien persisté."""
        target = await _seed_target(db_session, test_organization.id)
        await _seed_fingerprint(db_session, target.id, accepted=True)

        captures: list[HostKeyCapture] = []
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.COLLECT,
            host_model=target,
            password="s3cr3t",
            capture_out=captures,
        )
        rows_before = await _rows(db_session)
        result = await kwargs["server_host_key_verify"](
            HOST, "203.0.113.10", 22, _make_host_key(FP_B), "ssh-ed25519"
        )
        assert result is False  # connexion refusée
        assert captures[0].status == "mismatch"
        assert captures[0].details["expected_fingerprint"] == FP_A
        # Lecture seule : aucune ligne créée ni modifiée (l'empreinte
        # acceptée est intacte).
        rows_after = await _rows(db_session)
        assert len(rows_after) == len(rows_before) == 1
        assert rows_after[0].fingerprint == FP_A
        assert rows_after[0].accepted is True

        divergences = [
            d
            for (t, d) in _quiet_events
            if t is EventType.HOST_SSH_FINGERPRINT_DIVERGENCE
        ]
        assert len(divergences) == 1


class TestAuthenticationResolution:
    """Résolution kwargs d'authentification (clé référencée / fallbacks)."""

    async def _seed_ssh_key(self, db: AsyncSession) -> SSHKey:
        """Clé SSH réutilisable persistée (ed25519 réelle chiffrée)."""
        import asyncssh

        key = asyncssh.generate_private_key("ssh-ed25519")
        from app.core.secret_manager import get_secret_manager

        row = SSHKey(
            name="tofu-test-key",
            key_type="ssh-ed25519",
            public_key=key.export_public_key().decode().strip(),
            private_key_encrypted=get_secret_manager().encrypt(
                key.export_private_key().decode()
            ),
            fingerprint=key.get_fingerprint(),
        )
        db.add(row)
        # last_used_at ancien → touch doit rafraîchir (throttle OK).
        row.last_used_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(
            hours=2
        )
        await db.commit()
        await db.refresh(row)
        return row

    async def test_ssh_key_id_resolves_client_keys_and_touches_last_used(
        self, db_session: AsyncSession, test_organization
    ):
        """ssh_key_id → client_keys depuis le PEM déchiffré + last_used_at maj."""
        ssh_key = await self._seed_ssh_key(db_session)
        before = ssh_key.last_used_at

        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            ssh_key_id=ssh_key.id,
        )
        assert "password" not in kwargs
        assert len(kwargs["client_keys"]) == 1
        # Objet asyncssh SSHKey ré-importé depuis le PEM déchiffré.
        import asyncssh

        assert isinstance(kwargs["client_keys"][0], asyncssh.SSHKey)

        await db_session.refresh(ssh_key)
        assert ssh_key.last_used_at is not None
        assert ssh_key.last_used_at > before

    async def test_target_ssh_key_ref_resolves(
        self, db_session: AsyncSession, test_organization
    ):
        """host.ssh_key_id (voie canonique) → client_keys via resolve_for_host."""
        ssh_key = await self._seed_ssh_key(db_session)
        target = await _seed_target(db_session, test_organization.id)
        target.ssh_key_id = ssh_key.id
        await db_session.commit()

        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
        )
        assert len(kwargs["client_keys"]) == 1

    async def test_password_fallback(self, db_session: AsyncSession, test_organization):
        """Fallback credentials legacy : password des credentials chiffrées."""
        target = await _seed_target(db_session, test_organization.id)
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.STRICT,
            host_model=target,
        )
        assert kwargs["password"] == "s3cr3t"
        assert "client_keys" not in kwargs

    async def test_explicit_password_and_key_material(self, db_session: AsyncSession):
        """Matériau explicite (test-connection) : password direct puis PEM."""
        kwargs = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.COLLECT,
            password="explicit-pass",
        )
        assert kwargs["password"] == "explicit-pass"

        kwargs_key = await build_ssh_kwargs(
            db_session,
            host=HOST,
            port=22,
            username="deploy",
            mode=HostKeyPolicy.COLLECT,
            ssh_private_key="-----BEGIN OPENSSH PRIVATE KEY-----",
            passphrase="phrase",
        )
        assert kwargs_key["client_keys"] == ["-----BEGIN OPENSSH PRIVATE KEY-----"]
        assert kwargs_key["passphrase"] == "phrase"

    async def test_kwargs_never_contains_known_hosts(
        self, db_session: AsyncSession, test_organization
    ):
        """R4 : les kwargs produits ne contiennent jamais known_hosts."""
        target = await _seed_target(db_session, test_organization.id)
        for mode in (HostKeyPolicy.STRICT, HostKeyPolicy.COLLECT):
            kwargs = await build_ssh_kwargs(
                db_session,
                host=HOST,
                port=22,
                username="deploy",
                mode=mode,
                host_model=target,
                password="s3cr3t",
            )
            assert "known_hosts" not in kwargs
            assert "server_host_key_verify" in kwargs
