"""Schémas Pydantic des clés SSH et empreintes d'hôtes (STORY-131.2).

Contrats I/O de la gestion des clés SSH réutilisables (spec 06 § SSHKey)
et des empreintes d'hôtes (spec 15 § Hosts distants — TOFU), avec
validation stricte et documentation OpenAPI complète (rules 20/30).

Sécurité (rules 40) :

- :class:`SSHKeyResponse` n'expose **jamais** ``private_key_encrypted``
  ni ``decrypted_private_key`` — uniquement les métadonnées de gestion
  (nom, algorithme, clé publique, empreinte, dates) ;
- :class:`SSHKeyCreated` est le **seul** schéma portant la clé privée
  en clair, et uniquement pour les réponses 201 de ``POST
  /ssh-keys/generate`` et ``POST /ssh-keys/import`` (affichage unique —
  pattern :class:`~app.schemas.api_key.APIKeyCreated`, STORY-124) ;
- la clé privée stockée l'est exclusivement sous forme de token Fernet
  (modèle STORY-131.1) — aucun schéma ne la transporte hors création.
"""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

# Empreinte normalisée asyncssh ``get_fingerprint()`` :
# ``SHA256:`` + base64 sans padding du digest SHA-256 (32 octets → 43 car.).
_FINGERPRINT_PATTERN = r"^SHA256:[A-Za-z0-9+/]{43}$"


class SSHKeyGenerateRequest(BaseModel):
    """Payload de ``POST /ssh-keys/generate`` — génération serveur."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"name": "prod-deploy-ed25519", "key_type": "ssh-ed25519"},
                {"name": "legacy-rsa-key", "key_type": "ssh-rsa"},
            ]
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom d'affichage unique de la clé (1-100 caractères)",
        json_schema_extra={"example": "prod-deploy-ed25519"},
    )
    key_type: Literal["ssh-ed25519", "ssh-rsa"] = Field(
        "ssh-ed25519",
        description=(
            "Algorithme de la clé générée — `ssh-ed25519` (recommandé) "
            "ou `ssh-rsa` (legacy)."
        ),
        json_schema_extra={"example": "ssh-ed25519"},
    )


class SSHKeyImportRequest(BaseModel):
    """Payload de ``POST /ssh-keys/import`` — import d'une clé existante.

    La passphrase (optionnelle) ne sert qu'à **lire** la clé à l'import :
    la clé est ensuite re-stockée dé-passphrasée mais chiffrée via le
    SecretManager (arbitrage d'analyse STORY-131 — comportement standard
    d'un gestionnaire de clés). Elle n'est jamais persistée ni loggée.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "ops-laptop-key",
                    "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\\n...",
                },
            ]
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nom d'affichage unique de la clé (1-100 caractères)",
        json_schema_extra={"example": "ops-laptop-key"},
    )
    private_key: str = Field(
        ...,
        min_length=1,
        max_length=10000,
        description=(
            "Clé privée au format PEM/OpenSSH (`-----BEGIN OPENSSH PRIVATE "
            "KEY-----` ou PKCS#1/PKCS#8). Un format non reconnu → 422."
        ),
        json_schema_extra={"example": "-----BEGIN OPENSSH PRIVATE KEY-----\\n..."},
    )
    passphrase: Optional[str] = Field(
        None,
        max_length=1024,
        description=(
            "Passphrase de déchiffement de la clé importée (optionnelle) — "
            "utilisée uniquement à l'import, jamais stockée."
        ),
        json_schema_extra={"example": None},
    )


class SSHKeyUpdate(BaseModel):
    """Payload de ``PUT /ssh-keys/{id}`` — renommage uniquement.

    La rotation d'une clé passe par la création d'une nouvelle clé puis
    le déréférencement de l'ancienne (jamais de mutation du matériau).
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"name": "prod-deploy-ed25519-v2"}]}
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Nouveau nom d'affichage unique (1-100 caractères)",
        json_schema_extra={"example": "prod-deploy-ed25519-v2"},
    )


class SSHKeyResponse(BaseModel):
    """Réponse d'une clé SSH — **aucun matériau de clé privée**.

    Ne contient jamais ``private_key_encrypted`` ni
    ``decrypted_private_key`` (checklist sécurité STORY-131.2) : la clé
    publique et l'empreinte sont non sensibles par nature (déploiement
    ``authorized_keys`` / identification).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3f2b8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                "name": "prod-deploy-ed25519",
                "key_type": "ssh-ed25519",
                "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...",
                "fingerprint": "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc",
                "last_used_at": "2026-10-16T14:22:05Z",
                "created_at": "2026-10-16T10:00:00Z",
                "targets_count": 3,
            }
        },
    )

    id: str = Field(
        ...,
        description="ID unique de la clé",
        json_schema_extra={"example": "3f2b8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b"},
    )
    name: str = Field(
        ...,
        description="Nom d'affichage unique de la clé",
        json_schema_extra={"example": "prod-deploy-ed25519"},
    )
    key_type: str = Field(
        ...,
        description="Algorithme (ssh-ed25519 recommandé, ssh-rsa accepté)",
        json_schema_extra={"example": "ssh-ed25519"},
    )
    public_key: str = Field(
        ...,
        description=(
            "Partie publique (une ligne `algo base64 comment`) — déploiement "
            "authorized_keys, non sensible par nature"
        ),
        json_schema_extra={"example": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI..."},
    )
    fingerprint: str = Field(
        ...,
        description="Empreinte SHA256:<base64nopad> (identification, dédup)",
        json_schema_extra={
            "example": "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
        },
    )
    last_used_at: Optional[datetime] = Field(
        None,
        description="Dernière session SSH réussie utilisant cette clé",
        json_schema_extra={"example": "2026-10-16T14:22:05Z"},
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-10-16T10:00:00Z"},
    )
    targets_count: int = Field(
        0,
        ge=0,
        description=(
            "Nombre de cibles référençant cette clé (calculé par le service — "
            "valeur par défaut 0 en validation ORM)"
        ),
        json_schema_extra={"example": 3},
    )


class SSHKeyCreated(SSHKeyResponse):
    """Réponse 201 de ``POST /ssh-keys/generate`` et ``POST /ssh-keys/import``.

    ⚠️ **Affichage unique** : porte la clé privée complète en clair —
    c'est la **seule** occasion de la récupérer. Le serveur ne stocke
    qu'une version chiffrée (Fernet via SecretManager) : une fois
    perdue, la clé doit être supprimée et recréée. Ne jamais logger ni
    re-sauvegarder cette valeur côté client sans chiffrement adapté.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "3f2b8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                "name": "prod-deploy-ed25519",
                "key_type": "ssh-ed25519",
                "public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...",
                "fingerprint": "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc",
                "last_used_at": None,
                "created_at": "2026-10-16T10:00:00Z",
                "targets_count": 0,
                "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\\n...",
            }
        },
    )

    private_key: str = Field(
        ...,
        description=(
            "Clé privée complète (PEM/OpenSSH, dé-passphrasée) — AFFICHÉE "
            "UNE SEULE FOIS à la création : copiez-la maintenant, elle ne "
            "sera plus jamais retournée par l'API"
        ),
        json_schema_extra={"example": "-----BEGIN OPENSSH PRIVATE KEY-----\\n..."},
    )


class HostFingerprintResponse(BaseModel):
    """Réponse d'une empreinte d'hôte SSH (known_hosts, spec 15)."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "5a1c9b7e-2d4f-4a6b-9c8d-0e1f2a3b4c5d",
                "host_id": "550e8400-e29b-41d4-a716-446655440000",
                "hostname": "prod-vm01.example.com",
                "port": 22,
                "key_type": "ssh-ed25519",
                "fingerprint": "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc",
                "accepted": False,
                "accepted_at": None,
                "created_at": "2026-10-16T10:00:00Z",
            }
        },
    )

    id: str = Field(
        ...,
        description="ID unique de l'empreinte",
        json_schema_extra={"example": "5a1c9b7e-2d4f-4a6b-9c8d-0e1f2a3b4c5d"},
    )
    host_id: str = Field(
        ...,
        description="Cible vérifiée (targets.id — arbitrage F3 de STORY-131)",
        json_schema_extra={"example": "550e8400-e29b-41d4-a716-446655440000"},
    )
    hostname: str = Field(
        ...,
        description="Adresse de connexion vérifiée",
        json_schema_extra={"example": "prod-vm01.example.com"},
    )
    port: int = Field(
        ...,
        description="Port SSH de l'hôte vérifié",
        json_schema_extra={"example": 22},
    )
    key_type: str = Field(
        ...,
        description="Algorithme de la clé d'hôte présentée (ssh-ed25519…)",
        json_schema_extra={"example": "ssh-ed25519"},
    )
    fingerprint: str = Field(
        ...,
        description="Empreinte présentée SHA256:<base64nopad>",
        json_schema_extra={
            "example": "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
        },
    )
    accepted: bool = Field(
        ...,
        description=(
            "TRUE après acceptation explicite (TOFU) — une empreinte "
            "enregistrée mais non acceptée ne fait pas autorité"
        ),
        json_schema_extra={"example": False},
    )
    accepted_at: Optional[datetime] = Field(
        None,
        description="Date d'acceptation explicite (null si PENDING)",
        json_schema_extra={"example": None},
    )
    created_at: datetime = Field(
        ...,
        description="Date d'enregistrement de l'empreinte",
        json_schema_extra={"example": "2026-10-16T10:00:00Z"},
    )


class FingerprintAcceptRequest(BaseModel):
    """Payload de ``POST /targets/{id}/ssh-fingerprints/accept``.

    Acceptation **explicite** TOFU : le payload doit matcher une ligne
    PENDING existante ``(hostname, port, key_type)`` pour la cible, et
    l'empreinte soumise doit être identique à celle enregistrée — sinon
    409 (jamais d'ajout/écrasement silencieux, spec 15).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "hostname": "prod-vm01.example.com",
                    "port": 22,
                    "key_type": "ssh-ed25519",
                    "fingerprint": (
                        "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
                    ),
                }
            ]
        }
    )

    hostname: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Adresse de connexion vérifiée (doit matcher la ligne PENDING)",
        json_schema_extra={"example": "prod-vm01.example.com"},
    )
    port: int = Field(
        ...,
        ge=1,
        le=65535,
        description="Port SSH vérifié (doit matcher la ligne PENDING)",
        json_schema_extra={"example": 22},
    )
    key_type: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="Algorithme de la clé d'hôte (doit matcher la ligne PENDING)",
        json_schema_extra={"example": "ssh-ed25519"},
    )
    fingerprint: str = Field(
        ...,
        max_length=100,
        pattern=_FINGERPRINT_PATTERN,
        description=(
            "Empreinte présentée au format `SHA256:<base64 sans padding>` — "
            "doit être identique à celle enregistrée, sinon 409"
        ),
        json_schema_extra={
            "example": "SHA256:riuYU2/TOSwfigd2RdFbfw8dCjG7QZtoInqt30SgFpc"
        },
    )
