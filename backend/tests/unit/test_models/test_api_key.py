"""Tests unitaires du modèle APIKey (STORY-124.1).

Vérifie :
- les défauts du modèle : ``id`` UUID String(36), ``revoked`` False,
  ``expires_at`` NULL (n'expire jamais), ``last_used_at`` NULL,
  ``created_at`` non nul ;
- le bornage ``name`` ``String(100)`` et ``key_hash`` ``String(255)``
  (spec 06) ;
- le CASCADE : suppression du user → lignes ``api_keys`` purgées
  (hygiène des données — FK ``ondelete="CASCADE"`` + ``delete-orphan``) ;
- la sécurité : ``__repr__`` n'expose jamais le hash ni la clé ;
- l'indépendance des états ``revoked`` et ``expires_at`` (une clé
  expirée n'est pas révoquée — arbitration spec 06).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.api_key import APIKey
from app.models.user import User

# Hash factice de longueur réaliste (Argon2 ~97 chars) — jamais une
# valeur de clé wf_ak_ en clair.
FAKE_HASH = "$argon2id$v=19$m=65536,t=3,p=4$a2V5c2FsdA$k4j9PZ+hash=="
EXPIRY = datetime.now(timezone.utc) + timedelta(days=30)


def _make_key(user_id: str, name: str = "CI key") -> APIKey:
    """Construit une APIKey valide pour un utilisateur donné."""
    return APIKey(user_id=user_id, name=name, key_hash=FAKE_HASH)


class TestAPIKeyDefaults:
    """Cas nominaux : défauts et timestamps."""

    async def test_create_api_key_defaults(self, db_session, test_user) -> None:
        """Création avec defaults valides : id UUID, revoked False,
        expires_at NULL, last_used_at NULL, created_at défini."""
        key = _make_key(test_user.id)
        db_session.add(key)
        await db_session.flush()

        assert key.id is not None
        assert len(key.id) == 36, "id doit être un UUID String(36)"
        assert key.revoked is False, "une clé fraîche ne doit pas être révoquée"
        assert key.expires_at is None, "NULL = n'expire jamais"
        assert key.last_used_at is None, "jamais utilisée à la création"
        assert key.created_at is not None
        assert key.key_hash == FAKE_HASH
        assert key.name == "CI key"

    async def test_expiration_optional(self, db_session, test_user) -> None:
        """Une clé peut porter une date d'expiration (configurable)."""
        key = _make_key(test_user.id)
        key.expires_at = EXPIRY
        db_session.add(key)
        await db_session.flush()

        assert key.expires_at == EXPIRY


class TestColumnBounds:
    """Bornes structurelles : name String(100), key_hash String(255)."""

    def test_name_max_length(self) -> None:
        """La colonne name est bornée à String(100)."""
        column = APIKey.__table__.columns["name"]
        assert column.type.length == 100
        assert not column.nullable

    def test_key_hash_max_length(self) -> None:
        """La colonne key_hash est bornée à String(255)."""
        column = APIKey.__table__.columns["key_hash"]
        assert column.type.length == 255
        assert not column.nullable

    async def test_name_100_chars_accepted(self, db_session, test_user) -> None:
        """Un libellé de 100 caractères (borne max) est accepté."""
        key = _make_key(test_user.id, name="n" * 100)
        db_session.add(key)
        await db_session.flush()

        stored = (
            await db_session.execute(
                text("SELECT LENGTH(name) FROM api_keys WHERE id = :kid"),
                {"kid": key.id},
            )
        ).scalar_one()
        assert stored == 100

    async def test_key_hash_255_chars_accepted(self, db_session, test_user) -> None:
        """Un hash de 255 caractères (borne max) est accepté."""
        key = _make_key(test_user.id)
        key.key_hash = "x" * 255
        db_session.add(key)
        await db_session.flush()

        stored = (
            await db_session.execute(
                text("SELECT LENGTH(key_hash) FROM api_keys WHERE id = :kid"),
                {"kid": key.id},
            )
        ).scalar_one()
        assert stored == 255


class TestUserDeletionCascades:
    """CASCADE : suppression du user → purge de ses clés API."""

    async def test_user_deletion_cascades(self, db_session, test_user) -> None:
        """Suppression du user → lignes api_keys purgées."""
        db_session.add(_make_key(test_user.id))
        db_session.add(_make_key(test_user.id))
        await db_session.flush()

        count_before = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM api_keys WHERE user_id = :uid"),
                {"uid": test_user.id},
            )
        ).scalar_one()
        assert count_before == 2

        await db_session.delete(test_user)
        await db_session.flush()

        count_after = (
            await db_session.execute(text("SELECT COUNT(*) FROM api_keys"))
        ).scalar_one()
        assert count_after == 0, "Les clés API doivent être purgées"

    async def test_other_users_keys_preserved(
        self, db_session, test_user, test_organization
    ) -> None:
        """Isolation : la purge d'un user ne touche pas les clés d'un
        autre utilisateur."""
        other = User(
            email="other-apikey@example.com",
            username="other-apikey",
            hashed_password="h",
        )
        db_session.add(other)
        await db_session.flush()

        db_session.add(_make_key(test_user.id))
        db_session.add(_make_key(other.id))
        await db_session.flush()

        await db_session.delete(test_user)
        await db_session.flush()

        remaining = (await db_session.execute(select(APIKey))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].user_id == other.id


class TestReprSecurity:
    """Sécurité : __repr__ sans exposition du hash ni de la clé."""

    def test_repr_does_not_expose_hash(self) -> None:
        """__repr__ ne contient jamais la valeur du key_hash ni le nom
        de colonne."""
        key = _make_key("00000000-0000-0000-0000-000000000001")
        representation = repr(key)

        assert FAKE_HASH not in representation
        assert "key_hash" not in representation
        assert "user_id=00000000-0000-0000-0000-000000000001" in representation
        assert "name=CI key" in representation
        assert "revoked=False" in representation

        key.revoked = True
        assert "revoked=True" in repr(key)

    def test_tablename(self) -> None:
        """__tablename__ == 'api_keys' (convention spec 06)."""
        assert APIKey.__tablename__ == "api_keys"

    def test_no_plaintext_column(self) -> None:
        """Garantie structurelle : aucune colonne pour une valeur en
        clair — seules les colonnes attendues existent (spec 06)."""
        columns = set(APIKey.__table__.columns.keys())
        assert columns == {
            "id",
            "user_id",
            "name",
            "key_hash",
            "expires_at",
            "last_used_at",
            "revoked",
            "created_at",
        }


class TestRevokedDistinctFromExpiration:
    """Arbitrage spec 06 : ``revoked`` et ``expires_at`` sont deux états
    indépendants — l'expiration porte la sémantique temporelle,
    ``revoked`` porte l'action administrative."""

    async def test_revoked_distinct_from_expiration(
        self, db_session, test_user
    ) -> None:
        """Une clé expirée reste revoked=False ; une clé révoquée peut
        n'avoir aucune expiration."""
        expired_key = _make_key(test_user.id, name="expired")
        expired_key.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        db_session.add(expired_key)

        revoked_key = _make_key(test_user.id, name="revoked")
        revoked_key.revoked = True
        db_session.add(revoked_key)
        await db_session.flush()

        # Clé expirée → état administratif inchangé.
        assert expired_key.expires_at < datetime.now(timezone.utc)
        assert (
            expired_key.revoked is False
        ), "Une clé expirée n'est pas automatiquement révoquée"
        # Clé révoquée → sans expiration (n'expire jamais mais inactive).
        assert revoked_key.revoked is True
        assert revoked_key.expires_at is None


class TestRelationships:
    """Relation navigable User.api_keys."""

    async def test_user_relationship_api_keys(self, db_session, test_user) -> None:
        """User.api_keys navigable après flush d'une clé."""
        db_session.add(_make_key(test_user.id))
        await db_session.flush()

        # Rechargement explicite (selectinload) : le lazy-loading est
        # interdit en contexte async (greenlet).
        user = (
            await db_session.execute(select(User).options(selectinload(User.api_keys)))
        ).scalar_one()
        assert len(user.api_keys) == 1
        assert user.api_keys[0].key_hash == FAKE_HASH
