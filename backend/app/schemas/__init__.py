"""
Schemas Pydantic V2 pour validation des données API.

Ce module contient tous les schémas de validation pour l'API REST.
Utilise Pydantic V2 avec mode strict pour type safety maximale.
"""

from .compute import (
    ComputeGlobalView,
    ComputeStatsResponse,
    DiscoveredItem,
    ServiceWithMetrics,
    StackWithServices,
    StandaloneContainer,
    TargetGroup,
    TargetMetrics,
)
from .deployment import (
    DeploymentBase,
    DeploymentCreate,
    DeploymentResponse,
    DeploymentUpdate,
)
from .organization import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from .stack import StackBase, StackCreate, StackResponse, StackUpdate
from .target import TargetBase, TargetCreate, TargetResponse, TargetUpdate
from .user import (
    LoginResponse,
    Token,
    TokenData,
    UserBase,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
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
    # Compute schemas
    "ServiceWithMetrics",
    "StandaloneContainer",
    "DiscoveredItem",
    "StackWithServices",
    "ComputeGlobalView",
    "TargetMetrics",
    "TargetGroup",
    "ComputeStatsResponse",
]
