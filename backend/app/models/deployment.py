"""
Modèle Deployment pour suivi des déploiements de stacks.

STORY-103.3 : les valeurs des variables d'environnement sensibles des
snapshots (``config`` / ``variables``) sont chiffrées au repos via le
SecretManager (clé conservée en clair, valeur chiffrée — token Fernet
préfixe ``gAAAA``), et déchiffrées uniquement en mémoire au moment du
rendu/déploiement.
"""

import re
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from sqlalchemy import JSON, DateTime
from sqlalchemy import Enum as SQLEnum
from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from ..core.secret_manager import SecretManager, get_secret_manager
from ..database import Base

if TYPE_CHECKING:
    from .host import Host
    from .organization import Organization
    from .stack import Stack

# Heuristique de sensibilité — même règle que la détection des secrets
# d'environnement de l'adoption (adoption_service._SECRET_PATTERNS) et du
# typage des variables (docker_compose_service._infer_variable_type) :
# une variable dont le nom matche ces mots est considérée sensible.
_SENSITIVE_VARIABLE_PATTERN = re.compile(
    r"(?i)(PASSWORD|SECRET|TOKEN|API_KEY|PRIVATE|CREDENTIAL|AUTH_KEY|ACCESS_KEY)"
)


def is_sensitive_variable(name: str) -> bool:
    """Retourne True si le nom de variable semble être un secret.

    Args:
        name: Nom de la variable (clé du dict de variables).

    Returns:
        True si le nom matche l'heuristique (PASSWORD, SECRET, TOKEN,
        API_KEY, PRIVATE, CREDENTIAL, AUTH_KEY, ACCESS_KEY).
    """
    return bool(_SENSITIVE_VARIABLE_PATTERN.search(name))


def _has_unencrypted_sensitive_values(stored: dict[str, Any]) -> bool:
    """Détecte si un snapshot contient encore des valeurs sensibles en clair.

    Utilisé par la migration double lecture : un snapshot est « legacy » si
    au moins une valeur sensible (nom sensible, chaîne non vide) n'est pas
    un ciphertext Fernet. La comparaison ne peut PAS se faire sur les
    ciphertexts eux-mêmes (Fernet produit un token différent à chaque
    chiffrement — timestamp/IV aléatoires).

    Args:
        stored: Valeur de la colonne snapshot.

    Returns:
        True si au moins une valeur sensible est stockée en clair.
    """
    return any(
        isinstance(value, str)
        and value
        and is_sensitive_variable(key)
        and not SecretManager.is_encrypted(value)
        for key, value in stored.items()
    )


def encrypt_variables_for_storage(plain: dict[str, Any]) -> dict[str, Any]:
    """Chiffre les valeurs sensibles d'un snapshot de variables (STORY-103.3).

    Stratégie « clé conservée, valeur chiffrée » : les clés restent lisibles
    (l'UI peut lister les noms de variables), seules les valeurs dont le nom
    matche l'heuristique de sensibilité sont remplacées par un token Fernet
    (préfixe ``gAAAA``). Pas de migration de schéma, compatible double
    lecture. Idempotent : une valeur déjà chiffrée (token détecté) ou non
    sensible est laissée telle quelle.

    Args:
        plain: Snapshot de variables en clair (jamais loggé).

    Returns:
        Copie du dict où les valeurs sensibles sont des tokens Fernet.
    """
    manager = get_secret_manager()
    stored: dict[str, Any] = {}
    for key, value in plain.items():
        if (
            isinstance(value, str)
            and value
            and is_sensitive_variable(key)
            and not SecretManager.is_encrypted(value)
        ):
            stored[key] = manager.encrypt(value)
        else:
            stored[key] = value
    return stored


def decrypt_variables_from_storage(stored: dict[str, Any]) -> dict[str, Any]:
    """Déchiffre les valeurs d'un snapshot de variables (double lecture).

    Args:
        stored: Valeur de la colonne ``variables`` (ou ``config``) du
            déploiement.

    Returns:
        Snapshot avec valeurs sensibles déchiffrées — en mémoire uniquement,
        ne jamais logger ni écrire sur disque.

    Raises:
        SecretDecryptionError: Si un ciphertext est illisible (mauvaise
            clé maîtresse ou donnée corrompue/altérée).
    """
    manager = get_secret_manager()
    decrypted: dict[str, Any] = {}
    for key, value in stored.items():
        if isinstance(value, str) and SecretManager.is_encrypted(value):
            decrypted[key] = manager.decrypt(value)
        else:
            decrypted[key] = value
    return decrypted


class DeploymentStatus(str, Enum):
    """Statuts possibles pour un déploiement."""

    PENDING = "pending"
    DEPLOYING = "deploying"
    RUNNING = "running"
    FAILED = "failed"
    STOPPED = "stopped"
    ROLLING_BACK = "rolling_back"


class Deployment(Base):
    """
    Modèle déploiement pour tracking des stacks déployées.

    Représente l'instance d'une stack déployée sur une cible.
    """

    __tablename__ = "deployments"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Relations avec stack et host (STORY-166.1 : target_id renommée host_id)
    stack_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("stacks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    host_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("hosts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Alias de transition (purge STORY-166.6) : les services/API non encore
    # renommés continuent d'écrire/lire ``target_id`` — même colonne hosts.
    target_id = synonym("host_id")

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Informations de déploiement
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    # Statut
    status: Mapped[DeploymentStatus] = mapped_column(
        SQLEnum(DeploymentStatus), nullable=False, default=DeploymentStatus.PENDING
    )

    # Configuration utilisée au déploiement (snapshot)
    config: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Container ID (pour les déploiements Docker)
    container_id: Mapped[str] = mapped_column(
        String(128),
        nullable=True,
        index=True,
        comment="ID du conteneur Docker créé par ce déploiement",
    )

    # Variables appliquées
    variables: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)

    # Paramètres de target rendus (snapshot des target_parameters du stack avec variables Jinja résolues)
    rendered_target_parameters: Mapped[dict] = mapped_column(
        JSON,
        nullable=True,
        default=None,
        comment="Target parameters rendus avec Jinja lors de la création du déploiement",
    )

    # Logs et erreurs
    logs: Mapped[str] = mapped_column(Text, nullable=True)
    error_message: Mapped[str] = mapped_column(Text, nullable=True)

    # Task tracking (pour asyncio orchestrator)
    task_started_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    task_retry_count: Mapped[int] = mapped_column(nullable=False, default=0)

    # Métriques
    deploy_duration_seconds: Mapped[float] = mapped_column(nullable=True)

    # Timestamps
    deployed_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    stopped_at: Mapped[datetime] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Relations
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="deployments"
    )

    stack: Mapped["Stack"] = relationship("Stack", back_populates="deployments")

    host: Mapped["Host"] = relationship("Host", back_populates="deployments")
    # Alias de transition : relation legacy ``target`` (purge STORY-166.6).
    target = synonym("host")

    # ─── Snapshots : accès déchiffré + migration double lecture ──────

    def _decrypt_snapshot_in_place(self, column: str) -> dict[str, Any]:
        """Déchiffre un snapshot JSON avec migration double lecture.

        Double lecture :
        - valeurs chiffrées (token Fernet préfixe ``gAAAA``) → déchiffrement
          à la volée ;
        - ligne legacy avec valeurs sensibles en clair → lue telle quelle,
          puis **ré-encryptée au premier accès** : la réassignation de
          l'attribut marque la colonne *dirty* pour SQLAlchemy, la migration
          est donc persistée par le commit de l'appelant (idempotent).

        Args:
            column: Nom de l'attribut (``"variables"`` ou ``"config"``).

        Returns:
            Snapshot déchiffré — en mémoire uniquement, ne jamais logger.

        Raises:
            SecretDecryptionError: Si un ciphertext est illisible (mauvaise
                clé maîtresse ou donnée corrompue/altérée).
        """
        stored = getattr(self, column)
        if not isinstance(stored, dict) or not stored:
            return stored or {}
        decrypted = decrypt_variables_from_storage(stored)
        if _has_unencrypted_sensitive_values(stored):
            # Ligne legacy en clair (au moins une valeur sensible non
            # chiffrée) → ré-encryptage au premier accès.
            setattr(self, column, encrypt_variables_for_storage(decrypted))
        return decrypted

    @property
    def decrypted_variables(self) -> dict[str, Any]:
        """Variables du snapshot en clair — déchiffrement transparent.

        Returns:
            Snapshot ``variables`` déchiffré. Ne vit qu'en mémoire —
            consommé par le rendu/déploiement, jamais loggé ni écrit
            sur disque en clair.
        """
        return self._decrypt_snapshot_in_place("variables")

    @property
    def decrypted_config(self) -> dict[str, Any]:
        """Config du snapshot en clair — déchiffrement transparent.

        Returns:
            Snapshot ``config`` déchiffré. Ne vit qu'en mémoire —
            jamais loggé ni écrit sur disque en clair.
        """
        return self._decrypt_snapshot_in_place("config")

    def __repr__(self) -> str:
        return f"<Deployment(id={self.id}, name={self.name}, status={self.status})>"
