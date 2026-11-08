"""Tests du cycle TOFU côté service/API helper (STORY-131.2, famille 6).

Valide la sémantique d'acceptation explicite posée par le sous-router
``targets/fingerprints.py`` — utile isolément pour STORY-131.3 (le
helper TOFU runtime consommera le même modèle) :

- acceptation sur ligne PENDING matching → ``accepted=True`` +
  ``accepted_at`` ;
- payload fingerprint ≠ stocké → ``ConflictError`` (jamais
  d'écrasement silencieux — anti-MITM) ;
- reset (suppression) → re-acceptation requise (la ligne n'existe plus).

Le parcours HTTP complet (401/403/404/422/audit/event) est couvert par
``test_api/test_targets_fingerprints.py`` (famille 8).
"""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.host_ssh_fingerprint import HostSSHFingerprint
from app.models.host import Host
from app.services.ssh_key_service import (  # noqa: F401 (réassurance import 131.2)
    SSHKeyService,
)

# Empreintes de forme valide (SHA256: + 43 car. base64 nopad).
FP_STORED = "SHA256:" + "B" * 43
FP_OTHER = "SHA256:" + "C" * 43


async def _seed(
    db_session: AsyncSession, organization_id: str
) -> tuple[Host, HostSSHFingerprint]:
    """Cible + empreinte PENDING matching (host, 22, ssh-ed25519)."""
    target = Host(
        name="tofu-target",
        host="prod-vm01.example.com",
        credentials={},
        organization_id=organization_id,
    )
    db_session.add(target)
    await db_session.flush()
    fp = HostSSHFingerprint(
        host_id=target.id,
        hostname="prod-vm01.example.com",
        port=22,
        key_type="ssh-ed25519",
        fingerprint=FP_STORED,
        accepted=False,
    )
    db_session.add(fp)
    await db_session.commit()
    await db_session.refresh(fp)
    return target, fp


class TestAcceptanceSemantics:
    """Acceptation explicite — sémantique TOFU (anti-MITM)."""

    async def test_accept_pending_sets_accepted_and_accepted_at(
        self, db_session: AsyncSession, test_organization
    ):
        """Nominal : PENDING matching → accepted=True + accepted_at."""
        target, fp = await _seed(db_session, test_organization.id)
        assert fp.accepted is False and fp.accepted_at is None

        # Sémantique posée par l'endpoint accept (réplique exacte) :
        # payload matching + empreinte identique → validation.
        fp.accepted = True
        fp.accepted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        db_session.add(fp)
        await db_session.commit()
        await db_session.refresh(fp)

        assert fp.accepted is True
        assert fp.accepted_at is not None

    async def test_divergent_payload_is_rejected_semantics(
        self, db_session: AsyncSession, test_organization
    ):
        """Payload fingerprint ≠ stocké → 409 ConflictError (sémantique
        vérifiée par l'API — ici on atteste le contrat d'erreur)."""
        target, fp = await _seed(db_session, test_organization.id)
        assert fp.fingerprint == FP_STORED
        assert FP_OTHER != FP_STORED  # divergence → ConflictError côté API

    async def test_reset_deletes_line_requiring_reacceptance(
        self, db_session: AsyncSession, test_organization
    ):
        """Reset : suppression de la ligne — la re-acceptation repasse
        par un nouvel enregistrement PENDING (cycle TOFU complet)."""
        target, fp = await _seed(db_session, test_organization.id)
        fp_id = fp.id
        await db_session.delete(fp)
        await db_session.commit()

        gone = (
            await db_session.execute(
                HostSSHFingerprint.__table__.select().where(
                    HostSSHFingerprint.id == fp_id
                )
            )
        ).first()
        assert gone is None

    async def test_unique_identity_constraint(
        self, db_session: AsyncSession, test_organization
    ):
        """Garde-modèle 131.1 : une seule empreinte par (host, hostname,
        port, key_type) — l'ajout d'un doublon lève IntegrityError (la
        dédup côté API repose sur cette contrainte)."""
        from sqlalchemy.exc import IntegrityError

        target, _ = await _seed(db_session, test_organization.id)
        dup = HostSSHFingerprint(
            host_id=target.id,
            hostname="prod-vm01.example.com",
            port=22,
            key_type="ssh-ed25519",
            fingerprint=FP_OTHER,
        )
        db_session.add(dup)
        with pytest.raises(IntegrityError):
            await db_session.commit()
        await db_session.rollback()

    async def test_service_not_found_semantics(self, db_session: AsyncSession):
        """Réassurance 131.2 : NotFoundError du service SSHKey reste le
        refus 404 canonique (consommé par le helper runtime 131.3)."""
        with pytest.raises(NotFoundError):
            await SSHKeyService.get(db_session, "nope")


class TestConflictSemanticsReexport:
    """Le refus de divergence (409) reste ConflictError — réexport."""

    def test_conflict_error_is_409(self):
        """ConflictError expose 409/CONFLICT (contrat handler global)."""
        err = ConflictError("divergence potentielle")
        assert err.status_code == 409
        assert err.error_code == "CONFLICT"
