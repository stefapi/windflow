"""Service métier du cycle de vie des clés SSH réutilisables (STORY-131.2).

Centralise la logique des clés SSH (modèles STORY-131.1) : génération
serveur ed25519/RSA, import (avec passphrase de lecture uniquement),
consultation paginée, renommage, suppression contrôlée (jamais
silencieuse), suivi d'usage throttlé et résolution pour connexion.
Les endpoints (``api/v1/ssh_keys.py``) ne font qu'orchestrer ce service
— aucune logique métier côté HTTP (pattern ``api_key_service.py``).

Sécurité (rules 40, spec 15 § Hosts distants) :

- **Clé privée chiffrée au repos** : seule la colonne
  ``private_key_encrypted`` (token Fernet du SecretManager) est
  persistée — jamais une clé en clair ;
- **Affichage unique** : la clé privée en clair ne quitte le service
  que dans ``SSHKeyCreated`` (réponses 201 generate/import) ;
- **Dédup par empreinte** (invariant de service — la DB ne contraint
  que ``name``) : une même clé matérielle ne peut pas être enregistrée
  deux fois → 409 ``ConflictError`` ;
- **Suppression contrôlée** : refus 409 si des cibles référencent la
  clé, sauf ``force=True`` qui déréférence explicitement les cibles
  (``targets.ssh_key_id = NULL``) avant suppression — jamais de
  suppression silencieuse ;
- **Logs sans secret** : uniquement ``key_id``/``name``/``fingerprint``
  (public par nature) — jamais la clé privée ni la passphrase.

Arbitrages d'analyse STORY-131 (contexte de la story) :

- **Passphrase** : sert uniquement à lire la clé à l'import ; la clé
  est ensuite re-stockée **dé-passphrasée mais chiffrée** via le
  SecretManager (comportement standard d'un gestionnaire de clés) ;
- **Portée** : ``ssh_keys`` est une entité globale partagée (pas
  d'``organization_id`` en spec 06) — la protection repose sur
  ``require_admin`` côté API, l'isolation org est inapplicable par
  conception.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncssh
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.exceptions import (
    ConflictError,
    NotFoundError,
    UnprocessableEntityError,
)
from ..core.secret_manager import get_secret_manager
from ..models.ssh_key import SSHKey
from ..models.target import Target
from ..schemas.ssh_key import (
    SSHKeyGenerateRequest,
    SSHKeyImportRequest,
)

logger = logging.getLogger(__name__)

# Throttle de last_used_at : une seule écriture par fenêtre (pattern
# STORY-124.2 — évite une écriture SQL par session SSH réussie).
LAST_USED_THROTTLE_SECONDS = 60


def _utcnow_naive() -> datetime:
    """UTC now en naive — exclusif pour les clauses SQL (bind SQLite)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_key_material(key: asyncssh.SSHKey) -> dict[str, str]:
    """Exporte le matériau d'une clé asyncssh vers les colonnes du modèle.

    Args:
        key: Clé asyncssh générée ou importée (déjà dé-passphrasée).

    Returns:
        Dict ``{"public_key", "private_key_pem", "fingerprint", "key_type"}``
        — l'empreinte au format normalisé ``SHA256:<base64nopad>``.

    Raises:
        UnprocessableEntityError: Si l'export de la clé privée échoue
            (clé non exportable — n'est pas censé se produire pour les
            types proposés).
    """
    try:
        private_pem = key.export_private_key().decode("utf-8")
    except (asyncssh.KeyExportError, ValueError) as exc:
        # Garde défensive : n'expose jamais le matériau dans l'erreur.
        logger.warning("ssh_key.export_failed key_type=%s", key.get_algorithm())
        raise UnprocessableEntityError("Cette clé ne peut pas être importée") from exc
    return {
        "public_key": key.export_public_key().decode("utf-8").strip(),
        "private_key_pem": private_pem,
        # Divergence asyncssh documentée (131.1) : la lib expose
        # ``get_fingerprint()`` (pas d'attribut ``fingerprint``).
        "fingerprint": key.get_fingerprint(),
        "key_type": key.get_algorithm(),
    }


class SSHKeyService:
    """Service du cycle de vie des clés SSH (statique async)."""

    # ------------------------------------------------------------------
    # Création : génération serveur / import
    # ------------------------------------------------------------------

    @staticmethod
    async def generate(
        db: AsyncSession, data: SSHKeyGenerateRequest
    ) -> tuple[SSHKey, str]:
        """Génère une clé SSH côté serveur (ed25519 par défaut).

        La clé privée est chiffrée (Fernet) avant persistance ; sa
        valeur claire n'est retournée qu'ici (affichage unique —
        consommée par ``SSHKeyCreated``, STORY-131.2).

        Args:
            db: Session de base de données async.
            data: Payload de génération (nom + algorithme).

        Returns:
            Tuple ``(ligne persistée, clé privée PEM en clair)``.

        Raises:
            ConflictError: Nom ou empreinte déjà enregistré(e) (409).
        """
        key = asyncssh.generate_private_key(data.key_type)
        material = _normalize_key_material(key)
        row = SSHKey(
            name=data.name,
            key_type=material["key_type"],
            public_key=material["public_key"],
            private_key_encrypted=get_secret_manager().encrypt(
                material["private_key_pem"]
            ),
            fingerprint=material["fingerprint"],
        )
        await SSHKeyService._persist_new(db, row)
        logger.info(
            "ssh_key.generated key_id=%s name=%s key_type=%s",
            row.id,
            row.name,
            row.key_type,
        )
        return row, material["private_key_pem"]

    @staticmethod
    async def import_key(
        db: AsyncSession, data: SSHKeyImportRequest
    ) -> tuple[SSHKey, str]:
        """Importe une clé privée existante (PEM/OpenSSH).

        La passphrase éventuelle ne sert qu'à **lire** la clé ; la clé
        est ensuite re-stockée dé-passphrasée mais chiffrée via le
        SecretManager (arbitrage d'analyse — le secret au repos reste
        protégé AES-256/Fernet, et les connexions ultérieures n'ont
        plus besoin de la passphrase).

        Args:
            db: Session de base de données async.
            data: Payload d'import (nom, PEM, passphrase optionnelle).

        Returns:
            Tuple ``(ligne persistée, clé privée PEM dé-passphrasée)``.

        Raises:
            UnprocessableEntityError: PEM illisible ou passphrase
                incorrecte (422 ``VALIDATION_ERROR`` — message générique,
                jamais le matériau).
            ConflictError: Nom ou empreinte déjà enregistré(e) (409).
        """
        try:
            key = asyncssh.import_private_key(data.private_key, data.passphrase)
        except (
            asyncssh.KeyImportError,
            asyncssh.KeyEncryptionError,
            ValueError,
        ) as exc:
            # Message générique : ni le PEM ni la passphrase ne fuient
            # dans l'erreur ou les logs (rules 40).
            logger.warning(
                "ssh_key.import_rejected name=%s reason=unreadable_key",
                data.name,
            )
            raise UnprocessableEntityError(
                "Clé privée illisible ou passphrase incorrecte"
            ) from exc

        material = _normalize_key_material(key)
        row = SSHKey(
            name=data.name,
            key_type=material["key_type"],
            public_key=material["public_key"],
            private_key_encrypted=get_secret_manager().encrypt(
                material["private_key_pem"]
            ),
            fingerprint=material["fingerprint"],
        )
        await SSHKeyService._persist_new(db, row)
        logger.info(
            "ssh_key.imported key_id=%s name=%s key_type=%s",
            row.id,
            row.name,
            row.key_type,
        )
        return row, material["private_key_pem"]

    @staticmethod
    async def _persist_new(db: AsyncSession, row: SSHKey) -> None:
        """Commit d'une nouvelle clé avec vérification des unicités.

        La base ne contraint que ``name`` (spec 06) ; la dédup par
        **empreinte** est un invariant de service (une ``SSHKey`` par
        clé matérielle unique) vérifié ici avant persistance.

        Raises:
            ConflictError: Nom ou empreinte déjà enregistré(e).
        """
        dup_name = (
            await db.execute(select(SSHKey.id).where(SSHKey.name == row.name))
        ).scalar_one_or_none()
        if dup_name is not None:
            raise ConflictError(f"Une clé SSH nommée « {row.name} » existe déjà")

        dup_fp = (
            await db.execute(
                select(SSHKey.id).where(SSHKey.fingerprint == row.fingerprint)
            )
        ).scalar_one_or_none()
        if dup_fp is not None:
            raise ConflictError(
                "Cette clé SSH est déjà enregistrée (empreinte identique)"
            )

        db.add(row)
        await db.commit()
        await db.refresh(row)

    # ------------------------------------------------------------------
    # Consultation
    # ------------------------------------------------------------------

    @staticmethod
    async def get(db: AsyncSession, key_id: str) -> SSHKey:
        """Retourne une clé par son identifiant.

        Args:
            db: Session de base de données async.
            key_id: Identifiant de la clé.

        Returns:
            La ligne ``SSHKey`` correspondante.

        Raises:
            NotFoundError: Clé inexistante (404).
        """
        row = (
            await db.execute(select(SSHKey).where(SSHKey.id == key_id))
        ).scalar_one_or_none()
        if row is None:
            raise NotFoundError("SSH key", key_id)
        return row

    @staticmethod
    async def list_keys(
        db: AsyncSession, page: int = 1, per_page: int = 20
    ) -> list[tuple[SSHKey, int]]:
        """Liste les clés paginées avec leur nombre de cibles référençantes.

        Tri ``created_at desc`` (plus récentes d'abord — pattern
        STORY-128). Le comptage ``targets_count`` est porté par un
        ``LEFT JOIN`` groupé plutôt que par une requête N+1.

        Args:
            db: Session de base de données async.
            page: Page demandée (1-indexée, bornée par le Query endpoint).
            per_page: Taille de page (1-100, bornée par le Query endpoint).

        Returns:
            Liste de tuples ``(clé, nombre de cibles référençant la clé)``
            pour la page courante.
        """
        count_target = (
            select(func.count(Target.id))
            .where(Target.ssh_key_id == SSHKey.id)
            .correlate(SSHKey)
            .scalar_subquery()
        )
        rows = (
            await db.execute(
                select(SSHKey, count_target.label("targets_count"))
                .order_by(SSHKey.created_at.desc())
                .offset((page - 1) * per_page)
                .limit(per_page)
            )
        ).all()
        return [(row[0], int(row[1] or 0)) for row in rows]

    @staticmethod
    async def count(db: AsyncSession) -> int:
        """Compte l'ensemble des clés enregistrées (meta de pagination).

        Args:
            db: Session de base de données async.

        Returns:
            Nombre total de clés SSH.
        """
        result = await db.execute(select(func.count()).select_from(SSHKey))
        return int(result.scalar() or 0)

    @staticmethod
    async def targets_using(db: AsyncSession, key_id: str) -> list[str]:
        """Identifiants des cibles référençant la clé (suppression contrôlée).

        Args:
            db: Session de base de données async.
            key_id: Identifiant de la clé.

        Returns:
            Liste des ``targets.id`` avec ``ssh_key_id == key_id``.
        """
        rows = (
            (await db.execute(select(Target.id).where(Target.ssh_key_id == key_id)))
            .scalars()
            .all()
        )
        return list(rows)

    # ------------------------------------------------------------------
    # Renommage / suppression
    # ------------------------------------------------------------------

    @staticmethod
    async def rename(db: AsyncSession, key_id: str, new_name: str) -> SSHKey:
        """Renomme une clé (rotation = nouvelle clé, jamais de mutation).

        Args:
            db: Session de base de données async.
            key_id: Identifiant de la clé.
            new_name: Nouveau nom d'affichage unique.

        Returns:
            La ligne mise à jour.

        Raises:
            NotFoundError: Clé inexistante (404).
            ConflictError: Nom déjà pris par une autre clé (409).
        """
        row = await SSHKeyService.get(db, key_id)

        dup = (
            await db.execute(
                select(SSHKey.id).where(SSHKey.name == new_name, SSHKey.id != key_id)
            )
        ).scalar_one_or_none()
        if dup is not None:
            raise ConflictError(f"Une clé SSH nommée « {new_name} » existe déjà")

        row.name = new_name
        db.add(row)
        await db.commit()
        await db.refresh(row)
        logger.info("ssh_key.renamed key_id=%s name=%s", row.id, row.name)
        return row

    @staticmethod
    async def delete(db: AsyncSession, key_id: str, *, force: bool = False) -> int:
        """Supprime une clé — jamais silencieusement si référencée.

        Comportement (AC 1 de la story) :

        - des cibles référencent la clé et ``force=False`` → 409
          ``ConflictError`` (l'appelant doit déréférencer explicitement) ;
        - ``force=True`` → déréférencement explicite
          (``UPDATE targets SET ssh_key_id = NULL WHERE ...``) puis
          suppression de la clé (la FK ``SET NULL`` reste le garde-fou
          DB de dernier recours) ;
        - aucune référence → suppression directe.

        Args:
            db: Session de base de données async.
            key_id: Identifiant de la clé.
            force: Déréférencer explicitement les cibles avant
                suppression (défaut ``False``).

        Returns:
            Nombre de cibles déréférencées (0 si aucune).

        Raises:
            NotFoundError: Clé inexistante (404).
            ConflictError: Clé référencée par des cibles sans
                ``force=True`` (409).
        """
        row = await SSHKeyService.get(db, key_id)
        referencing = await SSHKeyService.targets_using(db, key_id)

        if referencing and not force:
            raise ConflictError(
                f"La clé SSH « {row.name} » est référencée par "
                f"{len(referencing)} cible(s) — déréférencez-les ou "
                "utilisez force=true"
            )

        dereferenced = 0
        if referencing:
            await db.execute(
                update(Target)
                .where(Target.ssh_key_id == key_id)
                .values(ssh_key_id=None)
                .execution_options(synchronize_session=False)
            )
            dereferenced = len(referencing)

        await db.delete(row)
        await db.commit()
        logger.info(
            "ssh_key.deleted key_id=%s name=%s dereferenced=%d",
            row.id,
            row.name,
            dereferenced,
        )
        return dereferenced

    # ------------------------------------------------------------------
    # Usage runtime (consommé par STORY-131.3)
    # ------------------------------------------------------------------

    @staticmethod
    async def touch_last_used(db: AsyncSession, key_id: str) -> None:
        """Alimente ``last_used_at`` (throttlé, best-effort).

        Une seule écriture par fenêtre
        ``LAST_USED_THROTTLE_SECONDS`` (condition SQL — pattern
        STORY-124.2). Toute défaillance est loggée puis avalée : cette
        métrique ne doit jamais bloquer une session SSH valide.

        Args:
            db: Session de base de données async.
            key_id: Identifiant de la clé utilisée avec succès.
        """
        try:
            now = _utcnow_naive()
            cutoff = now - timedelta(seconds=LAST_USED_THROTTLE_SECONDS)
            await db.execute(
                update(SSHKey)
                .where(
                    SSHKey.id == key_id,
                    (SSHKey.last_used_at.is_(None)) | (SSHKey.last_used_at < cutoff),
                )
                .values(last_used_at=now)
                .execution_options(synchronize_session=False)
            )
            await db.commit()
        except Exception:  # pragma: no cover - best-effort assumé
            await db.rollback()
            logger.warning("ssh_key.last_used_update_failed key_id=%s", key_id)

    @staticmethod
    async def resolve_for_target(db: AsyncSession, target: Target) -> dict[str, Any]:
        """Résout les kwargs asyncssh d'authentification par clé d'une cible.

        Priorité : ``target.ssh_key_id`` (entité réutilisable —
        STORY-131.1) puis, à défaut, le matériau legacy éventuel des
        credentials chiffrées (double lecture, STORY-103.2). La clé
        privée déchiffrée ne vit qu'en mémoire (jamais loggée).

        Args:
            db: Session de base de données async.
            target: Cible à accès SSH.

        Returns:
            Kwargs ``{"client_keys": [asyncssh.SSHKey], ...}`` pour
            ``asyncssh.connect`` — clé **re-importée depuis le PEM
            déchiffré** (sans passphrase : le re-stockage 131.2 est
            dé-passphrasé).

        Raises:
            NotFoundError: La clé référencée n'existe plus (FK SET NULL
                la garde en principe cohérente — garde défensive).
        """
        private_pem: Optional[str] = None

        if target.ssh_key_id is not None:
            row = await SSHKeyService.get(db, target.ssh_key_id)
            private_pem = row.decrypted_private_key
        else:
            credentials = target.decrypted_credentials
            legacy_key = credentials.get("ssh_private_key")
            if isinstance(legacy_key, str) and legacy_key.strip():
                private_pem = legacy_key

        if private_pem is None:
            return {}

        try:
            client_key = asyncssh.import_private_key(private_pem)
        except asyncssh.KeyImportError:  # pragma: no cover - garde défensive
            logger.error(
                "ssh_key.resolve_failed key_id=%s target_id=%s",
                target.ssh_key_id,
                target.id,
            )
            return {}

        if target.ssh_key_id is not None:
            await SSHKeyService.touch_last_used(db, target.ssh_key_id)
        return {"client_keys": [client_key]}
