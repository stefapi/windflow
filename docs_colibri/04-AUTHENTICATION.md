# Authentification Multi-Provider

[← Base de données](03-DATABASE-SCHEMA.md) | [Suivant : Git Integration →](05-GIT-INTEGRATION.md)

## 🔐 Vue d'ensemble

Windflow-sample supporte **4 providers d'authentification** :
1. **Local** : Argon2id + sessions sécurisées
2. **LDAP/Active Directory** : Bind + search avec mapping de groupes
3. **OIDC/OAuth2** : Keycloak, Google, Azure AD, etc.
4. **MFA** : TOTP (Time-based One-Time Password) + codes de backup

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Auth Flow                          │
├─────────────────────────────────────────────────────┤
│                                                      │
│  ┌─────────┐    ┌──────────────┐    ┌───────────┐  │
│  │  Login  │───►│ Auth Provider│───►│  Session  │  │
│  │  Form   │    │              │    │  DB/Cookie│  │
│  └─────────┘    └──────────────┘    └───────────┘  │
│                      │                              │
│         ┌────────────┼────────────┐                │
│         ▼            ▼            ▼                │
│    ┌─────────┐  ┌─────────┐  ┌─────────┐          │
│    │  Local  │  │  LDAP   │  │  OIDC   │          │
│    │Argon2id │  │   AD    │  │ OAuth2  │          │
│    └─────────┘  └─────────┘  └─────────┘          │
│         │            │            │                │
│         └────────────┼────────────┘                │
│                      ▼                              │
│               ┌───────────┐                        │
│               │    MFA    │                        │
│               │   TOTP    │                        │
│               └───────────┘                        │
└─────────────────────────────────────────────────────┘
```

## 1. Hashing des mots de passe (Argon2id)

### Configuration

```python
# auth/password.py
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHash
import secrets

# Paramètres Argon2id (sécurité optimale)
ARGON2_TIME_COST = 3           # 3 itérations
ARGON2_MEMORY_COST = 65536     # 64 MB
ARGON2_PARALLELISM = 1         # Single-threaded
ARGON2_HASH_LENGTH = 32        # 256-bit output
ARGON2_SALT_LENGTH = 16        # 128-bit salt

# Hasher global
password_hasher = PasswordHasher(
    time_cost=ARGON2_TIME_COST,
    memory_cost=ARGON2_MEMORY_COST,
    parallelism=ARGON2_PARALLELISM,
    hash_len=ARGON2_HASH_LENGTH,
    salt_len=ARGON2_SALT_LENGTH,
    type=argon2.Type.ID  # Argon2id
)
```

### Fonction hashPassword

```python
def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2id.
    
    Args:
        password: Mot de passe en clair
        
    Returns:
        Hash au format PHC: $argon2id$v=19$m=65536,t=3,p=1$...
    """
    return password_hasher.hash(password)
```

### Fonction verifyPassword

```python
def verify_password(password: str, hash: str) -> bool:
    """Vérifie un mot de passe contre son hash.
    
    Args:
        password: Mot de passe en clair
        hash: Hash Argon2id
        
    Returns:
        True si le mot de passe correspond
    """
    try:
        password_hasher.verify(hash, password)
        
        # Rehash si paramètres obsolètes
        if password_hasher.check_needs_rehash(hash):
            # Signal pour MAJ dans la DB (non géré ici)
            pass
            
        return True
    except (VerifyMismatchError, InvalidHash):
        return False
```

**Avantages Argon2id:**
- Résistant aux attaques GPU (memory-hard)
- Résistant aux attaques de timing
- Résistant aux attaques side-channel
- Standard recommandé par l'OWASP

## 2. Gestion des sessions

### Configuration

```python
# auth/session.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from datetime import datetime, timedelta
import secrets
from typing import Optional

from models.user import Session, User
from auth.config import get_auth_settings

SESSION_TOKEN_BYTES = 32  # 256 bits d'entropie
```

### Génération de token

```python
def generate_session_token() -> str:
    """Génère un token de session cryptographiquement sécurisé."""
    return secrets.token_urlsafe(SESSION_TOKEN_BYTES)
```

### Création de session

```python
async def create_user_session(
    db: AsyncSession,
    user_id: int,
    provider: str,  # 'local', 'ldap:AD', 'oidc:Keycloak'
) -> Session:
    """Crée une nouvelle session utilisateur.
    
    Args:
        db: Session de base de données
        user_id: ID de l'utilisateur
        provider: Provider d'authentification
        
    Returns:
        Session créée
    """
    # Nettoyer sessions expirées
    await delete_expired_sessions(db)
    
    # Générer token sécurisé
    session_id = generate_session_token()
    
    # Récupérer timeout depuis settings
    settings = await get_auth_settings(db)
    session_timeout = settings.session_timeout if settings else 86400  # 24h défaut
    
    expires_at = datetime.utcnow() + timedelta(seconds=session_timeout)
    
    # Créer en DB
    session = Session(
        id=session_id,
        user_id=user_id,
        provider=provider,
        expires_at=expires_at
    )
    db.add(session)
    
    # Mettre à jour lastLogin
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user:
        user.last_login = datetime.utcnow()
    
    await db.commit()
    await db.refresh(session)
    
    return session
```

### Validation de session

```python
async def validate_session(
    db: AsyncSession,
    session_id: str
) -> Optional[User]:
    """Valide une session et retourne l'utilisateur.
    
    Args:
        db: Session de base de données
        session_id: ID de session
        
    Returns:
        Utilisateur si session valide, None sinon
    """
    if not session_id:
        return None
    
    # Récupérer session
    result = await db.execute(
        select(Session)
        .where(Session.id == session_id)
        .where(Session.expires_at > datetime.utcnow())
    )
    session = result.scalar_one_or_none()
    
    if not session:
        return None
    
    # Récupérer utilisateur
    result = await db.execute(
        select(User)
        .where(User.id == session.user_id)
        .where(User.is_active == True)
    )
    user = result.scalar_one_or_none()
    
    return user
```

### Destruction de session (logout)

```python
async def destroy_session(
    db: AsyncSession,
    session_id: str
) -> None:
    """Détruit une session (logout).
    
    Args:
        db: Session de base de données
        session_id: ID de session à détruire
    """
    if session_id:
        await db.execute(
            delete(Session).where(Session.id == session_id)
        )
        await db.commit()


async def delete_expired_sessions(db: AsyncSession) -> None:
    """Nettoie les sessions expirées."""
    await db.execute(
        delete(Session).where(Session.expires_at < datetime.utcnow())
    )
    await db.commit()
```

## 3. Rate Limiting

### Configuration

```python
# auth/rate_limit.py
from datetime import datetime, timedelta
from typing import Dict, Optional
import asyncio
from dataclasses import dataclass

RATE_LIMIT_MAX_ATTEMPTS = 5           # 5 tentatives max
RATE_LIMIT_WINDOW_SECONDS = 900       # 15 minutes
RATE_LIMIT_LOCKOUT_SECONDS = 900      # 15 minutes de blocage

@dataclass
class RateLimitEntry:
    attempts: int
    last_attempt: datetime
    locked_until: Optional[datetime] = None
```

### Store en mémoire

```python
class RateLimitStore:
    """Store in-memory pour rate limiting."""
    
    def __init__(self):
        self._store: Dict[str, RateLimitEntry] = {}
        self._lock = asyncio.Lock()
        
        # Cleanup automatique toutes les 5 minutes
        asyncio.create_task(self._cleanup_loop())
    
    async def _cleanup_loop(self):
        """Nettoyage périodique des entrées expirées."""
        while True:
            await asyncio.sleep(300)  # 5 minutes
            await self.cleanup()
    
    async def cleanup(self):
        """Nettoie les entrées expirées."""
        async with self._lock:
            now = datetime.utcnow()
            expired_keys = [
                key for key, entry in self._store.items()
                if (now - entry.last_attempt).total_seconds() > RATE_LIMIT_WINDOW_SECONDS
            ]
            for key in expired_keys:
                del self._store[key]
    
    async def get(self, identifier: str) -> Optional[RateLimitEntry]:
        """Récupère une entrée."""
        async with self._lock:
            return self._store.get(identifier)
    
    async def set(self, identifier: str, entry: RateLimitEntry):
        """Définit une entrée."""
        async with self._lock:
            self._store[identifier] = entry
    
    async def delete(self, identifier: str):
        """Supprime une entrée."""
        async with self._lock:
            self._store.pop(identifier, None)

# Instance globale
rate_limit_store = RateLimitStore()
```

### Vérification de limitation

```python
async def is_rate_limited(identifier: str) -> tuple[bool, Optional[int]]:
    """Vérifie si un identifiant est rate limited.
    
    Args:
        identifier: Username ou IP
        
    Returns:
        (limited, retry_after_seconds)
    """
    entry = await rate_limit_store.get(identifier)
    now = datetime.utcnow()
    
    if not entry:
        return False, None
    
    # Vérifier si bloqué
    if entry.locked_until and entry.locked_until > now:
        retry_after = int((entry.locked_until - now).total_seconds())
        return True, retry_after
    
    # Réinitialiser si hors fenêtre
    if (now - entry.last_attempt).total_seconds() > RATE_LIMIT_WINDOW_SECONDS:
        await rate_limit_store.delete(identifier)
        return False, None
    
    return False, None
```

### Enregistrement d'échec

```python
async def record_failed_attempt(identifier: str) -> None:
    """Enregistre une tentative échouée.
    
    Args:
        identifier: Username ou IP
    """
    now = datetime.utcnow()
    entry = await rate_limit_store.get(identifier)
    
    if not entry or (now - entry.last_attempt).total_seconds() > RATE_LIMIT_WINDOW_SECONDS:
        # Nouvelle entrée
        await rate_limit_store.set(
            identifier,
            RateLimitEntry(attempts=1, last_attempt=now)
        )
        return
    
    # Incrémenter compteur
    entry.attempts += 1
    entry.last_attempt = now
    
    # Bloquer si trop de tentatives
    if entry.attempts >= RATE_LIMIT_MAX_ATTEMPTS:
        entry.locked_until = now + timedelta(seconds=RATE_LIMIT_LOCKOUT_SECONDS)
    
    await rate_limit_store.set(identifier, entry)
```

### Nettoyage sur succès

```python
async def clear_rate_limit(identifier: str) -> None:
    """Nettoie le rate limit sur succès."""
    await rate_limit_store.delete(identifier)
```

## 4. Authentification Locale

### Service d'authentification

```python
# auth/local.py
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from dataclasses import dataclass

from models.user import User
from auth.password import verify_password, hash_password

@dataclass
class LoginResult:
    success: bool
    user: Optional[User] = None
    requires_mfa: bool = False
    error: Optional[str] = None
```

### Flow complet

```python
async def authenticate_local(
    db: AsyncSession,
    username: str,
    password: str
) -> LoginResult:
    """Authentifie un utilisateur en mode local.
    
    Args:
        db: Session de base de données
        username: Nom d'utilisateur
        password: Mot de passe en clair
        
    Returns:
        Résultat de l'authentification
    """
    # Récupérer utilisateur
    result = await db.execute(
        select(User).where(User.username == username)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        # Protection timing attack : hash dummy
        hash_password('dummy_password')
        return LoginResult(
            success=False,
            error='Invalid username or password'
        )
    
    if not user.is_active:
        return LoginResult(
            success=False,
            error='Account is disabled'
        )
    
    # Vérifier mot de passe
    if not verify_password(password, user.password_hash):
        return LoginResult(
            success=False,
            error='Invalid username or password'
        )
    
    # MFA requis?
    if user.mfa_enabled:
        return LoginResult(
            success=True,
            user=user,
            requires_mfa=True
        )
    
    return LoginResult(
        success=True,
        user=user
    )
```

### API Route FastAPI

```python
# api/v1/auth.py
from fastapi import APIRouter, Depends, Response, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel

from database import get_db
from auth.local import authenticate_local
from auth.session import create_user_session
from auth.rate_limit import is_rate_limited, record_failed_attempt, clear_rate_limit

router = APIRouter(prefix="/api/auth", tags=["auth"])

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    success: bool
    requires_mfa: bool = False
    user: Optional[dict] = None
    error: Optional[str] = None

@router.post("/login")
async def login(
    request: Request,
    response: Response,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """Endpoint de login local."""
    
    username = body.username
    password = body.password
    
    # Rate limiting par username et IP
    client_ip = request.client.host
    
    limited_user, retry_user = await is_rate_limited(username)
    limited_ip, retry_ip = await is_rate_limited(client_ip)
    
    if limited_user or limited_ip:
        retry_after = retry_user or retry_ip
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": f"Too many failed attempts. Try again in {retry_after} seconds."
            }
        )
    
    # Authentification
    result = await authenticate_local(db, username, password)
    
    if not result.success:
        await record_failed_attempt(username)
        await record_failed_attempt(client_ip)
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"error": result.error}
        )
    
    if result.requires_mfa:
        # Stocker temporairement user ID pour vérification MFA
        # (peut utiliser session temporaire ou JWT)
        response.set_cookie(
            key="mfa_pending",
            value=str(result.user.id),
            httponly=True,
            samesite="strict",
            max_age=300  # 5 minutes
        )
        return {"requires_mfa": True}
    
    # Succès - créer session
    await clear_rate_limit(username)
    await clear_rate_limit(client_ip)
    
    session = await create_user_session(db, result.user.id, 'local')
    
    # Cookie de session
    response.set_cookie(
        key="windflow_session",
        value=session.id,
        httponly=True,
        secure=True,  # HTTPS only en production
        samesite="strict",
        max_age=session.expires_at.timestamp() - datetime.utcnow().timestamp()
    )
    
    return {
        "success": True,
        "user": {
            "id": result.user.id,
            "username": result.user.username,
            "email": result.user.email,
            "display_name": result.user.display_name
        }
    }
```

## 5. LDAP / Active Directory

### Configuration

```python
# auth/ldap_auth.py
from ldap3 import Server, Connection, ALL, SUBTREE
from ldap3.core.exceptions import LDAPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional, List
import ssl

from models.user import User, LDAPConfig
from auth.local import LoginResult
```

### Fonction d'authentification

```python
async def authenticate_ldap(
    db: AsyncSession,
    username: str,
    password: str,
    config_id: Optional[int] = None
) -> tuple[LoginResult, Optional[str]]:
    """Authentifie via LDAP/Active Directory.
    
    Args:
        db: Session de base de données
        username: Nom d'utilisateur
        password: Mot de passe
        config_id: ID de configuration LDAP (optionnel)
        
    Returns:
        (LoginResult, provider_name)
    """
    # Récupérer configs LDAP actives
    if config_id:
        result = await db.execute(
            select(LDAPConfig)
            .where(LDAPConfig.id == config_id)
            .where(LDAPConfig.enabled == True)
        )
        configs = result.scalars().all()
    else:
        result = await db.execute(
            select(LDAPConfig).where(LDAPConfig.enabled == True)
        )
        configs = result.scalars().all()
    
    if not configs:
        return (
            LoginResult(success=False, error='No LDAP configuration available'),
            None
        )
    
    # Essayer chaque config
    for config in configs:
        result, provider = await try_ldap_auth(db, username, password, config)
        if result.success:
            return result, provider
    
    return (
        LoginResult(success=False, error='Invalid username or password'),
        None
    )
```

### Flow LDAP

```python
async def try_ldap_auth(
    db: AsyncSession,
    username: str,
    password: str,
    config: LDAPConfig
) -> tuple[LoginResult, Optional[str]]:
    """Tente l'authentification LDAP avec une config."""
    
    try:
        # Configurer TLS
        tls_config = None
        if config.tls_enabled:
            tls_config = ssl.create_default_context()
            if config.tls_ca:
                # Charger CA cert
                pass
        
        # Serveur LDAP
        server = Server(
            config.server_url,
            get_info=ALL,
            tls=tls_config
        )
        
        # 1. Bind avec service account pour rechercher
        if config.bind_dn and config.bind_password:
            conn = Connection(
                server,
                user=config.bind_dn,
                password=config.bind_password,
                auto_bind=True
            )
        else:
            conn = Connection(server, auto_bind=True)
        
        # 2. Rechercher l'utilisateur
        user_filter = config.user_filter.replace('{{username}}', username)
        
        conn.search(
            search_base=config.base_dn,
            search_filter=user_filter,
            search_scope=SUBTREE,
            attributes=[
                config.username_attribute,
                config.email_attribute,
                config.display_name_attribute
            ]
        )
        
        if not conn.entries:
            conn.unbind()
            return (
                LoginResult(success=False, error='User not found'),
                None
            )
        
        user_entry = conn.entries[0]
        user_dn = user_entry.entry_dn
        
        conn.unbind()
        
        # 3. Bind en tant qu'utilisateur (authentification)
        try:
            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True
            )
            user_conn.unbind()
        except LDAPException:
            return (
                LoginResult(success=False, error='Invalid username or password'),
                None
            )
        
        # 4. Extraire attributs utilisateur
        ldap_username = getattr(
            user_entry,
            config.username_attribute,
            username
        ).value
        email = getattr(user_entry, config.email_attribute, None)
        email = email.value if email else None
        display_name = getattr(user_entry, config.display_name_attribute, None)
        display_name = display_name.value if display_name else None
        
        # 5. Vérifier groupe admin
        should_be_admin = False
        if config.admin_group:
            should_be_admin = await check_ldap_group_membership(
                config, user_dn, config.admin_group
            )
        
        auth_provider = f"ldap:{config.name}"
        
        # 6. Créer ou mettre à jour utilisateur local
        result = await db.execute(
            select(User).where(User.username == ldap_username)
        )
        user = result.scalar_one_or_none()
        
        if not user:
            user = User(
                username=ldap_username,
                email=email,
                display_name=display_name,
                password_hash='',  # Pas de mot de passe local pour LDAP
                auth_provider=auth_provider
            )
            db.add(user)
        else:
            user.email = email
            user.display_name = display_name
            user.auth_provider = auth_provider
        
        await db.commit()
        await db.refresh(user)
        
        # 7. Gérer rôle Admin (à implémenter selon votre logique RBAC)
        # if should_be_admin:
        #     await assign_admin_role(db, user.id)
        
        if not user.is_active:
            return (
                LoginResult(success=False, error='Account is disabled'),
                None
            )
        
        if user.mfa_enabled:
            return (
                LoginResult(success=True, user=user, requires_mfa=True),
                config.name
            )
        
        return (
            LoginResult(success=True, user=user),
            config.name
        )
        
    except LDAPException as e:
        print(f"[LDAP] Authentication error: {e}")
        return (
            LoginResult(success=False, error='LDAP authentication failed'),
            None
        )
```

### Vérification appartenance groupe

```python
async def check_ldap_group_membership(
    config: LDAPConfig,
    user_dn: str,
    group_dn_or_name: str
) -> bool:
    """Vérifie l'appartenance à un groupe LDAP."""
    
    try:
        server = Server(config.server_url, get_info=ALL)
        
        if config.bind_dn and config.bind_password:
            conn = Connection(
                server,
                user=config.bind_dn,
                password=config.bind_password,
                auto_bind=True
            )
        else:
            conn = Connection(server, auto_bind=True)
        
        # Détecter si DN complet ou juste nom
        is_full_dn = '=' in group_dn_or_name and ',' in group_dn_or_name
        
        if config.group_filter:
            # Filtre personnalisé
            search_base = config.group_base_dn or group_dn_or_name
            group_filter = (
                config.group_filter
                .replace('{{user_dn}}', user_dn)
                .replace('{{group}}', group_dn_or_name)
            )
        elif is_full_dn:
            # DN complet
            search_base = group_dn_or_name
            group_filter = f"(member={user_dn})"
        else:
            # Nom de groupe seulement
            if not config.group_base_dn:
                conn.unbind()
                return False
            search_base = config.group_base_dn
            group_filter = f"(&(cn={group_dn_or_name})(member={user_dn}))"
        
        conn.search(
            search_base=search_base,
            search_filter=group_filter,
            search_scope=SUBTREE
        )
        
        result = len(conn.entries) > 0
        conn.unbind()
        
        return result
        
    except LDAPException as e:
        print(f"[LDAP] Group membership check failed: {e}")
        return False
```

## 6. OIDC / OAuth2

### Configuration

```python
# auth/oidc.py
from authlib.integrations.httpx_client import AsyncOAuth2Client
from authlib.jose import jwt
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import secrets
from typing import Dict, Optional
from datetime import datetime, timedelta

from models.user import User, OIDCConfig
from auth.local import LoginResult
```

### Store temporaire pour state/nonce

```python
class OIDCStateStore:
    """Store temporaire pour OIDC state/nonce."""
    
    def __init__(self):
        self._store: Dict[str, dict] = {}
    
    def set(self, state: str, data: dict):
        """Stocke les données d'état."""
        self._store[state] = {
            **data,
            'expires_at': datetime.utcnow() + timedelta(minutes=10)
        }
    
    def get(self, state: str) -> Optional[dict]:
        """Récupère les données d'état."""
        data = self._store.get(state)
        if data and data['expires_at'] > datetime.utcnow():
            return data
        return None
    
    def delete(self, state: str):
        """Supprime les données d'état."""
        self._store.pop(state, None)

oidc_state_store = OIDCStateStore()
```

### Génération URL d'autorisation

```python
async def build_oidc_authorization_url(
    db: AsyncSession,
    config_id: int,
    redirect_url: str = '/'
) -> dict:
    """Génère l'URL d'autorisation OIDC.
    
    Args:
        db: Session de base de données
        config_id: ID de configuration OIDC
        redirect_url: URL de redirection après login
        
    Returns:
        {"url": "...", "state": "..."} ou {"error": "..."}
    """
    # Récupérer config
    result = await db.execute(
        select(OIDCConfig)
        .where(OIDCConfig.id == config_id)
        .where(OIDCConfig.enabled == True)
    )
    config = result.scalar_one_or_none()
    
    if not config:
        return {"error": "OIDC configuration not found"}
    
    try:
        # Créer client OAuth2
        client = AsyncOAuth2Client(
            client_id=config.client_id,
            client_secret=config.client_secret,
            redirect_uri=config.redirect_uri
        )
        
        # Découverte OIDC
        metadata = await client.fetch_openid_provider_configuration(
            config.issuer_url
        )
        
        # Générer state et nonce
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(16)
        
        # PKCE
        code_verifier = secrets.token_urlsafe(32)
        code_challenge = jwt.create_s256_code_challenge(code_verifier)
        
        # Stocker state
        oidc_state_store.set(state, {
            'config_id': config_id,
            'code_verifier': code_verifier,
            'nonce': nonce,
            'redirect_url': redirect_url
        })
        
        # Construire URL
        auth_url, _ = client.create_authorization
