# Design de l'API - WindFlow

## Vue d'Ensemble

L'API WindFlow suit les principes REST avec une architecture moderne basée sur FastAPI, offrant une documentation automatique et une intégration seamless entre tous les composants.

### Principes de Design

**Standards API :**
- **RESTful** : Conventions REST strictes avec codes de statut appropriés
- **OpenAPI 3.0** : Documentation automatique avec Swagger/ReDoc
- **Versioning** : Support multi-versions avec backward compatibility
- **Pagination** : Pagination standardisée avec métadonnées
- **Filtering** : Filtrage et tri avancés sur toutes les collections

## Architecture API

### Structure des Endpoints

```
/api/v1/
├── auth/                      # Authentification
├── organizations/             # Gestion des organisations
├── environments/              # Environnements de déploiement
├── stacks/                    # Stacks et templates
├── deployments/               # Déploiements
├── workflows/                 # Workflows et automatisation
├── monitoring/                # Métriques et monitoring
├── llm/                       # Services IA/LLM
└── admin/                     # Administration système
```

### Format de Réponse Standardisé

```python
class APIResponse(BaseModel):
    """Format de réponse API standardisé."""
    status: Literal["success", "error", "warning"]
    message: Optional[str] = None
    data: Optional[Dict] = None
    errors: Optional[List[str]] = None
    metadata: Optional[Dict] = None
    
class PaginatedResponse(APIResponse):
    """Réponse paginée standardisée."""
    data: List[Dict]
    pagination: PaginationMeta
    
class PaginationMeta(BaseModel):
    page: int
    per_page: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool
```

## Endpoints Principaux

### Authentification (`/api/v1/auth/`)

```python
@router.post("/login", response_model=AuthResponse)
async def login(credentials: LoginRequest):
    """Authentification par nom d'utilisateur/mot de passe."""
    
@router.post("/login-key", response_model=AuthResponse)
async def login_with_api_key(api_key: str = Header(...)):
    """Authentification par API key."""
    
@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_token: str = Header(...)):
    """Renouvellement du token d'accès."""
    
@router.post("/logout")
async def logout():
    """Déconnexion et invalidation des tokens."""
```

### Organisations (`/api/v1/organizations/`)

```python
@router.get("/", response_model=PaginatedResponse)
async def list_organizations(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, le=100),
    search: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    """Liste les organisations avec filtrage et pagination."""

@router.post("/", response_model=APIResponse)
async def create_organization(org: OrganizationCreate):
    """Crée une nouvelle organisation."""

@router.get("/{org_id}", response_model=APIResponse)
async def get_organization(org_id: UUID):
    """Récupère une organisation par ID."""

@router.put("/{org_id}", response_model=APIResponse)
async def update_organization(org_id: UUID, org: OrganizationUpdate):
    """Met à jour une organisation."""

@router.delete("/{org_id}")
async def delete_organization(org_id: UUID):
    """Supprime une organisation."""
```

### Stacks (`/api/v1/stacks/`)

```python
@router.post("/generate", response_model=APIResponse)
async def generate_stack_from_description(request: StackGenerationRequest):
    """Génère un stack via IA depuis une description."""
    
@router.post("/{stack_id}/optimize", response_model=APIResponse)
async def optimize_stack(stack_id: UUID, goals: OptimizationGoals):
    """Optimise un stack existant via IA."""
    
@router.post("/{stack_id}/validate", response_model=ValidationResponse)
async def validate_stack(stack_id: UUID):
    """Valide la configuration d'un stack."""
```

### Déploiements (`/api/v1/deployments/`)

```python
@router.post("/", response_model=APIResponse)
async def create_deployment(deployment: DeploymentCreate):
    """Crée un nouveau déploiement."""
    
@router.get("/{deployment_id}/status", response_model=APIResponse)
async def get_deployment_status(deployment_id: UUID):
    """Récupère le statut d'un déploiement."""
    
@router.get("/{deployment_id}/logs")
async def stream_deployment_logs(deployment_id: UUID):
    """Stream des logs de déploiement en temps réel."""
    
@router.post("/{deployment_id}/rollback", response_model=APIResponse)
async def rollback_deployment(deployment_id: UUID):
    """Effectue un rollback de déploiement."""
```

### LLM Services (`/api/v1/llm/`)

```python
@router.post("/analyze", response_model=AnalysisResponse)
async def analyze_configuration(request: AnalysisRequest):
    """Analyse une configuration via LLM."""
    
@router.post("/troubleshoot", response_model=TroubleshootResponse)
async def troubleshoot_issue(request: TroubleshootRequest):
    """Diagnostic automatique d'un problème."""
    
@router.post("/optimize", response_model=OptimizationResponse)
async def optimize_resources(request: OptimizationRequest):
    """Optimisation intelligente des ressources."""
```

## Modèles de Données API

### Modèles d'Authentification

```python
class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=8)
    remember_me: bool = False

class AuthResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user_info: UserInfo

class UserInfo(BaseModel):
    user_id: UUID
    username: str
    email: str
    is_superadmin: bool
    organizations: List[OrganizationMembership]
```

### Modèles d'Organisation

```python
class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    description: Optional[str] = Field(None, max_length=500)
    settings: Optional[Dict] = Field(default_factory=dict)
    quotas: Optional[Dict] = Field(default_factory=dict)

class OrganizationResponse(BaseModel):
    id: UUID
    name: str
    description: Optional[str]
    is_active: bool
    environment_count: int
    user_count: int
    created_at: datetime
    updated_at: datetime
```

### Modèles de Stack

```python
class StackGenerationRequest(BaseModel):
    description: str = Field(..., min_length=10, max_length=1000)
    target_platform: TargetPlatform = TargetPlatform.DOCKER
    environment_type: EnvironmentType = EnvironmentType.DEVELOPMENT
    resource_constraints: Optional[ResourceConstraints] = None
    security_level: SecurityLevel = SecurityLevel.STANDARD

class StackResponse(BaseModel):
    id: UUID
    name: str
    description: str
    configuration: Dict
    llm_optimized: bool
    status: StackStatus
    created_at: datetime
    last_deployed_at: Optional[datetime]
```

## Gestion des Erreurs

### Codes d'Erreur Standardisés

```python
class APIError(HTTPException):
    """Classe de base pour les erreurs API."""
    
    def __init__(self, status_code: int, code: str, message: str, details: Dict = None):
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(status_code=status_code, detail=self.to_dict())
    
    def to_dict(self):
        return {
            "status": "error",
            "error": {
                "code": self.code,
                "message": self.message,
                "details": self.details
            }
        }

# Erreurs communes
class ValidationError(APIError):
    def __init__(self, message: str, details: Dict = None):
        super().__init__(400, "VALIDATION_ERROR", message, details)

class NotFoundError(APIError):
    def __init__(self, resource: str, identifier: str):
        super().__init__(404, "NOT_FOUND", f"{resource} not found: {identifier}")

class PermissionDeniedError(APIError):
    def __init__(self, action: str, resource: str):
        super().__init__(403, "PERMISSION_DENIED", f"Permission denied for {action} on {resource}")
```

### Handler Global d'Erreurs

```python
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    return JSONResponse(
        status_code=exc.status_code,
        content=exc.to_dict()
    )

@app.exception_handler(ValidationError)
async def validation_error_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "status": "error",
            "message": "Validation failed",
            "errors": exc.errors()
        }
    )
```

## Sécurité API

### Authentification JWT

```python
class JWTBearer(HTTPBearer):
    def __init__(self, auto_error: bool = True):
        super().__init__(auto_error=auto_error)

    async def __call__(self, request: Request):
        credentials: HTTPAuthorizationCredentials = await super().__call__(request)
        if credentials:
            if not credentials.scheme == "Bearer":
                raise HTTPException(status_code=403, detail="Invalid authentication scheme.")
            if not self.verify_jwt(credentials.credentials):
                raise HTTPException(status_code=403, detail="Invalid token or expired token.")
            return credentials.credentials
        else:
            raise HTTPException(status_code=403, detail="Invalid authorization code.")

    def verify_jwt(self, token: str) -> bool:
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return True
        except JWTError:
            return False
```

### Rate Limiting

```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@router.post("/deployments/")
@limiter.limit("10/minute")  # Limite à 10 déploiements par minute
async def create_deployment(request: Request, deployment: DeploymentCreate):
    """Crée un déploiement avec rate limiting."""
    pass
```

## WebSocket API

### Streaming Temps Réel

```python
@router.websocket("/deployments/{deployment_id}/logs")
async def deployment_logs_websocket(websocket: WebSocket, deployment_id: UUID):
    """WebSocket pour logs de déploiement en temps réel."""
    await websocket.accept()
    
    try:
        # Vérification des permissions
        user = await authenticate_websocket(websocket)
        if not await can_access_deployment(user, deployment_id):
            await websocket.close(code=4003, reason="Permission denied")
            return
        
        # Stream des logs
        async for log_entry in get_deployment_logs_stream(deployment_id):
            await websocket.send_json({
                "type": "log",
                "data": log_entry.dict()
            })
            
    except WebSocketDisconnect:
        pass
    finally:
        await cleanup_log_stream(deployment_id)
```

## Documentation API

### Configuration OpenAPI

```python
app = FastAPI(
    title="WindFlow API",
    description="API intelligente pour le déploiement de containers",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Gestion de l'authentification et des tokens"
        },
        {
            "name": "Organizations", 
            "description": "Gestion des organisations multi-tenant"
        },
        {
            "name": "Stacks",
            "description": "Templates et configurations de stacks"
        },
        {
            "name": "Deployments",
            "description": "Déploiements et orchestration"
        },
        {
            "name": "LLM",
            "description": "Services d'intelligence artificielle"
        }
    ]
)
```

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Contexte du projet  
- [Architecture](02-architecture.md) - Architecture générale
- [Authentification](05-authentication.md) - Système d'authentification
- [Sécurité](13-security.md) - Sécurité des APIs
- [CLI Interface](08-cli-interface.md) - Interface CLI utilisant l'API
