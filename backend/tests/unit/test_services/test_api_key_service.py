"""Tests unitaires de ``ApiKeyService`` (STORY-124.2).

Couvre la mécanique complète des clés API ``wf_ak_`` au niveau
service — ces tests **sont** les tests sécurité de cette couche
(rules 40) :

- génération : préfixe ``wf_ak_`` + 48 caractères (longueur totale
  ``MAX_API_KEY_LENGTH``) ;
- création par hash : la base ne contient **jamais** la valeur claire,
  le hash est déterministe (lookup ``WHERE key_hash = :h`` possible) ;
- verify : refus des clés inconnues / malformées (avant hachage —
  anti-DoS) / révoquées / expirées / propriétaire inactif ; succès →
  ``User`` propriétaire + ``last_used_at`` alimenté ;
- ``last_used_at`` throttlé : deux verify dans la même minute → une
  seule écriture ;
- révocation scopée (clé étrangère → ``NotFoundError``) et idempotente ;
- listing scopé conservant les clés expirées (``revoked`` distinct de
  l'expiration — arbitrage n°2) ;
- logs : jamais la clé brute ni son hash (caplog).

Fixtures : ``db_session`` + ``test_user`` (conftest racine — base de
test issue exclusivement des migrations Alembic, STORY-120.2).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import API_KEY_PREFIX, MAX_API_KEY_LENGTH
from app.core.exceptions import InvalidApiKeyError, NotFoundError
from app.models.api_key import APIKey
from app.models.user import User
from app.schemas.api_key import APIKeyCreate
from app.services.api_key_service import ApiKeyService


async def _fetch_key_row(db: AsyncSession, key_id: str) -> APIKey | None:
    """Recharge une ligne par id (contournement de l'identity map)."""
    result = await db.execute(
        select(APIKey)
        .where(APIKey.id == key_id)
        .execution_options(populate_existing=True)
    )
    return result.scalar_one_or_none()


async def _make_second_user(db_session: AsyncSession) -> User:
    """Crée un second utilisateur isolé (isolation inter-utilisateurs)."""
    from app.schemas.user import UserCreate
    from app.services.user_service import UserService

    user = await UserService.create(
        db_session,
        UserCreate(
            email="apikey-other@example.com",
            username="apikey-otheruser",
            full_name="Other API Key User",
            password="otherpassword123",
            is_superuser=False,
        ),
    )
    await db_session.commit()
    return user


class TestCreate:
    """Création : génération wf_ak_, hash déterministe lookup-able."""

    async def test_create_generates_wf_ak_48_chars(self, db_session, test_user) -> None:
        """La clé générée porte le préfixe ``wf_ak_`` et 48 caractères
        aléatoires (longueur totale ``MAX_API_KEY_LENGTH``)."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="CI key")
        )

        assert created.key.startswith(API_KEY_PREFIX)
        random_part = created.key[len(API_KEY_PREFIX) :]
        assert len(random_part) == 48
        assert len(created.key) == MAX_API_KEY_LENGTH
        # Entropie : deux émissions diffèrent (CSPRNG)
        other = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="CI key 2")
        )
        assert created.key != other.key

    async def test_create_stores_hash_not_plaintext(
        self, db_session, test_user
    ) -> None:
        """``key_hash`` ≠ clé brute ; la clé n'est stockée nulle part
        dans la table (garantie structurelle spec 07)."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="secret check")
        )

        row = await _fetch_key_row(db_session, created.id)
        assert row is not None
        assert row.key_hash != created.key
        assert created.key not in row.key_hash
        assert row.key_hash.startswith("$argon2")

        # Aucune ligne de la table ne contient la valeur claire
        all_rows = (await db_session.execute(select(APIKey))).scalars().all()
        assert all(created.key != stored.key_hash for stored in all_rows)

    async def test_create_hash_is_deterministic_and_lookupable(
        self, db_session, test_user
    ) -> None:
        """Deux hash de la même clé sont identiques (sel dérivé) → le
        lookup par hash résout la clé émise à la création."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="determinism")
        )

        # verify() (lookup par hash) résout la clé fraîchement créée
        owner = await ApiKeyService.verify(db_session, created.key)
        assert owner.id == test_user.id

        # Deux invocations de verify réussissent : le hash recalculé
        # à partir de la même valeur claire retrouve toujours la ligne
        owner_again = await ApiKeyService.verify(db_session, created.key)
        assert owner_again.id == test_user.id

    async def test_create_with_and_without_expires_at(
        self, db_session, test_user
    ) -> None:
        """``expires_at`` fournie est persistée ; null = n'expire
        jamais (spec 06/07)."""
        expires_at = datetime.now(timezone.utc) + timedelta(days=90)
        with_expiry = await ApiKeyService.create(
            db_session,
            test_user.id,
            APIKeyCreate(name="expiring", expires_at=expires_at),
        )
        without_expiry = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="eternal")
        )

        row_with = await _fetch_key_row(db_session, with_expiry.id)
        row_without = await _fetch_key_row(db_session, without_expiry.id)
        assert row_with is not None and row_without is not None

        stored_expiry = row_with.expires_at.replace(tzinfo=timezone.utc)
        # Tolérance d'arrondi : la valeur naive SQLite est en UTC
        assert abs((stored_expiry - expires_at).total_seconds()) < 1
        assert row_without.expires_at is None, "null = n'expire jamais"


class TestVerify:
    """Vérification : lookup par hash, refus sémantique 401."""

    async def test_verify_nominal_returns_active_owner(
        self, db_session, test_user
    ) -> None:
        """Clé valide → ``User`` propriétaire actif ; ``last_used_at``
        alimenté (première utilisation)."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="nominal")
        )

        owner = await ApiKeyService.verify(db_session, created.key)

        assert isinstance(owner, User)
        assert owner.id == test_user.id
        assert owner.is_active is True

        row = await _fetch_key_row(db_session, created.id)
        assert row is not None
        assert row.last_used_at is not None, "last_used_at alimenté"

    async def test_verify_rejects_unknown_key(self, db_session, test_user) -> None:
        """Clé inconnue → ``InvalidApiKeyError`` (sémantique 401,
        mappée par STORY-124.3)."""
        from app.auth.jwt import generate_api_key

        with pytest.raises(InvalidApiKeyError) as exc_info:
            await ApiKeyService.verify(db_session, generate_api_key())
        # Anti-énumération : message générique, sans raison exacte
        assert exc_info.value.reason == "Invalid API key"

    async def test_verify_rejects_malformed_key(self, db_session, test_user) -> None:
        """Forme invalide (mauvais préfixe / longueur inexacte) rejetée
        **avant** hachage — le coût Argon2 n'est jamais encouru."""
        with pytest.raises(InvalidApiKeyError):
            await ApiKeyService.verify(db_session, "")
        with pytest.raises(InvalidApiKeyError):
            # Mauvais préfixe
            await ApiKeyService.verify(db_session, "wf_rt_" + "a" * 48)
        with pytest.raises(InvalidApiKeyError):
            # Bon préfixe, longueur inexacte (47 caractères)
            await ApiKeyService.verify(db_session, API_KEY_PREFIX + "a" * 47)
        with pytest.raises(InvalidApiKeyError):
            # Bon préfixe, longueur inexacte (49 caractères)
            await ApiKeyService.verify(db_session, API_KEY_PREFIX + "a" * 49)

        # Anti-DoS : une clé surdimensionnée est refusée par la
        # validation de forme, avant tout hachage Argon2
        with pytest.raises(InvalidApiKeyError):
            await ApiKeyService.verify(db_session, API_KEY_PREFIX + "a" * 5000)

    async def test_verify_rejects_revoked_key(self, db_session, test_user) -> None:
        """Clé révoquée → ``InvalidApiKeyError``."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="to revoke")
        )
        await ApiKeyService.revoke(db_session, test_user.id, created.id)

        with pytest.raises(InvalidApiKeyError):
            await ApiKeyService.verify(db_session, created.key)

    async def test_verify_rejects_expired_key(self, db_session, test_user) -> None:
        """``expires_at`` passé → ``InvalidApiKeyError``."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="short lived")
        )
        row = await _fetch_key_row(db_session, created.id)
        assert row is not None
        row.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.add(row)
        await db_session.commit()

        with pytest.raises(InvalidApiKeyError):
            await ApiKeyService.verify(db_session, created.key)

    async def test_verify_rejects_inactive_owner(self, db_session, test_user) -> None:
        """Propriétaire ``is_active=False`` → ``InvalidApiKeyError``
        (utilisateur désactivé = clé refusée)."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="inactive owner")
        )
        test_user.is_active = False
        db_session.add(test_user)
        await db_session.commit()

        with pytest.raises(InvalidApiKeyError):
            await ApiKeyService.verify(db_session, created.key)

    async def test_verify_exception_is_windflow_exception(self) -> None:
        """Conformité rules 30 : l'exception de refus hérite de
        ``WindFlowException`` (exceptions centralisées)."""
        from app.core.exceptions import WindFlowException

        assert issubclass(InvalidApiKeyError, WindFlowException)
        assert issubclass(NotFoundError, WindFlowException)

    async def test_last_used_at_throttled(self, db_session, test_user) -> None:
        """Deux ``verify`` dans la même minute → une seule écriture de
        ``last_used_at`` (arbitrage n°3)."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="throttled")
        )

        await ApiKeyService.verify(db_session, created.key)
        row = await _fetch_key_row(db_session, created.id)
        assert row is not None and row.last_used_at is not None
        first_used = row.last_used_at

        # Deuxième verify immédiat (même fenêtre de 60 s) : accepté,
        # mais last_used_at inchangé (pas de deuxième écriture)
        owner = await ApiKeyService.verify(db_session, created.key)
        assert owner.id == test_user.id

        row_again = await _fetch_key_row(db_session, created.id)
        assert row_again is not None
        assert (
            row_again.last_used_at == first_used
        ), "last_used_at ne doit pas être réécrit dans la fenêtre de throttle"


class TestRevoke:
    """Révocation : scopée au propriétaire, idempotente."""

    async def test_revoke_scoped_and_idempotent(self, db_session, test_user) -> None:
        """Révocation par le propriétaire OK ; clé étrangère →
        ``NotFoundError`` ; re-révocation = succès no-op."""
        other = await _make_second_user(db_session)

        mine = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="mine")
        )
        theirs = await ApiKeyService.create(
            db_session, other.id, APIKeyCreate(name="theirs")
        )

        # Révocation par le propriétaire
        revoked = await ApiKeyService.revoke(db_session, test_user.id, mine.id)
        assert revoked.revoked is True
        row = await _fetch_key_row(db_session, mine.id)
        assert row is not None and row.revoked is True

        # Re-révocation : succès no-op, état courant retourné
        revoked_again = await ApiKeyService.revoke(db_session, test_user.id, mine.id)
        assert revoked_again.revoked is True
        assert revoked_again.id == mine.id

        # Clé étrangère → NotFoundError (sans révéler l'existence)
        with pytest.raises(NotFoundError):
            await ApiKeyService.revoke(db_session, test_user.id, theirs.id)
        # Clé inexistante → NotFoundError également
        with pytest.raises(NotFoundError):
            await ApiKeyService.revoke(
                db_session, test_user.id, "00000000-0000-0000-0000-000000000000"
            )

        # La clé d'autrui reste non révoquée
        row_theirs = await _fetch_key_row(db_session, theirs.id)
        assert row_theirs is not None and row_theirs.revoked is False


class TestListForUser:
    """Listing : scopé, conservant les clés expirées."""

    async def test_list_for_user_scoped_and_keeps_expired(
        self, db_session, test_user
    ) -> None:
        """Un user ne voit que ses clés ; les clés expirées restent
        listées avec ``expires_at`` visible et ``revoked=False``
        (arbitrage n°2)."""
        other = await _make_second_user(db_session)

        active = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="active")
        )
        expiring = await ApiKeyService.create(
            db_session,
            test_user.id,
            APIKeyCreate(
                name="expired",
                expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            ),
        )
        await ApiKeyService.create(db_session, other.id, APIKeyCreate(name="foreign"))

        keys = await ApiKeyService.list_for_user(db_session, test_user.id)

        ids = {key.id for key in keys}
        assert ids == {active.id, expiring.id}, "isolation : uniquement ses clés"
        assert len(keys) == 2

        expired_entry = next(key for key in keys if key.id == expiring.id)
        assert expired_entry.expires_at is not None
        assert expired_entry.revoked is False, "expiré ≠ révoqué"

        # Les schémas de réponse ne portent jamais key_hash ni key
        dumped = expired_entry.model_dump()
        assert "key_hash" not in dumped
        assert "key" not in dumped


class TestLogsSecurity:
    """Sécurité (rules 40) : jamais la clé ni son hash dans les logs."""

    async def test_no_key_or_hash_in_logs(self, db_session, test_user, caplog) -> None:
        """caplog : les opérations create/revoke/verify ne loggent
        jamais la clé brute ni son hash."""
        caplog.set_level(logging.DEBUG, logger="app.services.api_key_service")

        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="log audit")
        )
        row = await _fetch_key_row(db_session, created.id)
        assert row is not None

        await ApiKeyService.verify(db_session, created.key)
        await ApiKeyService.revoke(db_session, test_user.id, created.id)
        # Un échec d'auth (clé inconnue) pour couvrir auth_failed
        from app.auth.jwt import generate_api_key

        with pytest.raises(InvalidApiKeyError):
            await ApiKeyService.verify(db_session, generate_api_key())

        log_output = caplog.text
        assert created.key not in log_output, "la clé brute ne doit jamais être loggée"
        assert row.key_hash not in log_output, "le hash ne doit jamais être loggé"
        # Les events attendus sont bien émis avec user_id/key_id
        assert "api_key.created" in log_output
        assert "api_key.revoked" in log_output
        assert "api_key.auth_failed" in log_output


class TestSchemaSecurity:
    """Schemas : exposition stricte (rules 40)."""

    async def test_response_schema_never_exposes_secrets(
        self, db_session, test_user
    ) -> None:
        """``APIKeyResponse`` (via list_for_user) n'expose ni ``key_hash``
        ni ``key`` — seul ``APIKeyCreated`` porte la clé brute."""
        created = await ApiKeyService.create(
            db_session, test_user.id, APIKeyCreate(name="schema check")
        )

        keys = await ApiKeyService.list_for_user(db_session, test_user.id)
        assert len(keys) == 1
        assert set(keys[0].model_dump().keys()) == {
            "id",
            "name",
            "expires_at",
            "last_used_at",
            "revoked",
            "created_at",
        }

        # APIKeyCreated est le seul schema portant key (usage création)
        assert "key" in created.model_dump()
        assert created.key.startswith(API_KEY_PREFIX)

        # La base ne stocke que le hash — vérification SQL brute
        plaintext_in_db = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM api_keys WHERE key_hash = :v"),
                {"v": created.key},
            )
        ).scalar_one()
        assert plaintext_in_db == 0
