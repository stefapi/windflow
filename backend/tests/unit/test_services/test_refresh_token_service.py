"""Tests unitaires de ``RefreshTokenService`` (STORY-123.2).

Couvre le cycle de vie complet des refresh tokens opaques au niveau
service — ces tests **sont** les tests sécurité de cette couche
(rules 40) :

- création par hash : la base ne contient **jamais** la valeur claire ;
- lookup par hash uniquement (isolation : un token ne résout que son
  utilisateur) ;
- refus des tokens inconnus / expirés / surdimensionnés (anti-DoS :
  validation de longueur **avant** hachage Argon2) ;
- rotation : l'ancien token est consommé, un nouveau est émis ;
- réutilisation d'un token consommé → refus **et révocation défensive
  de toute la famille** (spec 07 § rotation) ;
- révocations unitaire (idempotente) et globale ;
- purge des lignes expirées et révoquées au-delà de la rétention.

Fixtures : ``db_session`` + ``test_user`` (conftest racine — base de
test issue exclusivement des migrations Alembic, STORY-120.2).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import generate_refresh_token
from app.core.exceptions import InvalidRefreshTokenError, WindFlowException
from app.models.refresh_token import RefreshToken
from app.models.user import User
from app.services.refresh_token_service import (
    MAX_TOKEN_LENGTH,
    REVOKED_RETENTION_DAYS,
    RefreshTokenService,
)


async def _count_tokens(db: AsyncSession, user_id: str) -> int:
    """Compte les lignes refresh_tokens d'un utilisateur."""
    result = await db.execute(
        select(RefreshToken).where(RefreshToken.user_id == user_id)
    )
    return len(result.scalars().all())


async def _fetch_row(db: AsyncSession, token_id: str) -> RefreshToken | None:
    """Recharge une ligne par id (contournement de l'identity map)."""
    result = await db.execute(
        select(RefreshToken)
        .where(RefreshToken.id == token_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


class TestCreate:
    """Création : hash stocké, jamais la valeur claire (AC 4, part hash)."""

    async def test_create_stores_hash_not_plaintext(
        self, db_session, test_user
    ) -> None:
        """La ligne créée contient le hash Argon2 du token — la valeur
        claire n'apparaît ni dans la ligne ni dans la table."""
        token_plain = generate_refresh_token()
        row = await RefreshTokenService.create(db_session, test_user.id, token_plain)

        assert row.user_id == test_user.id
        assert row.revoked_at is None
        # Le hash stocké n'est PAS la valeur claire
        assert row.token_hash != token_plain
        assert token_plain not in row.token_hash
        # Le hash ressemble à de l'Argon2
        assert row.token_hash.startswith("$argon2")

        # Garantie structurelle : aucune ligne de la table ne contient la
        # valeur claire
        all_rows = (await db_session.execute(select(RefreshToken))).scalars().all()
        assert all(token_plain != stored.token_hash for stored in all_rows)

    async def test_create_computes_expiry_from_settings(
        self, db_session, test_user
    ) -> None:
        """``expires_at`` = now + ``refresh_token_expire_days`` (setting
        posé par STORY-123.1 — plus de constante 7 j côté jwt.py)."""
        from app.config import settings

        before = datetime.now(timezone.utc)
        row = await RefreshTokenService.create(
            db_session, test_user.id, generate_refresh_token()
        )
        after = datetime.now(timezone.utc)

        expected_min = before + timedelta(days=settings.refresh_token_expire_days)
        expected_max = after + timedelta(days=settings.refresh_token_expire_days)
        stored = row.expires_at.replace(tzinfo=timezone.utc)
        assert expected_min <= stored <= expected_max

    async def test_create_rejects_oversized_token(self, db_session, test_user) -> None:
        """Anti-DoS : un token au-delà de 512 caractères est refusé avant
        tout hachage."""
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.create(
                db_session, test_user.id, "x" * (MAX_TOKEN_LENGTH + 1)
            )

    async def test_create_rejects_empty_token(self, db_session, test_user) -> None:
        """Un token vide est refusé."""
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.create(db_session, test_user.id, "")


class TestVerify:
    """Vérification : lookup par hash, refus sémantique 401."""

    async def test_verify_resolves_by_hash_only(self, db_session, test_user) -> None:
        """Token valide → la ligne résolue appartient à l'utilisateur
        attendu (isolation : le token ne résout que son user)."""
        token_plain = generate_refresh_token()
        created = await RefreshTokenService.create(
            db_session, test_user.id, token_plain
        )

        resolved = await RefreshTokenService.verify(db_session, token_plain)

        assert resolved.id == created.id
        assert resolved.user_id == test_user.id

    async def test_verify_rejects_unknown_token(self, db_session, test_user) -> None:
        """Token inconnu → ``InvalidRefreshTokenError`` (sémantique 401 —
        mappée par STORY-123.3)."""
        await RefreshTokenService.create(
            db_session, test_user.id, generate_refresh_token()
        )

        with pytest.raises(InvalidRefreshTokenError) as exc_info:
            await RefreshTokenService.verify(db_session, generate_refresh_token())
        # Anti-énumération : le message ne révèle pas la cause exacte
        assert exc_info.value.reason == "Invalid or expired refresh token"

    async def test_verify_rejects_expired(self, db_session, test_user) -> None:
        """Ligne expirée (``expires_at`` dépassé) → refus."""
        token_plain = generate_refresh_token()
        row = await RefreshTokenService.create(db_session, test_user.id, token_plain)
        row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.add(row)
        await db_session.commit()

        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.verify(db_session, token_plain)

    async def test_verify_rejects_oversized_token(self, db_session, test_user) -> None:
        """Anti-DoS : token > 512 caractères refusé **avant** hachage (le
        coût Argon2 n'est jamais encouru)."""
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.verify(db_session, "y" * (MAX_TOKEN_LENGTH + 1))

    async def test_verify_rejects_empty_token(self, db_session, test_user) -> None:
        """Token vide → refus (validation de forme préalable)."""
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.verify(db_session, "")

    async def test_verify_exception_is_windflow_exception(self) -> None:
        """Conformité rules 30 : l'exception de refus hérite de
        ``WindFlowException`` (exceptions centralisées)."""
        assert issubclass(InvalidRefreshTokenError, WindFlowException)


class TestRotate:
    """Rotation atomique (AC 2, part mécanique)."""

    async def test_rotate_returns_new_token_and_revokes_old(
        self, db_session, test_user
    ) -> None:
        """Rotation : l'ancien token est consommé (``revoked_at`` posé),
        une nouvelle ligne active est créée, la valeur claire nouvelle
        est retournée et vérifiable."""
        old_plain = generate_refresh_token()
        old_row = await RefreshTokenService.create(db_session, test_user.id, old_plain)

        new_row, new_plain = await RefreshTokenService.rotate(db_session, old_plain)

        # Nouvelle ligne : active, même utilisateur, token distinct
        assert new_row.user_id == test_user.id
        assert new_row.revoked_at is None
        assert new_row.id != old_row.id
        assert new_plain != old_plain

        # Ancienne ligne : consommée
        stored_old = await _fetch_row(db_session, old_row.id)
        assert stored_old is not None
        assert stored_old.revoked_at is not None

        # Le nouveau token est immédiatement vérifiable
        resolved = await RefreshTokenService.verify(db_session, new_plain)
        assert resolved.id == new_row.id

        # L'ancien ne l'est plus (consommé → refus)
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.verify(db_session, old_plain)

    async def test_rotate_reused_revoked_token_revokes_family(
        self, db_session, test_user
    ) -> None:
        """Sécurité (spec 07 § rotation) : la réutilisation d'un token
        consommé → refus **et** révocation défensive de **tous** les
        tokens actifs de l'utilisateur (attaque par token volé)."""
        # Famille : token A (consommé plus tôt), token B (actif), token C
        plain_a = generate_refresh_token()
        row_a = await RefreshTokenService.create(db_session, test_user.id, plain_a)
        plain_b = generate_refresh_token()
        row_b = await RefreshTokenService.create(db_session, test_user.id, plain_b)
        plain_c = generate_refresh_token()
        row_c = await RefreshTokenService.create(db_session, test_user.id, plain_c)

        # Capture des ids AVANT toute révocation bulk : revoke_all_for_user
        # expire les objets en session (relecture = IO async interdite en
        # accès paresseux d'attribut).
        id_b, id_c = row_b.id, row_c.id

        # Simuler la consommation antérieure de A (logout ou rotation
        # précédente) — le token A est révoqué mais encore connu de
        # l'attaquant.
        row_a.revoked_at = datetime.now(timezone.utc)
        db_session.add(row_a)
        await db_session.commit()

        # Réutilisation du token consommé A
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.rotate(db_session, plain_a)

        # Défense : B et C (encore actifs) sont révoqués
        stored_b = await _fetch_row(db_session, id_b)
        stored_c = await _fetch_row(db_session, id_c)
        assert stored_b is not None and stored_b.revoked_at is not None
        assert stored_c is not None and stored_c.revoked_at is not None

    async def test_rotate_expired_token_rejects_without_side_effect(
        self, db_session, test_user
    ) -> None:
        """Token expiré → refus ; aucun nouveau token n'est émis."""
        plain = generate_refresh_token()
        row = await RefreshTokenService.create(db_session, test_user.id, plain)
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.add(row)
        await db_session.commit()

        count_before = await _count_tokens(db_session, test_user.id)
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.rotate(db_session, plain)
        count_after = await _count_tokens(db_session, test_user.id)

        assert count_before == count_after


class TestRevoke:
    """Révocation unitaire (logout — STORY-123.3)."""

    async def test_revoke_is_idempotent(self, db_session, test_user) -> None:
        """Double révocation sans erreur : la deuxième invocation
        retourne True sans lever ni dupliquer d'effet."""
        plain = generate_refresh_token()
        row = await RefreshTokenService.create(db_session, test_user.id, plain)

        assert await RefreshTokenService.revoke(db_session, plain) is True
        first_revoked_at = (await _fetch_row(db_session, row.id)).revoked_at

        assert await RefreshTokenService.revoke(db_session, plain) is True
        second_revoked_at = (await _fetch_row(db_session, row.id)).revoked_at

        # Même timestamp conservé (pas de ré-écriture)
        assert first_revoked_at == second_revoked_at

        # Le token révoqué n'est plus vérifiable
        with pytest.raises(InvalidRefreshTokenError):
            await RefreshTokenService.verify(db_session, plain)

    async def test_revoke_unknown_token_returns_false(self, db_session) -> None:
        """Logout tolérant : token inconnu → ``False`` (pas d'exception)."""
        assert (
            await RefreshTokenService.revoke(db_session, generate_refresh_token())
            is False
        )


class TestRevokeAllForUser:
    """Révocation globale (prérequis STORY-129 changement de mot de
    passe et défense anti-réutilisation)."""

    async def test_revoke_all_for_user_revokes_every_token(
        self, db_session, test_user
    ) -> None:
        """Tous les tokens actifs de l'utilisateur sont révoqués, aucun
        autre utilisateur n'est impacté (isolation)."""
        other = await _make_second_user(db_session)

        for _ in range(3):
            await RefreshTokenService.create(
                db_session, test_user.id, generate_refresh_token()
            )
        other_plain = generate_refresh_token()
        other_row = await RefreshTokenService.create(db_session, other.id, other_plain)

        # Capture AVANT la révocation bulk (expire les objets en session).
        other_row_id = other_row.id

        count = await RefreshTokenService.revoke_all_for_user(db_session, test_user.id)

        assert count == 3
        rows = (
            (
                await db_session.execute(
                    select(RefreshToken).where(RefreshToken.user_id == test_user.id)
                )
            )
            .scalars()
            .all()
        )
        assert all(row.revoked_at is not None for row in rows)

        # L'autre utilisateur conserve son token actif
        stored_other = await _fetch_row(db_session, other_row_id)
        assert stored_other is not None and stored_other.revoked_at is None
        resolved = await RefreshTokenService.verify(db_session, other_plain)
        assert resolved.id == other_row_id

    async def test_revoke_all_returns_zero_when_no_active_token(
        self, db_session, test_user
    ) -> None:
        """Aucun token actif → 0 révocation (idempotent)."""
        assert (
            await RefreshTokenService.revoke_all_for_user(db_session, test_user.id) == 0
        )


class TestPurgeExpired:
    """Purge (consommée par le job STORY-123.4)."""

    async def test_purge_expired_removes_expired_and_revoked(
        self, db_session, test_user
    ) -> None:
        """Sont purgées : les lignes expirées et les lignes révoquées
        au-delà de la rétention ; les lignes actives et révoquées
        récentes sont conservées."""
        # 1. Ligne expirée (résidu de login ancien)
        expired_plain = generate_refresh_token()
        expired_row = await RefreshTokenService.create(
            db_session, test_user.id, expired_plain
        )
        expired_row.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.add(expired_row)

        # 2. Ligne révoquée anciennement (au-delà de la rétention)
        old_revoked_plain = generate_refresh_token()
        old_revoked_row = await RefreshTokenService.create(
            db_session, test_user.id, old_revoked_plain
        )
        old_revoked_row.revoked_at = datetime.now(timezone.utc) - timedelta(
            days=REVOKED_RETENTION_DAYS + 1
        )
        old_revoked_row.expires_at = datetime.now(timezone.utc) + timedelta(days=7)
        db_session.add(old_revoked_row)

        # 3. Ligne révoquée récemment (fenêtre d'audit — conservée)
        recent_revoked_plain = generate_refresh_token()
        recent_revoked_row = await RefreshTokenService.create(
            db_session, test_user.id, recent_revoked_plain
        )
        recent_revoked_row.revoked_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.add(recent_revoked_row)

        # 4. Ligne active (jamais purgée)
        active_plain = generate_refresh_token()
        active_row = await RefreshTokenService.create(
            db_session, test_user.id, active_plain
        )

        await db_session.commit()

        purged = await RefreshTokenService.purge_expired(db_session)

        assert purged == 2  # expired + old_revoked
        assert await _fetch_row(db_session, expired_row.id) is None
        assert await _fetch_row(db_session, old_revoked_row.id) is None
        assert await _fetch_row(db_session, recent_revoked_row.id) is not None
        assert await _fetch_row(db_session, active_row.id) is not None

        # La ligne active reste vérifiable après la purge
        resolved = await RefreshTokenService.verify(db_session, active_plain)
        assert resolved.id == active_row.id

    async def test_purge_expired_empty_table_returns_zero(self, db_session) -> None:
        """Table vide → 0 suppression, aucune erreur."""
        assert await RefreshTokenService.purge_expired(db_session) == 0


# --- Helpers ---------------------------------------------------------------


async def _make_second_user(db_session: AsyncSession) -> User:
    """Crée un second utilisateur isolé (isolation inter-utilisateurs)."""
    from app.schemas.user import UserCreate
    from app.services.user_service import UserService

    user = await UserService.create(
        db_session,
        UserCreate(
            email="other@example.com",
            username="otheruser",
            full_name="Other User",
            password="otherpassword123",
            is_superuser=False,
        ),
    )
    await db_session.commit()
    return user
