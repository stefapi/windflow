"""Service métier du cycle de vie des clés API ``wf_ak_`` (STORY-124.2).

Centralise toute la logique des clés API (modèle STORY-124.1) :
création par hash, listing scopé, révocation idempotente et
vérification par hash avec alimentation throttlée de
``last_used_at``. Les endpoints (STORY-124.3) et les tests
transverses (STORY-124.4) ne doivent qu'orchestrer ce service —
aucune logique métier côté HTTP.

Sécurité (rules 40) :
- **Isolation par hash** : une clé soumise ne résout que sa ligne (et
  donc son propriétaire) — jamais l'inverse ;
- **Anti-DoS** : toute clé soumise est validée en forme (préfixe
  ``wf_ak_``, longueur exacte ``MAX_API_KEY_LENGTH``) **avant** tout
  hachage Argon2 ;
- **Anti-énumération** : refus sémantique 401 générique — le message
  client ne distingue jamais « clé inconnue » de « clé
  révoquée/expirée » (``InvalidApiKeyError``) ; une clé étrangère en
  révocation est traitée comme inexistante (``NotFoundError`` → 404) ;
- **Logs** : jamais la clé ni son hash — uniquement ``user_id`` et
  ``key_id`` (events ``api_key.created / revoked / auth_failed``).

Hash (arbitrage n°1, aligné sur F2/STORY-123) : Argon2 via le
``pwd_context`` passlib existant — zéro dépendance nouvelle. Le lookup
par ``key_hash`` exige un hash **déterministe** : le sel n'est pas
aléatoire mais **dérivé de la clé** (HMAC-SHA256 de la clé serveur) —
un attaquant qui lit la base ne peut pas reconstituer la clé (Argon2
reste unilatéral), et le même ``key_hash`` est retrouvé à chaque
vérification.

``last_used_at`` (arbitrage n°3) : alimenté de façon **throttlée**
(max 1 écriture/minute par clé, condition SQL) et **best-effort** —
une défaillance de cette écriture ne fait jamais échouer
l'authentification.
"""

from __future__ import annotations

import hashlib
import hmac
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..auth.jwt import API_KEY_PREFIX, MAX_API_KEY_LENGTH, generate_api_key
from ..config import settings
from ..core.exceptions import InvalidApiKeyError, NotFoundError
from ..models.api_key import APIKey
from ..models.user import User
from ..schemas.api_key import APIKeyCreate, APIKeyCreated, APIKeyResponse
from .user_service import pwd_context

logger = logging.getLogger(__name__)

# Throttle de last_used_at : une seule écriture par fenêtre (arbitrage
# n°3 — évite une écriture SQL par requête authentifiée par clé).
LAST_USED_THROTTLE_SECONDS = 60

# Ré-export pour la commodité des appelants STORY-124.3 (refus
# sémantique 401 / 404 sans divulgation).
__all__ = [
    "ApiKeyService",
    "InvalidApiKeyError",
    "NotFoundError",
    "LAST_USED_THROTTLE_SECONDS",
]


def _hash_key(key_plain: str) -> str:
    """Hache une clé API en Argon2 **déterministe** (lookup possible).

    Le sel est dérivé de la clé elle-même : HMAC-SHA256 keyed avec la
    clé serveur (``jwt_secret_key``) — le hash reste déterministe (la
    même clé produit toujours le même ``key_hash``, requis pour le
    lookup ``WHERE key_hash = :h``) tout en dépendant du secret
    serveur : une fuite isolée de la base ne permet pas de forger des
    hashes valides pour un autre déploiement.

    Args:
        key_plain: Valeur claire de la clé (déjà validée en forme)

    Returns:
        Hash Argon2 (~97 caractères, ``String(255)`` du modèle)
    """
    salt = hmac.new(
        settings.jwt_secret_key.encode(), key_plain.encode(), hashlib.sha256
    ).digest()[:16]
    handler = pwd_context.handler().using(salt=salt)  # type: ignore[union-attr]
    return str(handler.hash(key_plain))


def _validate_key_shape(key_plain: str) -> None:
    """Valide la forme de la clé soumise avant tout hachage (anti-DoS).

    Une clé émise fait exactement ``wf_ak_`` + 48 caractères base64url
    (``MAX_API_KEY_LENGTH`` au total) — tout écart est rejeté **avant**
    d'encourir le coût Argon2.

    Raises:
        InvalidApiKeyError: Clé vide, mal préfixée ou de longueur inexacte.
    """
    if (
        not key_plain
        or not key_plain.startswith(API_KEY_PREFIX)
        or len(key_plain) != MAX_API_KEY_LENGTH
    ):
        raise InvalidApiKeyError()


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


def _to_naive_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Convertit un datetime client en naive UTC pour stockage SQLite."""
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


class ApiKeyService:
    """Service du cycle de vie des clés API ``wf_ak_`` (statique async)."""

    @staticmethod
    async def create(
        db: AsyncSession, user_id: str, data: APIKeyCreate
    ) -> APIKeyCreated:
        """Crée une clé API — la valeur claire n'est retournée qu'ici.

        Génère ``wf_ak_`` + 48 caractères (entropie ~288 bits), persiste
        uniquement son hash déterministe et retourne ``APIKeyCreated``
        portant la clé brute : c'est l'**unique** occasion de la voir
        (affichage unique, spec 07 — jamais stockée ni loggée).

        Args:
            db: Session de base de données async
            user_id: Propriétaire de la clé
            data: Payload de création (libellé + expiration optionnelle)

        Returns:
            Schéma ``APIKeyCreated`` (métadonnées + clé brute une fois)
        """
        key_plain = generate_api_key()
        row = APIKey(
            user_id=user_id,
            name=data.name,
            key_hash=_hash_key(key_plain),
            expires_at=_to_naive_utc(data.expires_at),
        )
        db.add(row)
        await db.commit()
        await db.refresh(row)
        logger.info(
            "api_key.created user_id=%s key_id=%s",
            user_id,
            row.id,
        )
        return APIKeyCreated(
            id=row.id,
            name=row.name,
            expires_at=row.expires_at,
            last_used_at=row.last_used_at,
            revoked=row.revoked,
            created_at=row.created_at,
            key=key_plain,
        )

    @staticmethod
    async def list_for_user(
        db: AsyncSession, user_id: str, page: int = 1, per_page: int = 20
    ) -> list[APIKeyResponse]:
        """Liste les clés d'un utilisateur (scopé, sans secrets), paginées
        (STORY-128).

        Les clés **expirées restent listées** avec leur ``expires_at``
        visible, ``revoked`` restant distinct de l'expiration
        (arbitrage n°2). Jamais ``key_hash`` ni la valeur de clé dans
        les réponses. Tri ``created_at desc`` conservé (plus récentes
        d'abord).

        Args:
            db: Session de base de données async
            user_id: Propriétaire (scoping obligatoire)
            page: Page demandée (1-indexée, bornée par le Query endpoint)
            per_page: Taille de page (1-100, bornée par le Query endpoint)

        Returns:
            Clés de la page, les plus récentes d'abord
        """
        rows = (
            (
                await db.execute(
                    select(APIKey)
                    .where(APIKey.user_id == user_id)
                    .order_by(APIKey.created_at.desc())
                    .offset((page - 1) * per_page)
                    .limit(per_page)
                )
            )
            .scalars()
            .all()
        )
        return [APIKeyResponse.model_validate(row) for row in rows]

    @staticmethod
    async def count_for_user(db: AsyncSession, user_id: str) -> int:
        """Compte les clés d'un utilisateur (STORY-128).

        ``COUNT`` avec le **même scoping propriétaire** que
        :meth:`list_for_user` (rules 40 — pas d'oracle de comptage
        cross-user).

        Args:
            db: Session de base de données async
            user_id: Propriétaire (scoping obligatoire)

        Returns:
            Nombre total de clés de l'utilisateur
        """
        result = await db.execute(
            select(func.count()).select_from(APIKey).where(APIKey.user_id == user_id)
        )
        return int(result.scalar() or 0)

    @staticmethod
    async def revoke(db: AsyncSession, user_id: str, key_id: str) -> APIKeyResponse:
        """Révoque une clé API (scopé propriétaire, idempotent).

        Une clé étrangère ou introuvable lève ``NotFoundError`` (→ 404
        côté API, sans révéler l'existence de la clé d'autrui).
        Révoquer une clé déjà révoquée est un succès no-op qui retourne
        l'état courant.

        Args:
            db: Session de base de données async
            user_id: Propriétaire demandant la révocation (scoping)
            key_id: Identifiant de la clé à révoquer

        Returns:
            Schéma ``APIKeyResponse`` de la clé dans son état final

        Raises:
            NotFoundError: Clé inexistante ou appartenant à un autre user
        """
        row = (
            await db.execute(
                select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user_id)
            )
        ).scalar_one_or_none()

        if row is None:
            raise NotFoundError("API key", key_id)

        if not row.revoked:
            row.revoked = True
            db.add(row)
            await db.commit()
            await db.refresh(row)
            logger.info(
                "api_key.revoked user_id=%s key_id=%s",
                user_id,
                key_id,
            )
        return APIKeyResponse.model_validate(row)

    @staticmethod
    async def verify(db: AsyncSession, key_plain: str) -> User:
        """Authentifie par clé API et retourne le propriétaire actif.

        Validation de forme **avant** hachage (anti-DoS), puis lookup
        par hash déterministe. Refus (``InvalidApiKeyError``, 401
        générique anti-énumération) si : clé inconnue / révoquée /
        expirée / propriétaire inactif. En succès, alimente
        ``last_used_at`` de façon **throttlée** (max 1 écriture/minute)
        et **best-effort** — hors du chemin critique de la réponse.

        Args:
            db: Session de base de données async
            key_plain: Valeur claire soumise (header ``X-API-Key`` ou
                ``Authorization: Bearer wf_ak_…`` — résolu en 124.3)

        Returns:
            Le ``User`` propriétaire actif de la clé

        Raises:
            InvalidApiKeyError: Clé malformée, inconnue, révoquée,
                expirée ou propriétaire inactif
        """
        _validate_key_shape(key_plain)
        key_hash = _hash_key(key_plain)

        pair = (
            await db.execute(
                select(APIKey, User)
                .join(User, APIKey.user_id == User.id)
                .where(APIKey.key_hash == key_hash)
                # Recharge les attributs même si un objet traîne en
                # identity_map (refresh IO interdit hors greenlet).
                .execution_options(populate_existing=True)
            )
        ).first()

        if pair is None:
            logger.warning("api_key.auth_failed user_id=None reason=unknown")
            raise InvalidApiKeyError()

        row, owner = pair
        user_id, key_id = row.user_id, row.id

        if row.revoked:
            logger.warning(
                "api_key.auth_failed user_id=%s key_id=%s reason=revoked",
                user_id,
                key_id,
            )
            raise InvalidApiKeyError()

        now = datetime.now(timezone.utc)
        expires_at = _as_utc(row.expires_at)
        if expires_at is not None and expires_at <= now:
            logger.warning(
                "api_key.auth_failed user_id=%s key_id=%s reason=expired",
                user_id,
                key_id,
            )
            raise InvalidApiKeyError()

        if not owner.is_active:
            logger.warning(
                "api_key.auth_failed user_id=%s key_id=%s reason=owner_inactive",
                user_id,
                key_id,
            )
            raise InvalidApiKeyError()

        await ApiKeyService._touch_last_used(db, key_id)
        return owner

    @staticmethod
    async def _touch_last_used(db: AsyncSession, key_id: str) -> None:
        """Alimente ``last_used_at`` (throttlé, best-effort).

        Une seule écriture par fenêtre ``LAST_USED_THROTTLE_SECONDS``
        (condition SQL ``last_used_at IS NULL OR last_used_at <
        now - 60s`` — arbitrage n°3). Toute défaillance est loggée puis
        avalée : cette métrique ne doit jamais bloquer une
        authentification valide.

        Args:
            db: Session de base de données async
            key_id: Identifiant de la clé utilisée avec succès
        """
        try:
            now = _utcnow_naive()
            cutoff = now - timedelta(seconds=LAST_USED_THROTTLE_SECONDS)
            await db.execute(
                update(APIKey)
                .where(
                    APIKey.id == key_id,
                    (APIKey.last_used_at.is_(None)) | (APIKey.last_used_at < cutoff),
                )
                .values(last_used_at=now)
                .execution_options(synchronize_session=False)
            )
            await db.commit()
        except Exception:  # pragma: no cover - best-effort assumé
            await db.rollback()
            logger.warning("api_key.last_used_update_failed key_id=%s", key_id)
