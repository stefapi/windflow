"""
Routes de gestion des déploiements.
"""

from typing import List
from uuid import UUID
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from ...database import get_db
from ...schemas.deployment import DeploymentResponse, DeploymentCreate, DeploymentUpdate, DeploymentLogsResponse
from ...services.deployment_service import DeploymentService
from ...auth.dependencies import get_current_active_user
from ...models.user import User
from ...core.rate_limit import conditional_rate_limiter

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get(
    "",
    response_model=List[DeploymentResponse],
    summary="List all deployments",
    description="""
List all deployments in the current user's organization.

## Pagination
Use `skip` and `limit` parameters for pagination:
- Default: Returns first 100 deployments
- Maximum limit: 1000 deployments per request

## Filtering
Results are automatically filtered by organization membership.

## Sorting
Deployments are returned in reverse chronological order (newest first).

**Authentication Required**
""",
    responses={
        200: {
            "description": "List of deployments",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "990e8400-e29b-41d4-a716-446655440000",
                            "name": "production-api",
                            "status": "running",
                            "target_type": "docker",
                            "created_at": "2026-01-02T22:30:00Z"
                        },
                        {
                            "id": "880e8400-e29b-41d4-a716-446655440001",
                            "name": "staging-web",
                            "status": "pending",
                            "target_type": "docker-compose",
                            "created_at": "2026-01-02T21:15:00Z"
                        }
                    ]
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-126"
                    }
                }
            }
        }
    },
    tags=["deployments"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))]
)
async def list_deployments(
    request: Request,
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """List all deployments in organization."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Listing deployments for organization",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "organization_id": str(current_user.organization_id),
            "skip": skip,
            "limit": limit
        }
    )

    deployments = await DeploymentService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )

    logger.info(
        f"Retrieved {len(deployments)} deployments",
        extra={
            "correlation_id": correlation_id,
            "count": len(deployments)
        }
    )

    return deployments


@router.get(
    "/{deployment_id}",
    response_model=DeploymentResponse,
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
    summary="Get deployment by ID",
    description="""
Retrieve detailed information about a specific deployment.

## Response Details
Returns complete deployment information including:
- Current status and progress
- Configuration details
- Stack information
- Timestamps (created, updated, started, stopped)
- Resource allocation
- Error messages (if failed)

## Access Control
Users can only access deployments within their organization.

**Authentication Required**
""",
    responses={
        200: {
            "description": "Deployment details",
            "content": {
                "application/json": {
                    "example": {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "name": "production-api",
                        "status": "running",
                        "target_type": "docker",
                        "created_at": "2026-01-02T22:30:00Z",
                        "started_at": "2026-01-02T22:31:00Z",
                        "stack": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "api-stack"
                        },
                        "configuration": {
                            "replicas": 3,
                            "memory": "512Mi"
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this deployment"
                    }
                }
            }
        },
        404: {
            "description": "Deployment not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Deployment 990e8400-... not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-127"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def get_deployment(
    request: Request,
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Retrieve deployment by ID."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Retrieving deployment: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "deployment_id": str(deployment_id)
        }
    )

    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        logger.warning(
            f"Deployment not found: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier que le déploiement appartient à la même organisation
    if deployment.organization_id != current_user.organization_id:
        logger.warning(
            f"Access denied to deployment: {deployment_id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "deployment_id": str(deployment_id)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    return deployment


@router.get(
    "/{deployment_id}/logs",
    dependencies=[Depends(conditional_rate_limiter(60, 60))],
    response_model=DeploymentLogsResponse,
    summary="Get deployment logs",
    description="""
Retrieve logs for a specific deployment.

## Log Content
Returns all logs generated during the deployment process:
- Container startup logs
- Build output
- Error messages
- System events
- Deployment progress updates

## Real-time Logs
For real-time log streaming, use the WebSocket endpoint:
`/ws/deployments/{deployment_id}/logs`

## Access Control
Users can only access logs for deployments within their organization.

**Authentication Required**
""",
    responses={
        200: {
            "description": "Deployment logs",
            "content": {
                "application/json": {
                    "example": {
                        "deployment_id": "990e8400-e29b-41d4-a716-446655440000",
                        "logs": "[2026-01-02 22:30:00] Starting deployment...\n[2026-01-02 22:30:05] Pulling image nginx:latest\n[2026-01-02 22:30:15] Container started successfully",
                        "updated_at": "2026-01-02T22:30:15Z"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this deployment"
                    }
                }
            }
        },
        404: {
            "description": "Deployment not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Deployment 990e8400-... not found"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-128"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def get_deployment_logs(
    request: Request,
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Retrieve deployment logs."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Retrieving logs for deployment: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "deployment_id": str(deployment_id)
        }
    )

    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        logger.warning(
            f"Deployment not found: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier que le déploiement appartient à la même organisation
    if deployment.organization_id != current_user.organization_id:
        logger.warning(
            f"Access denied to deployment logs: {deployment_id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "deployment_id": str(deployment_id)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    return DeploymentLogsResponse(
        deployment_id=deployment.id,
        logs=deployment.logs,
        updated_at=deployment.updated_at
    )


@router.post(
    "",
    response_model=DeploymentResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
    summary="Create a new deployment",
    description="""
Create a new Docker deployment from a stack configuration.

## Process
1. Validates stack configuration
2. Prepares deployment environment
3. Initiates deployment process (async)
4. Returns deployment details with status

## Stack Types
- **Docker Container**: Single container deployment
- **Docker Compose**: Multi-container stack
- **Kubernetes**: K8s manifest deployment

## AI Optimization
When enabled, the LLM backend can:
- Optimize resource allocation
- Suggest security improvements
- Auto-configure health checks
- Recommend scaling strategies

## Real-time Updates
Subscribe to WebSocket endpoint `/ws/deployments/{deployment_id}`
for real-time deployment status updates.

**Authentication Required**
""",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "simple_nginx": {
                            "summary": "Simple Nginx deployment",
                            "description": "Basic web server deployment",
                            "value": {
                                "name": "my-nginx",
                                "stack_id": "550e8400-e29b-41d4-a716-446655440000",
                                "target_type": "docker",
                                "environment_id": "prod-env-1"
                            }
                        },
                        "with_ai_optimization": {
                            "summary": "Deployment with AI optimization",
                            "description": "Let AI optimize configuration",
                            "value": {
                                "name": "optimized-api",
                                "stack_id": "660e8400-e29b-41d4-a716-446655440001",
                                "target_type": "docker",
                                "environment_id": "staging-env",
                                "enable_ai_optimization": True,
                                "configuration": {
                                    "optimization_level": "balanced"
                                }
                            }
                        },
                        "docker_compose": {
                            "summary": "Docker Compose stack",
                            "description": "Multi-container application",
                            "value": {
                                "name": "full-stack-app",
                                "stack_id": "770e8400-e29b-41d4-a716-446655440002",
                                "target_type": "docker-compose",
                                "configuration": {
                                    "scale": {
                                        "web": 3,
                                        "api": 2
                                    }
                                }
                            }
                        },
                        "kubernetes": {
                            "summary": "Kubernetes deployment",
                            "description": "Deploy to K8s cluster",
                            "value": {
                                "name": "k8s-microservice",
                                "stack_id": "880e8400-e29b-41d4-a716-446655440003",
                                "target_type": "kubernetes",
                                "configuration": {
                                    "namespace": "production",
                                    "replicas": 5
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Deployment created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "name": "my-nginx",
                        "status": "pending",
                        "target_type": "docker",
                        "created_at": "2026-01-02T22:30:00Z",
                        "stack": {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "nginx-stack"
                        }
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_stack": {
                            "summary": "Stack not found",
                            "value": {
                                "error": "Stack Not Found",
                                "detail": "Stack with ID 550e8400-... does not exist",
                                "correlation_id": "abc-123"
                            }
                        },
                        "invalid_config": {
                            "summary": "Invalid configuration",
                            "value": {
                                "error": "Configuration Error",
                                "detail": "Missing required field: image",
                                "correlation_id": "abc-124"
                            }
                        }
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Insufficient permissions",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "User does not have permission to create deployments"
                    }
                }
            }
        },
        409: {
            "description": "Conflict - deployment name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Deployment with name 'my-nginx' already exists in organization"
                    }
                }
            }
        },
        429: {
            "description": "Rate limit exceeded",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Too Many Requests",
                        "detail": "Rate limit exceeded. Maximum 10 requests per minute.",
                        "retry_after": 30
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def create_deployment(
    request: Request,
    deployment_data: DeploymentCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Create a new deployment (implementation)."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Creating deployment: {deployment_data.name}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": str(deployment_data.stack_id) if hasattr(deployment_data, 'stack_id') else None
        }
    )

    # Vérifier que le nom n'existe pas déjà dans l'organisation (seulement si fourni)
    if deployment_data.name:
        existing = await DeploymentService.get_by_name(
            session,
            current_user.organization_id,
            deployment_data.name
        )
        if existing:
            logger.warning(
                f"Deployment name conflict: {deployment_data.name}",
                extra={"correlation_id": correlation_id, "user_id": str(current_user.id)}
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Déploiement avec le nom '{deployment_data.name}' existe déjà"
            )

    try:
        deployment = await DeploymentService.create(
            session,
            deployment_data,
            current_user.organization_id,
            current_user.id
        )

        logger.info(
            f"Deployment created successfully: {deployment.id}",
            extra={
                "correlation_id": correlation_id,
                "deployment_id": str(deployment.id),
                "user_id": str(current_user.id)
            }
        )

        return deployment
    except ValueError as e:
        logger.error(
            f"Failed to create deployment: {str(e)}",
            extra={"correlation_id": correlation_id, "user_id": str(current_user.id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.put(
    "/{deployment_id}",
    response_model=DeploymentResponse,
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    summary="Update deployment",
    description="""
Update an existing deployment's configuration.

## Updatable Fields
- **name**: Deployment name (must be unique in organization)
- **configuration**: Deployment-specific configuration
- **environment_id**: Target environment

## Restrictions
- Cannot update a deployment that is currently deploying
- Cannot change stack_id after creation
- Cannot change target_type after creation

## Name Uniqueness
If changing the name, it must not conflict with existing deployments
in the same organization.

**Authentication Required**
""",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "update_name": {
                            "summary": "Update deployment name",
                            "value": {
                                "name": "production-api-v2"
                            }
                        },
                        "update_config": {
                            "summary": "Update configuration",
                            "value": {
                                "configuration": {
                                    "replicas": 5,
                                    "memory": "1Gi"
                                }
                            }
                        },
                        "full_update": {
                            "summary": "Update multiple fields",
                            "value": {
                                "name": "staging-api",
                                "environment_id": "staging-env-2",
                                "configuration": {
                                    "replicas": 2
                                }
                            }
                        }
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Deployment updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "name": "production-api-v2",
                        "status": "running",
                        "updated_at": "2026-01-02T23:00:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Bad Request",
                        "detail": "Cannot update deployment while it is deploying"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this deployment"
                    }
                }
            }
        },
        404: {
            "description": "Deployment not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Deployment 990e8400-... not found"
                    }
                }
            }
        },
        409: {
            "description": "Name conflict",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Deployment with name 'production-api-v2' already exists"
                    }
                }
            }
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-129"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def update_deployment(
    request: Request,
    deployment_id: UUID,
    deployment_data: DeploymentUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Update deployment configuration."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Updating deployment: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "deployment_id": str(deployment_id)
        }
    )

    # Vérifier que le déploiement existe
    existing_deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not existing_deployment:
        logger.warning(
            f"Deployment not found: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if existing_deployment.organization_id != current_user.organization_id:
        logger.warning(
            f"Access denied to update deployment: {deployment_id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "deployment_id": str(deployment_id)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if deployment_data.name and deployment_data.name != existing_deployment.name:
        existing_name = await DeploymentService.get_by_name(
            session,
            current_user.organization_id,
            deployment_data.name
        )
        if existing_name:
            logger.warning(
                f"Deployment name conflict during update: {deployment_data.name}",
                extra={"correlation_id": correlation_id, "user_id": str(current_user.id)}
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Déploiement avec le nom '{deployment_data.name}' existe déjà"
            )

    deployment = await DeploymentService.update(session, str(deployment_id), deployment_data)

    logger.info(
        f"Deployment updated successfully: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "deployment_id": str(deployment_id),
            "user_id": str(current_user.id)
        }
    )

    return deployment


@router.post(
    "/{deployment_id}/retry",
    response_model=DeploymentResponse,
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    summary="Retry failed deployment",
    description="""
Retry a failed or pending deployment.

## Retry Behavior
- Resets deployment status to 'pending'
- Clears previous error messages
- Preserves original configuration
- Initiates new deployment attempt

## Eligible Statuses
Only deployments with the following statuses can be retried:
- **failed**: Deployment failed and can be retried
- **pending**: Deployment stuck in pending state

## Use Cases
- Transient network errors
- Temporary resource unavailability
- Configuration issues that have been fixed externally

**Authentication Required**
""",
    responses={
        200: {
            "description": "Deployment retry initiated",
            "content": {
                "application/json": {
                    "example": {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "name": "production-api",
                        "status": "pending",
                        "updated_at": "2026-01-02T23:15:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid deployment status",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Bad Request",
                        "detail": "Deployment must be in 'failed' or 'pending' status to be retried (current: running)"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this deployment"
                    }
                }
            }
        },
        404: {
            "description": "Deployment not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Deployment 990e8400-... not found"
                    }
                }
            }
        },
        500: {
            "description": "Retry failed",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "Failed to retry deployment",
                        "correlation_id": "abc-130"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def retry_deployment(
    request: Request,
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Retry a failed deployment."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Retrying deployment: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "deployment_id": str(deployment_id)
        }
    )

    # Récupérer le déploiement échoué
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        logger.warning(
            f"Deployment not found: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if deployment.organization_id != current_user.organization_id:
        logger.warning(
            f"Access denied to retry deployment: {deployment_id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "deployment_id": str(deployment_id)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    # Vérifier que le déploiement est en statut FAILED ou PENDING
    if deployment.status.value not in ["failed", "pending"]:
        logger.warning(
            f"Invalid status for retry: {deployment.status.value}",
            extra={
                "correlation_id": correlation_id,
                "deployment_id": str(deployment_id),
                "status": deployment.status.value
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le déploiement doit être en statut 'failed' ou 'pending' pour être réessayé (statut actuel: {deployment.status.value})"
        )

    # Relancer le déploiement existant
    success = await DeploymentService.retry_deployment(
        session,
        str(deployment_id),
        str(current_user.id)
    )

    if not success:
        logger.error(
            f"Failed to retry deployment: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Échec de la relance du déploiement"
        )

    # Récupérer le déploiement mis à jour
    updated_deployment = await DeploymentService.get_by_id(session, str(deployment_id))

    logger.info(
        f"Deployment retry initiated: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "deployment_id": str(deployment_id),
            "user_id": str(current_user.id)
        }
    )

    return updated_deployment


@router.post(
    "/{deployment_id}/cancel",
    response_model=DeploymentResponse,
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    summary="Cancel running deployment",
    description="""
Cancel a deployment that is currently in progress.

## Cancel Behavior
- Stops the deployment process immediately
- Sets status to 'stopped'
- Records cancellation timestamp
- Adds cancellation message to logs
- Cleans up any running containers/resources

## Eligible Statuses
Only deployments with the following statuses can be cancelled:
- **pending**: Deployment waiting to start
- **deploying**: Deployment currently in progress

## Important Notes
- Cancellation is immediate and cannot be undone
- Partial deployments may leave resources in inconsistent state
- Use with caution in production environments
- Consider using rollback instead for running deployments

**Authentication Required**
""",
    responses={
        200: {
            "description": "Deployment cancelled successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "990e8400-e29b-41d4-a716-446655440000",
                        "name": "production-api",
                        "status": "stopped",
                        "stopped_at": "2026-01-02T23:20:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Cannot cancel deployment",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Bad Request",
                        "detail": "Deployment cannot be cancelled (current status: running)"
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this deployment"
                    }
                }
            }
        },
        404: {
            "description": "Deployment not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Deployment 990e8400-... not found"
                    }
                }
            }
        },
        500: {
            "description": "Cancellation failed",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "Failed to cancel deployment",
                        "correlation_id": "abc-131"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def cancel_deployment(
    request: Request,
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Cancel a running deployment."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Cancelling deployment: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "deployment_id": str(deployment_id)
        }
    )

    # Récupérer le déploiement
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        logger.warning(
            f"Deployment not found: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if deployment.organization_id != current_user.organization_id:
        logger.warning(
            f"Access denied to cancel deployment: {deployment_id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "deployment_id": str(deployment_id)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    # Vérifier que le déploiement peut être annulé
    if deployment.status.value not in ["pending", "deploying"]:
        logger.warning(
            f"Cannot cancel deployment with status: {deployment.status.value}",
            extra={
                "correlation_id": correlation_id,
                "deployment_id": str(deployment_id),
                "status": deployment.status.value
            }
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Le déploiement ne peut pas être annulé (statut actuel: {deployment.status.value})"
        )

    # Annuler le déploiement via l'orchestrateur
    from ...services.deployment_orchestrator import DeploymentOrchestrator
    from ...models.deployment import DeploymentStatus

    # Annuler la tâche si elle existe
    await DeploymentOrchestrator.cancel_deployment(str(deployment_id))

    # Mettre à jour le statut
    deployment.status = DeploymentStatus.STOPPED
    deployment.stopped_at = datetime.utcnow()
    if deployment.logs:
        deployment.logs += "\n[SYSTEM] Déploiement annulé par l'utilisateur"
    else:
        deployment.logs = "[SYSTEM] Déploiement annulé par l'utilisateur"

    await session.commit()
    await session.refresh(deployment)

    logger.info(
        f"Deployment cancelled successfully: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "deployment_id": str(deployment_id),
            "user_id": str(current_user.id)
        }
    )

    return deployment


@router.delete(
    "/{deployment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
    summary="Delete deployment",
    description="""
Delete a deployment permanently.

## Delete Behavior
- Removes deployment record from database
- Deletes associated logs and metadata
- Does NOT stop running containers (cancel first if needed)
- Cannot be undone

## Important Notes
- **Warning**: This is a destructive operation
- Cancel the deployment first if it's still running
- Consider archiving instead of deleting for audit purposes
- All deployment history will be lost

## Best Practices
1. Cancel running deployments before deletion
2. Export logs if needed for compliance
3. Verify deployment ID before deletion
4. Use soft-delete in production environments

**Authentication Required**
""",
    responses={
        204: {
            "description": "Deployment deleted successfully (no content)"
        },
        400: {
            "description": "Cannot delete running deployment",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Bad Request",
                        "detail": "Cannot delete deployment while it is running. Cancel it first."
                    }
                }
            }
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token"
                    }
                }
            }
        },
        403: {
            "description": "Access denied",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this deployment"
                    }
                }
            }
        },
        404: {
            "description": "Deployment not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Deployment 990e8400-... not found"
                    }
                }
            }
        },
        500: {
            "description": "Deletion failed",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "Failed to delete deployment",
                        "correlation_id": "abc-132"
                    }
                }
            }
        }
    },
    tags=["deployments"]
)
async def delete_deployment(
    request: Request,
    deployment_id: UUID,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """Delete a deployment permanently."""
    correlation_id = getattr(request.state, "correlation_id", None)

    logger.info(
        f"Deleting deployment: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "deployment_id": str(deployment_id)
        }
    )

    # Vérifier que le déploiement existe
    deployment = await DeploymentService.get_by_id(session, str(deployment_id))
    if not deployment:
        logger.warning(
            f"Deployment not found: {deployment_id}",
            extra={"correlation_id": correlation_id, "deployment_id": str(deployment_id)}
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Déploiement {deployment_id} non trouvé"
        )

    # Vérifier les permissions
    if deployment.organization_id != current_user.organization_id:
        logger.warning(
            f"Access denied to delete deployment: {deployment_id}",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "deployment_id": str(deployment_id)
            }
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce déploiement"
        )

    await DeploymentService.delete(session, str(deployment_id))

    logger.info(
        f"Deployment deleted successfully: {deployment_id}",
        extra={
            "correlation_id": correlation_id,
            "deployment_id": str(deployment_id),
            "user_id": str(current_user.id)
        }
    )
