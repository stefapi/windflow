"""
Routes de gestion des stacks Docker Compose.
"""

import logging
from typing import Any, List

from fastapi import APIRouter, Depends, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...auth.rbac import require_admin, require_operator, require_viewer
from ...core.exceptions import (
    ConflictError,
    InvalidInputError,
    NotFoundError,
    PermissionDeniedError,
    ServiceUnavailableError,
    WindFlowException,
)
from ...core.rate_limit import conditional_rate_limiter
from ...database import get_db
from ...helper.pagination import PaginationQuery, build_meta
from ...helper.template_renderer import TemplateRenderer
from ...models.environment import Environment
from ...models.stack_version import StackVersion
from ...models.user import User
from ...schemas.common import PaginatedResponse
from ...schemas.stack import (
    StackActionResponse,
    StackCreate,
    StackDuplicateRequest,
    StackRedeployRequest,
    StackRedeployResponse,
    StackResponse,
    StackSummaryResponse,
    StackUpdate,
)
from ...schemas.stack_version import StackVersionCreate, StackVersionResponse
from ...services.audit_service import AuditService
from ...services.docker_client_service import DockerClientService
from ...services.stack_service import StackService
from ...services.user_organization_service import UserOrganizationService

router = APIRouter()
logger = logging.getLogger(__name__)


def _render_stack_variables(stack) -> StackResponse:
    """
    Rend les macros dans les variables par défaut d'un stack.

    Cette fonction génère de nouvelles valeurs pour les macros comme
    {{ generate_password(24) }} afin que le frontend reçoive des valeurs
    concrètes plutôt que les macros brutes.

    Args:
        stack: Stack SQLAlchemy avec variables potentiellement contenant des macros

    Returns:
        StackResponse avec variables rendues
    """
    import re

    # Convertir l'objet SQLAlchemy en StackResponse Pydantic
    stack_response = StackResponse.model_validate(stack)

    if not stack_response.variables:
        return stack_response

    # Créer un renderer pour exécuter les macros
    renderer = TemplateRenderer()

    # Pattern pour détecter les macros Jinja {{ ... }}
    macro_pattern = re.compile(r"\{\{.*?\}\}")

    # Parcourir les variables pour détecter les macros
    variables_to_render = {}
    macro_info = {}

    for var_name, var_def in stack_response.variables.items():
        var_dict = dict(var_def) if isinstance(var_def, dict) else var_def

        # Copier pour ne pas modifier l'original avant le rendu
        var_to_render = var_dict.copy()

        # Vérifier si la valeur par défaut contient une macro
        default_value = var_dict.get("default")
        if (
            default_value
            and isinstance(default_value, str)
            and macro_pattern.search(default_value)
        ):
            macro_info[var_name] = {"has_macro": True, "macro_template": default_value}
        else:
            macro_info[var_name] = {"has_macro": False, "macro_template": None}

        variables_to_render[var_name] = var_to_render

    # Rendre uniquement les variables (leurs champs default, description, etc.)
    rendered_variables = renderer.render_dict(variables_to_render, {})

    # Réintégrer les informations de macro sans les rendre
    for var_name, info in macro_info.items():
        if var_name in rendered_variables:
            rendered_variables[var_name].update(info)

    # Créer une copie du stack avec les variables rendues
    stack_dict = stack_response.model_dump()
    stack_dict["variables"] = rendered_variables

    # Rendre le nom de déploiement par défaut si présent
    if stack.deployment_name:
        # Extraire les valeurs par défaut des variables pour le contexte
        context = {
            var_name: var_def.get("default")
            for var_name, var_def in rendered_variables.items()
            if "default" in var_def
        }
        stack_dict["default_name"] = renderer.render_string(
            stack.deployment_name, context
        )
    else:
        stack_dict["default_name"] = None

    return StackResponse(**stack_dict)


@router.get(
    "/",
    response_model=PaginatedResponse,
    status_code=status.HTTP_200_OK,
    summary="List all stacks in organization",
    description="""
List all Docker Compose stacks available in the current user's organizations.

## Features
- **Pagination**: `?page=1&per_page=20` (max 100) — STORY-128 canonical format,
  response envelope `PaginatedResponse{data, pagination{page, per_page, total, pages}}`
- **Organization Scoped**: Only returns stacks belonging to the user's organizations
  (single scoped query, no per-org paging)
- **Lightweight Response**: Returns only essential metadata for listing (id, name, version, category, etc.)
- **Stable order**: `ORDER BY name` — no duplicates/holes across pages

## Use Cases
- Display available stacks in the UI
- Browse stack catalog

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        200: {
            "description": ("Paginated list of stacks — enveloppe spec 09"),
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "550e8400-e29b-41d4-a716-446655440000",
                                "version": "1.0.0",
                                "category": "web",
                                "name": "nginx-stack",
                                "description": "Nginx web server",
                                "icon_url": "https://cdn.windflow.io/icons/nginx.svg",
                                "author": "WindFlow Team",
                                "license": "MIT",
                                "rating": 4.8,
                                "tags": ["web", "server"],
                                "downloads": 150,
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 87,
                            "pages": 5,
                        },
                        "message": None,
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": {
                            "code": "INVALID_OR_EXPIRED_TOKEN",
                            "message": "Missing or invalid authentication token",
                        }
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125",
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def list_stacks(
    request: Request,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    include_archived: bool = Query(False, description="Inclure les stacks archivées"),
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
):
    """
    Liste paginée des stacks Docker Compose des organisations de l'utilisateur.

    Retourne une version allégée des stacks pour le listing.
    Par défaut, les stacks archivées sont exclues.

    STORY-128 : pagination canonique ``?page=&per_page=`` — requête unique
    multi-org avec tri stable ``ORDER BY name`` et ``COUNT`` scopusé
    (remplace l'agrégation par-org aux pages chevauchantes).

    Args:
        request: Requête HTTP (pour correlation_id)
        page: Page demandée (1-indexée, défaut 1)
        per_page: Taille de page (1-100, défaut 20)
        include_archived: Inclure les stacks archivées dans le résultat
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        PaginatedResponse: Page de stacks (champs restreints) + métadonnées
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        "Listing stacks for user organizations",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "page": page,
            "per_page": per_page,
            "include_archived": include_archived,
        },
    )

    # STORY-121.3 : scoping sur les organisations de l'utilisateur
    # (appartenances via l'association ; STORY-128 : requête unique IN)
    org_ids = await UserOrganizationService.get_user_organization_ids(
        session, current_user
    )
    stacks = await StackService.list_by_organizations(
        session,
        org_ids,
        page=page,
        per_page=per_page,
        include_archived=include_archived,
    )
    total = await StackService.count_by_organizations(
        session, org_ids, include_archived=include_archived
    )

    data: List[Any] = [
        StackSummaryResponse.model_validate(s).model_dump() for s in stacks
    ]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.get(
    "/{stack_id}",
    response_model=StackResponse,
    status_code=status.HTTP_200_OK,
    summary="Get stack by ID",
    description="""
Retrieve a specific stack by its unique identifier.

## Features
- **Macro Rendering**: Variables with Jinja macros are automatically rendered with fresh concrete values
- **Organization Scoped**: Only accessible if the stack belongs to the user's organization
- **Complete Details**: Returns full stack configuration including compose content and variables

## Variable Rendering
Each time you retrieve a stack, macros in variable defaults are re-rendered:
- `{{ generate_password(24) }}` → New random password each time
- `{{ get_valid_port() }}` → Available port number
- `{{ random_string(16) }}` → New random string

This allows users to get fresh values without modifying the stack template.

## Use Cases
- View stack details before deployment
- Get fresh generated values for variables
- Inspect stack configuration
- Prepare deployment parameters

## Access Control
- **Minimum role**: Viewer — read-only access for any authenticated user
""",
    responses={
        200: {
            "description": "Stack retrieved successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "postgres-db",
                        "description": "PostgreSQL database with automatic password generation",
                        "target_type": "docker",
                        "organization_id": "org-123",
                        "compose_content": "version: '3.8'\nservices:\n  db:\n    image: postgres:15-alpine",
                        "variables": {
                            "POSTGRES_PASSWORD": {
                                "default": "xK9$mP2#nL7@qR5!wT8&",
                                "description": "Database password (auto-generated)",
                                "has_macro": True,
                                "macro_template": "{{ generate_password(24) }}",
                            },
                            "POSTGRES_USER": {
                                "default": "windflow",
                                "description": "Database username",
                                "has_macro": False,
                            },
                            "DB_PORT": {
                                "default": "5433",
                                "description": "Database port (auto-assigned)",
                                "has_macro": True,
                                "macro_template": "{{ get_valid_port() }}",
                            },
                        },
                        "created_at": "2026-01-02T10:00:00Z",
                        "updated_at": "2026-01-02T10:00:00Z",
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this stack",
                    }
                }
            },
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 not found",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125",
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(100, 60))],
)
async def get_stack(
    request: Request,
    stack_id: str,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
):
    """
    Récupère une stack par son ID.

    Les macros dans les variables par défaut (comme {{ generate_password(24) }})
    sont rendues pour que le frontend reçoive des valeurs concrètes.

    Args:
        request: Requête HTTP (pour correlation_id)
        stack_id: ID de la stack (string UUID)
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack demandée avec variables rendues

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Getting stack {stack_id}",
        extra={"correlation_id": correlation_id, "stack_id": stack_id},
    )

    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvée")

    # Vérifier que la stack appartient à la même organisation
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette stack")

    # Rendre les macros dans les variables avant de retourner
    return _render_stack_variables(stack)


@router.post(
    "/",
    response_model=StackResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new stack",
    description="""
Create a new Docker Compose stack definition in the organization.

## Stack Definition
A stack is a reusable template that defines:
- **Docker Compose configuration**: Services, networks, volumes
- **Variables**: Configurable parameters with default values and macros
- **Target Type**: Deployment target (docker, docker-compose, kubernetes)
- **Metadata**: Name, description, tags

## Variable Macros
Stacks can use Jinja macros in variable defaults:
- `{{ generate_password(24) }}`: Auto-generate secure passwords
- `{{ get_valid_port() }}`: Find available ports
- `{{ random_string(16) }}`: Generate random strings

These macros are rendered when the stack is retrieved, providing fresh values each time.

## Target Types
- **docker**: Single container deployment
- **docker-compose**: Multi-container application
- **kubernetes**: Kubernetes manifest deployment

## Use Cases
- Create reusable application templates
- Define infrastructure as code
- Share stack configurations across teams
- Version control deployment configurations

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "simple_nginx": {
                            "summary": "Simple Nginx web server",
                            "description": "Basic web server stack with configurable port",
                            "value": {
                                "name": "nginx-webserver",
                                "description": "Nginx web server for static content",
                                "target_type": "docker",
                                "compose_content": """version: '3.8'
services:
  web:
    image: nginx:alpine
    ports:
      - "${PORT}:80"
    volumes:
      - ./html:/usr/share/nginx/html""",
                                "variables": {
                                    "PORT": {
                                        "default": "8080",
                                        "description": "HTTP port for the web server",
                                    }
                                },
                            },
                        },
                        "postgres_with_macros": {
                            "summary": "PostgreSQL database with auto-generated password",
                            "description": "Database stack with secure password generation",
                            "value": {
                                "name": "postgres-db",
                                "description": "PostgreSQL database with automatic password generation",
                                "target_type": "docker",
                                "compose_content": """version: '3.8'
services:
  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "${DB_PORT}:5432"
volumes:
  postgres_data:""",
                                "variables": {
                                    "POSTGRES_PASSWORD": {
                                        "default": "{{ generate_password(24) }}",
                                        "description": "Database password (auto-generated)",
                                    },
                                    "POSTGRES_USER": {
                                        "default": "windflow",
                                        "description": "Database username",
                                    },
                                    "POSTGRES_DB": {
                                        "default": "windflow_db",
                                        "description": "Database name",
                                    },
                                    "DB_PORT": {
                                        "default": "{{ get_valid_port() }}",
                                        "description": "Database port (auto-assigned)",
                                    },
                                },
                            },
                        },
                        "fullstack_app": {
                            "summary": "Full-stack application (frontend + backend + database)",
                            "description": "Complete multi-container application stack",
                            "value": {
                                "name": "fullstack-app",
                                "description": "Complete web application with React frontend, Node.js API, and PostgreSQL",
                                "target_type": "docker-compose",
                                "compose_content": """version: '3.8'
services:
  frontend:
    image: node:18-alpine
    working_dir: /app
    volumes:
      - ./frontend:/app
    ports:
      - "${FRONTEND_PORT}:3000"
    environment:
      - REACT_APP_API_URL=http://localhost:${BACKEND_PORT}
    command: npm start

  backend:
    image: node:18-alpine
    working_dir: /app
    volumes:
      - ./backend:/app
    ports:
      - "${BACKEND_PORT}:3001"
    environment:
      - DATABASE_URL=postgresql://${DB_USER}:${DB_PASSWORD}@db:5432/${DB_NAME}
      - JWT_SECRET=${JWT_SECRET}
    command: npm start
    depends_on:
      - db

  db:
    image: postgres:15-alpine
    environment:
      POSTGRES_PASSWORD: ${DB_PASSWORD}
      POSTGRES_USER: ${DB_USER}
      POSTGRES_DB: ${DB_NAME}
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:""",
                                "variables": {
                                    "FRONTEND_PORT": {
                                        "default": "3000",
                                        "description": "Frontend port",
                                    },
                                    "BACKEND_PORT": {
                                        "default": "3001",
                                        "description": "Backend API port",
                                    },
                                    "DB_USER": {
                                        "default": "appuser",
                                        "description": "Database username",
                                    },
                                    "DB_PASSWORD": {
                                        "default": "{{ generate_password(32) }}",
                                        "description": "Database password",
                                    },
                                    "DB_NAME": {
                                        "default": "appdb",
                                        "description": "Database name",
                                    },
                                    "JWT_SECRET": {
                                        "default": "{{ random_string(64) }}",
                                        "description": "JWT signing secret",
                                    },
                                },
                            },
                        },
                        "kubernetes_deployment": {
                            "summary": "Kubernetes deployment manifest",
                            "description": "Deploy application to Kubernetes cluster",
                            "value": {
                                "name": "k8s-microservice",
                                "description": "Microservice deployment for Kubernetes",
                                "target_type": "kubernetes",
                                "compose_content": """apiVersion: apps/v1
kind: Deployment
metadata:
  name: ${APP_NAME}
  namespace: ${NAMESPACE}
spec:
  replicas: ${REPLICAS}
  selector:
    matchLabels:
      app: ${APP_NAME}
  template:
    metadata:
      labels:
        app: ${APP_NAME}
    spec:
      containers:
      - name: app
        image: ${IMAGE}
        ports:
        - containerPort: 8080
        env:
        - name: DATABASE_URL
          value: ${DATABASE_URL}
---
apiVersion: v1
kind: Service
metadata:
  name: ${APP_NAME}-service
  namespace: ${NAMESPACE}
spec:
  selector:
    app: ${APP_NAME}
  ports:
  - port: 80
    targetPort: 8080
  type: LoadBalancer""",
                                "variables": {
                                    "APP_NAME": {
                                        "default": "my-app",
                                        "description": "Application name",
                                    },
                                    "NAMESPACE": {
                                        "default": "production",
                                        "description": "Kubernetes namespace",
                                    },
                                    "REPLICAS": {
                                        "default": "3",
                                        "description": "Number of replicas",
                                    },
                                    "IMAGE": {
                                        "default": "myapp:latest",
                                        "description": "Container image",
                                    },
                                    "DATABASE_URL": {
                                        "default": "postgresql://user:pass@db:5432/mydb",
                                        "description": "Database connection string",
                                    },
                                },
                            },
                        },
                    }
                }
            }
        }
    },
    responses={
        201: {
            "description": "Stack created successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "nginx-webserver",
                        "description": "Nginx web server for static content",
                        "target_type": "docker",
                        "organization_id": "org-123",
                        "compose_content": "version: '3.8'\nservices:\n  web:\n    image: nginx:alpine",
                        "variables": {
                            "PORT": {
                                "default": "8080",
                                "description": "HTTP port for the web server",
                            }
                        },
                        "created_at": "2026-01-02T22:30:00Z",
                        "updated_at": "2026-01-02T22:30:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "invalid_compose": {
                            "summary": "Invalid Docker Compose syntax",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Invalid Docker Compose YAML syntax",
                                "correlation_id": "abc-123",
                            },
                        },
                        "missing_field": {
                            "summary": "Missing required field",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Field 'name' is required",
                                "correlation_id": "abc-124",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        409: {
            "description": "Stack name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Stack with name 'nginx-webserver' already exists in organization",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125",
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def create_stack(
    request: Request,
    stack_data: StackCreate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Crée une nouvelle stack Docker Compose.

    Args:
        request: Requête HTTP (pour correlation_id)
        stack_data: Données de la stack à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack créée

    Raises:
        HTTPException: Si le nom existe déjà dans l'organisation
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Creating stack '{stack_data.name}'",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_name": stack_data.name,
        },
    )
    # Vérifier que le nom n'existe pas déjà dans l'organisation
    # STORY-121.3 : organisation primaire de l'utilisateur
    primary_org = await UserOrganizationService.get_primary_organization_id(
        session, current_user
    )
    if primary_org is None:
        raise InvalidInputError("Aucune organisation : rattachez d'abord votre compte")
    existing = await StackService.get_by_name(session, primary_org, stack_data.name)
    if existing:
        raise ConflictError(f"Stack avec le nom '{stack_data.name}' existe déjà")

    # STORY-122.3 (AC 4) : isolation — l'organisation cible du body doit
    # être une organisation de l'utilisateur (organization_id requis par
    # StackCreate est appliqué tel quel par le service). Répare au passage
    # l'appel historique StackService.create(session, data, org) (signature
    # à 2 arguments — TypeError 500 préexistant).
    if stack_data.organization_id != primary_org and not (
        await UserOrganizationService.is_member(
            session, current_user, stack_data.organization_id
        )
    ):
        raise PermissionDeniedError("Accès refusé à cette organisation")

    # STORY-166.4 : FK environment_id vérifiée à l'écriture (404 si
    # environnement inexistant) + isolation organisationnelle (404 si
    # l'environnement appartient à une autre organisation).
    if stack_data.environment_id is not None:
        environment = await session.get(Environment, str(stack_data.environment_id))
        if environment is None or environment.organization_id != (
            stack_data.organization_id
        ):
            raise NotFoundError(
                f"Environnement {stack_data.environment_id} introuvable "
                "dans cette organisation"
            )

    stack = await StackService.create(session, stack_data)
    return stack


@router.put(
    "/{stack_id}",
    response_model=StackResponse,
    status_code=status.HTTP_200_OK,
    summary="Update an existing stack",
    description="""
Update an existing stack's configuration, variables, or metadata.

## Partial Updates
All fields in the request body are optional. Only provided fields will be updated.

## Updatable Fields
- **name**: Stack name (must be unique in organization)
- **description**: Stack description
- **compose_content**: Docker Compose YAML or Kubernetes manifest
- **variables**: Variable definitions with defaults and macros
- **target_type**: Deployment target (docker, docker-compose, kubernetes)

## Name Uniqueness
If updating the name, it must not conflict with another stack in the organization.

## Variable Macros
You can add or update variables with Jinja macros:
- `{{ generate_password(24) }}`: Auto-generate passwords
- `{{ get_valid_port() }}`: Find available ports
- `{{ random_string(16) }}`: Generate random strings

## Use Cases
- Fix bugs in stack configuration
- Add new variables or services
- Update Docker image versions
- Improve stack documentation
- Modify resource limits

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "update_name": {
                            "summary": "Update stack name only",
                            "description": "Change the stack's display name",
                            "value": {"name": "nginx-webserver-v2"},
                        },
                        "update_description": {
                            "summary": "Update description",
                            "description": "Improve stack documentation",
                            "value": {
                                "description": "Nginx web server with SSL support and caching"
                            },
                        },
                        "add_variable": {
                            "summary": "Add new variable with macro",
                            "description": "Add a new configurable parameter",
                            "value": {
                                "variables": {
                                    "PORT": {
                                        "default": "8080",
                                        "description": "HTTP port",
                                    },
                                    "SSL_PORT": {
                                        "default": "8443",
                                        "description": "HTTPS port",
                                    },
                                    "SSL_CERT_PASSWORD": {
                                        "default": "{{ generate_password(32) }}",
                                        "description": "SSL certificate password",
                                    },
                                }
                            },
                        },
                        "update_compose": {
                            "summary": "Update Docker Compose configuration",
                            "description": "Modify services or add new ones",
                            "value": {"compose_content": """version: '3.8'
services:
  web:
    image: nginx:alpine
    ports:
      - "${PORT}:80"
      - "${SSL_PORT}:443"
    volumes:
      - ./html:/usr/share/nginx/html
      - ./ssl:/etc/nginx/ssl
    environment:
      - NGINX_HOST=${DOMAIN}
      - NGINX_PORT=80"""},
                        },
                    }
                }
            }
        }
    },
    responses={
        200: {
            "description": "Stack updated successfully",
            "content": {
                "application/json": {
                    "example": {
                        "id": "550e8400-e29b-41d4-a716-446655440000",
                        "name": "nginx-webserver-v2",
                        "description": "Nginx web server with SSL support and caching",
                        "target_type": "docker",
                        "organization_id": "org-123",
                        "compose_content": "version: '3.8'\nservices:\n  web:\n    image: nginx:alpine",
                        "variables": {
                            "PORT": {"default": "8080", "description": "HTTP port"},
                            "SSL_PORT": {
                                "default": "8443",
                                "description": "HTTPS port",
                            },
                        },
                        "created_at": "2026-01-02T10:00:00Z",
                        "updated_at": "2026-01-02T22:45:00Z",
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation Error",
                        "detail": "Invalid Docker Compose YAML syntax",
                        "correlation_id": "abc-123",
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this stack",
                    }
                }
            },
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 not found",
                    }
                }
            },
        },
        409: {
            "description": "Stack name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Stack with name 'nginx-webserver-v2' already exists in organization",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125",
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def update_stack(
    request: Request,
    stack_id: str,
    stack_data: StackUpdate,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Met à jour une stack Docker Compose.

    Args:
        request: Requête HTTP (pour correlation_id)
        stack_id: ID de la stack à modifier
        stack_data: Nouvelles données de la stack
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack mise à jour

    Raises:
        HTTPException: Si la stack n'existe pas, accès refusé ou nom en conflit
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Updating stack {stack_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": stack_id,
        },
    )
    # Vérifier que la stack existe
    existing_stack = await StackService.get_by_id(session, stack_id)
    if not existing_stack:
        raise NotFoundError(f"Stack {stack_id} non trouvée")

    # Vérifier les permissions (STORY-121.3 : appartenance via l'association)
    if not await UserOrganizationService.is_member(
        session, current_user, existing_stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette stack")

    # STORY-166.4 : FK environment_id vérifiée à l'écriture (404 si
    # inexistant) + isolation organisationnelle (404 si l'environnement
    # appartient à une autre organisation que la stack).
    if stack_data.environment_id is not None:
        environment = await session.get(Environment, str(stack_data.environment_id))
        if environment is None or environment.organization_id != (
            existing_stack.organization_id
        ):
            raise NotFoundError(
                f"Environnement {stack_data.environment_id} introuvable "
                "dans cette organisation"
            )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if stack_data.name and stack_data.name != existing_stack.name:
        # STORY-121.3 : unicité vérifiée dans l'organisation de la stack
        existing_name = await StackService.get_by_name(
            session, existing_stack.organization_id, stack_data.name
        )
        if existing_name:
            raise ConflictError(f"Stack avec le nom '{stack_data.name}' existe déjà")

    # Créer une version automatique si le compose_content change
    if (
        stack_data.compose_content  # type: ignore[attr-defined]
        and stack_data.compose_content != existing_stack.compose_content  # type: ignore[attr-defined]
    ):
        max_version_stmt = select(
            func.coalesce(func.max(StackVersion.version_number), 0)
        ).where(StackVersion.stack_id == stack_id)
        max_version = (await session.execute(max_version_stmt)).scalar() or 0

        # Sauvegarder l'état actuel avant modification
        version = StackVersion(
            stack_id=stack_id,
            version_number=max_version + 1,
            compose_content=existing_stack.compose_content,  # type: ignore[attr-defined]
            variables=existing_stack.variables or {},
            change_summary="Auto-saved before update",
            created_by=str(current_user.id),
        )
        session.add(version)

    stack = await StackService.update(session, stack_id, stack_data)
    return stack


@router.delete(
    "/{stack_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a stack",
    description="""
Delete a stack permanently from the organization.

## Warning
This operation is **irreversible**. The stack definition will be permanently deleted.

## Impact
- Stack configuration is removed
- Variable definitions are deleted
- Stack cannot be used for new deployments

## Safety Checks
- Stack must exist
- User must have access to the stack's organization
- Existing deployments using this stack are **not affected**

## Use Cases
- Remove obsolete stack templates
- Clean up test stacks
- Remove deprecated configurations
- Maintain stack catalog hygiene

## Access Control
- **Minimum role**: Admin — resource management (create/delete/configure)
""",
    responses={
        204: {"description": "Stack deleted successfully (no content returned)"},
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this stack",
                    }
                }
            },
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 not found",
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "An unexpected error occurred",
                        "correlation_id": "abc-125",
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def delete_stack(
    request: Request,
    stack_id: str,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
):
    """
    Supprime une stack Docker Compose.

    Args:
        request: Requête HTTP (pour correlation_id)
        stack_id: ID de la stack à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Deleting stack {stack_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": stack_id,
        },
    )
    # Vérifier que la stack existe
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvée")

    # Vérifier les permissions
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette stack")

    await StackService.delete(session, stack_id)

    # STORY-125.2 : audit de la suppression (après succès — test de référence
    # P1-4) : ligne avec acteur, org de la stack, action, cible et le
    # correlation_id du middleware (header X-Correlation-ID → DB).
    await AuditService.log_from_request(
        request,
        "stack.deleted",
        user=current_user,
        organization_id=stack.organization_id,
        resource_type="stack",
        resource_id=stack_id,
        details={"name": stack.name},
    )


@router.post(
    "/{stack_id}/regenerate-variable/{variable_name}",
    status_code=status.HTTP_200_OK,
    summary="Regenerate a variable value with macro",
    description="""
Regenerate a fresh value for a stack variable that contains a Jinja macro.

## Purpose
This endpoint allows you to generate a new value for variables with macros (like `{{ generate_password(24) }}`)
without having to reload the entire stack or create a new deployment.

## Use Cases
- **Get a fresh password**: Regenerate a new random password for testing
- **Get a new port**: Request a different available port number
- **Refresh random values**: Generate new random strings or tokens

## Access Control
- **Minimum role**: Operator — operational action (generate fresh values)

## Supported Macros
- `{{ generate_password(length) }}`: Generates a new secure random password
- `{{ get_valid_port() }}`: Returns a new available port number
- `{{ random_string(length) }}`: Generates a new random alphanumeric string

## Requirements
- Variable must exist in the stack
- Variable must have a `default` value
- Default value must contain a Jinja macro (`{{ ... }}`)

## Response
Returns the newly generated value along with the original macro template for reference.
""",
    responses={
        200: {
            "description": "Variable value regenerated successfully",
            "content": {
                "application/json": {
                    "examples": {
                        "password_regenerated": {
                            "summary": "Password regenerated",
                            "description": "New password generated from macro",
                            "value": {
                                "variable_name": "POSTGRES_PASSWORD",
                                "new_value": "xK9$mP2#nL7@qR5!wT8&vZ3%",
                                "macro_template": "{{ generate_password(24) }}",
                            },
                        },
                        "port_regenerated": {
                            "summary": "Port regenerated",
                            "description": "New available port assigned",
                            "value": {
                                "variable_name": "DB_PORT",
                                "new_value": "5433",
                                "macro_template": "{{ get_valid_port() }}",
                            },
                        },
                        "random_string_regenerated": {
                            "summary": "Random string regenerated",
                            "description": "New random string generated",
                            "value": {
                                "variable_name": "API_KEY",
                                "new_value": "aB3xY9mK2pL7wT8v",
                                "macro_template": "{{ random_string(16) }}",
                            },
                        },
                    }
                }
            },
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "examples": {
                        "no_default_value": {
                            "summary": "Variable has no default value",
                            "value": {
                                "error": "Bad Request",
                                "detail": "Variable 'PORT' n'a pas de valeur par défaut",
                            },
                        },
                        "no_macro": {
                            "summary": "Variable does not contain a macro",
                            "value": {
                                "error": "Bad Request",
                                "detail": "Variable 'STATIC_VALUE' ne contient pas de macro à régénérer",
                            },
                        },
                    }
                }
            },
        },
        401: {
            "description": "Authentication required",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Unauthorized",
                        "detail": "Missing or invalid authentication token",
                    }
                }
            },
        },
        403: {
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à ce stack",
                    }
                }
            },
        },
        404: {
            "description": "Stack or variable not found",
            "content": {
                "application/json": {
                    "examples": {
                        "stack_not_found": {
                            "summary": "Stack not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 non trouvé",
                            },
                        },
                        "variable_not_found": {
                            "summary": "Variable not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Variable 'UNKNOWN_VAR' non trouvée dans le stack",
                            },
                        },
                    }
                }
            },
        },
        500: {
            "description": "Internal server error",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Internal Server Error",
                        "detail": "Erreur lors de la régénération de la macro: Template syntax error",
                        "correlation_id": "abc-125",
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def regenerate_variable(
    request: Request,
    stack_id: str,
    variable_name: str,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
):
    """
    Régénère la valeur d'une variable contenant une macro Jinja.

    Cette route permet de régénérer une nouvelle valeur pour les variables
    qui contiennent des macros (comme generate_password, get_valid_port, etc.)
    sans avoir à recharger tout le stack.

    Args:
        request: Requête HTTP (pour correlation_id)
        stack_id: ID du stack
        variable_name: Nom de la variable à régénérer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        dict: Nouvelle valeur générée pour la variable

    Raises:
        HTTPException: Si le stack n'existe pas, accès refusé, variable introuvable ou pas de macro
    """
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Regenerating variable '{variable_name}' for stack {stack_id}",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": stack_id,
            "variable_name": variable_name,
        },
    )
    # Vérifier que le stack existe
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvé")

    # Vérifier les permissions
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à ce stack")

    # Vérifier que la variable existe
    if not stack.variables or variable_name not in stack.variables:
        raise NotFoundError(f"Variable '{variable_name}' non trouvée dans le stack")

    variable_def = stack.variables[variable_name]

    # Vérifier que la variable a une valeur par défaut
    if "default" not in variable_def:
        raise InvalidInputError(
            f"Variable '{variable_name}' n'a pas de valeur par défaut"
        )

    default_value = variable_def["default"]

    # Vérifier que la valeur par défaut contient une macro
    import re

    macro_pattern = re.compile(r"\{\{.*?\}\}")
    if not isinstance(default_value, str) or not macro_pattern.search(default_value):
        raise InvalidInputError(
            f"Variable '{variable_name}' ne contient pas de macro à régénérer"
        )

    # Régénérer la valeur en rendant le template
    renderer = TemplateRenderer()
    try:
        new_value = renderer.render_string(default_value, {})
        return {
            "variable_name": variable_name,
            "new_value": new_value,
            "macro_template": default_value,
        }
    except Exception as e:
        raise WindFlowException(f"Erreur lors de la régénération de la macro: {str(e)}")


# ─── Stack Versioning ────────────────────────────────────────────────


@router.get(
    "/{stack_id}/versions",
    response_model=PaginatedResponse,
    summary="List stack versions (paginated)",
    description="""
Version history of a stack, most recent first — STORY-128 canonical
pagination `?page=1&per_page=20` (max 100).

## Access Control
- **Minimum role**: Viewer — must be a member of the stack's organization
  (cross-organization isolation preserved)
""",
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
    responses={
        200: {
            "description": "Paginated version history — enveloppe spec 09",
            "content": {
                "application/json": {
                    "example": {
                        "data": [
                            {
                                "id": "990e8400-e29b-41d4-a716-446655440010",
                                "version_number": 3,
                                "change_summary": "Manual snapshot",
                            }
                        ],
                        "pagination": {
                            "page": 1,
                            "per_page": 20,
                            "total": 3,
                            "pages": 1,
                        },
                        "message": None,
                    }
                }
            },
        },
    },
)
async def list_stack_versions(
    stack_id: str,
    page: int = PaginationQuery.page,
    per_page: int = PaginationQuery.per_page,
    current_user: User = Depends(require_viewer),
    session: AsyncSession = Depends(get_db),
) -> PaginatedResponse:
    """Liste paginée de l'historique des versions d'un stack (STORY-128).

    Tri ``version_number desc`` conservé ; ``COUNT`` scopé au stack
    (même filtre que la liste).
    """
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvé")
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé")

    stmt = (
        select(StackVersion)
        .where(StackVersion.stack_id == stack_id)
        .order_by(StackVersion.version_number.desc())
        .offset((page - 1) * per_page)
        .limit(per_page)
    )
    result = await session.execute(stmt)
    versions = result.scalars().all()

    count_stmt = (
        select(func.count())
        .select_from(StackVersion)
        .where(StackVersion.stack_id == stack_id)
    )
    total = int((await session.execute(count_stmt)).scalar() or 0)

    data: List[Any] = [
        StackVersionResponse(
            id=v.id,
            stack_id=v.stack_id,
            version_number=v.version_number,
            compose_content=v.compose_content,
            variables=v.variables or {},
            change_summary=v.change_summary,
            created_by=v.created_by,
            author_name=v.author.username if v.author else None,
            created_at=v.created_at,
        ).model_dump()
        for v in versions
    ]
    return PaginatedResponse(data=data, pagination=build_meta(page, per_page, total))


@router.post(
    "/{stack_id}/versions",
    response_model=StackVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a manual version snapshot",
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def create_stack_version(
    stack_id: str,
    version_data: StackVersionCreate,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
) -> StackVersionResponse:
    """Crée un snapshot manuel de la version actuelle du stack."""
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvé")
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé")

    max_stmt = select(func.coalesce(func.max(StackVersion.version_number), 0)).where(
        StackVersion.stack_id == stack_id
    )
    max_version = (await session.execute(max_stmt)).scalar() or 0

    version = StackVersion(
        stack_id=stack_id,
        version_number=max_version + 1,
        compose_content=(
            stack.compose_content
            if hasattr(stack, "compose_content")
            else str(stack.template)
        ),
        variables=stack.variables or {},
        change_summary=version_data.change_summary or "Manual snapshot",
        created_by=str(current_user.id),
    )
    session.add(version)
    await session.commit()
    await session.refresh(version)

    return StackVersionResponse(
        id=version.id,
        stack_id=version.stack_id,
        version_number=version.version_number,
        compose_content=version.compose_content,
        variables=version.variables or {},
        change_summary=version.change_summary,
        created_by=version.created_by,
        author_name=(
            current_user.username if hasattr(current_user, "username") else None
        ),
        created_at=version.created_at,
    )


@router.post(
    "/{stack_id}/versions/{version_id}/restore",
    response_model=StackResponse,
    summary="Restore a stack to a previous version",
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(10, 60))],
)
async def restore_stack_version(
    request: Request,
    stack_id: str,
    version_id: str,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
):
    """Restaure un stack à une version précédente."""
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvé")
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé")

    version_stmt = select(StackVersion).where(
        StackVersion.id == version_id,
        StackVersion.stack_id == stack_id,
    )
    version = (await session.execute(version_stmt)).scalar_one_or_none()
    if not version:
        raise NotFoundError(f"Version {version_id} non trouvée")

    # Sauvegarder l'état actuel avant restauration
    max_stmt = select(func.coalesce(func.max(StackVersion.version_number), 0)).where(
        StackVersion.stack_id == stack_id
    )
    max_version = (await session.execute(max_stmt)).scalar() or 0

    current_snapshot = StackVersion(
        stack_id=stack_id,
        version_number=max_version + 1,
        compose_content=(
            stack.compose_content
            if hasattr(stack, "compose_content")
            else str(stack.template)
        ),
        variables=stack.variables or {},
        change_summary=f"Auto-saved before restore to v{version.version_number}",
        created_by=str(current_user.id),
    )
    session.add(current_snapshot)

    # Restaurer
    update_data = StackUpdate(compose_content=version.compose_content)  # type: ignore[call-arg]
    updated_stack = await StackService.update(session, stack_id, update_data)

    # STORY-125.2 : audit du rollback (après succès de la restauration —
    # catalogue spec 15 ``stack.rollback`` ; correlation_id du middleware).
    await AuditService.log_from_request(
        request,
        "stack.rollback",
        user=current_user,
        organization_id=stack.organization_id,
        resource_type="stack",
        resource_id=stack_id,
        details={"restored_version_id": version_id},
    )
    return updated_stack


# ─── Stack Actions (Start / Stop / Redeploy) ─────────────────────────


async def _get_stack_and_containers(
    stack_id: str,
    current_user: User,
    session: AsyncSession,
) -> tuple:
    """
    Helper : vérifie la stack (existence + permissions) et retourne
    les containers Docker associés via le label windflow.stack_id.

    Returns:
        (stack, stack_containers) — objets Stack et liste de ContainerInfo

    Raises:
        HTTPException: 404, 403 ou 503 si Docker indisponible
    """
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise NotFoundError(f"Stack {stack_id} non trouvée")
    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        raise PermissionDeniedError("Accès refusé à cette stack")

    # Récupérer les containers Docker associés
    try:
        docker = DockerClientService()
        if not await docker.ping():
            await docker.close()
            raise ServiceUnavailableError("Docker n'est pas disponible")
        all_containers = await docker.list_containers(all=True)
        await docker.close()
    except WindFlowException:
        raise
    except Exception as exc:
        logger.error(f"Docker indisponible : {exc}")
        raise ServiceUnavailableError(f"Docker n'est pas disponible : {exc}")

    # Filtrer par label windflow.stack_id
    stack_containers = [
        c for c in all_containers if c.labels.get("windflow.stack_id") == stack_id
    ]

    return stack, stack_containers


@router.post(
    "/{stack_id}/start",
    response_model=StackActionResponse,
    summary="Start all services of a stack",
    description="""
Start all containers belonging to a managed stack.

## Behavior
- Finds all Docker containers with the label `windflow.stack_id` matching the stack ID
- Starts each container that is not already running
- Returns the count of affected services

## Prerequisites
- Stack must exist and belong to the user's organization
- Docker must be available

## Access Control
- **Minimum role**: Operator — operational action on running resources
""",
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def start_stack(
    request: Request,
    stack_id: str,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
):
    """Démarre tous les containers d'une stack managée."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Starting stack {stack_id}",
        extra={"correlation_id": correlation_id, "stack_id": stack_id},
    )

    stack, containers = await _get_stack_and_containers(stack_id, current_user, session)

    if not containers:
        return StackActionResponse(
            success=True,
            message=f"Aucun container trouvé pour la stack '{stack.name}'",
            stack_id=stack_id,
            stack_name=stack.name,
            affected_services=0,
            action="start",
        )

    started = 0
    errors: list[str] = []
    docker = DockerClientService()
    try:
        for container in containers:
            if container.state != "running":
                try:
                    await docker.start_container(container.id)
                    started += 1
                except Exception as exc:
                    errors.append(f"{container.name}: {exc}")
            else:
                started += 1
    finally:
        await docker.close()

    message = f"Stack '{stack.name}' démarrée ({started}/{len(containers)} services)"
    if errors:
        message += f" — erreurs : {'; '.join(errors[:3])}"

    return StackActionResponse(
        success=len(errors) == 0,
        message=message,
        stack_id=stack_id,
        stack_name=stack.name,
        affected_services=started,
        action="start",
    )


@router.post(
    "/{stack_id}/stop",
    response_model=StackActionResponse,
    summary="Stop all services of a stack",
    description="""
Stop all containers belonging to a managed stack.

## Behavior
- Finds all Docker containers with the label `windflow.stack_id` matching the stack ID
- Stops each running container
- Returns the count of affected services

## Prerequisites
- Stack must exist and belong to the user's organization
- Docker must be available

## Access Control
- **Minimum role**: Operator — operational action on running resources
""",
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(30, 60))],
)
async def stop_stack(
    request: Request,
    stack_id: str,
    timeout: int = 10,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
):
    """Arrête tous les containers d'une stack managée."""
    correlation_id = getattr(request.state, "correlation_id", None)
    logger.info(
        f"Stopping stack {stack_id}",
        extra={"correlation_id": correlation_id, "stack_id": stack_id},
    )

    stack, containers = await _get_stack_and_containers(stack_id, current_user, session)

    if not containers:
        return StackActionResponse(
            success=True,
            message=f"Aucun container trouvé pour la stack '{stack.name}'",
            stack_id=stack_id,
            stack_name=stack.name,
            affected_services=0,
            action="stop",
        )

    stopped = 0
    errors: list[str] = []
    docker = DockerClientService()
    try:
        for container in containers:
            if container.state == "running":
                try:
                    await docker.stop_container(container.id, timeout=timeout)
                    stopped += 1
                except Exception as exc:
                    errors.append(f"{container.name}: {exc}")
            else:
                stopped += 1
    finally:
        await docker.close()

    message = f"Stack '{stack.name}' arrêtée ({stopped}/{len(containers)} services)"
    if errors:
        message += f" — erreurs : {'; '.join(errors[:3])}"

    return StackActionResponse(
        success=len(errors) == 0,
        message=message,
        stack_id=stack_id,
        stack_name=stack.name,
        affected_services=stopped,
        action="stop",
    )


@router.post(
    "/{stack_id}/redeploy",
    response_model=StackRedeployResponse,
    summary="Redeploy a stack",
    description="""
Redeploy all containers belonging to a managed stack.

## Strategies
- **stop_start** (default): Stop all containers, then start them all
- **rolling**: Restart containers one by one (stop → start → wait for running → next)

## Behavior
- Finds all Docker containers with the label `windflow.stack_id` matching the stack ID
- Applies the selected strategy
- Returns the count of affected services and strategy used

## Prerequisites
- Stack must exist and belong to the user's organization
- Docker must be available

## Access Control
- **Minimum role**: Operator — operational action (redeploy/rollback)
""",
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def redeploy_stack(
    request: Request,
    stack_id: str,
    redeploy_data: StackRedeployRequest = StackRedeployRequest(),
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
):
    """Redéploie une stack avec la stratégie choisie."""
    correlation_id = getattr(request.state, "correlation_id", None)
    strategy = redeploy_data.strategy
    logger.info(
        f"Redeploying stack {stack_id} (strategy={strategy})",
        extra={
            "correlation_id": correlation_id,
            "stack_id": stack_id,
            "strategy": strategy,
        },
    )

    stack, containers = await _get_stack_and_containers(stack_id, current_user, session)

    if not containers:
        return StackRedeployResponse(
            success=True,
            message=f"Aucun container trouvé pour la stack '{stack.name}'",
            stack_id=stack_id,
            stack_name=stack.name,
            affected_services=0,
            action="redeploy",
            strategy=strategy,
        )

    affected = 0
    errors: list[str] = []
    docker = DockerClientService()
    try:
        if strategy == "rolling":
            # Rolling : un par un, stop → start → vérifier running
            for container in containers:
                try:
                    await docker.stop_container(container.id, timeout=10)
                    await docker.start_container(container.id)
                    affected += 1
                except Exception as exc:
                    errors.append(f"{container.name}: {exc}")
        else:
            # stop_start : arrêter tout, puis démarrer tout
            for container in containers:
                try:
                    if container.state == "running":
                        await docker.stop_container(container.id, timeout=10)
                except Exception as exc:
                    errors.append(f"stop {container.name}: {exc}")

            for container in containers:
                try:
                    await docker.start_container(container.id)
                    affected += 1
                except Exception as exc:
                    errors.append(f"start {container.name}: {exc}")
    finally:
        await docker.close()

    message = (
        f"Stack '{stack.name}' redéployée ({affected}/{len(containers)} services, "
        f"stratégie : {strategy})"
    )
    if errors:
        message += f" — erreurs : {'; '.join(errors[:3])}"

    return StackRedeployResponse(
        success=len(errors) == 0,
        message=message,
        stack_id=stack_id,
        stack_name=stack.name,
        affected_services=affected,
        action="redeploy",
        strategy=strategy,
    )


@router.post(
    "/{stack_id}/duplicate",
    response_model=StackResponse,
    status_code=status.HTTP_200_OK,
    summary="Duplicate a stack",
    description="""
    Duplicate an existing stack with a new name.

    ## Features
    - **Copy Template**: Copies the full Docker Compose template
    - **Copy Variables**: Preserves all configurable variables
    - **Tag**: Adds a "duplicate" tag to the new stack
    - **Private**: The duplicated stack is private by default
    - **Organization**: Optionally target a different organization

    ## Access Control
    - **Minimum role**: Admin — stack creation (duplicated configuration)
    """,
    responses={
        200: {
            "description": "Stack duplicated successfully",
        },
        404: {
            "description": "Source stack not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Stack non trouvé: stack-123"}
                }
            },
        },
        409: {
            "description": "A stack with this name already exists in the target organization",
            "content": {
                "application/json": {
                    "example": {
                        "detail": "Un stack nommé 'My Stack (copy)' existe déjà"
                    }
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def duplicate_stack(
    stack_id: str,
    data: StackDuplicateRequest,
    current_user: User = Depends(require_admin),
    session: AsyncSession = Depends(get_db),
) -> StackResponse:
    """
    Duplique un stack existant.

    Crée une copie du stack avec un nouveau nom, optionnellement
    dans une autre organisation.
    """
    original_stack = await StackService.get_by_id(session, stack_id)

    if not original_stack:
        raise NotFoundError(f"Stack non trouvé: {stack_id}")

    # Vérifier l'unicité du nom dans l'organisation cible
    target_org_id = data.organization_id or original_stack.organization_id
    existing = await StackService.get_by_name(session, data.new_name, target_org_id)

    if existing:
        raise ConflictError(f"Un stack nommé '{data.new_name}' existe déjà")

    # Construire les données de la copie
    original_tags = list(original_stack.tags) if original_stack.tags else []
    stack_data = StackCreate(  # type: ignore[call-arg]
        name=data.new_name,
        description=f"Copie de {original_stack.name}: {original_stack.description or ''}",
        template=original_stack.template,
        variables=original_stack.variables or {},
        version=original_stack.version,
        category=original_stack.category,
        tags=original_tags + ["duplicate"],
        is_public=False,
        organization_id=target_org_id,
    )

    new_stack = await StackService.create(session, stack_data)

    return StackResponse.model_validate(new_stack)


@router.post(
    "/{stack_id}/archive",
    response_model=StackActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Archive a stack",
    description="""
    Archive a stack to remove it from the main listing.

    ## Features
    - **Soft archive**: Sets `is_archived=True` and `archived_at=now`
    - **Idempotent**: Archiving an already archived stack is a no-op
    - **Organization scoped**: Only accessible if the stack belongs to the user's organization

    ## Access Control
    - **Minimum role**: Operator — operational action on running resources
    """,
    responses={
        200: {
            "description": "Stack archived successfully",
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Stack non trouvé: stack-123"}
                }
            },
        },
        403: {
            "description": "Forbidden — stack belongs to another organization",
            "content": {
                "application/json": {
                    "example": {"detail": "Accès non autorisé à ce stack"}
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def archive_stack(
    stack_id: str,
    request: Request,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
) -> StackActionResponse:
    """
    Archive un stack.

    Marque le stack comme archivé pour le retirer de la vue principale.
    """
    correlation_id = getattr(request.state, "correlation_id", None)

    stack = await StackService.get_by_id(session, stack_id)

    if not stack:
        raise NotFoundError(f"Stack non trouvé: {stack_id}")

    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        logger.warning(
            "Archive denied — org mismatch",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "stack_id": stack_id,
                "stack_org": stack.organization_id,
                "user_org": "multiple",
            },
        )
        raise PermissionDeniedError("Accès non autorisé à ce stack")

    updated_stack = await StackService.archive(session, stack_id)

    logger.info(
        "Stack archived",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": stack_id,
        },
    )

    return StackActionResponse(
        success=True,
        message=f"Stack '{updated_stack.name}' archivée avec succès",
        stack_id=stack_id,
        stack_name=updated_stack.name,
        affected_services=0,
        action="archive",
    )


@router.post(
    "/{stack_id}/unarchive",
    response_model=StackActionResponse,
    status_code=status.HTTP_200_OK,
    summary="Unarchive a stack",
    description="""
    Restore an archived stack to the main listing.

    ## Features
    - **Restore**: Sets `is_archived=False` and `archived_at=None`
    - **Idempotent**: Unarchiving a non-archived stack is a no-op
    - **Organization scoped**: Only accessible if the stack belongs to the user's organization

    ## Access Control
    - **Minimum role**: Operator — operational action on running resources
    """,
    responses={
        200: {
            "description": "Stack unarchived successfully",
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {"detail": "Stack non trouvé: stack-123"}
                }
            },
        },
        403: {
            "description": "Forbidden — stack belongs to another organization",
            "content": {
                "application/json": {
                    "example": {"detail": "Accès non autorisé à ce stack"}
                }
            },
        },
    },
    tags=["stacks"],
    dependencies=[Depends(conditional_rate_limiter(20, 60))],
)
async def unarchive_stack(
    stack_id: str,
    request: Request,
    current_user: User = Depends(require_operator),
    session: AsyncSession = Depends(get_db),
) -> StackActionResponse:
    """
    Désarchive un stack.

    Restaure un stack archivé dans la vue principale.
    """
    correlation_id = getattr(request.state, "correlation_id", None)

    stack = await StackService.get_by_id(session, stack_id)

    if not stack:
        raise NotFoundError(f"Stack non trouvé: {stack_id}")

    if not await UserOrganizationService.is_member(
        session, current_user, stack.organization_id
    ):
        logger.warning(
            "Unarchive denied — org mismatch",
            extra={
                "correlation_id": correlation_id,
                "user_id": str(current_user.id),
                "stack_id": stack_id,
                "stack_org": stack.organization_id,
                "user_org": "multiple",
            },
        )
        raise PermissionDeniedError("Accès non autorisé à ce stack")

    updated_stack = await StackService.unarchive(session, stack_id)

    logger.info(
        "Stack unarchived",
        extra={
            "correlation_id": correlation_id,
            "user_id": str(current_user.id),
            "stack_id": stack_id,
        },
    )

    return StackActionResponse(
        success=True,
        message=f"Stack '{updated_stack.name}' désarchivée avec succès",
        stack_id=stack_id,
        stack_name=updated_stack.name,
        affected_services=0,
        action="unarchive",
    )
