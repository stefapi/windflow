# Authentification - WindFlow

## Vue d'Ensemble

WindFlow intègre un système d'authentification **JWT** autonome qui fonctionne sans dépendance externe. C'est une fonctionnalité du core — elle est disponible dès l'installation, sans plugin.

L'authentification gère les trois interfaces de WindFlow (Web UI, CLI, API) avec le même mécanisme : un access token de courte durée et un refresh token de longue durée.

Pour les besoins avancés (SSO, LDAP/AD, OIDC, 2FA), le **plugin Keycloak** est disponible dans la marketplace.

### Ce qui est Core vs Plugin

| Core (toujours disponible) | Plugin (optionnel) |
|---|---|
| Auth par mot de passe (JWT) | SSO Keycloak (LDAP, AD, OIDC, SAML) |
| Refresh tokens | 2FA (TOTP, WebAuthn) via Keycloak |
| API keys pour la CLI et l'automatisation | Providers externes (Google, GitHub, etc.) |
| Hashage bcrypt | |
| Protection brute-force (rate limiting) | |

---

## Authentification par Mot de Passe

### Flow

```mermaid
sequenceDiagram
    participant Client as Client (Web / CLI)
    participant API as API (FastAPI)
    participant DB as Database
    participant Cache as Cache (Redis ou mémoire)

    Client->>API: POST /api/v1/auth/login {username, password}
    API->>DB: Rechercher l'utilisateur
    DB->>API: User + hashed_password
    API->>API: Vérifier bcrypt(password, hash)
    alt Mot de passe correct
        API->>API: Générer access_token (JWT, 30 min)
        API->>API: Générer refresh_token (opaque, 7 jours)
        API->>DB: Stocker refresh_token (hash)
        API->>Cache: Stocker session
        API->>Client: 200 {access_token, refresh_token, user_info}
    else Mot de passe incorrect
        API->>Cache: Incrémenter compteur échecs (rate limit)
        API->>Client: 401 Unauthorized
    end
```

### Implémentation

```python
from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

class AuthService:
    """Service d'authentification core."""

    def __init__(self, db, cache, secret_key: str):
        self.db = db
        self.cache = cache  # Redis ou MemoryCache
        self.secret_key = secret_key
        self.access_token_ttl = timedelta(minutes=30)
        self.refresh_token_ttl = timedelta(days=7)

    async def login(self, username: str, password: str) -> dict:
        """Authentification par mot de passe."""

        # Protection brute-force
        if await self._is_rate_limited(username):
            raise AuthError("Too many failed attempts. Try again later.")

        # Vérification utilisateur
        user = await self.db.get_user_by_username(username)
        if not user or not pwd_context.verify(password, user.hashed_password):
            await self._record_failed_attempt(username)
            raise AuthError("Invalid credentials")

        # Génération des tokens
        access_token = self._create_access_token(user)
        refresh_token = self._create_refresh_token(user)

        # Stocker le refresh token (hashé) en base
        await self.db.store_refresh_token(
            user_id=user.id,
            token_hash=pwd_context.hash(refresh_token),
            expires_at=datetime.utcnow() + self.refresh_token_ttl,
        )

        # Reset compteur d'échecs
        await self._reset_failed_attempts(username)

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "expires_in": int(self.access_token_ttl.total_seconds()),
            "user": {
                "id": str(user.id),
                "username": user.username,
                "email": user.email,
                "is_superadmin": user.is_superadmin,
            },
        }

    def _create_access_token(self, user) -> str:
        """Crée un JWT access token."""
        payload = {
            "sub": str(user.id),
            "username": user.username,
            "is_superadmin": user.is_superadmin,
            "exp": datetime.utcnow() + self.access_token_ttl,
            "iat": datetime.utcnow(),
            "type": "access",
        }
        return jwt.encode(payload, self.secret_key, algorithm="HS256")

    def _create_refresh_token(self, user) -> str:
        """Crée un refresh token opaque."""
        import secrets
        return secrets.token_urlsafe(64)
```

### Access Token (JWT)

Le access token est un JWT signé avec le `SECRET_KEY` de l'instance. Il contient les informations minimales nécessaires pour identifier l'utilisateur et vérifier ses droits sans requête en base.

```python
# Payload du JWT
{
    "sub": "550e8400-e29b-41d4-a716-446655440000",  # user_id
    "username": "admin",
    "is_superadmin": true,
    "exp": 1711234567,  # Expiration (30 min)
    "iat": 1711232767,  # Émission
    "type": "access"
}
```

Durée : **30 minutes** par défaut (configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`).

### Refresh Token

Le refresh token est une chaîne opaque (pas un JWT). Son hash est stocké en base de données. Il sert uniquement à obtenir un nouveau access token quand celui-ci expire.

Durée : **7 jours** par défaut (configurable via `REFRESH_TOKEN_EXPIRE_DAYS`).

### Refresh Flow

```python
async def refresh(self, refresh_token: str) -> dict:
    """Renouvelle l'access token via le refresh token."""

    # Chercher le refresh token en base (comparaison par hash)
    stored_token = await self.db.find_valid_refresh_token(refresh_token)
    if not stored_token:
        raise AuthError("Invalid or expired refresh token")

    # Récupérer l'utilisateur
    user = await self.db.get_user_by_id(stored_token.user_id)
    if not user:
        raise AuthError("User not found")

    # Générer un nouveau access token
    new_access_token = self._create_access_token(user)

    return {
        "access_token": new_access_token,
        "token_type": "bearer",
        "expires_in": int(self.access_token_ttl.total_seconds()),
    }
```

---

## Authentification par API Key

Les API keys permettent une authentification non-interactive pour la CLI, les scripts, et les intégrations tierces.

### Création d'une API Key

```bash
# Via CLI (nécessite une session active)
windflow auth api-key create --name "CI/CD Pipeline" --expires 90d
# → API Key: wf_ak_a1b2c3d4e5f6... (affichée une seule fois)

# Via API
POST /api/v1/auth/api-keys
{
    "name": "CI/CD Pipeline",
    "expires_in_days": 90
}
```

### Utilisation

```bash
# Dans un header HTTP
curl -H "Authorization: Bearer wf_ak_a1b2c3d4e5f6..." \
     http://windflow:8080/api/v1/containers

# Dans la CLI
windflow --api-key wf_ak_a1b2c3d4e5f6... containers list

# Via variable d'environnement
export WINDFLOW_API_KEY=wf_ak_a1b2c3d4e5f6...
windflow containers list
```

### Implémentation

```python
class APIKeyService:
    """Gestion des API keys."""

    API_KEY_PREFIX = "wf_ak_"

    async def create_api_key(self, user: User, name: str, expires_in_days: int = None) -> str:
        """Crée une nouvelle API key pour un utilisateur."""
        import secrets

        # Générer la clé
        raw_key = self.API_KEY_PREFIX + secrets.token_urlsafe(48)

        # Stocker le hash en base (la clé brute n'est jamais stockée)
        await self.db.create_api_key(
            user_id=user.id,
            name=name,
            key_hash=pwd_context.hash(raw_key),
            expires_at=datetime.utcnow() + timedelta(days=expires_in_days) if expires_in_days else None,
        )

        return raw_key  # Retournée une seule fois

    async def authenticate(self, api_key: str) -> User:
        """Authentifie une requête via API key."""
        if not api_key.startswith(self.API_KEY_PREFIX):
            raise AuthError("Invalid API key format")

        # Chercher toutes les clés actives et comparer les hashes
        active_keys = await self.db.get_active_api_keys()
        for stored_key in active_keys:
            if pwd_context.verify(api_key, stored_key.key_hash):
                # Vérifier expiration
                if stored_key.expires_at and datetime.utcnow() > stored_key.expires_at:
                    raise AuthError("API key expired")
                # Mettre à jour last_used
                await self.db.update_api_key_last_used(stored_key.id)
                return await self.db.get_user_by_id(stored_key.user_id)

        raise AuthError("Invalid API key")
```

### Gestion des API Keys

```bash
# Lister les API keys de l'utilisateur
windflow auth api-key list
# NAME              CREATED      EXPIRES      LAST USED
# CI/CD Pipeline    2026-03-15   2026-06-13   2026-04-02
# Monitoring Bot    2026-03-20   Never        2026-04-03

# Révoquer une API key
windflow auth api-key revoke --name "CI/CD Pipeline"
```

---

## Authentification CLI

### Login Interactif

```bash
# Login standard (demande username et password)
windflow auth login
# Username: admin
# Password: ********
# ✓ Connected as admin (Super Admin)

# Login vers une instance spécifique
windflow auth login --url http://192.168.1.50:8080
```

### Stockage des Tokens CLI

Les tokens sont stockés localement dans `~/.windflow/credentials`, chiffrés avec une clé dérivée du mot de passe système de l'utilisateur.

```
~/.windflow/
├── credentials          # Tokens chiffrés (permissions 600)
└── config.yml           # URL de l'instance, préférences
```

```python
class CLIAuth:
    """Gestion de l'authentification pour la CLI."""

    CREDENTIALS_PATH = Path.home() / ".windflow" / "credentials"

    async def login(self, url: str, username: str, password: str):
        """Login CLI et stockage sécurisé des tokens."""
        # Appel API
        response = await httpx.AsyncClient().post(
            f"{url}/api/v1/auth/login",
            json={"username": username, "password": password},
        )
        response.raise_for_status()
        tokens = response.json()

        # Stocker les tokens localement
        self._store_credentials({
            "url": url,
            "access_token": tokens["access_token"],
            "refresh_token": tokens["refresh_token"],
            "user": tokens["user"],
        })

    def _store_credentials(self, data: dict):
        """Stocke les credentials chiffrés sur disque."""
        self.CREDENTIALS_PATH.parent.mkdir(parents=True, exist_ok=True)
        encrypted = self._encrypt(json.dumps(data))
        self.CREDENTIALS_PATH.write_bytes(encrypted)
        self.CREDENTIALS_PATH.chmod(0o600)

    async def get_authenticated_client(self) -> httpx.AsyncClient:
        """Retourne un client HTTP authentifié avec auto-refresh."""
        creds = self._load_credentials()
        client = httpx.AsyncClient(
            base_url=creds["url"],
            headers={"Authorization": f"Bearer {creds['access_token']}"},
        )
        # TODO: intercepteur pour auto-refresh si 401
        return client
```

### Session Status

```bash
windflow auth status
# Instance: http://192.168.1.50:8080
# User: admin (Super Admin)
# Token expires: in 24 minutes
# Organizations: homelab (Admin), work (Viewer)

windflow auth logout
# ✓ Logged out. Credentials removed.
```

---

## Protection Brute-Force

Le core implémente un rate limiting sur l'endpoint de login pour se protéger contre les attaques par force brute.

```python
class BruteForceProtection:
    """Protection contre les attaques brute-force."""

    MAX_ATTEMPTS = 5           # Tentatives avant blocage
    LOCKOUT_DURATION = 300     # Blocage de 5 minutes
    WINDOW_DURATION = 600      # Fenêtre de 10 minutes

    def __init__(self, cache):
        self.cache = cache  # Redis ou MemoryCache

    async def is_rate_limited(self, identifier: str) -> bool:
        """Vérifie si un identifiant (username ou IP) est bloqué."""
        key = f"auth:attempts:{identifier}"
        attempts = await self.cache.get(key)
        if attempts and int(attempts) >= self.MAX_ATTEMPTS:
            return True
        return False

    async def record_failed_attempt(self, identifier: str):
        """Enregistre une tentative échouée."""
        key = f"auth:attempts:{identifier}"
        current = await self.cache.get(key)
        count = int(current) + 1 if current else 1
        await self.cache.set(key, str(count), ttl=self.WINDOW_DURATION)

    async def reset_attempts(self, identifier: str):
        """Réinitialise le compteur après un login réussi."""
        key = f"auth:attempts:{identifier}"
        await self.cache.delete(key)
```

Le rate limiting fonctionne en mode standard (Redis) comme en mode léger (cache mémoire).

---

## Validation des Tokens dans l'API

### Dépendance FastAPI

```python
from fastapi import Depends, HTTPException, Header
from jose import jwt, JWTError

async def get_current_user(
    authorization: str = Header(None),
    api_key: str = Header(None, alias="X-API-Key"),
) -> User:
    """Extrait et valide l'utilisateur depuis le token JWT ou l'API key."""

    # Tentative par API key
    if api_key:
        return await api_key_service.authenticate(api_key)

    # Tentative par JWT (header Authorization: Bearer <token>)
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing authentication")

    token = authorization.removeprefix("Bearer ")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user = await db.get_user_by_id(payload["sub"])
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return user
```

### Utilisation sur les Endpoints

```python
@router.get("/api/v1/containers")
async def list_containers(user: User = Depends(get_current_user)):
    """Liste les containers — nécessite authentification."""
    ...

@router.post("/api/v1/plugins/install")
async def install_plugin(
    request: PluginInstallRequest,
    user: User = Depends(get_current_user),
):
    """Installe un plugin — nécessite authentification + rôle Admin (vérifié par RBAC)."""
    ...
```

---

## SSO via Plugin Keycloak

Le SSO n'est pas dans le core — il est fourni par le **plugin Keycloak**. Quand le plugin est installé, il ajoute un flow d'authentification OIDC/SAML en complément de l'auth JWT native.

### Ce que le Plugin Ajoute

- Bouton "Se connecter avec SSO" sur la page de login
- Support OIDC (OpenID Connect) et SAML 2.0
- Intégration LDAP / Active Directory
- 2FA (TOTP, WebAuthn) géré par Keycloak
- Mapping automatique des rôles Keycloak → rôles WindFlow
- Providers externes (Google, GitHub, GitLab) configurables dans Keycloak

### Flow SSO

```mermaid
sequenceDiagram
    participant User as Utilisateur
    participant WF as WindFlow UI
    participant KC as Keycloak (plugin)
    participant API as WindFlow API

    User->>WF: Clic "Se connecter avec SSO"
    WF->>KC: Redirect vers Keycloak login
    KC->>User: Page de login Keycloak (ou LDAP/AD)
    User->>KC: Saisie des credentials
    KC->>WF: Redirect avec authorization_code
    WF->>API: POST /api/v1/plugins/keycloak/auth/callback {code}
    API->>KC: Échange code → tokens Keycloak
    KC->>API: ID token + user info + rôles
    API->>API: Créer/mettre à jour l'utilisateur WindFlow
    API->>API: Mapper les rôles Keycloak → rôles WindFlow
    API->>API: Générer JWT WindFlow
    API->>WF: access_token + refresh_token
    WF->>User: Connecté ✓
```

L'utilisateur se retrouve avec un JWT WindFlow standard — le reste de l'application ne sait pas (et n'a pas besoin de savoir) si l'authentification a été faite par mot de passe ou par SSO.

### Configuration du Mapping de Rôles

```yaml
# Configuration du plugin Keycloak (via l'UI ou CLI)
role_mapping:
  windflow-admin: admin       # Groupe Keycloak "windflow-admin" → rôle WindFlow "admin"
  windflow-operator: operator
  windflow-viewer: viewer
default_role: viewer           # Rôle par défaut si aucun mapping ne correspond
auto_create_users: true        # Créer automatiquement les utilisateurs au premier login SSO
default_organization: "main"   # Organisation par défaut pour les nouveaux utilisateurs SSO
```

---

## Configuration

### Variables d'Environnement (core)

```bash
# Clé de signature des JWT (générée automatiquement par install.sh)
SECRET_KEY=a1b2c3d4...

# Durée des tokens
ACCESS_TOKEN_EXPIRE_MINUTES=30     # Défaut: 30
REFRESH_TOKEN_EXPIRE_DAYS=7        # Défaut: 7

# Protection brute-force
AUTH_MAX_ATTEMPTS=5                 # Défaut: 5
AUTH_LOCKOUT_SECONDS=300            # Défaut: 300 (5 min)
```

Tout le reste de la configuration auth (SSO, LDAP, 2FA, providers externes) est géré par le plugin Keycloak via son interface de configuration dans WindFlow.

---

## Résumé des Endpoints Auth

```
POST   /api/v1/auth/login              # Login par mot de passe
POST   /api/v1/auth/refresh            # Renouveler l'access token
POST   /api/v1/auth/logout             # Déconnexion (invalide le refresh token)
GET    /api/v1/auth/me                 # Infos utilisateur courant
POST   /api/v1/auth/api-keys           # Créer une API key
GET    /api/v1/auth/api-keys           # Lister ses API keys
DELETE /api/v1/auth/api-keys/{id}      # Révoquer une API key
PUT    /api/v1/auth/password           # Changer son mot de passe

# Ajoutés par le plugin Keycloak :
GET    /api/v1/plugins/keycloak/auth/login     # Redirect vers Keycloak
POST   /api/v1/plugins/keycloak/auth/callback  # Retour SSO
```

---

**Références :**
- [RBAC et Permissions](06-rbac-permissions.md) - Rôles et contrôle d'accès
- [Sécurité](13-security.md) - Stratégies de sécurité
- [API Design](07-api-design.md) - Endpoints API
- [CLI Interface](08-cli-interface.md) - Authentification CLI
