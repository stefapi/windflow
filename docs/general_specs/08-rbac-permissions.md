# Chapitre 08 — RBAC et permissions

> **Statut** : Spec cible · **Public** : Développeurs backend, administrateurs · **Lié à** : [07-authentification.md](07-authentification.md), [06-modele-de-donnees.md](06-modele-de-donnees.md), [02-familles-workloads.md](02-familles-workloads.md)

## Vue d'ensemble

Ce chapitre spécifie le contrôle d'accès basé sur les rôles (RBAC) intégré au core : hiérarchie des entités, définition des 4 rôles, matrice des permissions, implémentation, gestion des utilisateurs et scénarios d'usage. Le RBAC est conçu pour rester simple à comprendre et à configurer, pour un self-hoster seul comme pour une petite équipe. Pour une installation mono-utilisateur (homelab), il est transparent : l'utilisateur créé à l'installation est Super Admin et a tous les droits.

## Hiérarchie des entités

```
Instance WindFlow
└── Organisation(s)
    └── Environnement(s)          (dev, staging, prod, ou noms libres)
        ├── Hosts                 (substrats d'exécution)
        ├── Apps                  (workloads container-based)
        ├── Machines              (workloads VM-based)
        └── Stacks                (groupes de services et objets Compute)

Hors hiérarchie (globaux par organisation) :
├── Plugins                     (installés dans l'instance)
└── Marketplace                 (catalogue)
```

Les permissions sont vérifiées en cascade : l'accès à un workload nécessite l'accès à son environnement, qui nécessite l'accès à son organisation. Les entités Apps/Machines/Hosts sont définies au chapitre [02-familles-workloads.md](02-familles-workloads.md) et persistées au chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md).

## Rôles

WindFlow définit **4 rôles**, du plus restreint au plus large. Chaque rôle est attribué **par organisation** — un utilisateur peut avoir des rôles différents dans différentes organisations.

### Définition des rôles

```python
class Role(str, enum.Enum):
    VIEWER = "viewer"            # Lecture seule
    OPERATOR = "operator"        # Lecture + actions opérationnelles
    ADMIN = "admin"              # Tout sauf gestion système
    SUPER_ADMIN = "super_admin"  # Accès total (toutes organisations)
```

**Viewer** — Peut voir l'état de l'infrastructure mais ne peut rien modifier. Utile pour un collègue qui veut consulter le dashboard ou les logs sans risque.

**Operator** — Peut déployer des stacks, démarrer/arrêter des Apps et Machines, consulter les logs, utiliser le terminal. Ne peut pas ajouter de Hosts, installer de plugins ni gérer les utilisateurs. C'est le rôle de quelqu'un qui utilise l'infrastructure au quotidien.

**Admin** — Peut tout faire dans son organisation : créer des environnements, ajouter des Hosts, installer des plugins, gérer les utilisateurs. Ne peut pas accéder aux autres organisations ni aux paramètres système globaux.

**Super Admin** — Accès total à toutes les organisations et aux paramètres système. C'est le rôle de l'utilisateur créé à l'installation. Il y a toujours au moins un Super Admin.

### Matrice des permissions

Cette matrice est la **référence unique** des permissions RBAC ; les autres chapitres (07, 09, 15, 16) y renvoient.

| Action | Viewer | Operator | Admin | Super Admin |
|--------|--------|----------|-------|-------------|
| **Apps** | | | | |
| Lister / Inspecter / Logs | ✅ | ✅ | ✅ | ✅ |
| Start / Stop / Restart / Console | — | ✅ | ✅ | ✅ |
| Créer / Supprimer / Configurer | — | — | ✅ | ✅ |
| **Machines** | | | | |
| Lister / Inspecter | ✅ | ✅ | ✅ | ✅ |
| Console VNC/SPICE / Power / Snapshot | — | ✅ | ✅ | ✅ |
| Créer / Supprimer / Hardware | — | — | ✅ | ✅ |
| **Stacks** | | | | |
| Lister / Voir config | ✅ | ✅ | ✅ | ✅ |
| Déployer / Rollback | — | ✅ | ✅ | ✅ |
| Créer / Éditer / Supprimer | — | — | ✅ | ✅ |
| **Volumes & networks** | | | | |
| Lister / Inspecter | ✅ | ✅ | ✅ | ✅ |
| Volume Browser (lecture) | ✅ | ✅ | ✅ | ✅ |
| Volume Browser (écriture) | — | ✅ | ✅ | ✅ |
| Créer / Supprimer / Prune | — | — | ✅ | ✅ |
| **Hosts** | | | | |
| Lister / Voir statut / Métriques | ✅ | ✅ | ✅ | ✅ |
| Ajouter / Supprimer / Scanner | — | — | ✅ | ✅ |
| **Plugins** | | | | |
| Voir les plugins installés | ✅ | ✅ | ✅ | ✅ |
| Utiliser les fonctions plugin | ✅ | ✅ | ✅ | ✅ |
| Installer / Désinstaller / Configurer | — | — | ✅ | ✅ |
| **Marketplace** | | | | |
| Parcourir le catalogue | ✅ | ✅ | ✅ | ✅ |
| Installer une entrée | — | — | ✅ | ✅ |
| **Environnements** | | | | |
| Lister | ✅ | ✅ | ✅ | ✅ |
| Créer / Modifier / Supprimer | — | — | ✅ | ✅ |
| **Organisations** | | | | |
| Voir son organisation | ✅ | ✅ | ✅ | ✅ |
| Modifier l'organisation | — | — | ✅ | ✅ |
| Créer une organisation | — | — | — | ✅ |
| **Utilisateurs** | | | | |
| Voir les membres | ✅ | ✅ | ✅ | ✅ |
| Ajouter / Retirer / Changer rôle | — | — | ✅ | ✅ |
| **Système** | | | | |
| Paramètres globaux / Registres | — | — | — | ✅ |
| Backup / Restore | — | — | — | ✅ |
| Audit (consultation) | — | — | ✅ | ✅ |

### RBAC par famille

La matrice ci-dessus s'applique à l'identique aux trois familles du modèle directeur — seuls les noms de ressources changent :

| Permission | Apps | Machines | Hosts |
|---|---|---|---|
| Lecture (tous rôles) | Lister, logs, inspecter | Lister, inspecter | Lister, statut, métriques |
| Opération (Operator+) | Start/Stop/Restart/Update/Console/Backup | Power/Snapshot/Console VNC | SSH/journalctl (lecture) |
| Gestion (Admin+) | Créer/Supprimer/Configurer | Créer/Supprimer/Hardware | Ajouter/Supprimer/Scanner |

Les ContextualActions par profil (chapitre 02) héritent de la catégorie de leur verbe : une action de lecture est accessible au Viewer, une action opérationnelle à l'Operator, une action de gestion à l'Admin.

## Implémentation

### Modèle de données

Le rôle est porté par la table d'association `user_organizations` (détail au chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)) :

```python
class UserOrganization(Base):
    """Association utilisateur ↔ organisation avec rôle."""
    __tablename__ = "user_organizations"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), primary_key=True)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"), primary_key=True)
    role: Mapped[str] = mapped_column(String(20))  # viewer, operator, admin
```

Le Super Admin est identifié par le flag `is_superadmin` sur l'entité `User`, pas par une entrée dans `user_organizations`. C'est un rôle système, pas organisationnel.

### Service d'autorisation

Exemple illustratif — logique de vérification centralisée :

```python
class AuthorizationService:
    """Service central d'autorisation RBAC."""

    async def check_permission(
        self, user: User, action: str, resource_type: str,
        organization_id: UUID = None, environment_id: UUID = None,
    ) -> bool:
        # Super Admin : tous les droits
        if user.is_superadmin:
            return True

        # Résoudre l'organisation (directement ou via l'environnement)
        org_id = organization_id or await self._resolve_org_from_env(environment_id)
        if not org_id:
            return False

        # Rôle de l'utilisateur dans l'organisation (avec cache)
        role = await self._get_user_role(user.id, org_id)
        return self._role_allows(role, action, resource_type) if role else False
```

La résolution du rôle suit trois catégories d'actions, alignées sur la matrice ci-dessus :

```python
def _role_allows(self, role: str, action: str, resource_type: str) -> bool:
    read_actions = {"list", "read", "inspect", "logs", "browse_read"}
    if action in read_actions:
        return True   # tous les rôles

    operate_actions = {"start", "stop", "restart", "deploy", "rollback",
                       "exec", "console", "browse_write", "snapshot"}
    if action in operate_actions:
        return role in ("operator", "admin")

    manage_actions = {"create", "update", "delete", "install", "uninstall",
                      "configure", "add_host", "remove_host",
                      "manage_users", "manage_environments"}
    return role == "admin" if action in manage_actions else False
```

Le rôle de l'utilisateur est mis en cache (TTL 300 s) dans le cache du core — Redis en mode standard, mémoire en mode léger.

### Dépendance FastAPI

Exemple illustratif — vérification du rôle minimum sur un endpoint :

```python
role_hierarchy = {"viewer": 0, "operator": 1, "admin": 2, "super_admin": 3}

@router.post("/compute/stacks/{stack_id}/deploy")
async def deploy_stack(stack_id: UUID, user: User = Depends(require_role("operator"))):
    """Déployer une stack — nécessite le rôle Operator minimum."""
    ...

@router.post("/plugins/install")
async def install_plugin(request: PluginInstallRequest, user: User = Depends(require_role("admin"))):
    """Installer un plugin — nécessite le rôle Admin."""
    ...
```

### Permissions sur les endpoints plugin

Les endpoints ajoutés par les plugins héritent automatiquement du RBAC du core (chapitre [11-plugins.md](11-plugins.md)). Par défaut : lecture à partir de Viewer, écriture à partir d'Operator. Un plugin peut spécifier des rôles minimum plus élevés dans son manifest :

```yaml
# Extrait du manifest plugin
extensions:
  api_module: extensions/api.py
  api_permissions:
    read: viewer        # Endpoints GET
    write: operator     # Endpoints POST/PUT/DELETE
    admin: admin        # Endpoints spécifiques (ex : configuration plugin)
```

## Gestion des utilisateurs

```bash
# Créer un utilisateur (Super Admin requis)
windflow admin user create --username alice --email alice@example.com --org homelab --role operator

# Changer un rôle
windflow admin user role --username alice --org homelab --role admin

# Retirer d'une organisation
windflow admin user remove --username alice --org homelab

# Lister les membres d'une organisation
windflow admin user list --org homelab
# USERNAME    EMAIL                 ROLE       JOINED
# admin       admin@example.com     admin      2026-03-15
# alice       alice@example.com     operator   2026-04-01
```

Les mêmes opérations sont disponibles via l'API (`/organizations/{id}/users`, chapitre [09-api.md](09-api.md)) et depuis l'UI (Settings → Utilisateurs).

## Scénarios d'usage

### Homelab solo

Un seul utilisateur, Super Admin. Le RBAC est transparent — accès total, rien à configurer.

### Petite équipe (2-5 personnes)

- **Admin principal** : Super Admin, gère l'infrastructure et les plugins ;
- **Développeurs** : rôle Operator, déploient des stacks et accèdent aux logs/terminal ;
- **Observateur** (client, manager) : rôle Viewer, consulte le dashboard et les logs.

### Multi-projets

Plusieurs organisations pour séparer les projets :

- Organisation « Projet A » : Alice (Admin), Bob (Operator) ;
- Organisation « Projet B » : Alice (Admin), Charlie (Operator), Dave (Viewer).

Alice gère les deux projets. Bob ne voit que le Projet A. Charlie ne voit que le Projet B.

### SSO externe (plugin Keycloak)

Quand le plugin Keycloak est installé, les utilisateurs se connectent via LDAP/AD ou OIDC ; les rôles WindFlow sont mappés depuis les groupes du provider SSO (chapitre [07-authentification.md](07-authentification.md)).

## Sécurité du RBAC

### Invalidation du cache

Quand un rôle est modifié, le cache de permissions est invalidé immédiatement pour l'utilisateur concerné. En mode léger (cache mémoire), l'invalidation est instantanée ; en mode standard (Redis), un message est publié pour invalider le cache sur tous les workers.

### Audit des permissions

Toutes les modifications de permissions (ajout/suppression d'utilisateur, changement de rôle) sont loggées dans le journal d'audit avec qui, quand, quoi, depuis quelle IP (chapitre [15-securite.md](15-securite.md)). Consultation : UI (Settings → Audit) et CLI (`windflow admin audit`, chapitre [10-cli-tui.md](10-cli-tui.md)).

### Protection contre l'escalade

- Un Admin ne peut pas se promouvoir Super Admin ;
- un Operator ne peut pas se promouvoir Admin ;
- le dernier Super Admin ne peut pas être supprimé ;
- le changement de rôle nécessite au minimum le rôle Admin dans l'organisation concernée (ou Super Admin).

## Voir aussi

- [07-authentification.md](07-authentification.md) — authentification JWT et clés API, en amont du RBAC
- [06-modele-de-donnees.md](06-modele-de-donnees.md) — tables `users`, `organizations`, `user_organizations`, `environments`
- [02-familles-workloads.md](02-familles-workloads.md) — familles et ContextualActions auxquelles s'appliquent les rôles
- [09-api.md](09-api.md) — application du RBAC aux endpoints
- [11-plugins.md](11-plugins.md) — permissions des routes injectées par les plugins
