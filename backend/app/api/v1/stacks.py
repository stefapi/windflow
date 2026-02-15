"""
Routes de gestion des stacks Docker Compose.
"""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from ...database import get_db
from ...schemas.stack import StackResponse, StackCreate, StackUpdate
from ...services.stack_service import StackService
from ...auth.dependencies import get_current_active_user
from ...models.user import User
from ...helper.template_renderer import TemplateRenderer
from ...helper.jinja_functions import JinjaFunctions

router = APIRouter()


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
    macro_pattern = re.compile(r'\{\{.*?\}\}')

    # Parcourir les variables pour détecter et marquer les macros
    variables_with_macro_info = {}
    for var_name, var_def in stack_response.variables.items():
        var_dict = dict(var_def) if isinstance(var_def, dict) else var_def

        # Vérifier si la valeur par défaut contient une macro
        default_value = var_dict.get('default')
        if default_value and isinstance(default_value, str) and macro_pattern.search(default_value):
            # Marquer comme ayant une macro et sauvegarder le template original
            var_dict['has_macro'] = True
            var_dict['macro_template'] = default_value
        else:
            var_dict['has_macro'] = False
            var_dict['macro_template'] = None

        variables_with_macro_info[var_name] = var_dict

    # Rendre les variables (qui peuvent contenir des macros dans les defaults)
    rendered_variables = renderer.render_dict(variables_with_macro_info, {})

    # Créer une copie du stack avec les variables rendues
    stack_dict = stack_response.model_dump()
    stack_dict['variables'] = rendered_variables

    # Rendre le nom de déploiement par défaut si présent
    if stack.deployment_name:
        # Extraire les valeurs par défaut des variables pour le contexte
        context = {var_name: var_def.get('default') for var_name, var_def in rendered_variables.items() if 'default' in var_def}
        stack_dict['default_name'] = renderer.render_string(stack.deployment_name, context)
    else:
        stack_dict['default_name'] = None

    return StackResponse(**stack_dict)


@router.get(
    "/",
    response_model=List[StackResponse],
    status_code=status.HTTP_200_OK,
    summary="List all stacks in organization",
    description="""
List all Docker Compose stacks available in the current user's organization.

## Features
- **Pagination**: Use `skip` and `limit` parameters for pagination
- **Macro Rendering**: Variables with Jinja macros (like `{{ generate_password(24) }}`) are automatically rendered with concrete values
- **Organization Scoped**: Only returns stacks belonging to the user's organization

## Variable Macros
The following macros are automatically rendered:
- `{{ generate_password(length) }}`: Generates a secure random password
- `{{ get_valid_port() }}`: Returns an available port number
- `{{ random_string(length) }}`: Generates a random alphanumeric string

## Use Cases
- Display available stacks in the UI
- Select a stack for deployment
- Browse stack catalog

**Authentication Required**
""",
    responses={
        200: {
            "description": "List of stacks retrieved successfully",
            "content": {
                "application/json": {
                    "example": [
                        {
                            "id": "550e8400-e29b-41d4-a716-446655440000",
                            "name": "nginx-stack",
                            "description": "Nginx web server",
                            "target_type": "docker",
                            "organization_id": "org-123",
                            "variables": {
                                "PORT": {
                                    "default": "8080",
                                    "description": "HTTP port"
                                }
                            },
                            "created_at": "2026-01-02T10:00:00Z",
                            "updated_at": "2026-01-02T10:00:00Z"
                        },
                        {
                            "id": "660e8400-e29b-41d4-a716-446655440001",
                            "name": "postgres-stack",
                            "description": "PostgreSQL database",
                            "target_type": "docker",
                            "organization_id": "org-123",
                            "variables": {
                                "POSTGRES_PASSWORD": {
                                    "default": "aB3$xY9#mK2@pL7!",
                                    "description": "Database password",
                                    "has_macro": True,
                                    "macro_template": "{{ generate_password(24) }}"
                                }
                            },
                            "created_at": "2026-01-02T11:00:00Z",
                            "updated_at": "2026-01-02T11:00:00Z"
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
                        "correlation_id": "abc-125"
                    }
                }
            }
        }
    },
    tags=["stacks"]
)
async def list_stacks(
    skip: int = 0,
    limit: int = 100,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Liste les stacks Docker Compose de l'organisation.

    Les macros dans les variables par défaut (comme {{ generate_password(24) }})
    sont rendues pour que le frontend reçoive des valeurs concrètes.

    Args:
        skip: Nombre d'éléments à ignorer pour la pagination
        limit: Nombre maximum d'éléments à retourner
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        List[StackResponse]: Liste des stacks avec variables rendues
    """
    stacks = await StackService.list_by_organization(
        session,
        current_user.organization_id,
        skip,
        limit
    )

    # Rendre les macros dans les variables de chaque stack
    rendered_stacks = [_render_stack_variables(stack) for stack in stacks]

    return rendered_stacks


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

**Authentication Required**
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
                                "macro_template": "{{ generate_password(24) }}"
                            },
                            "POSTGRES_USER": {
                                "default": "windflow",
                                "description": "Database username",
                                "has_macro": False
                            },
                            "DB_PORT": {
                                "default": "5433",
                                "description": "Database port (auto-assigned)",
                                "has_macro": True,
                                "macro_template": "{{ get_valid_port() }}"
                            }
                        },
                        "created_at": "2026-01-02T10:00:00Z",
                        "updated_at": "2026-01-02T10:00:00Z"
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
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this stack"
                    }
                }
            }
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 not found"
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
    tags=["stacks"]
)
async def get_stack(
    stack_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Récupère une stack par son ID.

    Les macros dans les variables par défaut (comme {{ generate_password(24) }})
    sont rendues pour que le frontend reçoive des valeurs concrètes.

    Args:
        stack_id: ID de la stack (string UUID)
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack demandée avec variables rendues

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier que la stack appartient à la même organisation
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

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

**Authentication Required**
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
                                        "description": "HTTP port for the web server"
                                    }
                                }
                            }
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
                                        "description": "Database password (auto-generated)"
                                    },
                                    "POSTGRES_USER": {
                                        "default": "windflow",
                                        "description": "Database username"
                                    },
                                    "POSTGRES_DB": {
                                        "default": "windflow_db",
                                        "description": "Database name"
                                    },
                                    "DB_PORT": {
                                        "default": "{{ get_valid_port() }}",
                                        "description": "Database port (auto-assigned)"
                                    }
                                }
                            }
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
                                        "description": "Frontend port"
                                    },
                                    "BACKEND_PORT": {
                                        "default": "3001",
                                        "description": "Backend API port"
                                    },
                                    "DB_USER": {
                                        "default": "appuser",
                                        "description": "Database username"
                                    },
                                    "DB_PASSWORD": {
                                        "default": "{{ generate_password(32) }}",
                                        "description": "Database password"
                                    },
                                    "DB_NAME": {
                                        "default": "appdb",
                                        "description": "Database name"
                                    },
                                    "JWT_SECRET": {
                                        "default": "{{ random_string(64) }}",
                                        "description": "JWT signing secret"
                                    }
                                }
                            }
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
                                        "description": "Application name"
                                    },
                                    "NAMESPACE": {
                                        "default": "production",
                                        "description": "Kubernetes namespace"
                                    },
                                    "REPLICAS": {
                                        "default": "3",
                                        "description": "Number of replicas"
                                    },
                                    "IMAGE": {
                                        "default": "myapp:latest",
                                        "description": "Container image"
                                    },
                                    "DATABASE_URL": {
                                        "default": "postgresql://user:pass@db:5432/mydb",
                                        "description": "Database connection string"
                                    }
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
                                "description": "HTTP port for the web server"
                            }
                        },
                        "created_at": "2026-01-02T22:30:00Z",
                        "updated_at": "2026-01-02T22:30:00Z"
                    }
                }
            }
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
                                "correlation_id": "abc-123"
                            }
                        },
                        "missing_field": {
                            "summary": "Missing required field",
                            "value": {
                                "error": "Validation Error",
                                "detail": "Field 'name' is required",
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
        409: {
            "description": "Stack name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Stack with name 'nginx-webserver' already exists in organization"
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
    tags=["stacks"]
)
async def create_stack(
    stack_data: StackCreate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Crée une nouvelle stack Docker Compose.

    Args:
        stack_data: Données de la stack à créer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack créée

    Raises:
        HTTPException: Si le nom existe déjà dans l'organisation
    """
    # Vérifier que le nom n'existe pas déjà dans l'organisation
    existing = await StackService.get_by_name(
        session,
        current_user.organization_id,
        stack_data.name
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Stack avec le nom '{stack_data.name}' existe déjà"
        )

    stack = await StackService.create(session, stack_data, current_user.organization_id)
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

**Authentication Required**
""",
    openapi_extra={
        "requestBody": {
            "content": {
                "application/json": {
                    "examples": {
                        "update_name": {
                            "summary": "Update stack name only",
                            "description": "Change the stack's display name",
                            "value": {
                                "name": "nginx-webserver-v2"
                            }
                        },
                        "update_description": {
                            "summary": "Update description",
                            "description": "Improve stack documentation",
                            "value": {
                                "description": "Nginx web server with SSL support and caching"
                            }
                        },
                        "add_variable": {
                            "summary": "Add new variable with macro",
                            "description": "Add a new configurable parameter",
                            "value": {
                                "variables": {
                                    "PORT": {
                                        "default": "8080",
                                        "description": "HTTP port"
                                    },
                                    "SSL_PORT": {
                                        "default": "8443",
                                        "description": "HTTPS port"
                                    },
                                    "SSL_CERT_PASSWORD": {
                                        "default": "{{ generate_password(32) }}",
                                        "description": "SSL certificate password"
                                    }
                                }
                            }
                        },
                        "update_compose": {
                            "summary": "Update Docker Compose configuration",
                            "description": "Modify services or add new ones",
                            "value": {
                                "compose_content": """version: '3.8'
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
      - NGINX_PORT=80"""
                            }
                        }
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
                            "PORT": {
                                "default": "8080",
                                "description": "HTTP port"
                            },
                            "SSL_PORT": {
                                "default": "8443",
                                "description": "HTTPS port"
                            }
                        },
                        "created_at": "2026-01-02T10:00:00Z",
                        "updated_at": "2026-01-02T22:45:00Z"
                    }
                }
            }
        },
        400: {
            "description": "Invalid request",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Validation Error",
                        "detail": "Invalid Docker Compose YAML syntax",
                        "correlation_id": "abc-123"
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
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this stack"
                    }
                }
            }
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 not found"
                    }
                }
            }
        },
        409: {
            "description": "Stack name already exists",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Conflict",
                        "detail": "Stack with name 'nginx-webserver-v2' already exists in organization"
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
    tags=["stacks"]
)
async def update_stack(
    stack_id: str,
    stack_data: StackUpdate,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Met à jour une stack Docker Compose.

    Args:
        stack_id: ID de la stack à modifier
        stack_data: Nouvelles données de la stack
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        StackResponse: Stack mise à jour

    Raises:
        HTTPException: Si la stack n'existe pas, accès refusé ou nom en conflit
    """
    # Vérifier que la stack existe
    existing_stack = await StackService.get_by_id(session, stack_id)
    if not existing_stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier les permissions
    if existing_stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    # Si changement de nom, vérifier qu'il n'existe pas déjà
    if stack_data.name and stack_data.name != existing_stack.name:
        existing_name = await StackService.get_by_name(
            session,
            current_user.organization_id,
            stack_data.name
        )
        if existing_name:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Stack avec le nom '{stack_data.name}' existe déjà"
            )

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

**Authentication Required**
""",
    responses={
        204: {
            "description": "Stack deleted successfully (no content returned)"
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
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Access denied to this stack"
                    }
                }
            }
        },
        404: {
            "description": "Stack not found",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Not Found",
                        "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 not found"
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
    tags=["stacks"]
)
async def delete_stack(
    stack_id: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Supprime une stack Docker Compose.

    Args:
        stack_id: ID de la stack à supprimer
        current_user: Utilisateur courant
        session: Session de base de données

    Raises:
        HTTPException: Si la stack n'existe pas ou accès refusé
    """
    # Vérifier que la stack existe
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvée"
        )

    # Vérifier les permissions
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à cette stack"
        )

    await StackService.delete(session, stack_id)


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

**Authentication Required**
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
                                "macro_template": "{{ generate_password(24) }}"
                            }
                        },
                        "port_regenerated": {
                            "summary": "Port regenerated",
                            "description": "New available port assigned",
                            "value": {
                                "variable_name": "DB_PORT",
                                "new_value": "5433",
                                "macro_template": "{{ get_valid_port() }}"
                            }
                        },
                        "random_string_regenerated": {
                            "summary": "Random string regenerated",
                            "description": "New random string generated",
                            "value": {
                                "variable_name": "API_KEY",
                                "new_value": "aB3xY9mK2pL7wT8v",
                                "macro_template": "{{ random_string(16) }}"
                            }
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
                        "no_default_value": {
                            "summary": "Variable has no default value",
                            "value": {
                                "error": "Bad Request",
                                "detail": "Variable 'PORT' n'a pas de valeur par défaut"
                            }
                        },
                        "no_macro": {
                            "summary": "Variable does not contain a macro",
                            "value": {
                                "error": "Bad Request",
                                "detail": "Variable 'STATIC_VALUE' ne contient pas de macro à régénérer"
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
            "description": "Access denied to this stack",
            "content": {
                "application/json": {
                    "example": {
                        "error": "Forbidden",
                        "detail": "Accès refusé à ce stack"
                    }
                }
            }
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
                                "detail": "Stack 550e8400-e29b-41d4-a716-446655440000 non trouvé"
                            }
                        },
                        "variable_not_found": {
                            "summary": "Variable not found",
                            "value": {
                                "error": "Not Found",
                                "detail": "Variable 'UNKNOWN_VAR' non trouvée dans le stack"
                            }
                        }
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
                        "detail": "Erreur lors de la régénération de la macro: Template syntax error",
                        "correlation_id": "abc-125"
                    }
                }
            }
        }
    },
    tags=["stacks"]
)
async def regenerate_variable(
    stack_id: str,
    variable_name: str,
    current_user: User = Depends(get_current_active_user),
    session: AsyncSession = Depends(get_db)
):
    """
    Régénère la valeur d'une variable contenant une macro Jinja.

    Cette route permet de régénérer une nouvelle valeur pour les variables
    qui contiennent des macros (comme generate_password, get_valid_port, etc.)
    sans avoir à recharger tout le stack.

    Args:
        stack_id: ID du stack
        variable_name: Nom de la variable à régénérer
        current_user: Utilisateur courant
        session: Session de base de données

    Returns:
        dict: Nouvelle valeur générée pour la variable

    Raises:
        HTTPException: Si le stack n'existe pas, accès refusé, variable introuvable ou pas de macro
    """
    # Vérifier que le stack existe
    stack = await StackService.get_by_id(session, stack_id)
    if not stack:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Stack {stack_id} non trouvé"
        )

    # Vérifier les permissions
    if stack.organization_id != current_user.organization_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès refusé à ce stack"
        )

    # Vérifier que la variable existe
    if not stack.variables or variable_name not in stack.variables:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Variable '{variable_name}' non trouvée dans le stack"
        )

    variable_def = stack.variables[variable_name]

    # Vérifier que la variable a une valeur par défaut
    if 'default' not in variable_def:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Variable '{variable_name}' n'a pas de valeur par défaut"
        )

    default_value = variable_def['default']

    # Vérifier que la valeur par défaut contient une macro
    import re
    macro_pattern = re.compile(r'\{\{.*?\}\}')
    if not isinstance(default_value, str) or not macro_pattern.search(default_value):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Variable '{variable_name}' ne contient pas de macro à régénérer"
        )

    # Régénérer la valeur en rendant le template
    renderer = TemplateRenderer()
    try:
        new_value = renderer.render_string(default_value, {})
        return {
            "variable_name": variable_name,
            "new_value": new_value,
            "macro_template": default_value
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la régénération de la macro: {str(e)}"
        )
