"""
Schemas Pydantic V2 pour les clés API ``wf_ak_`` (STORY-124.2).

Validation stricte avec type hints obligatoires (rules 30) et
documentation OpenAPI complète (examples par champ).

Sécurité (rules 40) :
- ``APIKeyResponse`` n'expose **jamais** ``key_hash`` ni la valeur de
  la clé — uniquement les métadonnées (nom, dates, statut) ;
- ``APIKeyCreated`` est le **seul** schema portant la clé brute, et
  uniquement pour la réponse 201 du ``POST /auth/api-keys``
  (affichage unique — la valeur n'est plus récupérable ensuite).
"""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class APIKeyCreate(BaseModel):
    """
    Schema de création d'une clé API.

    **Règles de validation :**
    - name: 1-100 caractères (borné par la colonne ``String(100)``) ;
    - expires_at: optionnelle — ``null`` signifie que la clé n'expire
      jamais (sémantique documentée spec 06/07).
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "name": "CLI laptop",
                    "expires_at": "2027-01-01T00:00:00Z",
                },
                {"name": "CI pipeline"},
            ]
        }
    )

    name: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Libellé de la clé choisi par l'utilisateur",
        json_schema_extra={"example": "CLI laptop"},
    )
    expires_at: Optional[datetime] = Field(
        None,
        description=("Date d'expiration de la clé (UTC) — null = n'expire jamais"),
        json_schema_extra={"example": "2027-01-01T00:00:00Z"},
    )


class APIKeyResponse(BaseModel):
    """
    Schema de réponse d'une clé API (sans données sensibles).

    Ne contient **jamais** ``key_hash`` ni la valeur de la clé :
    uniquement les métadonnées nécessaires à la gestion (liste,
    révocation). Consommé par ``GET /auth/api-keys`` (STORY-124.3).
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                "name": "CLI laptop",
                "expires_at": "2027-01-01T00:00:00Z",
                "last_used_at": "2026-09-13T14:22:05Z",
                "revoked": False,
                "created_at": "2026-09-13T10:00:00Z",
            }
        },
    )

    id: str = Field(
        ...,
        description="ID unique de la clé",
        json_schema_extra={"example": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b"},
    )
    name: str = Field(
        ...,
        description="Libellé de la clé",
        json_schema_extra={"example": "CLI laptop"},
    )
    expires_at: Optional[datetime] = Field(
        None,
        description="Date d'expiration (null = n'expire jamais)",
        json_schema_extra={"example": "2027-01-01T00:00:00Z"},
    )
    last_used_at: Optional[datetime] = Field(
        None,
        description="Dernière utilisation réussie (mise à jour throttlée)",
        json_schema_extra={"example": "2026-09-13T14:22:05Z"},
    )
    revoked: bool = Field(
        ...,
        description="Clé révoquée (distinct de l'expiration)",
        json_schema_extra={"example": False},
    )
    created_at: datetime = Field(
        ...,
        description="Date de création",
        json_schema_extra={"example": "2026-09-13T10:00:00Z"},
    )


class APIKeyCreated(APIKeyResponse):
    """
    Schema de la réponse 201 du ``POST /auth/api-keys``.

    ⚠️ **Affichage unique** : porte la clé brute complète ``wf_ak_...``
    — c'est la **seule** occasion de la récupérer. Le serveur ne stocke
    que son hash (jamais la valeur) : une fois perdue, la clé doit être
    révoquée et recréée. Ne jamais logguer ni re-sauvegarder cette
    valeur en clair côté client sans chiffrement adapté.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "9d2c8a4f-1b3e-4f5a-8a7b-2c9d0e1f2a3b",
                "name": "CLI laptop",
                "expires_at": "2027-01-01T00:00:00Z",
                "last_used_at": None,
                "revoked": False,
                "created_at": "2026-09-13T10:00:00Z",
                "key": "wf_ak_<48 caractères base64url>",
            }
        },
    )

    key: str = Field(
        ...,
        description=(
            "Clé API complète (wf_ak_...) — AFFICHÉE UNE SEULE FOIS à la "
            "création : copiez-la maintenant, elle ne sera plus jamais "
            "retournée par l'API"
        ),
        json_schema_extra={"example": "wf_ak_<48 caractères base64url>"},
    )
