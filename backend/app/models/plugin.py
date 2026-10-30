"""
Modèle Plugin pour la gestion des plugins installés.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any, Optional
from uuid import uuid4

from sqlalchemy import JSON, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..core.secret_manager import SecretManager, get_secret_manager
from ..database import Base

if TYPE_CHECKING:
    pass

# Masques renvoyés par l'UI/réponses pour un champ password déjà défini —
# une valeur entrante égale à un de ces masques est IGNORÉE à l'écriture
# (round-trip masque, STORY-169.4 arbitrage n°5 : ne jamais écraser un
# secret stocké par son propre masque).
_CONFIG_MASKS: tuple[str, ...] = ("********", "***")


def sensitive_config_keys(manifest_data: dict) -> set[str]:
    """Collecte les clés de configuration sensibles déclarées au manifest.

    Source unique de vérité partagée avec ``_build_safe_env_vars``
    (plugin_lifecycle_service) et ``mask_password_fields``
    (schemas/plugin) : un champ de ``manifest_data["config"]`` de type
    ``password`` rend sa clé sensible (chiffrée au repos, masquée dans
    les env vars des hooks et les réponses API). Il n'existe pas de type
    ``encrypted`` dans l'enum ``ConfigFieldType`` — seul ``password``
    déclare un secret (C12).

    Args:
        manifest_data: Le manifest validé (colonne ``manifest_data``).

    Returns:
        L'ensemble des clés de type ``password`` (vide si pas de config).
    """
    keys: set[str] = set()
    for field_def in (manifest_data or {}).get("config", []):
        if isinstance(field_def, dict) and field_def.get("type") == "password":
            key = field_def.get("key")
            if key:
                keys.add(key)
    return keys


def encrypt_config_values_for_storage(manifest_data: dict, values: dict) -> dict:
    """Chiffre les valeurs de config sensibles pour stockage (STORY-169.4).

    Stratégie « clé conservée, valeur chiffrée » (pattern
    ``models/deployment.py`` STORY-103.3) : les clés restent lisibles
    (l'UI liste les champs du wizard, ``PluginResponse`` masque par clé),
    seules les valeurs des champs ``type=password`` du manifest deviennent
    des tokens Fernet (préfixe ``gAAAA``). La sensibilité vient du
    manifest, pas d'une heuristique de nom.

    Idempotent et tolérant : une valeur déjà chiffrée (token détecté), non
    ``str``, vide, ou dont la clé n'est pas déclarée password est laissée
    telle quelle — double lecture legacy compatible, aucune migration DB.

    Args:
        manifest_data: Le manifest validé (source des clés sensibles).
        values: Les valeurs de configuration entrantes (jamais loggées).

    Returns:
        Copie du dict où les valeurs sensibles sont des tokens Fernet.
    """
    sensitive = sensitive_config_keys(manifest_data)
    manager = get_secret_manager()
    stored: dict[str, Any] = {}
    for key, value in values.items():
        if (
            key in sensitive
            and isinstance(value, str)
            and value
            and not SecretManager.is_encrypted(value)
        ):
            stored[key] = manager.encrypt(value)
        else:
            stored[key] = value
    return stored


def decrypt_config_values_from_storage(stored: dict) -> dict:
    """Déchiffre les valeurs de config lues depuis la base (double lecture).

    Chaque valeur détectée comme token Fernet est déchiffrée, le reste
    (données legacy en clair, non-str) est conservé tel quel. Les valeurs
    déchiffrées vivent **en mémoire uniquement** : ne jamais les logger
    ni les écrire sur disque (rules 40 / C12).

    Args:
        stored: Valeurs de la colonne ``config_values``.

    Returns:
        Copie du dict avec valeurs déchiffrées.

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


class PluginStatus(str, Enum):
    """Statuts possibles d'un plugin installé."""

    INSTALLED = "installed"
    INSTALLING = "installing"
    RUNNING = "running"
    STOPPED = "stopped"
    UPDATING = "updating"
    ERROR = "error"


class Plugin(Base):
    """
    Modèle plugin pour la gestion du cycle de vie des plugins.

    Représente un plugin installé dans le système WindFlow.

    Stockage chiffré (STORY-169.4 / C12) : dans ``config_values``, les
    valeurs des champs ``type=password`` du manifest sont des tokens
    Fernet (préfixe ``gAAAA``) — clés conservées lisibles, valeurs
    chiffrées, aucune migration (pattern ``models/deployment.py``).
    Double lecture : les données legacy en clair sont relues telles
    quelles et re-chiffrées à la prochaine écriture
    (``encrypt_config_values_for_storage`` /
    ``decrypt_config_values_from_storage``).
    """

    __tablename__ = "plugins"

    # Clé primaire
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )

    # Informations de base
    name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
        comment="Identifiant unique du plugin (kebab-case)",
    )
    version: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Version du plugin (semver)",
    )
    display_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="Nom affiché dans l'UI",
    )
    description: Mapped[Optional[str]] = mapped_column(
        Text,
        nullable=True,
        comment="Description du plugin",
    )

    # Catégorie et type
    category: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
        comment="Catégorie du plugin (PluginCategory value)",
    )
    type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        comment="Type de plugin (PluginType value)",
    )

    # Statut
    status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PluginStatus.INSTALLED.value,
        comment="Statut du plugin (PluginStatus value)",
    )

    # Données du manifest validé
    manifest_data: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        comment="Manifest validé complet (JSON)",
    )

    # Configuration utilisateur
    config_values: Mapped[dict] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
        comment="Valeurs de configuration saisies par l'utilisateur",
    )

    # Organisation (multi-tenant)
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Utilisateur ayant installé le plugin
    installed_by: Mapped[Optional[str]] = mapped_column(
        String(36),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        comment="ID de l'utilisateur ayant installé le plugin",
    )

    # Timestamps
    installed_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Plugin(id={self.id}, name={self.name}, version={self.version}, status={self.status})>"
