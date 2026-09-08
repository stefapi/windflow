"""
Schemas Pydantic V2 pour la gestion des membres d'une organisation.

Endpoints spec 09 § Organizations : ``GET /{id}/users``,
``POST /{id}/users`` (rôle par défaut ``viewer``),
``PUT /{id}/users/{user_id}`` (changement de rôle) et
``DELETE /{id}/users/{user_id}`` (retrait).

Sécurité :
- ``role`` borné à l'enum partagé ``Role`` (``viewer`` / ``operator`` /
  ``admin``) — ``super_admin`` est structurellement impossible (422
  Pydantic immédiat, protection anti-escalade ; le Super Admin est un
  rôle système porté par ``User.is_superuser``) ;
- schéma de réponse en **whitelist stricte** : ni ``hashed_password`` ni
  ``keycloak_id`` (ni aucun champ password/token) ne peuvent être exposés
  par construction.
"""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from ..enums.rbac import Role


class OrganizationMemberAddRequest(BaseModel):
    """
    Schema d'ajout d'un membre à une organisation (POST /{id}/users).

    **Règles de validation :**
    - ``user_id`` : UUID requis de l'utilisateur à ajouter (422 si format invalide) ;
    - ``role`` : optionnel, borné à l'enum ``Role`` — défaut ``viewer``
      (spec 09 : rôle par défaut ``viewer`` à l'ajout) ; toute valeur hors
      ``{viewer, operator, admin}`` (dont ``super_admin``) → 422.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "user_id": "770e8400-e29b-41d4-a716-446655440010",
                },
                {
                    "user_id": "770e8400-e29b-41d4-a716-446655440010",
                    "role": "operator",
                },
                {
                    "user_id": "770e8400-e29b-41d4-a716-446655440010",
                    "role": "viewer",
                },
            ]
        }
    )

    user_id: UUID = Field(
        ...,
        description="ID de l'utilisateur à ajouter comme membre",
        json_schema_extra={"example": "770e8400-e29b-41d4-a716-446655440010"},
    )
    role: Role = Field(
        default=Role.VIEWER,
        description="Rôle du membre dans l'organisation "
        "(viewer | operator | admin) — défaut viewer ; "
        "super_admin est un rôle système et n'est pas une valeur valide",
        json_schema_extra={"example": "viewer"},
    )


class MemberRoleUpdateRequest(BaseModel):
    """
    Schema de changement de rôle d'un membre (PUT /{id}/users/{user_id}).

    **Règles de validation :**
    - ``role`` : requis, borné à l'enum ``Role`` — toute valeur hors
      ``{viewer, operator, admin}`` (dont ``super_admin``) → 422.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {"role": "operator"},
                {"role": "admin"},
                {"role": "viewer"},
            ]
        }
    )

    role: Role = Field(
        ...,
        description="Nouveau rôle du membre dans l'organisation "
        "(viewer | operator | admin) ; super_admin est un rôle système "
        "et n'est pas une valeur valide",
        json_schema_extra={"example": "operator"},
    )


class OrganizationMemberResponse(BaseModel):
    """
    Schema de réponse d'un membre d'une organisation.

    Whitelist stricte de champs : expose uniquement les informations
    nécessaires à la gestion des membres. Les champs sensibles
    (``hashed_password``, ``keycloak_id``) sont absents **par
    construction** — ce schéma ne réutilise pas ``UserResponse``.
    """

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "user_id": "770e8400-e29b-41d4-a716-446655440010",
                "username": "jdoe",
                "email": "jdoe@example.com",
                "full_name": "John Doe",
                "role": "viewer",
                "joined_at": "2026-09-08T10:00:00Z",
            }
        },
    )

    user_id: str = Field(
        ...,
        description="ID unique de l'utilisateur membre",
        json_schema_extra={"example": "770e8400-e29b-41d4-a716-446655440010"},
    )
    username: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Username de l'utilisateur membre",
        json_schema_extra={"example": "jdoe"},
    )
    email: str = Field(
        ...,
        description="Email de l'utilisateur membre",
        json_schema_extra={"example": "jdoe@example.com"},
    )
    full_name: Optional[str] = Field(
        None,
        max_length=255,
        description="Nom complet de l'utilisateur membre",
        json_schema_extra={"example": "John Doe"},
    )
    role: Role = Field(
        ...,
        description="Rôle de l'utilisateur dans l'organisation "
        "(viewer | operator | admin)",
        json_schema_extra={"example": "viewer"},
    )
    joined_at: datetime = Field(
        ...,
        description="Date d'adhésion de l'utilisateur à l'organisation",
        json_schema_extra={"example": "2026-09-08T10:00:00Z"},
    )
