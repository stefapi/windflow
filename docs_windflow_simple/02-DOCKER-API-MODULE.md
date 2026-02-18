# Module API Docker - Cœur du projet

[← Architecture](01-ARCHITECTURE.md) | [Suivant : Base de données →](03-DATABASE-SCHEMA.md)

## 🎯 Vue d'ensemble

Le module `docker.ts` (2800+ lignes) est le **cœur technique** de Windflow-sample. Il implémente l'intégralité de l'API Docker v1.41+ **sans dépendance externe** (pas de dockerode), en communiquant directement avec le daemon Docker via :
- Unix socket (`/var/run/docker.sock`)
- HTTP/HTTPS avec TLS (mTLS)
- WebSocket (Hawser Edge mode)

## 🏗️ Architecture du module

### Structure principale

```typescript
// src/lib/server/docker.ts

// 1. Configuration et connexion
export interface DockerClientConfig {
  type: 'socket' | 'http' | 'https';
  socketPath?: string;
  host?: string;
  port?: number;
  ca?: string;
  cert?: string;
  key?: string;
  connectionType?: 'socket' | 'direct' | 'hawser-standard' | 'hawser-edge';
  environmentId?: number;
}

// 2. Fonction centrale de requête
export async function dockerFetch(
  path: string,
  options: RequestInit = {},
  envId?: number | null
): Promise<Response>

// 3. Opérations conteneurs (20+ fonctions)
export async function listContainers(all: boolean, envId?: number): Promise<ContainerInfo[]>
export async function startContainer(id: string, envId?: number): Promise<void>
export async function stopContainer(id: string, envId?: number): Promise<void>
// ... etc

// 4. Opérations images (15+ fonctions)
export async function listImages(envId?: number): Promise<ImageInfo[]>
export async function pullImage(name: string, onProgress, envId?: number): Promise<void>
// ... etc

// 5. Opérations volumes (10+ fonctions)
export async function listVolumes(envId?: number): Promise<VolumeInfo[]>
// ... etc

// 6. Opérations réseaux (8+ fonctions)
export async function listNetworks(envId?: number): Promise<NetworkInfo[]>
// ... etc
```

## 🔑 Composants clés

### 1. dockerFetch() - Fonction centrale

C'est la fonction qui route toutes les requêtes vers le bon mode de connexion.

```python
# Équivalent Python avec routing multi-mode
from typing import Optional, Dict, Any
from enum import Enum
import httpx
import socket

class ConnectionType(Enum):
    SOCKET = "socket"
    HTTP = "http"
    HTTPS = "https"
    HAWSER_EDGE = "hawser-edge"

class DockerFetcher:
    """Gestionnaire de requêtes Docker multi-modes"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.conn_type = ConnectionType(config.get("connection_type", "socket"))
        
    async def docker_fetch(
        self,
        path: str,
        method: str = "GET",
        body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        streaming: bool = False
    ) -> httpx.Response:
        """
        Requête vers Docker API avec routing automatique
        
        Args:
            path: Chemin API (ex: /containers/json)
            method: Méthode HTTP
            body: Corps de requête (optionnel)
            headers: Headers additionnels
            streaming: True pour connexions longues (events, logs)
            
        Returns:
            Response HTTP
        """
        
        # Router vers la bonne méthode selon le type de connexion
        if self.conn_type == ConnectionType.SOCKET:
            return await self._fetch_unix_socket(path, method, body, headers)
        elif self.conn_type == ConnectionType.HAWSER_EDGE:
            return await self._fetch_hawser_edge(path, method, body, headers)
        else:  # HTTP/HTTPS
            return await self._fetch_http(path, method, body, headers, streaming)
    
    async def _fetch_unix_socket(
        self,
        path: str,
        method: str,
        body: Optional[bytes],
        headers: Optional[Dict[str, str]]
    ) -> httpx.Response:
        """Requête via Unix socket"""
        url = f"http://localhost{path}"
        
        transport = httpx.AsyncHTTPTransport(
            uds=self.config["socket_path"]
        )
        
        async with httpx.AsyncClient(transport=transport) as client:
            response = await client.request(
                method,
                url,
                content=body,
                headers=headers or {},
                timeout=30.0
            )
            return response
    
    async def _fetch_http(
        self,
        path: str,
        method: str,
        body: Optional[bytes],
        headers: Optional[Dict[str, str]],
        streaming: bool
    ) -> httpx.Response:
        """Requête via HTTP/HTTPS avec TLS optionnel"""
        protocol = self.config["type"]
        host = self.config["host"]
        port = self.config["port"]
        url = f"{protocol}://{host}:{port}{path}"
        
        # Configuration TLS
        verify = self.config.get("ca_cert", True)
        cert = None
        if self.config.get("client_cert") and self.config.get("client_key"):
            cert = (self.config["client_cert"], self.config["client_key"])
        
        timeout = None if streaming else 30.0
        
        async with httpx.AsyncClient(verify=verify, cert=cert) as client:
            response = await client.request(
                method,
                url,
                content=body,
                headers=headers or {},
                timeout=timeout
            )
            return response
    
    async def _fetch_hawser_edge(
        self,
        path: str,
        method: str,
        body: Optional[bytes],
        headers: Optional[Dict[str, str]]
    ) -> httpx.Response:
        """Requête via Hawser Edge (WebSocket)"""
        # Implémentation WebSocket (voir doc Hawser)
        raise NotImplementedError("Voir 08-HAWSER-PROXY.md")
```

### 2. Gestion des conteneurs

#### Lister les conteneurs

```python
from typing import List, Dict, Optional
from dataclasses import dataclass

@dataclass
class ContainerInfo:
    """Information conteneur"""
    id: str
    name: str
    image: str
    state: str  # running, exited, paused, etc.
    status: str  # Up 2 hours, Exited (0) 3 minutes ago
    created: int  # Unix timestamp
    ports: List[Dict[str, Any]]
    networks: Dict[str, Dict[str, str]]
    health: Optional[str] = None  # healthy, unhealthy, starting
    restart_count: int = 0
    
class DockerContainers:
    """Gestionnaire d'opérations conteneurs"""
    
    def __init__(self, fetcher: DockerFetcher):
        self.fetcher = fetcher
        
    async def list_containers(
        self,
        all: bool = True,
        filters: Optional[Dict[str, List[str]]] = None
    ) -> List[ContainerInfo]:
        """
        Lister les conteneurs
        
        Args:
            all: True = tous, False = running seulement
            filters: Filtres Docker (ex: {"status": ["running"]})
            
        Returns:
            Liste de ContainerInfo
        """
        path = f"/containers/json?all={str(all).lower()}"
        
        if filters:
            import json
            path += f"&filters={json.dumps(filters)}"
        
        response = await self.fetcher.docker_fetch(path)
        containers_raw = response.json()
        
        # Parser et enrichir les données
        containers = []
        for c in containers_raw:
            # Extraire networks avec IPs
            networks = {}
            if c.get("NetworkSettings", {}).get("Networks"):
                for net_name, net_data in c["NetworkSettings"]["Networks"].items():
                    networks[net_name] = {
                        "ipAddress": net_data.get("IPAddress", "")
                    }
            
            # Extraire health status
            health = None
            status_str = c.get("Status", "")
            if "(healthy)" in status_str:
                health = "healthy"
            elif "(unhealthy)" in status_str:
                health = "unhealthy"
            elif "(health: starting)" in status_str:
                health = "starting"
            
            container = ContainerInfo(
                id=c["Id"],
                name=c["Names"][0].lstrip("/") if c.get("Names") else "unnamed",
                image=c["Image"],
                state=c["State"],
                status=c.get("Status", ""),
                created=c["Created"],
                ports=c.get("Ports", []),
                networks=networks,
                health=health,
                restart_count=0  # Nécessite inspect pour ce champ
            )
            containers.append(container)
        
        return containers

# Usage
async def example_list():
    config = {"connection_type": "socket", "socket_path": "/var/run/docker.sock"}
    fetcher = DockerFetcher(config)
    containers_mgr = DockerContainers(fetcher)
    
    # Lister tous les conteneurs
    all_containers = await containers_mgr.list_containers(all=True)
    print(f"Total containers: {len(all_containers)}")
    
    # Lister seulement running
    running = await containers_mgr.list_containers(
        all=False,
        filters={"status": ["running"]}
    )
    print(f"Running containers: {len(running)}")
    
    for c in running:
        print(f"  - {c.name} ({c.image}): {c.status}")
```

#### Créer et démarrer un conteneur

```python
from typing import Dict, List, Optional

@dataclass
class CreateContainerOptions:
    """Options de création de conteneur"""
    name: str
    image: str
    cmd: Optional[List[str]] = None
    env: Optional[List[str]] = None
    ports: Optional[Dict[str, Dict[str, str]]] = None
    volumes: Optional[Dict[str, Dict]] = None
    volume_binds: Optional[List[str]] = None
    network_mode: Optional[str] = "bridge"
    restart_policy: str = "no"
    labels: Optional[Dict[str, str]] = None
    
class DockerContainers:
    # ... (suite de la classe précédente)
    
    async def create_container(
        self,
        options: CreateContainerOptions
    ) -> str:
        """
        Créer un conteneur
        
        Returns:
            Container ID
        """
        # Construire la configuration Docker
        config = {
            "Image": options.image,
            "Env": options.env or [],
            "Labels": options.labels or {},
            "HostConfig": {
                "RestartPolicy": {
                    "Name": options.restart_policy
                }
            }
        }
        
        # Ajouter commande si spécifiée
        if options.cmd:
            config["Cmd"] = options.cmd
        
        # Ajouter ports
        if options.ports:
            config["ExposedPorts"] = {}
            config["HostConfig"]["PortBindings"] = {}
            
            for container_port, host_config in options.ports.items():
                config["ExposedPorts"][container_port] = {}
                config["HostConfig"]["PortBindings"][container_port] = [host_config]
        
        # Ajouter volumes
        if options.volume_binds:
            config["HostConfig"]["Binds"] = options.volume_binds
        
        if options.volumes:
            config["Volumes"] = options.volumes
        
        # Ajouter network
        if options.network_mode:
            config["HostConfig"]["NetworkMode"] = options.network_mode
        
        # Créer le conteneur
        import json
        response = await self.fetcher.docker_fetch(
            f"/containers/create?name={options.name}",
            method="POST",
            body=json.dumps(config).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        result = response.json()
        return result["Id"]
    
    async def start_container(self, container_id: str):
        """Démarrer un conteneur"""
        await self.fetcher.docker_fetch(
            f"/containers/{container_id}/start",
            method="POST"
        )
    
    async def stop_container(self, container_id: str, timeout: int = 10):
        """Arrêter un conteneur"""
        await self.fetcher.docker_fetch(
            f"/containers/{container_id}/stop?t={timeout}",
            method="POST"
        )
    
    async def remove_container(self, container_id: str, force: bool = False):
        """Supprimer un conteneur"""
        await self.fetcher.docker_fetch(
            f"/containers/{container_id}?force={str(force).lower()}",
            method="DELETE"
        )

# Usage complet
async def example_create_nginx():
    config = {"connection_type": "socket", "socket_path": "/var/run/docker.sock"}
    fetcher = DockerFetcher(config)
    containers = DockerContainers(fetcher)
    
    # Créer un conteneur nginx
    options = CreateContainerOptions(
        name="my-nginx",
        image="nginx:latest",
        ports={
            "80/tcp": {"HostPort": "8080"}
        },
        env=["NGINX_HOST=example.com"],
        restart_policy="unless-stopped",
        labels={"app": "web", "env": "prod"}
    )
    
    container_id = await containers.create_container(options)
    print(f"Created container: {container_id}")
    
    # Démarrer
    await containers.start_container(container_id)
    print("Container started")
    
    # Attendre 5 secondes
    import asyncio
    await asyncio.sleep(5)
    
    # Arrêter et supprimer
    await containers.stop_container(container_id)
    await containers.remove_container(container_id)
    print("Container stopped and removed")
```

### 3. Gestion des images

#### Pull avec progression

```python
import json
from typing import Callable, Optional

class DockerImages:
    """Gestionnaire d'opérations images"""
    
    def __init__(self, fetcher: DockerFetcher):
        self.fetcher = fetcher
    
    async def pull_image(
        self,
        image: str,
        tag: str = "latest",
        on_progress: Optional[Callable[[Dict], None]] = None
    ):
        """
        Pull une image avec progression en temps réel
        
        Args:
            image: Nom de l'image (ex: nginx, mysql, myregistry.com/myapp)
            tag: Tag de l'image
            on_progress: Callback appelé pour chaque événement de progression
        """
        # Parser image pour extraction registry potentiel
        if ":" in image and "/" in image.split(":")[-1]:
            # Format: registry:port/image:tag
            from_image = image
        else:
            from_image = image
        
        path = f"/images/create?fromImage={from_image}&tag={tag}"
        
        # Requête avec streaming
        response = await self.fetcher.docker_fetch(
            path,
            method="POST",
            streaming=True
        )
        
        # Parser le stream ligne par ligne
        async for line in response.aiter_lines():
            if line:
                try:
                    event = json.loads(line)
                    if on_progress:
                        on_progress(event)
                    
                    # Vérifier erreurs
                    if "error" in event:
                        raise Exception(f"Pull failed: {event['error']}")
                        
                except json.JSONDecodeError:
                    continue
    
    async def list_images(self) -> List[Dict]:
        """Lister toutes les images"""
        response = await self.fetcher.docker_fetch("/images/json")
        return response.json()
    
    async def remove_image(self, image_id: str, force: bool = False):
        """Supprimer une image"""
        await self.fetcher.docker_fetch(
            f"/images/{image_id}?force={str(force).lower()}",
            method="DELETE"
        )
    
    async def inspect_image(self, image_id: str) -> Dict:
        """Inspecter une image"""
        response = await self.fetcher.docker_fetch(f"/images/{image_id}/json")
        return response.json()

# Usage avec barre de progression
async def example_pull_with_progress():
    from rich.progress import Progress, BarColumn, TextColumn
    
    config = {"connection_type": "socket", "socket_path": "/var/run/docker.sock"}
    fetcher = DockerFetcher(config)
    images = DockerImages(fetcher)
    
    # Créer barre de progression (rich)
    with Progress(
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%")
    ) as progress:
        task = progress.add_task("Pulling nginx:latest", total=100)
        
        def on_progress(event):
            if "status" in event:
                status = event["status"]
                layer_id = event.get("id", "")
                
                # Afficher progression
                if status == "Downloading":
                    current = event.get("progressDetail", {}).get("current", 0)
                    total = event.get("progressDetail", {}).get("total", 1)
                    percent = (current / total) * 100 if total > 0 else 0
                    progress.update(task, completed=percent)
                elif status == "Download complete":
                    progress.update(task, completed=100)
                
                # Log
                progress_str = event.get("progress", "")
                progress.console.print(f"{status} {layer_id} {progress_str}")
        
        await images.pull_image("nginx", "latest", on_progress=on_progress)
    
    print("✓ Pull completed")
```

### 4. Exec dans un conteneur

```python
class DockerExec:
    """Gestionnaire d'exec dans conteneurs"""
    
    def __init__(self, fetcher: DockerFetcher):
        self.fetcher = fetcher
    
    async def exec_command(
        self,
        container_id: str,
        cmd: List[str],
        user: str = "root",
        working_dir: Optional[str] = None
    ) -> str:
        """
        Exécuter une commande dans un conteneur
        
        Args:
            container_id: ID du conteneur
            cmd: Commande à exécuter (liste)
            user: Utilisateur (défaut: root)
            working_dir: Répertoire de travail
            
        Returns:
            Sortie de la commande (stdout)
        """
        # 1. Créer l'exec
        exec_config = {
            "Cmd": cmd,
            "AttachStdout": True,
            "AttachStderr": True,
            "Tty": False,
            "User": user
        }
        
        if working_dir:
            exec_config["WorkingDir"] = working_dir
        
        response = await self.fetcher.docker_fetch(
            f"/containers/{container_id}/exec",
            method="POST",
            body=json.dumps(exec_config).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        exec_id = response.json()["Id"]
        
        # 2. Démarrer l'exec
        start_config = {
            "Detach": False,
            "Tty": False
        }
        
        response = await self.fetcher.docker_fetch(
            f"/exec/{exec_id}/start",
            method="POST",
            body=json.dumps(start_config).encode(),
            headers={"Content-Type": "application/json"}
        )
        
        # 3. Lire la sortie (démultiplexage Docker stream)
        output = await response.aread()
        stdout = self._demux_docker_stream(output)
        
        # 4. Vérifier le code de sortie
        inspect_response = await self.fetcher.docker_fetch(f"/exec/{exec_id}/json")
        exec_info = inspect_response.json()
        
        if exec_info["ExitCode"] != 0:
            raise Exception(f"Command failed with exit code {exec_info['ExitCode']}: {stdout}")
        
        return stdout
    
    def _demux_docker_stream(self, buffer: bytes) -> str:
        """
        Démultiplexer un stream Docker
        
        Docker envoie les données avec un header de 8 bytes:
        - 1 byte: type (0=stdin, 1=stdout, 2=stderr)
        - 3 bytes: padding
        - 4 bytes: taille du frame (big endian)
        - N bytes: payload
        """
        stdout_chunks = []
        offset = 0
        
        while offset < len(buffer):
            if offset + 8 > len(buffer):
                break
            
            stream_type = buffer[offset]
            frame_size = int.from_bytes(buffer[offset+4:offset+8], 'big')
            
            if frame_size == 0 or frame_size > len(buffer) - offset - 8:
                # Invalid frame, retour brut
                return buffer.decode('utf-8', errors='replace')
            
            payload = buffer[offset+8:offset+8+frame_size]
            
            if stream_type == 1:  # stdout
                stdout_chunks.append(payload)
            
            offset += 8 + frame_size
        
        return b''.join(stdout_chunks).decode('utf-8')

# Usage
async def example_exec():
    config = {"connection_type": "socket", "socket_path": "/var/run/docker.sock"}
    fetcher = DockerFetcher(config)
    exec_mgr = DockerExec(fetcher)
    
    # Lister fichiers dans /etc
    output = await exec_mgr.exec_command(
        "my-container",
        ["ls", "-la", "/etc"]
    )
    print("Files in /etc:")
    print(output)
    
    # Installer package
    output = await exec_mgr.exec_command(
        "my-container",
        ["apt-get", "update", "&&", "apt-get", "install", "-y", "curl"]
    )
    print("Package installed")
```

## 🎨 Frontend Vue 3 - Composants

### Composant liste de conteneurs

```vue
<!-- ContainerList.vue -->
<template>
  <div class="container-list">
    <div class="header">
      <h2>Conteneurs</h2>
      <div class="actions">
        <button @click="refreshContainers" :disabled="loading">
          <RefreshIcon />
          Rafraîchir
        </button>
        <button @click="showCreateModal = true" class="primary">
          <PlusIcon />
          Créer
        </button>
      </div>
    </div>

    <!-- Filtres -->
    <div class="filters">
      <input
        v-model="searchQuery"
        type="text"
        placeholder="Rechercher..."
        class="search-input"
      />
      <select v-model="statusFilter">
        <option value="">Tous les états</option>
        <option value="running">Running</option>
        <option value="exited">Exited</option>
        <option value="paused">Paused</option>
      </select>
    </div>

    <!-- Liste -->
    <div v-if="loading" class="loading">
      Chargement...
    </div>

    <div v-else-if="error" class="error">
      {{ error }}
    </div>

    <table v-else class="containers-table">
      <thead>
        <tr>
          <th>Nom</th>
          <th>Image</th>
          <th>État</th>
          <th>Ports</th>
          <th>Actions</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="container in filteredContainers"
          :key="container.id"
          :class="{ running: container.state === 'running' }"
        >
          <td>
            <router-link :to="`/containers/${container.id}`">
              {{ container.name }}
            </router-link>
          </td>
          <td>{{ container.image }}</td>
          <td>
            <span :class="`status status-${container.state}`">
              {{ container.state }}
            </span>
          </td>
          <td>
            <div v-if="container.ports.length > 0" class="ports">
              <span v-for="port in container.ports" :key="port.PublicPort">
                {{ port.PublicPort }}:{{ port.PrivatePort }}
              </span>
            </div>
            <span v-else class="text-muted">-</span>
          </td>
          <td>
            <div class="actions-cell">
              <button
                v-if="container.state === 'running'"
                @click="stopContainer(container.id)"
                title="Arrêter"
              >
                <StopIcon />
              </button>
              <button
                v-else
                @click="startContainer(container.id)"
                title="Démarrer"
              >
                <PlayIcon />
              </button>
              <button @click="openLogs(container.id)" title="Logs">
                <LogsIcon />
              </button>
              <button
                @click="deleteContainer(container.id)"
                class="danger"
                title="Supprimer"
              >
                <TrashIcon />
              </button>
            </div>
          </td>
        </tr>
      </tbody>
    </table>

    <!-- Modal création -->
    <CreateContainerModal
      v-if="showCreateModal"
      @close="showCreateModal = false"
      @created="onContainerCreated"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { useDockerStore } from '@/stores/docker';
import { useNotification } from '@/composables/useNotification';
import RefreshIcon from '@/components/icons/RefreshIcon.vue';
import PlusIcon from '@/components/icons/PlusIcon.vue';
import PlayIcon from '@/components/icons/PlayIcon.vue';
import StopIcon from '@/components/icons/StopIcon.vue';
import LogsIcon from '@/components/icons/LogsIcon.vue';
import TrashIcon from '@/components/icons/TrashIcon.vue';
import CreateContainerModal from './CreateContainerModal.vue';

interface Container {
  id: string;
  name: string;
  image: string;
  state: string;
  status: string;
  ports: Array<{
    PrivatePort: number;
    PublicPort?: number;
    Type: string;
  }>;
}

const dockerStore = useDockerStore();
const { showSuccess, showError } = useNotification();

const containers = ref<Container[]>([]);
const loading = ref(false);
const error = ref<string | null>(null);
const searchQuery = ref('');
const statusFilter = ref('');
const showCreateModal = ref(false);

// Conteneurs filtrés
const filteredContainers = computed(() => {
  let result = containers.value;

  // Filtre par recherche
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase();
    result = result.filter(
      (c) =>
        c.name.toLowerCase().includes(query) ||
        c.image.toLowerCase().includes(query)
    );
  }

  // Filtre par statut
  if (statusFilter.value) {
    result = result.filter((c) => c.state === statusFilter.value);
  }

  return result;
});

// Charger les conteneurs
async function refreshContainers() {
  loading.value = true;
  error.value = null;

  try {
    const response = await fetch('/api/containers?all=true');
    if (!response.ok) throw new Error('Erreur lors du chargement');

    containers.value = await response.json();
  } catch (e: any) {
    error.value = e.message;
    showError('Erreur', e.message);
  } finally {
    loading.value = false;
  }
}

// Démarrer un conteneur
async function startContainer(id: string) {
  try {
    await fetch(`/api/containers/${id}/start`, { method: 'POST' });
    showSuccess('Conteneur démarré');
    await refreshContainers();
  } catch (e: any) {
    showError('Erreur', e.message);
  }
}

// Arrêter un conteneur
async function stopContainer(id: string) {
  try {
    await fetch(`/api/containers/${id}/stop`, { method: 'POST' });
    showSuccess('Conteneur arrêté');
    await refreshContainers();
  } catch (e: any) {
    showError('Erreur', e.message);
  }
}

// Supprimer un conteneur
async function deleteContainer(id: string) {
  if (!confirm('Êtes-vous sûr de vouloir supprimer ce conteneur ?')) return;

  try {
    await fetch(`/api/containers/${id}?force=true`, { method: 'DELETE' });
    showSuccess('Conteneur supprimé');
    await refreshContainers();
  } catch (e: any) {
    showError('Erreur', e.message);
  }
}

// Ouvrir logs
function openLogs(id: string) {
  window.open(`/containers/${id}/logs`, '_blank');
}

// Callback création
function onContainerCreated() {
  showCreateModal.value = false;
  refreshContainers();
}

// Chargement initial
onMounted(() => {
  refreshContainers();
});
</script>

<style scoped>
.container-list {
  padding: 20px;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;
}

.actions {
  display: flex;
  gap: 10px;
}

.filters {
  display: flex;
  gap: 15
