# Règles de Développement Backend - WindFlow

## Stack Technologique Backend

### Framework Principal
- **FastAPI** avec Python 3.11+ obligatoire
- **Pydantic V2** pour la validation des données
- **SQLAlchemy 2.0** avec async/await natif
- **Alembic** pour les migrations de base de données

### Architecture des Services

#### Structure Obligatoire
```
windflow/
├── api/
│   ├── v1/              # Endpoints API versionnés
│   ├── dependencies/    # Dependencies FastAPI
│   └── middleware/      # Middlewares personnalisés
├── core/
│   ├── config.py       # Configuration centralisée
│   ├── security.py     # Utilitaires sécurité
│   └── database.py     # Configuration DB
├── models/             # Modèles SQLAlchemy
├── schemas/            # Schémas Pydantic
├── services/           # Logique métier
├── tasks/              # Tâches Celery
├── tests/              # Tests automatisés
└── main.py            # Point d'entrée FastAPI
```

## Conventions de Code Python

### Type Hints Obligatoires
```python
# ✅ CORRECT - Type hints complets
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

async def create_deployment(
    deployment_data: DeploymentCreateSchema,
    user_id: UUID,
    db: AsyncSession
) -> DeploymentResponse:
    """Crée un nouveau déploiement."""
    pass

# ❌ INCORRECT - Pas de type hints
def create_deployment(deployment_data, user_id, db):
    pass
```

### Docstrings Google Style
```python
def optimize_deployment_config(
    config: Dict[str, Any],
    target_type: str,
    constraints: Optional[ResourceConstraints] = None
) -> OptimizedConfig:
    """Optimise une configuration de déploiement via LLM.
    
    Args:
        config: Configuration de déploiement initiale
        target_type: Type de cible (docker, kubernetes, vm)
        constraints: Contraintes de ressources optionnelles
        
    Returns:
        OptimizedConfig: Configuration optimisée
        
    Raises:
        LLMServiceError: Erreur du service LLM
        InvalidConfigError: Configuration invalide
        
    Example:
        >>> config = {"services": {"web": {"image": "nginx"}}}
        >>> optimized = optimize_deployment_config(config, "kubernetes")
        >>> print(optimized.resource_allocation)
    """
```

### Gestion des Erreurs

#### Exceptions Personnalisées
```python
# exceptions.py
class WindFlowException(Exception):
    """Exception de base pour WindFlow."""
    
    def __init__(self, message: str, code: str = "WINDFLOW_ERROR"):
        self.message = message
        self.code = code
        super().__init__(self.message)

class DeploymentError(WindFlowException):
    """Erreur lors du déploiement."""
    pass

class StackNotFoundError(WindFlowException):
    """Stack non trouvé."""
    
    def __init__(self, stack_id: UUID):
        super().__init__(
            f"Stack {stack_id} non trouvé",
            "STACK_NOT_FOUND"
        )
```

#### Middleware de Gestion d'Erreurs
```python
# middleware/error_handler.py
from fastapi import Request, Response
from fastapi.responses import JSONResponse
import logging

logger = logging.getLogger(__name__)

async def error_handler_middleware(request: Request, call_next):
    """Middleware de gestion globale des erreurs."""
    try:
        response = await call_next(request)
        return response
    except WindFlowException as e:
        logger.error(
            "WindFlow error",
            extra={
                "error_code": e.code,
                "message": e.message,
                "path": request.url.path,
                "method": request.method
            }
        )
        return JSONResponse(
            status_code=400,
            content={
                "error": e.code,
                "message": e.message,
                "timestamp": datetime.utcnow().isoformat()
            }
        )
    except Exception as e:
        logger.exception("Erreur non gérée")
        return JSONResponse(
            status_code=500,
            content={
                "error": "INTERNAL_ERROR",
                "message": "Erreur interne du serveur"
            }
        )
```

## Modèles de Données

### Conventions SQLAlchemy 2.0
```python
# models/base.py
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy import String, DateTime, Boolean, Text
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

class Base(DeclarativeBase):
    """Modèle de base pour tous les modèles WindFlow."""
    pass

# models/deployment.py
class Deployment(Base):
    __tablename__ = "deployments"
    
    # UUID obligatoire pour tous les IDs
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    
    # Colonnes obligatoires avec types explicites
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    
    # JSON pour configuration complexe
    configuration: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Timestamps obligatoires
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        onupdate=datetime.utcnow,
        nullable=True
    )
    
    # Relations avec lazy loading
    deployments: Mapped[List["DeploymentEvent"]] = relationship(
        "DeploymentEvent",
        back_populates="deployment",
        lazy="select"
    )
```

### Schemas Pydantic V2
```python
# schemas/deployment.py
from pydantic import BaseModel, ConfigDict, Field, validator
from uuid import UUID
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum

class DeploymentStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"

class DeploymentBase(BaseModel):
    """Schéma de base pour les déploiements."""
    model_config = ConfigDict(
        from_attributes=True,
        use_enum_values=True,
        validate_assignment=True
    )
    
    name: str = Field(..., min_length=1, max_length=100)
    target_type: str = Field(..., regex=r"^(docker|kubernetes|vm|physical)$")
    configuration: Optional[Dict[str, Any]] = None

class DeploymentCreate(DeploymentBase):
    """Schéma pour la création d'un déploiement."""
    
    @validator('name')
    def validate_name(cls, v):
        if not v.replace('-', '').replace('_', '').isalnum():
            raise ValueError('Le nom ne peut contenir que des caractères alphanumériques, - et _')
        return v

class DeploymentResponse(DeploymentBase):
    """Schéma de réponse pour un déploiement."""
    id: UUID
    status: DeploymentStatus
    created_at: datetime
    updated_at: Optional[datetime] = None
```

## Services et Logique Métier

### Pattern Repository
```python
# services/deployment_repository.py
from abc import ABC, abstractmethod
from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

class DeploymentRepository(ABC):
    """Interface repository pour les déploiements."""
    
    @abstractmethod
    async def create(self, deployment: DeploymentCreate) -> Deployment:
        pass
    
    @abstractmethod
    async def get_by_id(self, deployment_id: UUID) -> Optional[Deployment]:
        pass
    
    @abstractmethod
    async def get_by_user(self, user_id: UUID, limit: int = 20) -> List[Deployment]:
        pass

class SQLDeploymentRepository(DeploymentRepository):
    """Implémentation SQLAlchemy du repository."""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, deployment: DeploymentCreate) -> Deployment:
        db_deployment = Deployment(**deployment.model_dump())
        self.db.add(db_deployment)
        await self.db.commit()
        await self.db.refresh(db_deployment)
        return db_deployment
```

### Services avec Dependency Injection
```python
# services/deployment_service.py
from dependency_injector.wiring import Provide, inject
from container import Container

class DeploymentService:
    """Service de gestion des déploiements."""
    
    @inject
    async def create_deployment(
        self,
        deployment_data: DeploymentCreate,
        user_id: UUID,
        repository: DeploymentRepository = Provide[Container.deployment_repository]
    ) -> DeploymentResponse:
        """Crée un nouveau déploiement."""
        
        # Validation métier
        await self._validate_deployment_config(deployment_data)
        
        # Optimisation LLM si activée
        if deployment_data.enable_llm_optimization:
            deployment_data.configuration = await self._optimize_with_llm(
                deployment_data.configuration,
                deployment_data.target_type
            )
        
        # Création en base
        deployment = await repository.create(deployment_data)
        
        # Lancement asynchrone du déploiement
        await self._trigger_deployment_task(deployment.id)
        
        return DeploymentResponse.model_validate(deployment)
```

## Tâches Asynchrones

### Configuration Celery
```python
# core/celery_app.py
from celery import Celery
from core.config import settings

celery_app = Celery(
    "windflow",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        "windflow.tasks.deployment",
        "windflow.tasks.monitoring",
        "windflow.tasks.backup"
    ]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
    worker_prefetch_multiplier=1,
    task_routes={
        "windflow.tasks.deployment.*": {"queue": "deployment"},
        "windflow.tasks.monitoring.*": {"queue": "monitoring"},
        "windflow.tasks.backup.*": {"queue": "backup"}
    }
)
```

### Tâches avec Retry Policy
```python
# tasks/deployment.py
from celery import current_task
from celery.exceptions import Retry
import asyncio

@celery_app.task(
    bind=True,
    autoretry_for=(DeploymentError,),
    retry_kwargs={'max_retries': 3, 'countdown': 60},
    retry_backoff=True
)
def deploy_stack_task(self, deployment_id: str):
    """Tâche de déploiement d'un stack."""
    
    try:
        # Mise à jour du statut
        current_task.update_state(
            state='PROGRESS',
            meta={'step': 'Initialisation', 'progress': 10}
        )
        
        # Exécution du déploiement
        result = asyncio.run(deploy_stack_async(UUID(deployment_id)))
        
        return {
            'deployment_id': deployment_id,
            'status': 'success',
            'result': result
        }
        
    except DeploymentError as exc:
        # Log de l'erreur avec contexte
        logger.error(
            "Échec du déploiement",
            extra={
                'deployment_id': deployment_id,
                'error': str(exc),
                'retry_count': self.request.retries
            }
        )
        raise self.retry(countdown=60 * (2 ** self.request.retries))
```

## Configuration et Variables d'Environnement

### Configuration Centralisée
```python
# core/config.py
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Configuration centralisée de l'application."""
    
    # Database
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    
    # Redis
    REDIS_URL: str
    REDIS_MAX_CONNECTIONS: int = 100
    
    # Security
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # Vault
    VAULT_URL: str
    VAULT_TOKEN: Optional[str] = None
    
    # LLM
    LLM_PROVIDER: str = "openai"
    LLM_MODEL: str = "gpt-4-turbo-preview"
    LLM_MAX_TOKENS: int = 2000
    
    # Monitoring
    PROMETHEUS_ENABLED: bool = True
    LOG_LEVEL: str = "INFO"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()
```

## Logging Structuré

### Configuration Logging
```python
# core/logging.py
import logging
import sys
from pythonjsonlogger import jsonlogger

def setup_logging():
    """Configure le logging structuré."""
    
    # Formatter JSON
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(name)s %(levelname)s %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S'
    )
    
    # Handler pour stdout
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    
    # Configuration du logger principal
    logger = logging.getLogger("windflow")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    
    return logger

# Utilisation avec contexte
logger = logging.getLogger("windflow.deployment")

def log_deployment_event(deployment_id: UUID, event: str, **kwargs):
    """Log un événement de déploiement avec contexte."""
    logger.info(
        f"Deployment event: {event}",
        extra={
            'deployment_id': str(deployment_id),
            'event_type': event,
            'correlation_id': get_correlation_id(),
            **kwargs
        }
    )
```

## Tests Backend

### Structure des Tests
```python
# tests/conftest.py
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

@pytest.fixture
async def async_db():
    """Base de données de test."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///./test.db",
        echo=True
    )
    
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    
    async_session = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    
    async with async_session() as session:
        yield session
    
    await engine.dispose()

# tests/test_deployment_service.py
@pytest.mark.asyncio
async def test_create_deployment(async_db):
    """Test de création d'un déploiement."""
    
    # Arrange
    deployment_data = DeploymentCreate(
        name="test-deployment",
        target_type="docker",
        configuration={"replicas": 2}
    )
    
    repository = SQLDeploymentRepository(async_db)
    service = DeploymentService()
    
    # Act
    result = await service.create_deployment(
        deployment_data,
        user_id=UUID('12345678-1234-5678-9012-123456789012'),
        repository=repository
    )
    
    # Assert
    assert result.name == "test-deployment"
    assert result.status == DeploymentStatus.PENDING
    assert result.id is not None
```

## Performance et Monitoring

### Métriques Prometheus
```python
# core/metrics.py
from prometheus_client import Counter, Histogram, Gauge
import time
from functools import wraps

# Métriques métier
DEPLOYMENT_COUNTER = Counter(
    'windflow_deployments_total',
    'Nombre total de déploiements',
    ['target_type', 'status']
)

DEPLOYMENT_DURATION = Histogram(
    'windflow_deployment_duration_seconds',
    'Durée des déploiements',
    ['target_type'],
    buckets=(1, 5, 10, 30, 60, 120, 300, 600, 1200, float('inf'))
)

ACTIVE_DEPLOYMENTS = Gauge(
    'windflow_active_deployments',
    'Nombre de déploiements actifs'
)

def monitor_deployment(target_type: str):
    """Décorateur pour monitorer les déploiements."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            ACTIVE_DEPLOYMENTS.inc()
            
            try:
                result = await func(*args, **kwargs)
                DEPLOYMENT_COUNTER.labels(
                    target_type=target_type,
                    status='success'
                ).inc()
                return result
            except Exception as e:
                DEPLOYMENT_COUNTER.labels(
                    target_type=target_type,
                    status='error'
                ).inc()
                raise
            finally:
                duration = time.time() - start_time
                DEPLOYMENT_DURATION.labels(target_type=target_type).observe(duration)
                ACTIVE_DEPLOYMENTS.dec()
        
        return wrapper
    return decorator
```

Ces règles assurent un développement backend cohérent, maintenable et performant pour WindFlow.
