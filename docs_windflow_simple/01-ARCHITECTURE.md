# Architecture du projet Windflow-sample

[← Retour](00-OVERVIEW.md) | [Suivant : Module Docker →](02-DOCKER-API-MODULE.md)

## 🏛️ Architecture globale

### Vue d'ensemble des couches

```
┌────────────────────────────────────────────────────────────┐
│                    CLIENT (Browser)                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │     Vue 3    │  │  WebSocket   │  │   xterm.js   │    │
│  │  Components  │  │   (Events)   │  │  (Terminal)  │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
└─────────┼──────────────────┼──────────────────┼────────────┘
          │                  │                  │
          │ HTTP/SSE         │ WS              │ WS
          │                  │                  │
┌─────────▼──────────────────▼──────────────────▼────────────┐
│               Python FastAPI                          │
│  ┌────────────────────────────────────────────────────┐    │
│  │              API Routes (/api/*)                    │    │
│  │  ┌──────┐  ┌──────┐  ┌──────┐  ┌──────┐          │    │
│  │  │Docker│  │Images│  │Stacks│  │ Auth │          │    │
│  │  └───┬──┘  └───┬──┘  └───┬──┘  └───┬──┘          │    │
│  └──────┼─────────┼─────────┼─────────┼──────────────┘    │
│  ┌──────▼─────────▼─────────▼─────────▼──────────────┐    │
│  │           Server Modules (src/lib/server/)         │    │
│  │  ┌────────────────────────────────────────────┐   │    │
│  │  │  docker.ts (API Docker native - 2800L)     │   │    │
│  │  │  - dockerFetch()                           │   │    │
│  │  │  - Container operations                    │   │    │
│  │  │  - Image operations                        │   │    │
│  │  │  - Volume/Network management               │   │    │
│  │  └────────────────────────────────────────────┘   │    │
│  │  ┌────────────────────────────────────────────┐   │    │
│  │  │  auth.ts (Multi-provider authentication)   │   │    │
│  │  │  - Local (bcrypt)                          │   │    │
│  │  │  - LDAP/AD                                 │   │    │
│  │  │  - OIDC/OAuth2                             │   │    │
│  │  │  - MFA (TOTP)                              │   │    │
│  │  └────────────────────────────────────────────┘   │    │
│  │  ┌────────────────────────────────────────────┐   │    │
│  │  │  db.ts (Drizzle ORM)                       │   │    │
│  │  │  hawser.ts (WebSocket proxy)               │   │    │
│  │  │  git.ts (Git integration)                  │   │    │
│  │  │  scheduler.ts (Cron jobs)                  │   │    │
│  │  └────────────────────────────────────────────┘   │    │
│  └────────────────────────────────────────────────────┘    │
└────────────┬──────────────────┬──────────────────┬─────────┘
             │                  │                  │
    ┌────────▼────────┐  ┌──────▼──────┐  ┌──────▼──────┐
    │  Background     │  │  Database   │  │   Docker    │
    │  Processes      │  │  SQLite/PG  │  │   Daemon    │
    │  - Metrics      │  │             │  │             │
    │  - Events       │  │             │  │             │
    └─────────────────┘  └─────────────┘  └─────────────┘
```

## 🔄 Flux de données

### 1. Gestion de conteneur (exemple)

```mermaid
sequenceDiagram
    participant Client
    participant API
    participant Docker
    participant DB

    Client->>API: POST /api/containers/start
    API->>Docker: dockerFetch("/containers/{id}/start")
    Docker-->>API: 204 No Content
    API->>DB: Log audit event
    API-->>Client: 200 OK {status: "started"}
    
    Note over API,Docker: Événements en temps réel via SSE
    Docker->>API: Event stream (container started)
    API->>Client: SSE event
```

### 2. Auto-update avec scan de vulnérabilités

```mermaid
flowchart TD
    A[Scheduler déclenche] --> B{Check nouvelle image}
    B -->|Oui| C[Pull temp image]
    B -->|Non| Z[Fin]
    C --> D[Scan vulnérabilités]
    D --> E{Critères OK?}
    E -->|Oui| F[Stop container]
    E -->|Non| G[Delete temp image]
    G --> Z
    F --> H[Rename old -> backup]
    H --> I[Create new container]
    I --> J[Start new container]
    J --> K{Success?}
    K -->|Oui| L[Delete old container]
    K -->|Non| M[Rollback: restore old]
    L --> N[Notification success]
    M --> O[Notification error]
    N --> Z
    O --> Z
```

### 3. Intégration Git avec webhook

```mermaid
sequenceDiagram
    participant Git as Git Remote
    participant Webhook as Webhook
    participant API as Windflow-sample API
    participant Docker as Docker Daemon

    Git->>Webhook: Push event
    Webhook->>API: POST /api/git/webhook/{id}
    Note over Webhook,API: HMAC signature verification
    API->>API: Clone/pull repository
    API->>API: Parse compose file
    API->>Docker: Deploy stack
    Docker-->>API: Containers created
    API->>API: Store deployment event
    API-->>Webhook: 200 OK
```

## 🗄️ Architecture de la base de données

### Schéma relationnel simplifié

```
┌─────────────┐         ┌──────────────┐
│   users     │1       *│user_roles    │
│  - id       ├─────────┤  - user_id   │
│  - username │         │  - role_id   │
│  - password │         │  - env_id    │
└─────────────┘         └──────┬───────┘
                               │
                        ┌──────▼───────┐
                        │   roles      │
                       *│  - id        │
┌──────────────┐        │  - name      │
│ environments │        │  - perms     │
│  - id        │        └──────────────┘
│  - name      │
│  - host      │        ┌─────────────────┐
│  - conn_type │       *│  audit_logs     │
└──────┬───────┘        │  - user_id      │
       │                │  - action       │
       │1               │  - entity_type  │
       │                │  - env_id       │
       │                └─────────────────┘
       │*
┌──────▼──────────┐    ┌─────────────────┐
│  git_stacks     │    │  auto_update    │
│  - stack_name   │    │  - container    │
│  - env_id       │    │  - enabled      │
│  - repo_id      │    │  - cron         │
│  - last_sync    │    │  - vuln_crit    │
└─────────────────┘    └─────────────────┘

┌─────────────────┐    ┌─────────────────┐
│  host_metrics   │    │ container_events│
│  - env_id       │    │  - env_id       │
│  - cpu_percent  │    │  - action       │
│  - mem_percent  │    │  - timestamp    │
│  - timestamp    │    └─────────────────┘
└─────────────────┘
```

## 🔌 Modes de connexion Docker

### 1. Socket Unix (Local)

```python
# Backend Python équivalent
import socket
import json

def docker_request_unix(path: str, method: str = "GET"):
    """Requête Docker via Unix socket"""
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.connect("/var/run/docker.sock")
    
    request = f"{method} {path} HTTP/1.1\r\n"
    request += "Host: localhost\r\n"
    request += "Connection: close\r\n\r\n"
    
    sock.sendall(request.encode())
    response = sock.recv(4096)
    sock.close()
    
    # Parse HTTP response
    headers, body = response.split(b'\r\n\r\n', 1)
    return json.loads(body)

# Usage
containers = docker_request_unix("/containers/json", "GET")
print(f"Found {len(containers)} containers")
```

### 2. HTTP/HTTPS avec TLS

```python
# Backend Python avec TLS client
import requests
from pathlib import Path

def docker_request_tls(
    host: str,
    port: int,
    path: str,
    ca_cert: str,
    client_cert: str,
    client_key: str
):
    """Requête Docker via HTTPS avec mTLS"""
    
    # Écrire les certificats temporairement
    ca_path = Path("/tmp/ca.crt")
    cert_path = Path("/tmp/client.crt")
    key_path = Path("/tmp/client.key")
    
    ca_path.write_text(ca_cert)
    cert_path.write_text(client_cert)
    key_path.write_text(client_key)
    
    url = f"https://{host}:{port}{path}"
    response = requests.get(
        url,
        verify=str(ca_path),
        cert=(str(cert_path), str(key_path))
    )
    
    return response.json()

# Usage
env = {
    "host": "docker.example.com",
    "port": 2376,
    "ca_cert": "-----BEGIN CERTIFICATE-----\n...",
    "client_cert": "-----BEGIN CERTIFICATE-----\n...",
    "client_key": "-----BEGIN RSA PRIVATE KEY-----\n..."
}

containers = docker_request_tls(
    env["host"], env["port"], "/containers/json",
    env["ca_cert"], env["client_cert"], env["client_key"]
)
```

### 3. Hawser Edge (WebSocket)

```python
# Backend Python - Client WebSocket
import asyncio
import websockets
import json
import base64

class HawserEdgeClient:
    """Client pour Hawser Edge via WebSocket"""
    
    def __init__(self, ws_url: str, env_id: int):
        self.ws_url = ws_url
        self.env_id = env_id
        self.ws = None
        
    async def connect(self):
        """Établir connexion WebSocket"""
        self.ws = await websockets.connect(self.ws_url)
        
    async def docker_request(self, method: str, path: str, body=None):
        """Envoyer requête Docker via WebSocket"""
        message = {
            "type": "docker_request",
            "environment_id": self.env_id,
            "method": method,
            "path": path,
            "body": body,
            "request_id": "req_" + str(time.time())
        }
        
        await self.ws.send(json.dumps(message))
        
        # Attendre réponse
        response_raw = await self.ws.recv()
        response = json.loads(response_raw)
        
        # Décoder body si base64
        if response.get("isBinary"):
            body = base64.b64decode(response["body"])
        else:
            body = response["body"]
            
        return {
            "status": response["statusCode"],
            "body": body,
            "headers": response["headers"]
        }

# Usage
async def main():
    client = HawserEdgeClient("ws://localhost:3000/hawser/edge", env_id=2)
    await client.connect()
    
    result = await client.docker_request("GET", "/containers/json")
    containers = json.loads(result["body"])
    print(f"Found {len(containers)} containers")

asyncio.run(main())
```

## 📦 Architecture des modules principaux

### Module Docker (`docker.ts`)

```typescript
// Structure du module (TypeScript original)
export class DockerClient {
  // Cache des environnements
  private static envCache = new Map<number, Environment>();
  
  // Configuration client
  async getConfig(envId: number): Promise<DockerConfig> {
    // Check cache first
    // Fetch from DB if not cached
  }
  
  // Requête HTTP/Socket/WebSocket
  async dockerFetch(path: string, options): Promise<Response> {
    const config = await this.getConfig(envId);
    
    if (config.connectionType === 'socket') {
      return this.fetchUnixSocket(path, options);
    } else if (config.connectionType === 'hawser-edge') {
      return this.fetchHawserEdge(path, options);
    } else {
      return this.fetchHttps(path, options);
    }
  }
  
  // Opérations conteneurs
  async listContainers(all: boolean): Promise<Container[]>
  async startContainer(id: string): Promise<void>
  async stopContainer(id: string): Promise<void>
  async removeContainer(id: string): Promise<void>
  async inspectContainer(id: string): Promise<ContainerInspect>
  async execInContainer(id: string, cmd: string[]): Promise<string>
  
  // Opérations images
  async listImages(): Promise<Image[]>
  async pullImage(name: string, onProgress): Promise<void>
  async removeImage(id: string): Promise<void>
  
  // ... etc
}
```

### Équivalent Python moderne

```python
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
import httpx
import asyncio

@dataclass
class DockerConfig:
    """Configuration connexion Docker"""
    connection_type: str  # 'socket' | 'http' | 'hawser-edge'
    socket_path: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    ca_cert: Optional[str] = None
    client_cert: Optional[str] = None
    client_key: Optional[str] = None

class DockerClient:
    """Client Docker API natif"""
    
    def __init__(self, config: DockerConfig):
        self.config = config
        self._client = None
        
    async def __aenter__(self):
        """Context manager pour connexions"""
        if self.config.connection_type == 'socket':
            self._client = httpx.AsyncClient(
                transport=httpx.AsyncHTTPTransport(
                    uds=self.config.socket_path
                )
            )
        else:
            self._client = httpx.AsyncClient(
                verify=self.config.ca_cert,
                cert=(self.config.client_cert, self.config.client_key)
            )
        return self
        
    async def __aexit__(self, *args):
        await self._client.aclose()
        
    async def docker_fetch(
        self, 
        path: str, 
        method: str = "GET",
        **kwargs
    ) -> httpx.Response:
        """Requête vers API Docker"""
        if self.config.connection_type == 'socket':
            url = f"http://localhost{path}"
        else:
            url = f"https://{self.config.host}:{self.config.port}{path}"
            
        response = await self._client.request(method, url, **kwargs)
        response.raise_for_status()
        return response
        
    async def list_containers(self, all: bool = True) -> List[Dict]:
        """Lister les conteneurs"""
        response = await self.docker_fetch(
            f"/containers/json?all={str(all).lower()}"
        )
        return response.json()
        
    async def start_container(self, container_id: str):
        """Démarrer un conteneur"""
        await self.docker_fetch(
            f"/containers/{container_id}/start",
            method="POST"
        )
        
    async def pull_image(
        self, 
        image: str, 
        on_progress: Optional[Callable] = None
    ):
        """Pull une image avec progression"""
        response = await self.docker_fetch(
            f"/images/create?fromImage={image}",
            method="POST"
        )
        
        # Stream des événements de progression
        async for line in response.aiter_lines():
            if line:
                import json
                event = json.loads(line)
                if on_progress:
                    on_progress(event)

# Usage
async def example():
    config = DockerConfig(
        connection_type='socket',
        socket_path='/var/run/docker.sock'
    )
    
    async with DockerClient(config) as docker:
        containers = await docker.list_containers()
        print(f"Containers: {len(containers)}")
        
        # Pull image avec progression
        def progress(event):
            if 'status' in event:
                print(f"{event['status']}: {event.get('progress', '')}")
                
        await docker.pull_image("nginx:latest", on_progress=progress)

asyncio.run(example())
```

## 🔐 Architecture de sécurité

### Couches de sécurité

```
┌────────────────────────────────────────────────┐
│  1. Auth Layer (Multi-provider)                │
│     - Local (bcrypt + salt)                    │
│     - LDAP/AD (bind + search)                  │
│     - OIDC (JWT validation)                    │
│     - MFA (TOTP)                               │
└────────────────┬───────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────┐
│  2. Session Management                         │
│     - Cookie-based (httpOnly, secure, sameSite)│
│     - Expiration (24h default)                 │
│     - Cleanup automatique                      │
└────────────────┬───────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────┐
│  3. RBAC (Role-Based Access Control)           │
│     - Permissions par ressource                │
│     - Environment-specific roles               │
│     - Admin vs User vs Viewer                  │
└────────────────┬───────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────┐
│  4. Audit Logging                              │
│     - Toutes actions utilisateur               │
│     - IP + User-Agent                          │
│     - Timestamp précis                         │
│     - Retention configurable                   │
└────────────────┬───────────────────────────────┘
                 │
┌────────────────▼───────────────────────────────┐
│  5. Secret Encryption                          │
│     - AES-256-GCM                              │
│     - Key derivation (scrypt)                  │
│     - Rotation automatique                     │
└────────────────────────────────────────────────┘
```

### Flux d'authentification OIDC

```mermaid
sequenceDiagram
    participant User
    participant Windflow-sample
    participant OIDC as OIDC Provider

    User->>Windflow-sample: Click "Login with OIDC"
    Windflow-sample->>OIDC: Redirect to /authorize
    OIDC->>User: Show login page
    User->>OIDC: Enter credentials
    OIDC->>Windflow-sample: Redirect with code
    Windflow-sample->>OIDC: POST /token (exchange code)
    OIDC-->>Windflow-sample: { access_token, id_token }
    Windflow-sample->>Windflow-sample: Validate JWT signature
    Windflow-sample->>Windflow-sample: Extract claims (email, name, groups)
    Windflow-sample->>Windflow-sample: Create/update user in DB
    Windflow-sample->>Windflow-sample: Create session
    Windflow-sample-->>User: Set session cookie + redirect
```

## 🔄 Processus en arrière-plan

### Architecture multi-process

```
┌──────────────────────────────────────────┐
│       Main Process                       │
│  - Web Server                            │
│  - API Routes                            │
│  - WebSocket handling                    │
└────────┬─────────────────────┬───────────┘
         │                     │
    ┌────▼─────┐        ┌─────▼──────┐
    │ Metrics  │        │  Events    │
    │Collector │        │ Collector  │
    └────┬─────┘        └─────┬──────┘
         │                     │
    ┌────▼─────┐        ┌─────▼──────┐
    │ metrics. │        │ events.    │
    │ json     │        │ jsonl      │
    └──────────┘        └────────────┘
         │                     │
         └──────────┬──────────┘
                    │
         ┌──────────▼──────────┐
         │   Database          │
         │   (persist data)    │
         └─────────────────────┘
```

### Python équivalent - Metrics Collector

```python
# metrics_collector.py
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List

class MetricsCollector:
    """Collecteur de métriques Docker"""
    
    def __init__(self, docker_client, data_dir: Path):
        self.docker = docker_client
        self.data_dir = data_dir
        self.metrics_file = data_dir / "metrics.json"
        
    async def collect_host_metrics(self) -> Dict:
        """Collecter métriques système"""
        import psutil
        
        return {
            "cpu_percent": psutil.cpu_percent(interval=1),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_used": psutil.virtual_memory().used,
            "memory_total": psutil.virtual_memory().total,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    async def collect_container_stats(self) -> List[Dict]:
        """Collecter stats de tous les conteneurs"""
        containers = await self.docker.list_containers(all=False)
        stats = []
        
        for container in containers:
            try:
                response = await self.docker.docker_fetch(
                    f"/containers/{container['Id']}/stats?stream=false"
                )
                stat_data = response.json()
                
                # Calculer CPU %
                cpu_delta = (stat_data['cpu_stats']['cpu_usage']['total_usage'] -
                            stat_data['precpu_stats']['cpu_usage']['total_usage'])
                system_delta = (stat_data['cpu_stats']['system_cpu_usage'] -
                               stat_data['precpu_stats']['system_cpu_usage'])
                cpu_percent = (cpu_delta / system_delta) * 100.0
                
                # Calculer Memory %
                mem_usage = stat_data['memory_stats']['usage']
                mem_limit = stat_data['memory_stats']['limit']
                mem_percent = (mem_usage / mem_limit) * 100.0
                
                stats.append({
                    "container_id": container['Id'],
                    "container_name": container['Names'][0].lstrip('/'),
                    "cpu_percent": cpu_percent,
                    "memory_percent": mem_percent,
                    "memory_usage": mem_usage,
                    "timestamp": datetime.utcnow().isoformat()
                })
            except Exception as e:
                print(f"Error collecting stats for {container['Id']}: {e}")
                
        return stats
        
    async def write_metrics(self, data: Dict):
        """Écrire métriques dans fichier JSON"""
        self.metrics_file.write_text(json.dumps(data, indent=2))
        
    async def run(self, interval: int = 10):
        """Boucle principale de collecte"""
        print(f"Starting metrics collector (interval: {interval}s)")
        
        while True:
            try:
                host_metrics = await self.collect_host_metrics()
                container_stats = await self.collect_container_stats()
                
                data = {
                    "host": host_metrics,
                    "containers": container_stats,
                    "collected_at": datetime.utcnow().isoformat()
                }
                
                await self.write_metrics(data)
                print(f"✓ Collected metrics at {data['collected_at']}")
                
            except Exception as e:
                print(f"✗ Error collecting metrics: {e}")
                
            await asyncio.sleep(interval)

# Runner
if __name__ == "__main__":
    from docker_client import DockerClient, DockerConfig
    
    config = DockerConfig(
        connection_type='socket',
        socket_path='/var/run/docker.sock'
    )
    
    async def main():
        async with DockerClient(config) as docker:
            collector = MetricsCollector(
                docker,
                Path("./data")
            )
            await collector.run(interval=10)
    
    asyncio.run(main())
```

## 🎯 Points clés de l'architecture

1. **Découplage** : Modules indépendants communiquant via interfaces claires
2. **Scalabilité** : Support multi-environnements sans limite
3. **Résilience** : Retry logic, circuit breakers, fallbacks
4. **Performance** : Cache intelligent, stream processing, async/await
5. **Sécurité** : Defence in depth, encryption at rest, audit trail
6. **Maintenabilité** : Code modulaire, tests unitaires, documentation

---

[← Retour](00-OVERVIEW.md) | [Suivant : Module Docker →](02-DOCKER-API-MODULE.md)
