# RBAC et Permissions - WindFlow

## Vue d'Ensemble

WindFlow implémente un système RBAC (Role-Based Access Control) intégré au core qui permet de contrôler les accès par organisation, environnement et type de ressource. Le système est conçu pour être simple à comprendre et à configurer, tout en couvrant les besoins d'un self-hoster seul comme d'une petite équipe.

Pour une installation mono-utilisateur (homelab), le RBAC est transparent — l'utilisateur créé à l'installation est Super Admin et a tous les droits. Le RBAC devient utile quand plusieurs personnes partagent la même instance WindFlow.

### Hiérarchie des Entités

```
Instance WindFlow
└── Organization(s)
    └── Environment(s)          (dev, staging, prod, ou noms libres)
        ├── Targets             (machines locales et distantes)
        ├── Stacks              (groupes de services Docker)
        ├── Containers          (containers individuels)
        └── VMs                 (machines virtuelles)

Hors hiérarchie (globaux par organisation) :
├── Plugins                     (installés dans l'instance)
└── Marketplace                 (catalogue)
```

Les permissions sont vérifiées en cascade : accès à un container nécessite l'accès à son environnement, qui nécessite l'accès à son organisation.

---

## Rôles

WindFlow définit 4 rôles, du plus restreint au plus large. Chaque rôle est attribué par organisation — un utilisateur peut avoir des rôles différents dans différentes organisations.

### Définition des Rôles

```python
class Role(str, enum.Enum):
    VIEWER = "viewer"          # Lecture seule sur tout
    OPERATOR = "operator"      # Lecture + actions opérationnelles (start, stop, deploy, logs)
    ADMIN = "admin"            # Tout sauf gestion système
    SUPER_ADMIN = "super_admin"  # Accès total (toutes les organisations)
```

**Viewer** — Peut voir l'état de l'infrastructure mais ne peut rien modifier. Utile pour un collègue qui veut consulter le dashboard ou les logs sans risque.

**Operator** — Peut déployer des stacks, démarrer/arrêter des containers et VMs, consulter les logs, utiliser le terminal. Ne peut pas créer de targets, installer de plugins, ou gérer les utilisateurs. C'est le rôle de quelqu'un qui utilise l'infrastructure au quotidien.

**Admin** — Peut tout faire dans son organisation : créer des environnements, ajouter des targets, installer des plugins, gérer les utilisateurs. Ne peut pas accéder aux autres organisations ni aux paramètres système globaux.

**Super Admin** — Accès total à toutes les organisations et aux paramètres système. C'est le rôle de l'utilisateur créé à l'installation. Il y a toujours au moins un Super Admin.

### Matrice des Permissions

| Action | Viewer | Operator | Admin | Super Admin |
|--------|--------|----------|-------|-------------|
| **Containers** | | | | |
| Lister / Inspecter | ✅ | ✅ | ✅ | ✅ |
| Logs | ✅ | ✅ | ✅ | ✅ |
| Start / Stop / Restart | — | ✅ | ✅ | ✅ |
| Terminal (exec) | — | ✅ | ✅ | ✅ |
| Créer / Supprimer | — | — | ✅ | ✅ |
| **VMs** | | | | |
| Lister / Inspecter | ✅ | ✅ | ✅ | ✅ |
| Console VNC/SPICE | — | ✅ | ✅ | ✅ |
| Start / Stop / Snapshot | — | ✅ | ✅ | ✅ |
| Créer / Supprimer | — | — | ✅ | ✅ |
| **Stacks** | | | | |
| Lister / Voir config | ✅ | ✅ | ✅ | ✅ |
| Déployer / Rollback | — | ✅ | ✅ | ✅ |
| Créer / Éditer / Supprimer | — | — | ✅ | ✅ |
| **Volumes & Networks** | | | | |
| Lister / Inspecter | ✅ | ✅ | ✅ | ✅ |
| Volume Browser (lecture) | ✅ | ✅ | ✅ | ✅ |
| Volume Browser (écriture) | — | ✅ | ✅ | ✅ |
| Créer / Supprimer | — | — | ✅ | ✅ |
| **Targets** | | | | |
| Lister / Voir status | ✅ | ✅ | ✅ | ✅ |
| Ajouter / Supprimer | — | — | ✅ | ✅ |
| **Plugins** | | | | |
| Voir les plugins installés | ✅ | ✅ | ✅ | ✅ |
| Utiliser les fonctions plugin | ✅ | ✅ | ✅ | ✅ |
| Installer / Désinstaller | — | — | ✅ | ✅ |
| Configurer | — | — | ✅ | ✅ |
| **Marketplace** | | | | |
| Parcourir le catalogue | ✅ | ✅ | ✅ | ✅ |
| Installer une stack/plugin | — | — | ✅ | ✅ |
| **Environnements** | | | | |
| Lister | ✅ | ✅ | ✅ | ✅ |
| Créer / Modifier / Supprimer | — | — | ✅ | ✅ |
| **Organisations** | | | | |
| Voir son organisation | ✅ | ✅ | ✅ | ✅ |
| Modifier l'organisation | — | — | ✅ | ✅ |
| Créer une organisation | — | — | — | ✅ |
| **Utilisateurs** | | | | |
| Voir les membres | ✅ | ✅ | ✅ | ✅ |
| Ajouter / Supprimer / Changer rôle | — | — | ✅ | ✅ |
| **Système** | | | | |
| Paramètres globaux | — | — | — | ✅ |
| Gérer les registres de plugins | — | — | — | ✅ |
| Backup / Restore | — | — | — | ✅ |

---

## Implémentation

### Modèle de Données

```python
class UserOrganization(Base):
    """Association utilisateur ↔ organisation avec rôle."""
    __tablename__ = "user_organizations"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))  # viewer, operator, admin
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
```

Le Super Admin est identifié par le flag `is_superadmin` sur l'entité User, pas par une entrée dans `user_organizations`. C'est un rôle système, pas organisationnel.

### Service d'Autorisation

```python
class AuthorizationService:
    """Service central d'autorisation RBAC."""

    def __init__(self, db, cache):
        self.db = db
        self.cache = cache  # Redis ou MemoryCache selon le mode

    async def check_permission(
        self, user: User, action: str, resource_type: str,
        organization_id: UUID = None, environment_id: UUID = None
    ) -> bool:
        """Vérifie si un utilisateur a le droit d'effectuer une action."""

        # Super Admin a tous les droits
        if user.is_superadmin:
            return True

        # Déterminer l'organisation concernée
        org_id = organization_id or await self._resolve_org_from_env(environment_id)
        if not org_id:
            return False

        # Récupérer le rôle de l'utilisateur dans l'organisation
        role = await self._get_user_role(user.id, org_id)
        if not role:
            return False

        # Vérifier la permission selon le rôle
        return self._role_allows(role, action, resource_type)

    def _role_allows(self, role: str, action: str, resource_type: str) -> bool:
        """Vérifie si un rôle permet une action sur un type de ressource."""

        # Actions de lecture — tous les rôles
        read_actions = {"list", "read", "inspect", "logs", "browse_read"}
        if action in read_actions:
            return True

        # Actions opérationnelles — operator et au-dessus
        operate_actions = {"start", "stop", "restart", "deploy", "rollback",
                          "exec", "console", "browse_write", "snapshot"}
        if action in operate_actions:
            return role in ("operator", "admin")

        # Actions de gestion — admin uniquement
        manage_actions = {"create", "update", "delete", "install", "uninstall",
                         "configure", "add_target", "remove_target",
                         "manage_users", "manage_environments"}
        if action in manage_actions:
            return role == "admin"

        return False

    async def _get_user_role(self, user_id: UUID, org_id: UUID) -> str | None:
        """Récupère le rôle d'un utilisateur dans une organisation (avec cache)."""
        cache_key = f"role:{user_id}:{org_id}"
        cached = await self.cache.get(cache_key)
        if cached:
            return cached

        user_org = await self.db.get_user_organization(user_id, org_id)
        if not user_org:
            return None

        await self.cache.set(cache_key, user_org.role, ttl=300)
        return user_org.role
```

### Dépendance FastAPI

```python
from fastapi import Depends, HTTPException

async def require_role(min_role: str):
    """Dépendance FastAPI pour vérifier le rôle minimum."""

    role_hierarchy = {"viewer": 0, "operator": 1, "admin": 2, "super_admin": 3}

    async def checker(
        user: User = Depends(get_current_user),
        org_id: UUID = None,
    ):
        if user.is_superadmin:
            return user

        if org_id:
            auth_service = get_auth_service()
            user_role = await auth_service._get_user_role(user.id, org_id)
            if not user_role or role_hierarchy.get(user_role, 0) < role_hierarchy[min_role]:
                raise HTTPException(status_code=403, detail="Permission denied")

        return user

    return checker

# Utilisation sur les endpoints
@router.post("/stacks/{stack_id}/deploy")
async def deploy_stack(
    stack_id: UUID,
    user: User = Depends(require_role("operator")),
):
    """Déployer une stack — nécessite le rôle Operator minimum."""
    ...

@router.post("/plugins/install")
async def install_plugin(
    request: PluginInstallRequest,
    user: User = Depends(require_role("admin")),
):
    """Installer un plugin — nécessite le rôle Admin."""
    ...
```

### Permissions sur les Endpoints Plugin

Les endpoints ajoutés par les plugins héritent automatiquement du RBAC du core. Par défaut, les endpoints plugin sont accessibles à partir du rôle Viewer (lecture) et Operator (écriture). Un plugin peut spécifier un rôle minimum différent dans son manifest :

```yaml
# Extrait du manifest plugin
extensions:
  api_module: extensions/api.py
  api_permissions:
    read: viewer        # Endpoints GET
    write: operator     # Endpoints POST/PUT/DELETE
    admin: admin        # Endpoints spécifiques (ex: configuration plugin)
```

---

## Gestion des Utilisateurs

### Créer un Utilisateur

```bash
# Via CLI (Super Admin requis)
windflow admin user create --username alice --email alice@example.com --org my-org --role operator

# Via API
POST /api/v1/organizations/{org_id}/users
{
  "username": "alice",
  "email": "alice@example.com",
  "role": "operator"
}
```

### Changer un Rôle

```bash
windflow admin user role --username alice --org my-org --role admin
```

### Supprimer un Utilisateur d'une Organisation

```bash
windflow admin user remove --username alice --org my-org
```

### Listing

```bash
# Lister les utilisateurs d'une organisation
windflow admin user list --org my-org

# Résultat :
# USERNAME    EMAIL                 ROLE       JOINED
# admin       admin@example.com     admin      2026-03-15
# alice       alice@example.com     operator   2026-04-01
# bob         bob@example.com       viewer     2026-04-10
```

---

## Scénarios d'Usage

### Homelab Solo

Un seul utilisateur, Super Admin. Le RBAC est transparent — il a accès à tout. Pas besoin de configurer quoi que ce soit.

### Petite Équipe (2-5 personnes)

- **Admin principal** : Super Admin, gère l'infrastructure et les plugins
- **Développeurs** : rôle Operator, peuvent déployer des stacks et accéder aux logs/terminal
- **Observateur** (client, manager) : rôle Viewer, peut voir le dashboard et les logs

### Multi-Projets

Plusieurs organisations pour séparer les projets :

- Organisation "Projet A" : Alice (Admin), Bob (Operator)
- Organisation "Projet B" : Alice (Admin), Charlie (Operator), Dave (Viewer)

Alice gère les deux projets. Bob ne voit que le Projet A. Charlie ne voit que le Projet B.

### SSO Externe (via Plugin Keycloak)

Quand le plugin Keycloak est installé, les utilisateurs peuvent se connecter via LDAP/AD ou OIDC. Les rôles WindFlow sont mappés depuis les groupes/rôles du provider SSO. La configuration du mapping se fait dans le plugin Keycloak.

---

## Sécurité

### Invalidation du Cache

Quand un rôle est modifié, le cache de permissions est invalidé immédiatement pour l'utilisateur concerné. En mode léger (cache mémoire), l'invalidation est instantanée. En mode standard (Redis), un message est publié pour invalider le cache sur tous les workers.

### Audit

Toutes les modifications de permissions (ajout/suppression d'utilisateur, changement de rôle) sont loggées dans le journal d'audit avec : qui, quand, quoi, depuis quelle IP. Le journal est consultable depuis l'UI (page Settings > Audit) et via la CLI (`windflow admin audit`).

### Protection contre l'Escalade

- Un Admin ne peut pas se promouvoir Super Admin
- Un Operator ne peut pas se promouvoir Admin
- Le dernier Super Admin ne peut pas être supprimé
- Le changement de rôle nécessite au minimum le rôle Admin dans l'organisation concernée (ou Super Admin)

---

**Références :**
- [Vue d'Ensemble](01-overview.md) - Vision du projet
- [Architecture](02-architecture.md) - Architecture du système
- [Authentification](05-authentication.md) - Système d'authentification
- [Sécurité](13-security.md) - Sécurité globale
- [API Design](07-api-design.md) - APIs avec permissions
- [Architecture Modulaire](../ARCHITECTURE-MODULAIRE.md) - Permissions des plugins
