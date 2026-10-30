"""
Schemas Pydantic V2 pour validation des données API.

Ce module contient tous les schémas de validation pour l'API REST.
Utilise Pydantic V2 avec mode strict pour type safety maximale.
"""

from ..enums.target import CapabilityType
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
    DeploymentEventResponse,
    DeploymentResponse,
    DeploymentUpdate,
)
from .host import (
    HostCreateRequest,
    HostHealthCheckResponse,
    HostResponse,
    HostUpdate,
)
from .organization import (
    OrganizationBase,
    OrganizationCreate,
    OrganizationResponse,
    OrganizationUpdate,
)
from .stack import StackBase, StackCreate, StackResponse, StackUpdate
from .target_capability import TargetCapabilityBase, TargetCapabilityResponse
from .user import (
    LoginResponse,
    PasswordChangeRequest,
    PasswordChangeResponse,
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
    "PasswordChangeRequest",
    "PasswordChangeResponse",
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
    # Host schemas (canoniques — STORY-166.2)
    "HostCreateRequest",
    "HostUpdate",
    "HostResponse",
    "HostHealthCheckResponse",
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
    "DeploymentEventResponse",
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
