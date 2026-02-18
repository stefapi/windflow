# Code Snippets - Extraits réutilisables

[← Déploiement](14-DEPLOYMENT.md) | [Retour à l'accueil →](README.md)

## 🛠️ Collection d'extraits de code réutilisables

### 1. Validation et sanitization

```python
# utils/validation.py
import re
from typing import Optional

def sanitize_container_name(name: str) -> str:
    """Sanitiser un nom de conteneur"""
    # Docker n'accepte que [a-zA-Z0-9][a-zA-Z0-9_.-]
    return re.sub(r'[^a-zA-Z0-9_.-]', '_', name)

def validate_path(path: str) -> bool:
    """Valider un path pour éviter les traversals"""
    # Pas de .. ou path absolu suspect
    if '..' in path or path.startswith('/etc') or path.startswith('/root'):
        return False
    return True

def validate_env_var_name(name: str) -> bool:
    """Valider un nom de variable d'environnement"""
    return bool(re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', name))
```

### 2. Parsing logs Docker

```python
# utils/docker_logs.py
from typing import AsyncIterator

async def stream_docker_logs(
    docker_client,
    container_id: str,
    tail: int = 100,
    timestamps: bool = True
) -> AsyncIterator[str]:
    """Stream les logs d'un conteneur"""
    response = await docker_client.docker_fetch(
        f"/containers/{container_id}/logs",
        params={
            "stdout": True,
            "stderr": True,
            "tail": tail,
            "timestamps": timestamps,
            "follow": True
        }
    )

    async for chunk in response.aiter_bytes():
        # Demultiplexer le stream Docker
        if len(chunk) > 8:
            yield chunk[8:].decode('utf-8', errors='replace')
```

### 3. Formatage bytes

```python
# utils/format.py

def format_bytes(bytes_value: int) -> str:
    """Formater des bytes en unités lisibles"""
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_value < 1024:
            return f"{bytes_value:.1f} {unit}"
        bytes_value /= 1024
    return f"{bytes_value:.1f} PB"

def format_duration(seconds: int) -> str:
    """Formater une durée en secondes"""
    if seconds < 60:
        return f"{seconds}s"
    elif seconds < 3600:
        return f"{seconds // 60}m {seconds % 60}s"
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
```

### 4. Retry decorator

```python
# utils/retry.py
import asyncio
from functools import wraps
from typing import Callable

def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator pour retry avec exponential backoff"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_exception = None
            current_delay = delay

            for attempt in range(max_attempts):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_attempts - 1:
                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

            raise last_exception
        return wrapper
    return decorator

# Usage
@retry(max_attempts=3, delay=1.0)
async def fetch_container(container_id: str):
    return await docker.inspect_container(container_id)
```

### 5. Cache simple

```python
# utils/cache.py
from typing import Dict, Any, Optional
from datetime import datetime, timedelta

class SimpleCache:
    """Cache simple avec expiration"""

    def __init__(self):
        self._cache: Dict[str, tuple] = {}

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None

        value, expires_at = self._cache[key]
        if datetime.utcnow() > expires_at:
            del self._cache[key]
            return None

        return value

    def set(self, key: str, value: Any, ttl_seconds: int = 300):
        expires_at = datetime.utcnow() + timedelta(seconds=ttl_seconds)
        self._cache[key] = (value, expires_at)

    def delete(self, key: str):
        self._cache.pop(key, None)

    def clear(self):
        self._cache.clear()

# Singleton
cache = SimpleCache()
```

### 6. Audit logger

```python
# utils/audit.py
from typing import Optional
from datetime import datetime

async def log_audit(
    db,
    action: str,
    entity_type: str,
    entity_id: str = None,
    entity_name: str = None,
    user_id: int = None,
    username: str = None,
    environment_id: int = None,
    description: str = None,
    ip_address: str = None,
    user_agent: str = None
):
    """Logger une action d'audit"""
    await db.execute("""
        INSERT INTO audit_logs
        (user_id, username, action, entity_type, entity_id, entity_name,
         environment_id, description, ip_address, user_agent, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, [
        user_id, username, action, entity_type, entity_id, entity_name,
        environment_id, description, ip_address, user_agent, datetime.utcnow()
    ])
```

### 7. Notifications

```python
# utils/notifications.py
from typing import Dict, Any
import asyncio

class NotificationService:
    """Service de notifications multi-canal"""

    def __init__(self):
        self.handlers = {}

    def register_handler(self, channel: str, handler):
        self.handlers[channel] = handler

    async def send(self, channel: str, title: str, message: str, data: dict = None):
        if channel in self.handlers:
            await self.handlers[channel].send(title, message, data)

class WebhookHandler:
    """Handler pour webhooks"""

    def __init__(self, url: str):
        self.url = url

    async def send(self, title: str, message: str, data: dict = None):
        import httpx

        payload = {
            "title": title,
            "message": message,
            "data": data or {}
        }

        async with httpx.AsyncClient() as client:
            await client.post(self.url, json=payload)

class EmailHandler:
    """Handler pour emails"""

    def __init__(self, smtp_config: dict):
        self.config = smtp_config

    async def send(self, title: str, message: str, data: dict = None):
        # Implementation SMTP
        pass
```

### 8. Rate limiting

```python
# utils/rate_limit.py
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict

class RateLimiter:
    """Rate limiter simple par IP"""

    def __init__(self, max_requests: int = 100, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window = timedelta(seconds=window_seconds)
        self.requests: Dict[str, list] = defaultdict(list)

    def is_allowed(self, key: str) -> bool:
        """Vérifier si la requête est autorisée"""
        now = datetime.utcnow()

        # Nettoyer les anciennes requêtes
        self.requests[key] = [
            t for t in self.requests[key]
            if now - t < self.window
        ]

        if len(self.requests[key]) >= self.max_requests:
            return False

        self.requests[key].append(now)
        return True

    def get_remaining(self, key: str) -> int:
        """Obtenir le nombre de requêtes restantes"""
        self.is_allowed(key)  # Clean first
        return max(0, self.max_requests - len(self.requests[key]))
```

---

[← Déploiement](14-DEPLOYMENT.md) | [Retour à l'accueil →](README.md)
