"""
Schemas Pydantic V2 pour validation des données API.

Ce module contient tous les schémas de validation pour l'API REST.
Utilise Pydantic V2 avec mode strict pour type safety maximale.
"""

from .user import (
    UserBase,
    UserCreate,
    UserUpdate,
    UserResponse,
    UserLogin,
    Token,
    LoginResponse,
    TokenData
)
from .organization import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationUpdate,
    OrganizationResponse
)
from .target import (
    TargetBase,
    TargetCreate,
    TargetUpdate,
    TargetResponse
)
from .stack import (
    StackBase,
    StackCreate,
    StackUpdate,
    StackResponse
)
from .deployment import (
    DeploymentBase,
    DeploymentCreate,
    DeploymentUpdate,
    DeploymentResponse
)

__all__ = [
    # User schemas
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserResponse",
    "UserLogin",
    "Token",
    "LoginResponse",
    "TokenData",
    # Organization schemas
    "OrganizationBase",
    "OrganizationCreate",
    "OrganizationUpdate",
    "OrganizationResponse",
    # Target schemas
    "TargetBase",
    "TargetCreate",
    "TargetUpdate",
    "TargetResponse",
    # Stack schemas
    "StackBase",
    "StackCreate",
    "StackUpdate",
    "StackResponse",
    # Target Capability schemas
    "CapabilityType",
    "TargetCapabilityBase",
    "TargetCapabilityResponse",
    # Deployment schemas
    "DeploymentBase",
    "DeploymentCreate",
    "DeploymentUpdate",
    "DeploymentResponse",
]
