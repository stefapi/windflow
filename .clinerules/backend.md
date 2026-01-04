# Règles de Développement Backend - WindFlow

**Note** : Pour le stack technologique et l'architecture générale, voir `memory-bank/techContext.md` et `memory-bank/systemPatterns.md`.

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

**Note** : Pour les patterns Repository et Dependency Injection, voir `memory-bank/systemPatterns.md`.

### Bonnes Pratiques de Services
- **Responsabilité unique** : Chaque service gère une fonctionnalité métier spécifique
- **Validation métier** : Valider les données avant traitement en base
- **Gestion d'erreurs** : Lever des exceptions métier explicites
- **Logging contextuel** : Inclure l'ID de l'entité et l'utilisateur dans les logs

## Tâches Asynchrones

### DeploymentOrchestrator - Gestion des Tâches Asyncio

WindFlow utilise **asyncio** pour la gestion des tâches asynchrones, avec un orchestrateur dédié qui fournit :
- Retry automatique avec backoff exponentiel
- Recovery après crash au démarrage
- Tracking des tâches actives
- Persistance en base de données

```python
# services/deployment_orchestrator.py
from typing import Dict, Any
import asyncio
from datetime import datetime

class DeploymentOrchestrator:
    """Orchestrateur de déploiements basé sur asyncio."""
    
    _active_tasks: Dict[str, asyncio.Task] = {}
    MAX_RETRIES = 3
    INITIAL_RETRY_DELAY = 60  # secondes
    
    @classmethod
    async def start_deployment(
        cls,
        deployment_id: str,
        stack_id: str,
        target_id: str,
        user_id: str,
        configuration: Dict[str, Any]
    ) -> asyncio.Task:
        """Démarre un déploiement en arrière-plan."""
        
        # Marquer le démarrage
        async with AsyncSessionLocal() as db:
            deployment = await db.get(Deployment, deployment_id)
            deployment.task_started_at = datetime.utcnow()
            deployment.task_retry_count = 0
            await db.commit()
        
        # Créer la tâche avec retry automatique
        task = asyncio.create_task(
            cls._execute_deployment_with_retry(
                deployment_id, stack_id, target_id, 
                user_id, configuration
            )
        )
        
        # Tracker la tâche
        cls._active_tasks[deployment_id] = task
        return task
```

### Tâches avec Retry Automatique
```python
# tasks/background_tasks.py
import asyncio
from typing import Dict, Any

async def deploy_stack_async(
    deployment_id: str,
    stack_id: str,
    target_id: str,
    user_id: str,
    configuration: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Déploiement asynchrone d'une stack.
    
    Le retry est géré automatiquement par DeploymentOrchestrator.
    """
    async with AsyncSessionLocal() as db:
        # Mise à jour du statut
        await DeploymentService.update_status(
            db, deployment_id, DeploymentStatus.DEPLOYING,
            logs="[INFO] Démarrage du déploiement..."
        )
        
        # Charger la stack
        stack = await db.get(Stack, stack_id)
        if not stack:
            raise ValueError(f"Stack {stack_id} non trouvé")
        
        # Exécuter le déploiement selon le type
        if stack.target_type == TargetType.DOCKER.value:
            result = await deploy_docker_container(...)
        else:
            result = await deploy_docker_compose(...)
        
        # Marquer comme réussi
        await DeploymentService.update_status(
            db, deployment_id, DeploymentStatus.RUNNING,
            logs="[SUCCESS] Déploiement terminé avec succès"
        )
        
        return result
```

### Recovery au Démarrage
```python
# main.py - Lifespan startup
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    
    # Startup
    await db.connect()
    await db.create_tables()
    
    # Recovery des déploiements PENDING/DEPLOYING
    from services.deployment_orchestrator import DeploymentOrchestrator
    
    stats = await DeploymentOrchestrator.recover_pending_deployments(
        max_age_minutes=0,  # Réessayer tous les PENDING
        timeout_minutes=60  # Marquer FAILED ceux > 60min
    )
    
    logger.info(
        f"Recovery: {stats['retried']} relancés, "
        f"{stats['failed']} marqués FAILED"
    )
    
    yield
    
    # Shutdown
    await db.disconnect()
```

## Configuration et Variables d'Environnement

**Note** : Pour la configuration générale et les variables d'environnement, voir `memory-bank/techContext.md`.

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

**Note** : Pour les stratégies et règles de test générales, voir `memory-bank/testing.md`.

## Performance et Monitoring

**Note** : Pour les métriques et monitoring, voir `memory-bank/techContext.md`.

Ces règles assurent un développement backend cohérent, maintenable et performant pour WindFlow.
