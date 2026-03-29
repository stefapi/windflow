"""
Module d'authentification JWT pour WindFlow.

Gère la création et validation des tokens JWT, ainsi que les dépendances
FastAPI pour protéger les routes.
"""

from .dependencies import get_current_active_user, get_current_user, require_superuser
from .jwt import create_access_token, decode_access_token

__all__ = [
    "create_access_token",
    "decode_access_token",
    "get_current_user",
    "get_current_active_user",
    "require_superuser",
]
