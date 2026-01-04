# RBAC et Permissions - WindFlow

## Vue d'Ensemble

WindFlow implémente un système RBAC (Role-Based Access Control) granulaire permettant un contrôle fin des accès selon les organisations, environnements et ressources.

### Modèle de Permissions

**Hiérarchie des Entités :**
```
Organization
├── Environments
│   ├── Elements
│   │   ├── Stacks
│   │   │   └── Applications
│   │   └── Infrastructure (VMs, Networks, Volumes)
│   └── Workflows
└── Users & Groups
```

## Rôles et Permissions

### Rôles Système

```python
class SystemRole(str, enum.Enum):
    SUPERADMIN = "superadmin"        # Accès total système
    ORG_OWNER = "org_owner"          # Propriétaire organisation
    ORG_ADMIN = "org_admin"          # Administrateur organisation
    DEVELOPER = "developer"          # Développeur avec déploiement
    OPERATOR = "operator"            # Opérateur infrastructure
    VIEWER = "viewer"                # Lecture seule

class Permission(str, enum.Enum):
    # Organisations
    ORG_CREATE = "org:create"
    ORG_READ = "org:read"
    ORG_UPDATE = "org:update"
    ORG_DELETE = "org:delete"
    ORG_MANAGE_USERS = "org:manage_users"
    
    # Environnements
    ENV_CREATE = "env:create"
    ENV_READ = "env:read"
    ENV_UPDATE = "env:update"
    ENV_DELETE = "env:delete"
    
    # Stacks et Déploiements
    STACK_CREATE = "stack:create"
    STACK_READ = "stack:read"
    STACK_UPDATE = "stack:update"
    STACK_DELETE = "stack:delete"
    STACK_DEPLOY = "stack:deploy"
    
    # Infrastructure
    INFRA_CREATE = "infra:create"
    INFRA_READ = "infra:read"
    INFRA_UPDATE = "infra:update"
    INFRA_DELETE = "infra:delete"
    
    # Monitoring
    METRICS_READ = "metrics:read"
    LOGS_READ = "logs:read"
    
    # Administration
    ADMIN_USERS = "admin:users"
    ADMIN_SYSTEM = "admin:system"
```

### Matrice des Permissions

| Rôle | Organisations | Environnements | Stacks | Déploiements | Infrastructure | Monitoring |
|------|---------------|----------------|--------|--------------|----------------|------------|
| SuperAdmin | ✅ Tous | ✅ Tous | ✅ Tous | ✅ Tous | ✅ Tous | ✅ Tous |
| Org Owner | ✅ Propriétaire | ✅ Org | ✅ Org | ✅ Org | ✅ Org | ✅ Org |
| Org Admin | 👁️ Org | ✅ Org | ✅ Org | ✅ Org | ✅ Org | ✅ Org |
| Developer | 👁️ Org | 👁️ Assignés | ✅ Assignés | ✅ Assignés | 👁️ Assignés | 👁️ Assignés |
| Operator | 👁️ Org | 👁️ Assignés | 👁️ Assignés | 👁️ Assignés | ✅ Assignés | ✅ Assignés |
| Viewer | 👁️ Org | 👁️ Assignés | 👁️ Assignés | 👁️ Assignés | 👁️ Assignés | 👁️ Assignés |

## Implémentation

### Service d'Autorisation

```python
class AuthorizationService:
    """Service central d'autorisation RBAC."""
    
    def __init__(self, db: Database, cache: Redis):
        self.db = db
        self.cache = cache
        
    async def check_permission(self, user: User, permission: Permission, 
                               resource_id: str = None, resource_type: str = None) -> bool:
        """Vérifie si un utilisateur a une permission sur une ressource."""
        
        # Cache des permissions utilisateur
        cache_key = f"permissions:{user.id}:{resource_type}:{resource_id}"
        cached_result = await self.cache.get(cache_key)
        
        if cached_result is not None:
            return json.loads(cached_result)
        
        # Super-administrateur a tous les droits
        if user.is_superadmin:
            await self.cache.setex(cache_key, 300, "true")
            return True
        
        # Vérification des permissions par contexte
        has_permission = False
        
        if resource_type == "organization":
            has_permission = await self._check_org_permission(user, permission, resource_id)
        elif resource_type == "environment":
            has_permission = await self._check_env_permission(user, permission, resource_id)
        elif resource_type == "stack":
            has_permission = await self._check_stack_permission(user, permission, resource_id)
        else:
            has_permission = await self._check_global_permission(user, permission)
        
        # Mise en cache du résultat
        await self.cache.setex(cache_key, 300, json.dumps(has_permission))
        
        return has_permission
    
    async def _check_org_permission(self, user: User, permission: Permission, org_id: str) -> bool:
        """Vérification des permissions au niveau organisation."""
        
        user_org = await self.db.get_user_organization(user.id, org_id)
        if not user_org:
            return False
        
        role_permissions = {
            "owner": [Permission.ORG_CREATE, Permission.ORG_READ, Permission.ORG_UPDATE, Permission.ORG_DELETE, Permission.ORG_MANAGE_USERS],
            "admin": [Permission.ORG_READ, Permission.ORG_UPDATE, Permission.ORG_MANAGE_USERS],
            "member": [Permission.ORG_READ],
            "viewer": [Permission.ORG_READ]
        }
        
        return permission in role_permissions.get(user_org.role, [])
```

### Décorateur de Permission

```python
def require_permission(permission: Permission, resource_type: str = None):
    """Décorateur pour vérifier les permissions sur les endpoints API."""
    
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            # Extraction du user depuis le context
            user = get_current_user()
            
            # Extraction de l'ID de ressource depuis les paramètres
            resource_id = kwargs.get(f"{resource_type}_id") if resource_type else None
            
            # Vérification de la permission
            auth_service = get_auth_service()
            if not await auth_service.check_permission(user, permission, resource_id, resource_type):
                raise PermissionDeniedError(permission.value, resource_type or "system")
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

# Utilisation
@router.post("/organizations/{org_id}/environments/")
@require_permission(Permission.ENV_CREATE, "organization")
async def create_environment(org_id: UUID, env_data: EnvironmentCreate):
    """Créer un environnement (nécessite permission ENV_CREATE)."""
    pass
```

### Middleware d'Autorisation

```python
class AuthorizationMiddleware:
    """Middleware d'autorisation pour les requêtes API."""
    
    def __init__(self, app: FastAPI):
        self.app = app
        
    async def __call__(self, request: Request, call_next):
        # Vérification de l'authentification
        if not hasattr(request.state, "user"):
            return await call_next(request)
        
        user = request.state.user
        path = request.url.path
        method = request.method
        
        # Vérification des permissions basées sur la route
        permission_required = self._get_required_permission(path, method)
        
        if permission_required:
            auth_service = get_auth_service()
            resource_type, resource_id = self._extract_resource_info(path)
            
            if not await auth_service.check_permission(user, permission_required, resource_id, resource_type):
                return JSONResponse(
                    status_code=403,
                    content={"error": "Permission denied"}
                )
        
        return await call_next(request)
```

## Tags et Groupes

### Système de Tags

```python
class TagBasedPermissions:
    """Permissions basées sur les tags pour un contrôle granulaire."""
    
    async def check_tag_access(self, user: User, resource_tags: List[str]) -> bool:
        """Vérifie l'accès basé sur les tags."""
        
        user_tags = await self.get_user_tags(user)
        
        # Règles d'accès par tags
        for user_tag in user_tags:
            if user_tag.name in resource_tags:
                return user_tag.access_level >= TagAccessLevel.READ
        
        return False
    
    async def filter_resources_by_tags(self, user: User, resources: List[Resource]) -> List[Resource]:
        """Filtre les ressources selon les tags accessibles."""
        
        accessible_resources = []
        
        for resource in resources:
            if await self.check_tag_access(user, resource.tags):
                accessible_resources.append(resource)
        
        return accessible_resources
```

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Contexte du projet
- [Architecture](02-architecture.md) - Architecture du système
- [Authentification](05-authentication.md) - Système d'authentification
- [Sécurité](13-security.md) - Sécurité globale
- [API Design](07-api-design.md) - APIs avec permissions
