# Base de données - Schéma complet

[← Module Docker](02-DOCKER-API-MODULE.md) | [Suivant : Authentification →](04-AUTHENTICATION.md)

## 📊 Vue d'ensemble

Windflow-sample utilise **Drizzle ORM** avec support dual SQLite (développement) et PostgreSQL (production).

## 🗄️ Schéma relationnel complet

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           GESTION UTILISATEURS                          │
├─────────────────────────────────────────────────────────────────────────┤
│  users ──1:N──► user_roles ──N:1──► roles                               │
│    │                  │                                                 │
│    │                  └──► environments (scope)                        │
│    └──1:N──► sessions                                                    │
│    └──1:N──► user_preferences                                            │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         ENVIRONNEMENTS DOCKER                           │
├─────────────────────────────────────────────────────────────────────────┤
│  environments                                                            │
│    ├──1:N──► host_metrics                                                │
│    ├──1:N──► container_events                                            │
│    ├──1:N──► git_stacks                                                  │
│    ├──1:N──► auto_update_settings                                        │
│    ├──1:N──► hawser_tokens                                               │
│    └──1:N──► vulnerability_scans                                         │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           GIT INTEGRATION                               │
├─────────────────────────────────────────────────────────────────────────┤
│  git_credentials ──1:N──► git_repositories ──1:N──► git_stacks          │
│                                │                      │                  │
│                                └──────────────────────┘                  │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                           AUDIT & SECURITY                              │
├─────────────────────────────────────────────────────────────────────────┤
│  audit_logs ──N:1──► users                                              │
│  audit_logs ──N:1──► environments                                       │
│  auth_settings (singleton)                                               │
│  ldap_config / oidc_config                                               │
└─────────────────────────────────────────────────────────────────────────┘
```

## 📋 Tables détaillées

### 1. Users et Auth

```python
# models/user.py - SQLAlchemy
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class User(Base):
    """Utilisateur du système"""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String(255), unique=True, nullable=False, index=True)
    email = Column(String(255), nullable=True)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(255), nullable=True)
    avatar = Column(Text, nullable=True)  # Base64 image
    auth_provider = Column(String(50), default="local")  # local, ldap, oidc
    mfa_enabled = Column(Boolean, default=False)
    mfa_secret = Column(String(255), nullable=True)  # TOTP secret encrypted
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    roles = relationship("UserRole", back_populates="user", cascade="all, delete")
    sessions = relationship("Session", back_populates="user", cascade="all, delete")
    preferences = relationship("UserPreference", back_populates="user", cascade="all, delete")
    audit_logs = relationship("AuditLog", back_populates="user")


class Session(Base):
    """Session utilisateur"""
    __tablename__ = "sessions"

    id = Column(String(255), primary_key=True)  # UUID
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    provider = Column(String(50), nullable=False)  # local, ldap, oidc
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relations
    user = relationship("User", back_populates="sessions")


class Role(Base):
    """Rôle système"""
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    is_system = Column(Boolean, default=False)  # System roles cannot be deleted
    permissions = Column(Text, nullable=False)  # JSON array of permissions
    environment_ids = Column(Text, nullable=True)  # JSON array of env IDs (null = all)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    user_roles = relationship("UserRole", back_populates="role", cascade="all, delete")


class UserRole(Base):
    """Association User-Role avec scope environnement"""
    __tablename__ = "user_roles"
    __table_args__ = (
        UniqueConstraint("user_id", "role_id", "environment_id", name="uq_user_role_env"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    role_id = Column(Integer, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    # Relations
    user = relationship("User", back_populates="roles")
    role = relationship("Role", back_populates="user_roles")
```

### 2. Environments Docker

```python
# models/environment.py
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class Environment(Base):
    """Environnement Docker (connexion à un daemon)"""
    __tablename__ = "environments"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    
    # Connexion HTTP/TLS
    host = Column(String(255), nullable=True)
    port = Column(Integer, default=2375)
    protocol = Column(String(10), default="http")  # http, https
    
    # Certificats TLS (stockés chiffrés)
    tls_ca = Column(Text, nullable=True)
    tls_cert = Column(Text, nullable=True)
    tls_key = Column(Text, nullable=True)
    tls_skip_verify = Column(Boolean, default=False)
    
    # UI
    icon = Column(String(50), default="globe")  # Lucide icon name
    
    # Features
    collect_activity = Column(Boolean, default=True)
    collect_metrics = Column(Boolean, default=True)
    highlight_changes = Column(Boolean, default=True)
    labels = Column(Text, nullable=True)  # JSON
    
    # Type de connexion
    connection_type = Column(String(50), default="socket")
    # socket, direct, hawser-standard, hawser-edge
    socket_path = Column(String(255), default="/var/run/docker.sock")
    
    # Hawser
    hawser_token = Column(String(255), nullable=True)
    hawser_last_seen = Column(DateTime, nullable=True)
    hawser_agent_id = Column(String(255), nullable=True)
    hawser_agent_name = Column(String(255), nullable=True)
    hawser_version = Column(String(50), nullable=True)
    hawser_capabilities = Column(Text, nullable=True)  # JSON array
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    host_metrics = relationship("HostMetric", back_populates="environment", cascade="all, delete")
    container_events = relationship("ContainerEvent", back_populates="environment", cascade="all, delete")
    git_stacks = relationship("GitStack", back_populates="environment", cascade="all, delete")
    auto_updates = relationship("AutoUpdateSettings", back_populates="environment", cascade="all, delete")
    vulnerability_scans = relationship("VulnerabilityScan", back_populates="environment", cascade="all, delete")


class HostMetric(Base):
    """Métriques système collectées"""
    __tablename__ = "host_metrics"

    id = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    cpu_percent = Column(Float, nullable=False)
    memory_percent = Column(Float, nullable=False)
    memory_used = Column(BigInteger, nullable=True)
    memory_total = Column(BigInteger, nullable=True)
    timestamp = Column(DateTime, server_default=func.now(), index=True)

    # Relations
    environment = relationship("Environment", back_populates="host_metrics")


class ContainerEvent(Base):
    """Événements Docker (start, stop, die, etc.)"""
    __tablename__ = "container_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    container_id = Column(String(255), nullable=False)
    container_name = Column(String(255), nullable=True)
    image = Column(String(255), nullable=True)
    action = Column(String(50), nullable=False)  # start, stop, die, destroy, etc.
    actor_attributes = Column(Text, nullable=True)  # JSON
    timestamp = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, server_default=func.now())

    # Index composé pour requêtes par env + temps
    __table_args__ = (
        Index("idx_container_events_env_timestamp", "environment_id", "timestamp"),
    )

    # Relations
    environment = relationship("Environment", back_populates="container_events")
```

### 3. Git Integration

```python
# models/git.py
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from database import Base

class GitCredential(Base):
    """Credentials Git (SSH ou HTTPS)"""
    __tablename__ = "git_credentials"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    auth_type = Column(String(20), default="none", nullable=False)
    # none, https, ssh
    
    # HTTPS auth
    username = Column(String(255), nullable=True)
    password = Column(Text, nullable=True)  # Encrypted
    
    # SSH auth
    ssh_private_key = Column(Text, nullable=True)  # Encrypted
    ssh_passphrase = Column(Text, nullable=True)  # Encrypted
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    repositories = relationship("GitRepository", back_populates="credential")


class GitRepository(Base):
    """Dépôt Git configuré"""
    __tablename__ = "git_repositories"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), unique=True, nullable=False)
    url = Column(String(500), nullable=False)
    branch = Column(String(100), default="main")
    credential_id = Column(Integer, ForeignKey("git_credentials.id", ondelete="SET NULL"))
    compose_path = Column(String(255), default="docker-compose.yml")
    environment_id = Column(Integer, nullable=True)  # Default environment
    
    # Auto-update
    auto_update = Column(Boolean, default=False)
    auto_update_schedule = Column(String(20), default="daily")  # daily, weekly, custom
    auto_update_cron = Column(String(100), default="0 3 * * *")
    
    # Webhook
    webhook_enabled = Column(Boolean, default=False)
    webhook_secret = Column(String(255), nullable=True)  # For HMAC signature
    
    # Sync status
    last_sync = Column(DateTime, nullable=True)
    last_commit = Column(String(40), nullable=True)  # Git SHA
    sync_status = Column(String(20), default="pending")  # pending, synced, error
    sync_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relations
    credential = relationship("GitCredential", back_populates="repositories")
    stacks = relationship("GitStack", back_populates="repository", cascade="all, delete")


class GitStack(Base):
    """Stack déployée depuis Git"""
    __tablename__ = "git_stacks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stack_name = Column(String(255), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    repository_id = Column(Integer, ForeignKey("git_repositories.id", ondelete="CASCADE"), nullable=False)
    compose_path = Column(String(255), default="docker-compose.yml")
    
    # Auto-update (peut override repository)
    auto_update = Column(Boolean, default=False)
    auto_update_schedule = Column(String(20), default="daily")
    auto_update_cron = Column(String(100), default="0 3 * * *")
    
    # Webhook spécifique
    webhook_enabled = Column(Boolean, default=False)
    webhook_secret = Column(String(255), nullable=True)
    
    # Sync status
    last_sync = Column(DateTime, nullable=True)
    last_commit = Column(String(40), nullable=True)
    sync_status = Column(String(20), default="pending")
    sync_error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Unique constraint
    __table_args__ = (
        UniqueConstraint("stack_name", "environment_id", name="uq_git_stack_env"),
    )

    # Relations
    repository = relationship("GitRepository", back_populates="stacks")
    environment = relationship("Environment", back_populates="git_stacks")
```

### 4. Auto-Update et Vulnerability Scanning

```python
# models/auto_update.py
from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class AutoUpdateSettings(Base):
    """Configuration auto-update par conteneur"""
    __tablename__ = "auto_update_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="NO ACTION"))
    container_name = Column(String(255), nullable=False)
    enabled = Column(Boolean, default=False)
    
    # Schedule
    schedule_type = Column(String(20), default="daily")  # daily, weekly, custom
    cron_expression = Column(String(100), nullable=True)
    
    # Vulnerability criteria
    vulnerability_criteria = Column(String(20), default="never")
    # never, critical, high, medium, low
    
    # Status
    last_checked = Column(DateTime, nullable=True)
    last_updated = Column(DateTime, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("environment_id", "container_name", name="uq_auto_update_env_container"),
    )

    # Relations
    environment = relationship("Environment", back_populates="auto_updates")


class VulnerabilityScan(Base):
    """Résultat de scan de vulnérabilités"""
    __tablename__ = "vulnerability_scans"

    id = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    image_id = Column(String(255), nullable=False)
    image_name = Column(String(255), nullable=False)
    scanner = Column(String(20), nullable=False)  # grype, trivy
    
    scanned_at = Column(DateTime, nullable=False)
    scan_duration = Column(Integer, nullable=True)  # seconds
    
    # Counts
    critical_count = Column(Integer, default=0)
    high_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    low_count = Column(Integer, default=0)
    negligible_count = Column(Integer, default=0)
    unknown_count = Column(Integer, default=0)
    
    # Full results
    vulnerabilities = Column(Text, nullable=True)  # JSON array
    error = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_vuln_scan_env_image", "environment_id", "image_id"),
    )

    # Relations
    environment = relationship("Environment", back_populates="vulnerability_scans")


class ScheduleExecution(Base):
    """Historique des exécutions de schedules"""
    __tablename__ = "schedule_executions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    schedule_type = Column(String(50), nullable=False)  # auto_update, git_sync
    schedule_id = Column(Integer, nullable=False)  # ID in auto_update_settings or git_stacks
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    entity_name = Column(String(255), nullable=False)  # Container or stack name
    
    triggered_by = Column(String(50), nullable=False)  # schedule, manual, webhook
    triggered_at = Column(DateTime, nullable=False)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    
    status = Column(String(20), nullable=False)  # pending, running, success, failed
    error_message = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON
    logs = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        Index("idx_schedule_exec_type_id", "schedule_type", "schedule_id"),
    )
```

### 5. Tables Supplémentaires

```python
# models/hawser.py
class HawserToken(Base):
    """Tokens pour agents Hawser Edge"""
    __tablename__ = "hawser_tokens"

    id = Column(Integer, primary_key=True, autoincrement=True)
    token = Column(String(255), unique=True, nullable=False)  # Hashed token
    token_prefix = Column(String(16), nullable=False)  # First 8 chars pour identification
    name = Column(String(255), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    is_active = Column(Boolean, default=True)
    last_used = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    expires_at = Column(DateTime, nullable=True)

    # Relations
    environment = relationship("Environment", back_populates="hawser_tokens")


# models/stack.py
class StackSource(Base):
    """Source d'une stack (internal vs git)"""
    __tablename__ = "stack_sources"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stack_name = Column(String(255), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    source_type = Column(String(20), default="internal", nullable=False)
    # internal, git
    
    git_repository_id = Column(Integer, ForeignKey("git_repositories.id", ondelete="SET NULL"))
    git_stack_id = Column(Integer, ForeignKey("git_stacks.id", ondelete="SET NULL"))
    compose_path = Column(String(500), nullable=True)
    env_path = Column(String(500), nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stack_name", "environment_id", name="uq_stack_source_env"),
    )


class StackEnvironmentVariable(Base):
    """Variables d'environnement par stack"""
    __tablename__ = "stack_environment_variables"

    id = Column(Integer, primary_key=True, autoincrement=True)
    stack_name = Column(String(255), nullable=False)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"))
    key = Column(String(255), nullable=False)
    value = Column(Text, nullable=False)  # Encrypted if is_secret
    is_secret = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("stack_name", "environment_id", "key", name="uq_stack_env_var"),
    )


class PendingContainerUpdate(Base):
    """Conteneurs en attente de mise à jour"""
    __tablename__ = "pending_container_updates"

    id = Column(Integer, primary_key=True, autoincrement=True)
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"), nullable=False)
    container_id = Column(String(255), nullable=False)
    container_name = Column(String(255), nullable=False)
    current_image = Column(String(500), nullable=False)
    checked_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint("environment_id", "container_id", name="uq_pending_update_env_container"),
    )


# models/preferences.py
class UserPreference(Base):
    """Préférences utilisateur (unified key-value store)"""
    __tablename__ = "user_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True)
    # NULL = shared (free edition), set = per-user (enterprise)
    
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="CASCADE"), nullable=True)
    # NULL = global preferences
    
    key = Column(String(255), nullable=False)
    # Ex: 'dashboard_layout', 'containers_grid_columns', 'theme_mode', etc.
    
    value = Column(Text, nullable=False)  # JSON value
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "environment_id", "key", name="uq_user_pref"),
    )

    # Relations
    user = relationship("User", back_populates="preferences")
```

### 6. Audit et Settings

```python
# models/audit.py
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.sql import func
from database import Base

class AuditLog(Base):
    """Log d'audit pour toutes les actions"""
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"))
    username = Column(String(255), nullable=False)
    action = Column(String(100), nullable=False)
    # container.start, container.stop, image.pull, stack.deploy, etc.
    
    entity_type = Column(String(50), nullable=False)
    # container, image, volume, network, stack, user, etc.
    entity_id = Column(String(255), nullable=True)
    entity_name = Column(String(255), nullable=True)
    
    environment_id = Column(Integer, ForeignKey("environments.id", ondelete="SET NULL"))
    description = Column(Text, nullable=True)
    details = Column(Text, nullable=True)  # JSON additional info
    
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    # Index pour recherche par user
    __table_args__ = (
        Index("idx_audit_logs_user_id", "user_id"),
        Index("idx_audit_logs_created_at", "created_at"),
    )

    # Relations
    user = relationship("User", back_populates="audit_logs")


class AuthSettings(Base):
    """Configuration d'authentification (singleton)"""
    __tablename__ = "auth_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auth_enabled = Column(Boolean, default=False)
    default_provider = Column(String(20), default="local")
    session_timeout = Column(Integer, default=86400)  # seconds
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class LDAPConfig(Base):
    """Configuration LDAP/Active Directory"""
    __tablename__ = "ldap_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=False)
    
    server_url = Column(String(255), nullable=False)  # ldap://host:389
    bind_dn = Column(String(255), nullable=True)
    bind_password = Column(Text, nullable=True)  # Encrypted
    base_dn = Column(String(255), nullable=False)
    
    # User search
    user_filter = Column(String(255), default="(uid={{username}})")
    username_attribute = Column(String(50), default="uid")
    email_attribute = Column(String(50), default="mail")
    display_name_attribute = Column(String(50), default="cn")
    
    # Group search
    group_base_dn = Column(String(255), nullable=True)
    group_filter = Column(String(255), nullable=True)
    admin_group = Column(String(100), nullable=True)
    role_mappings = Column(Text, nullable=True)  # JSON
    
    # TLS
    tls_enabled = Column(Boolean, default=False)
    tls_ca = Column(Text, nullable=True)
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())


class OIDCConfig(Base):
    """Configuration OpenID Connect"""
    __tablename__ = "oidc_config"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    enabled = Column(Boolean, default=False)
    
    issuer_url = Column(String(255), nullable=False)
    client_id = Column(String(255), nullable=False)
    client_secret = Column(Text, nullable=False)  # Encrypted
    redirect_uri = Column(String(255), nullable=False)
    scopes = Column(String(255), default="openid profile email")
    
    # Claims mapping
    username_claim = Column(String(50), default="preferred_username")
    email_claim = Column(String(50), default="email")
    display_name_claim = Column(String(50), default="name")
    
    # Role mapping
    admin_claim = Column(String(100), nullable=True)
    admin_value = Column(String(100), nullable=True)
    role_mappings_claim = Column(String(50), default="groups")
    role_mappings = Column(Text, nullable=True)  # JSON
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
```

## 🔧 Setup Python avec SQLAlchemy

### Configuration base de données

```python
# database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
import os

# SQLite (développement)
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./data/Windflow-sample.db")

# PostgreSQL (production)
# DATABASE_URL = "postgresql+asyncpg://user:pass@localhost/Windflow-sample"

# Engine async
engine = create_async_engine(
    DATABASE_URL,
    echo=False,  # True pour debug SQL
    future=True
)

# Session factory
AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# Base pour models
Base = declarative_base()

# Dependency FastAPI
async def get_db():
    """Dependency pour obtenir une session DB"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
```

### Initialisation et migrations

```python
# init_db.py
from sqlalchemy import text
from database import engine, Base
from models import *  # Import tous les models

async def init_database():
    """Créer toutes les tables"""
    async with engine.begin() as conn:
        # Créer tables
        await conn.run_sync(Base.metadata.create_all)
        
        # Insérer données initiales
        await insert_initial_data(conn)

async def insert_initial_data(conn):
    """Insérer données par défaut"""
    # Rôle admin par défaut
    await conn.execute(text("""
        INSERT OR IGNORE INTO roles (name, description, is_system, permissions)
        VALUES ('admin', 'Administrator with full access', 1, '["*"]')
    """))
    
    await conn.execute(text("""
        INSERT OR IGNORE INTO roles (name, description, is_system, permissions)
        VALUES ('user', 'Standard user', 1, '["containers:read", "images:read"]')
    """))
    
    await conn.execute(text("""
        INSERT OR IGNORE INTO roles (name, description, is_system, permissions)
        VALUES ('viewer', 'Read-only access', 1, '["*:read"]')
    """))
    
    # Auth settings par défaut
    await conn.execute(text("""
        INSERT OR IGNORE INTO auth_settings (id, auth_enabled, default_provider)
        VALUES (1, 0, 'local')
    """))
    
    # Environnement local par défaut
    await conn.execute(text("""
        INSERT OR IGNORE INTO environments (name, connection_type, socket_path)
        VALUES ('local', 'socket', '/var/run/docker.sock')
    """))

# Usage
if __name__ == "__main__":
    import asyncio
    asyncio.run(init_database())
    print("Database initialized!")
```

### Repository pattern

```python
# repositories/user.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from models.user import User, Session, Role, UserRole
from typing import Optional, List

class UserRepository:
    """Repository pour les opérations User"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def get_by_id(self, user_id: int) -> Optional[User]:
        """Obtenir utilisateur par ID"""
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def get_by_username(self, username: str) -> Optional[User]:
        """Obtenir utilisateur par username"""
        result = await self.db.execute(
            select(User).where(User.username == username)
        )
        return result.scalar_one_or_none()
    
    async def create(self, username: str, password_hash: str, **kwargs) -> User:
        """Créer un utilisateur"""
        user = User(
            username=username,
            password_hash=password_hash,
            **kwargs
        )
        self.db.add(user)
        await self.db.flush()
        return user
    
    async def update_last_login(self, user_id: int):
        """Mettre à jour dernière connexion"""
        from datetime import datetime
        user = await self.get_by_id(user_id)
        if user:
            user.last_login = datetime.utcnow()
    
    async def get_user_permissions(self, user_id: int, env_id: Optional[int] = None) -> List[str]:
        """Obtenir permissions d'un utilisateur pour un environnement"""
        query = (
            select(Role.permissions)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        
        if env_id:
            query = query.where(
                (UserRole.environment_id == env_id) | 
                (UserRole.environment_id.is_(None))
            )
        
        result = await self.db.execute(query)
        permissions = []
        for row in result:
            import json
            permissions.extend(json.loads(row[0]))
        
        return list(set(permissions))


class SessionRepository:
    """Repository pour les sessions"""
    
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def create(self, user_id: int, provider: str, timeout: int = 86400) -> Session:
        """Créer une session"""
        import uuid
        from datetime import datetime, timedelta
        
        session = Session(
            id=str(uuid.uuid4()),
            user_id=user_id,
            provider=provider,
            expires_at=datetime.utcnow() + timedelta(seconds=timeout)
        )
        self.db.add(session)
        await self.db.flush()
        return session
    
    async def get_valid(self, session_id: str) -> Optional[Session]:
        """Obtenir session valide"""
        from datetime import datetime
        
        result = await self.db.execute(
            select(Session)
            .where(Session.id == session_id)
            .where(Session.expires_at > datetime.utcnow())
        )
        return result.scalar_one_or_none()
    
    async def delete(self, session_id: str):
        """Supprimer une session (logout)"""
        await self.db.execute(
            Session.__table__.delete().where(Session.id == session_id)
        )
    
    async def cleanup_expired(self):
        """Nettoyer les sessions expirées"""
        from datetime import datetime
        await self.db.execute(
            Session.__table__.delete().where(Session.expires_at < datetime.utcnow())
        )
```

## 🎨 Frontend Vue 3 - Stores Pinia

```typescript
// stores/user.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

interface User {
  id: number;
  username: string;
  email?: string;
  displayName?: string;
  avatar?: string;
  roles: string[];
  permissions: string[];
}

export const useUserStore = defineStore('user', () => {
  const user = ref<User | null>(null);
  const isAuthenticated = computed(() => user.value !== null);
  const isAdmin = computed(() => 
    user.value?.roles.includes('admin') || 
    user.value?.permissions.includes('*')
  );

  async function login(username: string, password: string) {
    const response = await fetch('/api/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password })
    });

    if (!response.ok) {
      throw new Error('Login failed');
    }

    const data = await response.json();
    user.value = data.user;
    return data;
  }

  async function logout() {
    await fetch('/api/auth/logout', { method: 'POST' });
    user.value = null;
  }

  async function fetchCurrentUser() {
    try {
      const response = await fetch('/api/auth/session');
      if (response.ok) {
        const data = await response.json();
        user.value = data.user;
      }
    } catch {
      user.value = null;
    }
  }

  function hasPermission(permission: string): boolean {
    if (!user.value) return false;
    if (user.value.permissions.includes('*')) return true;
    
    // Check wildcard (e.g., "containers:*" matches "containers:start")
    const [resource] = permission.split(':');
    if (user.value.permissions.includes(`${resource}:*`)) return true;
    
    return user.value.permissions.includes(permission);
  }

  return {
    user,
    isAuthenticated,
    isAdmin,
    login,
    logout,
    fetchCurrentUser,
    hasPermission
  };
});
```

```typescript
// stores/environment.ts
import { defineStore } from 'pinia';
import { ref, computed } from 'vue';

interface Environment {
  id: number;
  name: string;
  host?: string;
  port?: number;
  connectionType: string;
  icon: string;
}

export const useEnvironmentStore = defineStore('environment', () => {
  const environments = ref<Environment[]>([]);
  const currentEnvironment = ref<Environment | null>(null);
  
  const currentEnvId = computed(() => currentEnvironment.value?.id ?? null);
  
  async function fetchEnvironments() {
    const response = await fetch('/api/environments');
    if (response.ok) {
      environments.value = await response.json();
      
      // Set first as default if none selected
      if (!currentEnvironment.value && environments.value.length > 0) {
        currentEnvironment.value = environments.value[0];
      }
    }
  }
  
  function setEnvironment(envId: number) {
    const env = environments.value.find(e => e.id === envId);
    if (env) {
      currentEnvironment.value = env;
      localStorage.setItem('currentEnvId', String(envId));
    }
  }
  
  function getEnvId(): number | null {
    return currentEnvironment.value?.id ?? null;
  }
  
  return {
    environments,
    currentEnvironment,
    currentEnvId,
    fetchEnvironments,
    setEnvironment,
    getEnvId
  };
});
```

---

[← Module Docker](02-DOCKER-API-MODULE.md) | [Suivant : Authentification →](04-AUTHENTICATION.md)
