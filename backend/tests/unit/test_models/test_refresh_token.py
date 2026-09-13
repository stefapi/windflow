"""Tests unitaires du modèle RefreshToken (STORY-123.1).

Vérifie :
- les défauts du modèle : ``id`` UUID String(36), ``revoked_at`` NULL
  (token actif), timestamps ``created_at``/``updated_at`` non nuls ;
- le bornage ``token_hash`` ``String(255)`` (spec 06) ;
- le CASCADE : suppression du user → lignes ``refresh_tokens`` purgées
  (hygiène des données — FK ``ondelete="CASCADE"`` + ``delete-orphan``) ;
- la sécurité : ``__repr__`` n'expose jamais la valeur du hash ;
- la relation navigable ``User.refresh_tokens`` (pattern STORY-121.1).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import selectinload

from app.models.refresh_token import RefreshToken
from app.models.user import User

# Hash factice de longueur réaliste (Argon2 ~97 chars) — jamais une
# valeur de token en clair.
FAKE_HASH = "$argon2id$v=19$m=65536,t=3,p=4$c2FsdHNhbHQ$k4j9PZ+hash=="
EXPIRY = datetime.now(timezone.utc) + timedelta(days=7)


def _make_token(user_id: str) -> RefreshToken:
    """Construit un RefreshToken valide pour un utilisateur donné."""
    return RefreshToken(user_id=user_id, token_hash=FAKE_HASH, expires_at=EXPIRY)


class TestRefreshTokenDefaults:
    """Cas nominaux : défauts et timestamps."""

    async def test_create_refresh_token_defaults(self, db_session, test_user) -> None:
        """Création avec defaults valides : id UUID, revoked_at NULL,
        created_at défini après flush."""
        token = _make_token(test_user.id)
        db_session.add(token)
        await db_session.flush()

        assert token.id is not None
        assert len(token.id) == 36, "id doit être un UUID String(36)"
        assert token.revoked_at is None, "un token frais doit être actif"
        assert token.created_at is not None
        assert token.updated_at is not None
        assert token.token_hash == FAKE_HASH
        assert token.expires_at == EXPIRY

    async def test_revoked_token_keeps_trace(self, db_session, test_user) -> None:
        """Un token révoqué porte revoked_at (trace auditable, AC 3)."""
        revoked_at = datetime.now(timezone.utc)
        token = _make_token(test_user.id)
        token.revoked_at = revoked_at
        db_session.add(token)
        await db_session.flush()

        assert token.revoked_at == revoked_at


class TestColumnBounds:
    """Bornes structurelles : token_hash String(255) (spec 06)."""

    def test_token_hash_max_length(self) -> None:
        """La colonne token_hash est bornée à String(255)."""
        column = RefreshToken.__table__.columns["token_hash"]
        assert column.type.length == 255
        assert not column.nullable

    async def test_token_hash_255_chars_accepted(self, db_session, test_user) -> None:
        """Un hash de 255 caractères (borne max) est accepté."""
        token = _make_token(test_user.id)
        token.token_hash = "x" * 255
        db_session.add(token)
        await db_session.flush()

        stored = (
            await db_session.execute(
                text(
                    "SELECT LENGTH(token_hash) FROM refresh_tokens " "WHERE id = :tid"
                ),
                {"tid": token.id},
            )
        ).scalar_one()
        assert stored == 255


class TestUserDeletionCascades:
    """CASCADE : suppression du user → purge de ses refresh tokens."""

    async def test_user_deletion_cascades(self, db_session, test_user) -> None:
        """Suppression du user → lignes refresh_tokens purgées."""
        db_session.add(_make_token(test_user.id))
        db_session.add(_make_token(test_user.id))
        await db_session.flush()

        count_before = (
            await db_session.execute(
                text("SELECT COUNT(*) FROM refresh_tokens " "WHERE user_id = :uid"),
                {"uid": test_user.id},
            )
        ).scalar_one()
        assert count_before == 2

        await db_session.delete(test_user)
        await db_session.flush()

        count_after = (
            await db_session.execute(text("SELECT COUNT(*) FROM refresh_tokens"))
        ).scalar_one()
        assert count_after == 0, "Les refresh tokens doivent être purgés"

    async def test_other_users_tokens_preserved(
        self, db_session, test_user, test_organization
    ) -> None:
        """Isolation : la purge d'un user ne touche pas les tokens d'un
        autre utilisateur."""
        other = User(
            email="other-refresh@example.com",
            username="other-refresh",
            hashed_password="h",
        )
        db_session.add(other)
        await db_session.flush()

        db_session.add(_make_token(test_user.id))
        db_session.add(_make_token(other.id))
        await db_session.flush()

        await db_session.delete(test_user)
        await db_session.flush()

        remaining = (await db_session.execute(select(RefreshToken))).scalars().all()
        assert len(remaining) == 1
        assert remaining[0].user_id == other.id


class TestReprSecurity:
    """Sécurité : __repr__ sans exposition du hash."""

    def test_repr_does_not_expose_hash(self) -> None:
        """__repr__ ne contient jamais la valeur du token_hash."""
        token = _make_token("00000000-0000-0000-0000-000000000001")
        representation = repr(token)

        assert FAKE_HASH not in representation
        assert "token_hash" not in representation
        assert "user_id=00000000-0000-0000-0000-000000000001" in representation
        assert "revoked=False" in representation

        token.revoked_at = datetime.now(timezone.utc)
        assert "revoked=True" in repr(token)

    def test_tablename(self) -> None:
        """__tablename__ == 'refresh_tokens' (convention spec 06)."""
        assert RefreshToken.__tablename__ == "refresh_tokens"

    def test_no_plaintext_column(self) -> None:
        """Garantie structurelle : aucune colonne pour une valeur en
        clair — seules les colonnes attendues existent (spec 06 +
        revoked_at)."""
        columns = set(RefreshToken.__table__.columns.keys())
        assert columns == {
            "id",
            "user_id",
            "token_hash",
            "expires_at",
            "revoked_at",
            "created_at",
            "updated_at",
        }


class TestRelationships:
    """Relation navigable User.refresh_tokens."""

    async def test_user_relationship_refresh_tokens(
        self, db_session, test_user
    ) -> None:
        """User.refresh_tokens navigable après flush d'un token."""
        db_session.add(_make_token(test_user.id))
        await db_session.flush()

        # Rechargement explicite (selectinload) : le lazy-loading est
        # interdit en contexte async (greenlet).
        user = (
            await db_session.execute(
                select(User).options(selectinload(User.refresh_tokens))
            )
        ).scalar_one()
        assert len(user.refresh_tokens) == 1
        assert user.refresh_tokens[0].token_hash == FAKE_HASH
