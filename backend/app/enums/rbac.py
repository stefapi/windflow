"""
Centralized enums for the RBAC domain.

Single source of truth — imported by models, schemas, and services.
"""

from enum import Enum


class Role(str, Enum):
    """
    Rôles organisationnels portés par la table d'association ``user_organizations``.

    ``super_admin`` est **volontairement absent** : le Super Admin est un rôle
    système identifié par le flag ``User.is_superuser`` (spec 08 — RBAC &
    permissions), jamais une valeur d'association stockée dans
    ``user_organizations`` (protection anti-escalade).
    """

    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"
