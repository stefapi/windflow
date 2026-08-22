# Chapitre 07 — Authentification

> **Statut** : Spec cible · **Public** : Développeurs backend, administrateurs · **Lié à** : [08-rbac-permissions.md](08-rbac-permissions.md), [09-api.md](09-api.md), [15-securite.md](15-securite.md)

## Vue d'ensemble

Ce chapitre spécifie le système d'authentification **JWT** autonome du core : authentification par mot de passe, refresh tokens, clés API, protection brute-force et validation des tokens sur l'API. Les besoins avancés (SSO, LDAP/AD, OIDC, 2FA) sont apportés par le plugin Keycloak. L'authentification en ligne de commande (`windflow auth …`) est spécifiée au chapitre [10-cli-tui.md](10-cli-tui.md) — ce chapitre n'en donne que le mécanisme sous-jacent. Les mesures de sécurité transverses (chiffrement des secrets, réseau, audit) sont au chapitre [15-securite.md](15-securite.md).

## Ce qui est core vs plugin

| Core (toujours disponible) | Plugin (optionnel) |
|---|---|
| Auth par mot de passe (JWT) | SSO Keycloak (LDAP, AD, OIDC, SAML) |
| Refresh tokens | 2FA (TOTP, WebAuthn) via Keycloak |
| Clés API pour la CLI et l'automatisation | Providers externes (Google, GitHub…) |
| Hashage bcrypt | |
| Protection brute-force (rate limiting) | |

## Authentification par mot de passe

### Diagramme — Flow de login

```mermaid
sequenceDiagram
    participant Client as Client - Web ou CLI
    participant API as API FastAPI
    participant DB as Database
    participant Cache as Cache - Redis ou mémoire

    Client->>API: POST /api/v1/auth/login username password
    API->>DB: Rechercher l'utilisateur
    DB->>API: User + hashed_password
    API->>API: Vérifier bcrypt - password - hash
    alt Mot de passe correct
        API->>API: Générer access_token - JWT 30 min
        API->>API: Générer refresh_token - opaque 7 jours
        API->>DB: Stocker refresh_token hashé
        API->>Cache: Stocker session
        API->>Client: 200 access_token refresh_token user_info
    else Mot de passe incorrect
        API->>Cache: Incrémenter compteur échecs - rate limit
        API->>Client: 401 Unauthorized
    end
```

Les mots de passe sont hashés avec bcrypt (cost factor 12). Le même mécanisme couvre les trois interfaces de WindFlow (Web UI, CLI, API) : un access token de courte durée et un refresh token de longue durée.

### Access token (JWT)

Le access token est un JWT signé **HS256** avec le `SECRET_KEY` de l'instance. Il contient les informations minimales pour identifier l'utilisateur et vérifier ses droits sans requête en base.

```json
{
    "sub": "550e8400-e29b-41d4-a716-446655440000",
    "username": "admin",
    "is_superadmin": true,
    "exp": 1711234567,
    "iat": 1711232767,
    "type": "access"
}
```

Durée : **30 minutes** par défaut (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

### Refresh token

Le refresh token est une chaîne **opaque** (pas un JWT). Son hash est stocké en base (`refresh_tokens`, chapitre [06-modele-de-donnees.md](06-modele-de-donnees.md)). Il sert uniquement à obtenir un nouveau access token quand celui-ci expire. Durée : **7 jours** par défaut (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`).

Le refresh flow : le client envoie `POST /api/v1/auth/refresh` avec son refresh token ; le serveur retrouve l'entrée par comparaison de hash, vérifie l'utilisateur et l'expiration, et émet un nouvel access token. La déconnexion (`POST /api/v1/auth/logout`) invalide le refresh token en base.

## Authentification par clé API

Les clés API permettent une authentification non-interactive pour la CLI, les scripts et les intégrations tierces.

- **Format** : préfixe `wf_ak_` + 48 caractères aléatoires (`secrets.token_urlsafe`) ;
- **Stockage** : seul le hash bcrypt de la clé est stocké en base (`api_keys.key_hash`) — la clé brute n'est jamais conservée ;
- **Affichage** : la clé complète est affichée **une seule fois** à la création ;
- **Expiration** : configurable à la création (null = n'expire jamais) ;
- **Révocation** : à tout moment, par nom ou par identifiant.

Création et gestion (`windflow auth api-key create|list|revoke`) : chapitre [10-cli-tui.md](10-cli-tui.md).

Utilisation :

```bash
# Header HTTP
curl -H "Authorization: Bearer wf_ak_a1b2c3d4e5f6..." \
     http://windflow:8080/api/v1/apps

# Variable d'environnement pour la CLI
export WINDFLOW_API_KEY=wf_ak_a1b2c3d4e5f6...
windflow apps list
```

## Exemples de requêtes et réponses

Exemple illustratif — login et rafraîchissement :

```bash
# Login
curl -X POST http://windflow:8080/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "s3cr3t"}'
```

```json
{
    "access_token": "eyJhbGciOiJIUzI1NiIs...",
    "refresh_token": "9f8e7d6c5b4a3f2e1d0c...",
    "token_type": "bearer",
    "expires_in": 1800,
    "user": {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "username": "admin",
        "email": "admin@example.com",
        "is_superadmin": true
    }
}
```

```bash
# Renouvellement de l'access token
curl -X POST http://windflow:8080/api/v1/auth/refresh \
  -H "Content-Type: application/json" \
  -d '{"refresh_token": "9f8e7d6c5b4a3f2e1d0c..."}'
# → { "access_token": "eyJ...", "token_type": "bearer", "expires_in": 1800 }
```

Les erreurs suivent l'enveloppe standard du chapitre [09-api.md](09-api.md) : `401` avec `INVALID_CREDENTIALS` (identifiants incorrects), `INVALID_OR_EXPIRED_TOKEN` (token invalide/expiré) ou `TOO_MANY_ATTEMPTS` (compteur brute-force dépassé).

## Protection brute-force

Le core implémente un rate limiting sur l'endpoint de login :

| Paramètre | Valeur par défaut | Variable |
|---|---|---|
| Tentatives avant blocage | 5 | `AUTH_MAX_ATTEMPTS` |
| Durée du blocage | 300 s (5 min) | `AUTH_LOCKOUT_SECONDS` |
| Fenêtre de comptage | 600 s (10 min) | — |

Le compteur est indexé par couple (username ou IP) dans le cache (Redis en mode standard, mémoire en mode léger) ; il est réinitialisé après un login réussi. Ce rate limiting fonctionne donc dans les deux profils de déploiement. La limite `POST /auth/login` (5/minute par IP) est aussi appliquée au niveau API (chapitre [09-api.md](09-api.md)).

## Validation des tokens dans l'API

Toutes les requêtes (sauf `/auth/login`, `/system/health` et `/system/ready`) passent par la dépendance `get_current_user`, qui accepte soit un JWT (`Authorization: Bearer <token>`), soit une clé API (header `Authorization: Bearer wf_ak_…` ou `X-API-Key`). Le token décodé, l'utilisateur est rechargé depuis la base (un token dont l'utilisateur a été désactivé est refusé), puis les permissions RBAC sont vérifiées par le middleware (chapitre [08-rbac-permissions.md](08-rbac-permissions.md)).

Les connexions WebSocket utilisent le même JWT, passé en query parameter (`?token=<jwt>`, chapitre [09-api.md](09-api.md)).

## SSO via plugin Keycloak

Le SSO n'est pas dans le core — il est fourni par le **plugin Keycloak** (chapitre [12-marketplace.md](12-marketplace.md)). Quand le plugin est installé, il ajoute un flow d'authentification OIDC/SAML en complément de l'auth JWT native.

### Ce que le plugin ajoute

- Bouton « Se connecter avec SSO » sur la page de login (maquette : Écran 24 du chapitre [14-ui-maquettes.md](14-ui-maquettes.md)) ;
- support OIDC (OpenID Connect) et SAML 2.0 ;
- intégration LDAP / Active Directory ;
- 2FA (TOTP, WebAuthn) géré par Keycloak ;
- mapping automatique des rôles Keycloak → rôles WindFlow ;
- providers externes (Google, GitHub, GitLab) configurables dans Keycloak.

### Diagramme — Flow SSO

```mermaid
sequenceDiagram
    participant User as Utilisateur
    participant WF as WindFlow UI
    participant KC as Keycloak - plugin
    participant API as WindFlow API

    User->>WF: Clic Se connecter avec SSO
    WF->>KC: Redirect vers Keycloak login
    KC->>User: Page de login Keycloak ou LDAP AD
    User->>KC: Saisie des credentials
    KC->>WF: Redirect avec authorization_code
    WF->>API: POST /api/v1/plugins/keycloak/auth/callback code
    API->>KC: Échange code vers tokens Keycloak
    KC->>API: ID token + user info + rôles
    API->>API: Créer ou mettre à jour l utilisateur WindFlow
    API->>API: Mapper les rôles Keycloak vers rôles WindFlow
    API->>API: Générer JWT WindFlow
    API->>WF: access_token + refresh_token
    WF->>User: Connecté
```

L'utilisateur se retrouve avec un JWT WindFlow standard — le reste de l'application ne sait pas (et n'a pas besoin de savoir) si l'authentification a été faite par mot de passe ou par SSO.

### Mapping des rôles

```yaml
# Configuration du plugin Keycloak (via l'UI ou la CLI)
role_mapping:
  windflow-admin: admin       # Groupe Keycloak → rôle WindFlow
  windflow-operator: operator
  windflow-viewer: viewer
default_role: viewer           # Rôle si aucun mapping ne correspond
auto_create_users: true        # Création au premier login SSO
default_organization: "main"   # Organisation par défaut des nouveaux utilisateurs
```

Les rôles effectifs des utilisateurs WindFlow — y compris ceux issus du mapping SSO — sont consultables et gérables dans Settings → Utilisateurs (Écran 23 du chapitre [14-ui-maquettes.md](14-ui-maquettes.md)).

## Configuration

Variables d'environnement core :

```bash
# Clé de signature des JWT (générée automatiquement par install.sh)
SECRET_KEY=a1b2c3d4...

# Durée des tokens
ACCESS_TOKEN_EXPIRE_MINUTES=30     # Défaut : 30
REFRESH_TOKEN_EXPIRE_DAYS=7        # Défaut : 7

# Protection brute-force
AUTH_MAX_ATTEMPTS=5                # Défaut : 5
AUTH_LOCKOUT_SECONDS=300           # Défaut : 300
```

Tout le reste de la configuration auth (SSO, LDAP, 2FA, providers externes) est géré par le plugin Keycloak via son interface de configuration dans WindFlow. La protection du `SECRET_KEY` est traitée au chapitre [15-securite.md](15-securite.md).

## Endpoints auth

La liste canonique des endpoints (`/api/v1/auth/login`, `/refresh`, `/logout`, `/me`, `/password`, `/api-keys`) et les routes ajoutées par le plugin Keycloak sont au chapitre [09-api.md](09-api.md).

## Voir aussi

- [08-rbac-permissions.md](08-rbac-permissions.md) — rôles et contrôle d'accès appliqués après authentification
- [10-cli-tui.md](10-cli-tui.md) — `windflow auth login|status|logout`, gestion des clés API en CLI
- [09-api.md](09-api.md) — endpoints auth, auth WebSocket, rate limiting
- [15-securite.md](15-securite.md) — protection du SECRET_KEY, audit des logins, checklists
- [12-marketplace.md](12-marketplace.md) — fiche du plugin Keycloak
