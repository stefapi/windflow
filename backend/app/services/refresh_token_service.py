"""Service métier du cycle de vie des refresh tokens opaques (STORY-123.2).

Centralise toute la logique de ``refresh_tokens`` (modèle STORY-123.1) :
création par hash, vérification, **rotation à chaque usage** avec
révocation défensive de la famille, révocation unitaire/globale et purge.
Les endpoints auth (STORY-123.3) et le job de purge (STORY-123.4) ne
doivent qu'orchestrer ce service — aucune logique métier côté HTTP.

Sécurité (rules 40) :
- **Isolation par hash** : un token soumis ne résout que sa ligne (et
  donc son utilisateur) — jamais l'inverse ;
- **Anti-DoS** : tout token soumis est validé (non vide, ``<= 512``
  caractères) **avant** tout hachage Argon2 ;
- **Réutilisation d'un token consommé** → refus **et** révocation
  défensive de tous les tokens de l'utilisateur (spec 07 § rotation) ;
- **Logs** : jamais de valeur de token (claire ou hash) — uniquement
  ``user_id`` et identifiants de lignes.

Hash (arbitrage n°1 tranché en STORY-123.1) : Argon2 via le
``pwd_context`` passlib existant — zéro dépendance nouvelle. Le lookup
par ``token_hash`` exige un hash **déterministe** : le sel n'est donc pas
aléatoire mais **dérivé du token** (HMAC-SHA256 de la clé serveur) — un
attaquant qui lit la base ne peut pas reconstituer le token (Argon2
reste unilatéral), et deux émissions du même token produisent la même
ligne de hash.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Union, cast

from sqlalchemy import CursorResult, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import generate_refresh_token
from ..config import settings
from ..core.exceptions import InvalidRefreshTokenError
from ..models.refresh_token import RefreshToken
from .user_service import pwd_context

logger = logging.getLogger(__name__)

# Borne anti-DoS : tout token soumis au-delà de cette longueur est refusé
# avant tout hachage Argon2 (coûteux en CPU/mémoire).
MAX_TOKEN_LENGTH = 512

# Rétention des lignes révoquées/expirées avant purge (jours) — fenêtre
# d'audit courte ; les lignes actives ne sont JAMAIS purgées.
REVOKED_RETENTION_DAYS = 7


# InvalidRefreshTokenError (core/exceptions.py — hérite de WindFlowException,
# rules 30) est ré-exportée ici pour la commodité des appelants STORY-123.3 :
# refus sémantique 401 sans divulgation de la raison exacte.
__all__ = ["RefreshTokenService", "InvalidRefreshTokenError"]


def _hash_token(token_plain: str) -> str:
    """Hache un refresh token en Argon2 **déterministe** (lookup possible).

    Le sel est dérivé du token lui-même : HMAC-SHA256 keyed avec la clé
    serveur (``jwt_secret_key``) — le hash reste déterministe (deux
    émissions du même token → même ``token_hash``, requis pour le lookup
    ``WHERE token_hash = :h``) tout en dépendant du secret serveur : une
    fuite isolée de la base ne permet pas de forger des hashes valides
    pour un autre déploiement.

    Args:
        token_plain: Valeur claire du token (déjà validée en longueur)

    Returns:
        Hash Argon2 (~97 caractères, ``String(255)`` du modèle)
    """
    salt = hmac.new(
        settings.jwt_secret_key.encode(), token_plain.encode(), hashlib.sha256
    ).digest()[:16]
    handler = pwd_context.handler().using(salt=salt)  # type: ignore[union-attr]
    return str(handler.hash(token_plain))


def _validate_token_shape(token_plain: str) -> None:
    """Valide la forme du token soumis avant tout hachage (anti-DoS).

    Raises:
        InvalidRefreshTokenError: Token vide ou au-delà de 512 caractères.
    """
    if not token_plain or len(token_plain) > MAX_TOKEN_LENGTH:
        raise InvalidRefreshTokenError()


def _as_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Normalise un datetime en aware UTC (SQLite stocke en naive)."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _utcnow_naive() -> datetime:
    """UTC now en naive — exclusif pour les clauses SQL (bind SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class RefreshTokenService:
    """Service du cycle de vie des refresh tokens opaques (statique async)."""

    @staticmethod
    async def create(db: AsyncSession, user_id: str, token_plain: str) -> RefreshToken:
        """Persiste le hash d'un refresh token fraîchement émis.

        Durée de vie : ``settings.refresh_token_expire_days`` (7 j par
        défaut, STORY-123.1). La valeur claire n'est jamais loggée ni
        stockée (garantie structurelle du modèle).

        Args:
            db: Session de base de données async
            user_id: Propriétaire du token
            token_plain: Valeur claire émise par ``create_token_pair``

        Returns:
            Ligne ``RefreshToken`` créée (active, ``revoked_at`` NULL)
        """
        _validate_token_shape(token_plain)
        token_hash = _hash_token(token_plain)
        expires_at = datetime.now(timezone.utc) + timedelta(
            days=settings.refresh_token_expire_days
        )

        row = RefreshToken(
            id=str(uuid.uuid4()),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        logger.info(
            "refresh_token.created user_id=%s token_id=%s expires_at=%s",
            user_id,
            row.id,
            expires_at.isoformat(),
        )
        return row

    @staticmethod
    async def verify(db: AsyncSession, token_plain: str) -> RefreshToken:
        """Résout la ligne d'un refresh token par hash (isolation).

        Refuse les tokens inconnus, expirés (``expires_at`` dépassé) et
        consommés/révoqués (``revoked_at`` non nul). Un token **consommé**
        réutilisé déclenche la **révocation défensive de la famille**
        (comportement partagé avec ``rotate`` — un token déjà révoqué ne
        peut pas servir à nouveau, spec 07 § rotation).

        Args:
            db: Session de base de données async
            token_plain: Valeur claire soumise

        Returns:
            Ligne ``RefreshToken`` valide et active

        Raises:
            InvalidRefreshTokenError: Token invalide/expiré/consommé/inconnu
        """
        _validate_token_shape(token_plain)
        token_hash = _hash_token(token_plain)

        row = (
            await db.execute(
                select(RefreshToken).where(RefreshToken.token_hash == token_hash)
                # Recharge les attributs même si un objet expiré traîne
                # en identity_map (refresh IO interdit hors greenlet).
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

        if row is None:
            raise InvalidRefreshTokenError()

        # Captures AVANT toute révocation bulk (qui expire les objets en
        # session — les attributs ne seraient plus accessibles sans IO).
        user_id, token_id = row.user_id, row.id
        now = datetime.now(timezone.utc)
        expires_at = _as_utc(row.expires_at)
        revoked_at = _as_utc(row.revoked_at)

        if revoked_at is not None:
            # Token consommé réutilisé → défense : toute la famille tombe
            await RefreshTokenService.revoke_all_for_user(db, user_id)
            logger.warning(
                "refresh_token.reuse_detected user_id=%s token_id=%s "
                "family_revoked=True",
                user_id,
                token_id,
            )
            raise InvalidRefreshTokenError()

        if expires_at is not None and expires_at <= now:
            raise InvalidRefreshTokenError()

        return row

    @staticmethod
    async def rotate(db: AsyncSession, token_plain: str) -> tuple[RefreshToken, str]:
        """Consomme un refresh token et en émet un nouveau (rotation).

        Atomique en une transaction session :
        1. résolution par hash (refus si inconnu/expiré/consommé — un
           consommé réutilisé révoque défensivement toute la famille) ;
        2. ``revoked_at`` posé sur l'ancienne ligne (token consommé) ;
        3. émission d'un nouveau token opaque + création de sa ligne ;
        4. commit unique des deux écritures.

        Args:
            db: Session de base de données async
            token_plain: Valeur claire du token courant

        Returns:
            Tuple (nouvelle ligne active, nouvelle valeur claire)

        Raises:
            InvalidRefreshTokenError: Token invalide/expiré/consommé/inconnu
        """
        current = await RefreshTokenService.verify(db, token_plain)

        # Marquer l'ancien token comme consommé (même transaction que la
        # création du nouveau — commit dans ``create``).
        current.revoked_at = datetime.now(timezone.utc)
        db.add(current)

        new_plain = generate_refresh_token()
        new_row = await RefreshTokenService.create(db, current.user_id, new_plain)

        logger.info(
            "refresh_token.rotated user_id=%s old_token_id=%s new_token_id=%s",
            current.user_id,
            current.id,
            new_row.id,
        )
        return new_row, new_plain

    @staticmethod
    async def revoke(db: AsyncSession, token_plain: str) -> bool:
        """Révoque la ligne résolue par hash (idempotent).

        Args:
            db: Session de base de données async
            token_plain: Valeur claire du token à révoquer

        Returns:
            ``True`` si une ligne a été trouvée (et révoquée si besoin),
            ``False`` si le token est inconnu (logout tolérant).
        """
        if not token_plain or len(token_plain) > MAX_TOKEN_LENGTH:
            return False
        token_hash = _hash_token(token_plain)

        row = (
            await db.execute(
                select(RefreshToken)
                .where(RefreshToken.token_hash == token_hash)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()

        if row is None:
            return False

        if row.revoked_at is None:
            row.revoked_at = datetime.now(timezone.utc)
            db.add(row)
            await db.commit()
            logger.info(
                "refresh_token.revoked user_id=%s token_id=%s",
                row.user_id,
                row.id,
            )
        return True

    @staticmethod
    async def revoke_all_for_user(
        db: AsyncSession, user_id: Union[str, uuid.UUID]
    ) -> int:
        """Révoque globalement tous les tokens actifs d'un utilisateur.

        Consommé par ``/logout`` (révocation globale selon l'arbitrage
        n°2, STORY-123.3), par le changement de mot de passe
        (STORY-129) et par la défense anti-réutilisation (``verify``).

        Args:
            db: Session de base de données async
            user_id: Utilisateur cible

        Returns:
            Nombre de lignes révoquées par cette invocation
        """
        user_id_str = str(user_id) if isinstance(user_id, uuid.UUID) else user_id

        # ``rowcount`` n'existe que sur ``CursorResult`` (retour réel des
        # UPDATE/DELETE) — le type annoncé de ``execute`` est plus large.
        result = cast(
            CursorResult,
            await db.execute(
                update(RefreshToken)
                .where(
                    RefreshToken.user_id == user_id_str,
                    RefreshToken.revoked_at.is_(None),
                )
                .values(revoked_at=_utcnow_naive())
                .execution_options(synchronize_session=False)
            ),
        )
        # L'UPDATE bulk ignore les objets déjà chargés en session : on
        # expire leur état pour qu'une relecture voie ``revoked_at`` posé.
        for obj in db.identity_map.values():
            if isinstance(obj, RefreshToken):
                db.expire(obj)
        await db.commit()
        count = result.rowcount or 0
        if count:
            logger.info(
                "refresh_token.revoked_all user_id=%s count=%d",
                user_id_str,
                count,
            )
        return count

    @staticmethod
    async def purge_expired(db: AsyncSession) -> int:
        """Supprime les lignes expirées ou révoquées au-delà de la rétention.

        Sont purgées (fenêtre d'audit ``REVOKED_RETENTION_DAYS``) :
        - les lignes **expirées** (``expires_at <= now``) ;
        - les lignes **révoquées** depuis plus de la rétention.

        Les lignes actives ne sont jamais touchées. Implémentation
        consommée par le job de purge (STORY-123.4).

        Args:
            db: Session de base de données async

        Returns:
            Nombre de lignes supprimées
        """
        now = _utcnow_naive()
        retention_cutoff = now - timedelta(days=REVOKED_RETENTION_DAYS)

        expired_result = cast(
            CursorResult,
            await db.execute(
                delete(RefreshToken)
                .where(RefreshToken.expires_at <= now)
                .execution_options(synchronize_session=False)
            ),
        )
        expired_count = expired_result.rowcount or 0

        revoked_result = cast(
            CursorResult,
            await db.execute(
                delete(RefreshToken)
                .where(
                    RefreshToken.revoked_at.is_not(None),
                    RefreshToken.revoked_at <= retention_cutoff,
                )
                .execution_options(synchronize_session=False)
            ),
        )
        revoked_count = revoked_result.rowcount or 0
        await db.commit()

        total = expired_count + revoked_count
        if total:
            logger.info(
                "refresh_token.purged expired=%d revoked=%d total=%d",
                expired_count,
                revoked_count,
                total,
            )
        return total
