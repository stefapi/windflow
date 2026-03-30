# Volume Browser - Navigation dans les Volumes

[← Navigateur de volumes](12-VOLUME-BROWSER.md) | [Suivant : Hawser Proxy →](17-HAWSER-PROXY.md)

## 📁 Vue d'ensemble

Le **Volume Browser** est un système complet permettant de naviguer, éditer et gérer les fichiers à l'intérieur des volumes Docker sans avoir à monter le volume ou accéder au système hôte.

## 🔧 Architecture

### Principe de Fonctionnement

```
┌──────────────────────────────────────────────────────────┐
│                    Volume Browser                        │
├──────────────────────────────────────────────────────────┤
│                                                          │
│  1. Créer conteneur helper temporaire                   │
│     ↓                                                    │
│  2. Monter le volume dans /data                         │
│     ↓                                                    │
│  3. Exécuter commandes (ls, cat, tar, etc.)             │
│     ↓                                                    │
│  4. Streamer résultats via Docker API                   │
│     ↓                                                    │
│  5. Cleanup automatique après inactivité                │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### Conteneur Helper

Le Volume Browser utilise une image Alpine Linux légère comme conteneur temporaire :

```python
# Configuration du conteneur helper
VOLUME_HELPER_IMAGE = "alpine:latest"
VOLUME_HELPER_IDLE_TIMEOUT = 5 * 60  # 5 minutes d'inactivité
VOLUME_HELPER_MAX_AGE = 30 * 60  # 30 minutes maximum

async def create_volume_helper_container(
    volume_name: str,
    env_id: Optional[int] = None
) -> str:
    """
    Créer un conteneur helper pour un volume
    
    Args:
        volume_name: Nom du volume Docker
        env_id: ID de l'environnement
    
    Returns:
        container_id: ID du conteneur créé
    """
    # S'assurer que l'image est disponible
    await ensure_volume_helper_image(env_id)
    
    # Configuration du conteneur
    config = {
        "Image": VOLUME_HELPER_IMAGE,
        "Cmd": ["/bin/sh", "-c", "sleep infinity"],
        "HostConfig": {
            "Binds": [f"{volume_name}:/data:rw"],
            "AutoRemove": False,  # Géré manuellement
            "NetworkMode": "none"  # Pas d'accès réseau nécessaire
        },
        "Labels": {
            "Colibri.type": "volume-helper",
            "Colibri.volume": volume_name,
            "Colibri.created": datetime.now().isoformat()
        }
    }
    
    # Créer et démarrer le conteneur
    container = await docker.create_container(config, env_id)
    await docker.start_container(container["Id"], env_id)
    
    return container["Id"]
```

## 📂 Opérations Fichiers

### 1. Lister Répertoire

```python
async def list_volume_directory(
    volume_name: str,
    path: str = "/",
    env_id: Optional[int] = None
) -> List[FileEntry]:
    """
    Lister le contenu d'un répertoire dans un volume
    
    Args:
        volume_name: Nom du volume
        path: Chemin relatif dans le volume
        env_id: ID de l'environnement
    
    Returns:
        Liste des fichiers et répertoires
    """
    # Obtenir ou créer conteneur helper
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    # Construire chemin complet
    full_path = f"/data{path}"
    
    # Exécuter ls -la avec format parsable
    cmd = [
        "ls", "-laGh", "--time-style=+%Y-%m-%dT%H:%M:%S",
        full_path
    ]
    
    result = await docker.exec_in_container(
        container_id=container_id,
        cmd=cmd,
        env_id=env_id
    )
    
    # Parser la sortie
    entries = parse_ls_output(result["output"])
    
    return entries


def parse_ls_output(output: str) -> List[FileEntry]:
    """Parser la sortie de ls -la"""
    entries = []
    lines = output.strip().split('\n')[1:]  # Skip total line
    
    for line in lines:
        parts = line.split(None, 7)
        if len(parts) < 8:
            continue
        
        permissions = parts[0]
        size = parts[3]
        date = parts[4]
        time = parts[5]
        name = parts[6]
        
        # Déterminer le type
        file_type = "file"
        if permissions.startswith('d'):
            file_type = "directory"
        elif permissions.startswith('l'):
            file_type = "symlink"
        
        entries.append({
            "name": name,
            "type": file_type,
            "size": size,
            "permissions": permissions,
            "modified": f"{date}T{time}",
            "path": name
        })
    
    return entries
```

### 2. Lire Fichier

```python
async def read_volume_file(
    volume_name: str,
    file_path: str,
    env_id: Optional[int] = None
) -> str:
    """
    Lire le contenu d'un fichier dans un volume
    
    Args:
        volume_name: Nom du volume
        file_path: Chemin du fichier
        env_id: ID de l'environnement
    
    Returns:
        Contenu du fichier en string
    """
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    full_path = f"/data{file_path}"
    
    # Vérifier que c'est bien un fichier
    stat_result = await docker.exec_in_container(
        container_id=container_id,
        cmd=["test", "-f", full_path],
        env_id=env_id
    )
    
    if stat_result["exit_code"] != 0:
        raise FileNotFoundError(f"Not a file: {file_path}")
    
    # Lire le fichier
    result = await docker.exec_in_container(
        container_id=container_id,
        cmd=["cat", full_path],
        env_id=env_id
    )
    
    return result["output"]
```

### 3. Écrire Fichier

```python
async def write_volume_file(
    volume_name: str,
    file_path: str,
    content: str,
    env_id: Optional[int] = None
) -> bool:
    """
    Écrire du contenu dans un fichier du volume
    
    Args:
        volume_name: Nom du volume
        file_path: Chemin du fichier
        content: Contenu à écrire
        env_id: ID de l'environnement
    
    Returns:
        True si succès
    """
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    full_path = f"/data{file_path}"
    
    # Créer les répertoires parents si nécessaire
    parent_dir = os.path.dirname(full_path)
    await docker.exec_in_container(
        container_id=container_id,
        cmd=["mkdir", "-p", parent_dir],
        env_id=env_id
    )
    
    # Écrire le fichier via echo et redirection
    # Escape le contenu pour bash
    escaped_content = content.replace("'", "'\\''")
    
    result = await docker.exec_in_container(
        container_id=container_id,
        cmd=["/bin/sh", "-c", f"echo -n '{escaped_content}' > {full_path}"],
        env_id=env_id
    )
    
    return result["exit_code"] == 0
```

### 4. Télécharger Archive

```python
async def get_volume_archive(
    volume_name: str,
    path: str,
    env_id: Optional[int] = None
) -> Response:
    """
    Télécharger un fichier ou répertoire en tar.gz
    
    Args:
        volume_name: Nom du volume
        path: Chemin à archiver
        env_id: ID de l'environnement
    
    Returns:
        Response avec stream tar.gz
    """
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    full_path = f"/data{path}"
    
    # Utiliser docker cp API pour récupérer l'archive
    # Docker API retourne un tar stream
    response = await docker.get_container_archive(
        container_id=container_id,
        path=full_path,
        env_id=env_id
    )
    
    return response
```

### 5. Upload Archive

```python
async def put_volume_archive(
    volume_name: str,
    path: str,
    archive: bytes,
    env_id: Optional[int] = None
) -> bool:
    """
    Uploader et extraire une archive tar dans le volume
    
    Args:
        volume_name: Nom du volume
        path: Répertoire cible
        archive: Données tar/tar.gz
        env_id: ID de l'environnement
    
    Returns:
        True si succès
    """
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    full_path = f"/data{path}"
    
    # Utiliser docker cp API pour uploader
    await docker.put_container_archive(
        container_id=container_id,
        path=full_path,
        data=archive,
        env_id=env_id
    )
    
    return True
```

### 6. Supprimer Fichier/Répertoire

```python
async def delete_volume_path(
    volume_name: str,
    path: str,
    recursive: bool = False,
    env_id: Optional[int] = None
) -> bool:
    """
    Supprimer un fichier ou répertoire du volume
    
    Args:
        volume_name: Nom du volume
        path: Chemin à supprimer
        recursive: Supprimer récursivement (rm -r)
        env_id: ID de l'environnement
    
    Returns:
        True si succès
    """
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    full_path = f"/data{path}"
    
    # Construire commande rm
    cmd = ["rm"]
    if recursive:
        cmd.append("-rf")
    else:
        cmd.append("-f")
    cmd.append(full_path)
    
    result = await docker.exec_in_container(
        container_id=container_id,
        cmd=cmd,
        env_id=env_id
    )
    
    return result["exit_code"] == 0
```

## 🔄 Gestion du Cache

### Cache de Conteneurs

```python
# Cache global des conteneurs helpers
volume_helper_cache: Dict[str, VolumeHelperInfo] = {}

@dataclass
class VolumeHelperInfo:
    container_id: str
    volume_name: str
    environment_id: Optional[int]
    created_at: datetime
    last_used: datetime

async def get_or_create_volume_helper_container(
    volume_name: str,
    env_id: Optional[int] = None
) -> str:
    """
    Obtenir un conteneur helper depuis le cache ou en créer un
    
    Returns:
        container_id
    """
    cache_key = f"{env_id or 'local'}:{volume_name}"
    
    # Vérifier le cache
    if cache_key in volume_helper_cache:
        info = volume_helper_cache[cache_key]
        
        # Vérifier que le conteneur existe toujours
        try:
            await docker.inspect_container(info.container_id, env_id)
            
            # Mettre à jour last_used
            info.last_used = datetime.now()
            
            return info.container_id
        except:
            # Conteneur n'existe plus, supprimer du cache
            del volume_helper_cache[cache_key]
    
    # Créer nouveau conteneur
    container_id = await create_volume_helper_container(volume_name, env_id)
    
    # Ajouter au cache
    volume_helper_cache[cache_key] = VolumeHelperInfo(
        container_id=container_id,
        volume_name=volume_name,
        environment_id=env_id,
        created_at=datetime.now(),
        last_used=datetime.now()
    )
    
    return container_id
```

### Cleanup Automatique

```python
async def cleanup_expired_volume_helpers():
    """
    Nettoyer les conteneurs helpers expirés
    
    Appelé périodiquement (toutes les 30 minutes)
    """
    now = datetime.now()
    to_remove = []
    
    for cache_key, info in volume_helper_cache.items():
        # Calculer durée depuis dernière utilisation
        idle_duration = (now - info.last_used).total_seconds()
        total_age = (now - info.created_at).total_seconds()
        
        should_remove = (
            idle_duration > VOLUME_HELPER_IDLE_TIMEOUT or
            total_age > VOLUME_HELPER_MAX_AGE
        )
        
        if should_remove:
            try:
                # Arrêter et supprimer le conteneur
                await docker.stop_container(info.container_id, info.environment_id)
                await docker.remove_container(
                    info.container_id,
                    force=True,
                    env_id=info.environment_id
                )
                
                to_remove.append(cache_key)
                
                print(f"[VolumeHelper] Cleaned up {cache_key} "
                      f"(idle: {idle_duration}s, age: {total_age}s)")
            except Exception as e:
                print(f"[VolumeHelper] Error cleaning up {cache_key}: {e}")
    
    # Supprimer du cache
    for key in to_remove:
        del volume_helper_cache[key]
    
    print(f"[VolumeHelper] Cleanup complete: removed {len(to_remove)} helpers")
```

### Cleanup au Démarrage

```python
async def cleanup_stale_volume_helpers(environments: List[Environment]):
    """
    Nettoyer les conteneurs helpers orphelins au démarrage
    
    Args:
        environments: Liste de tous les environnements
    """
    cleaned_count = 0
    
    for env in environments:
        try:
            # Lister tous les conteneurs avec label Colibri.type=volume-helper
            containers = await docker.list_containers(
                all=True,
                filters={"label": ["Colibri.type=volume-helper"]},
                env_id=env.id
            )
            
            for container in containers:
                try:
                    # Arrêter et supprimer
                    await docker.stop_container(container["Id"], env.id)
                    await docker.remove_container(container["Id"], force=True, env_id=env.id)
                    cleaned_count += 1
                except Exception as e:
                    print(f"[VolumeHelper] Error removing {container['Id']}: {e}")
        
        except Exception as e:
            print(f"[VolumeHelper] Error cleaning env {env.name}: {e}")
    
    print(f"[VolumeHelper] Startup cleanup: removed {cleaned_count} stale helpers")
```

## 🔒 Sécurité

### Validation des Chemins

```python
def validate_path(path: str) -> bool:
    """
    Valider qu'un chemin est sûr (pas de path traversal)
    
    Args:
        path: Chemin à valider
    
    Returns:
        True si valide
    
    Raises:
        ValueError si chemin dangereux
    """
    # Normaliser le chemin
    normalized = os.path.normpath(path)
    
    # Vérifier path traversal
    if normalized.startswith(".."):
        raise ValueError("Path traversal detected")
    
    # Vérifier caractères dangereux
    dangerous_chars = [';', '|', '&', '$', '`', '\n', '\r']
    if any(char in path for char in dangerous_chars):
        raise ValueError("Dangerous characters in path")
    
    return True
```

### Permissions

```python
async def change_permissions(
    volume_name: str,
    path: str,
    mode: str,
    recursive: bool = False,
    env_id: Optional[int] = None
) -> bool:
    """
    Changer les permissions d'un fichier/répertoire
    
    Args:
        volume_name: Nom du volume
        path: Chemin du fichier
        mode: Mode octal (ex: "755", "644")
        recursive: Appliquer récursivement
        env_id: ID de l'environnement
    
    Returns:
        True si succès
    """
    # Valider le mode
    if not re.match(r'^[0-7]{3,4}$', mode):
        raise ValueError("Invalid permission mode")
    
    container_id = await get_or_create_volume_helper_container(
        volume_name, env_id
    )
    
    full_path = f"/data{path}"
    
    cmd = ["chmod"]
    if recursive:
        cmd.append("-R")
    cmd.extend([mode, full_path])
    
    result = await docker.exec_in_container(
        container_id=container_id,
        cmd=cmd,
        env_id=env_id
    )
    
    return result["exit_code"] == 0
```

## 📊 API Routes

```python
from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/volumes", tags=["volumes"])

@router.get("/{volume_name}/browse")
async def browse_volume(
    volume_name: str,
    path: str = "/",
    env_id: Optional[int] = None
):
    """Lister le contenu d'un répertoire dans un volume"""
    try:
        validate_path(path)
        entries = await list_volume_directory(volume_name, path, env_id)
        return {"entries": entries}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{volume_name}/file")
async def read_file(
    volume_name: str,
    path: str,
    env_id: Optional[int] = None
):
    """Lire le contenu d'un fichier"""
    try:
        validate_path(path)
        content = await read_volume_file(volume_name, path, env_id)
        return {"content": content}
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{volume_name}/file")
async def write_file(
    volume_name: str,
    path: str,
    content: str,
    env_id: Optional[int] = None
):
    """Écrire du contenu dans un fichier"""
    try:
        validate_path(path)
        success = await write_volume_file(volume_name, path, content, env_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{volume_name}/download")
async def download_archive(
    volume_name: str,
    path: str,
    env_id: Optional[int] = None
):
    """Télécharger un fichier/répertoire en tar"""
    try:
        validate_path(path)
        response = await get_volume_archive(volume_name, path, env_id)
        
        return StreamingResponse(
            response.body,
            media_type="application/x-tar",
            headers={
                "Content-Disposition": f"attachment; filename={os.path.basename(path)}.tar"
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{volume_name}/upload")
async def upload_archive(
    volume_name: str,
    path: str,
    file: UploadFile,
    env_id: Optional[int] = None
):
    """Uploader et extraire une archive"""
    try:
        validate_path(path)
        archive_data = await file.read()
        success = await put_volume_archive(volume_name, path, archive_data, env_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{volume_name}/path")
async def delete_path(
    volume_name: str,
    path: str,
    recursive: bool = False,
    env_id: Optional[int] = None
):
    """Supprimer un fichier ou répertoire"""
    try:
        validate_path(path)
        success = await delete_volume_path(volume_name, path, recursive, env_id)
        return {"success": success}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## 🎨 Frontend Vue 3

```vue
<!-- components/VolumeBrowser.vue -->
<template>
  <div class="volume-browser">
    <!-- Breadcrumb navigation -->
    <div class="breadcrumb">
      <span 
        v-for="(part, index) in pathParts" 
        :key="index"
        @click="navigateToIndex(index)"
        class="breadcrumb-item"
      >
        {{ part || 'Root' }}
      </span>
    </div>

    <!-- File list -->
    <div class="file-list">
      <div 
        v-for="entry in entries" 
        :key="entry.name"
        @click="handleClick(entry)"
        @dblclick="handleDoubleClick(entry)"
        :class="['file-entry', entry.type, { selected: isSelected(entry) }]"
      >
        <Icon :name="getIcon(entry)" />
        <span class="name">{{ entry.name }}</span>
        <span class="size">{{ entry.size }}</span>
        <span class="modified">{{ formatDate(entry.modified) }}</span>
      </div>
    </div>

    <!-- File editor modal -->
    <Modal v-if="editingFile" @close="editingFile = null">
      <FileEditor
        :volume="volumeName"
        :path="editingFile.path"
        :env-id="envId"
        @saved="handleFileSaved"
      />
    </Modal>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';

const props = defineProps<{
  volumeName: string;
  envId?: number;
}>();

const currentPath = ref('/');
const entries = ref<FileEntry[]>([]);
const selectedEntries = ref<Set<string>>(new Set());
const editingFile = ref<FileEntry | null>(null);

const pathParts = computed(() => 
  currentPath.value.split('/').filter(Boolean)
);

async function loadDirectory(path: string) {
  const response = await fetch(
    `/api/volumes/${props.volumeName}/browse?path=${encodeURIComponent(path)}&env_id=${props.envId || ''}`
  );
  const data = await response.json();
  entries.value = data.entries;
  currentPath.value = path;
}

function handleClick(entry: FileEntry) {
  if (entry.type === 'directory') {
    loadDirectory(`${currentPath.value}/${entry.name}`.replace('//', '/'));
  }
}

function handleDoubleClick(entry: FileEntry) {
  if (entry.type === 'file') {
    editingFile.value = entry;
  }
}

function navigateToIndex(index: number) {
  const parts = pathParts.value.slice(0, index + 1);
  loadDirectory('/' + parts.join('/'));
}

onMounted(() => {
  loadDirectory(currentPath.value);
});
</script>
```

---

[← Navigateur de volumes](12-VOLUME-BROWSER.md) | [Suivant : Hawser Proxy →](17-HAWSER-PROXY.md)
