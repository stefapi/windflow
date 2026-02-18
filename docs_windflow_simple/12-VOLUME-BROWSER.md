# Volume Browser - Navigation des volumes

[← Terminal WebSocket](11-TERMINAL-WEBSOCKET.md) | [Suivant : Background Processes →](13-BACKGROUND-PROCESSES.md)

## 📁 Vue d'ensemble

Système de navigation et d'édition de fichiers dans les volumes Docker via des conteneurs "helper" temporaires.

## 1. Volume Browser Backend

```python
# volumes/browser.py
import asyncio
import tarfile
import io
from pathlib import Path

class VolumeBrowser:
    """Navigateur de volumes Docker"""

    HELPER_IMAGE = "busybox:latest"

    def __init__(self, docker_client):
        self.docker = docker_client

    async def list_files(self, volume_name: str, path: str = "/", env_id: int = None) -> list:
        """Lister les fichiers d'un volume"""
        # Créer un conteneur helper temporaire
        container_id = await self._create_helper_container(volume_name, env_id)

        try:
            # Exécuter ls -la
            result = await self.docker.exec_in_container(
                container_id,
                ["ls", "-la", path],
                env_id=env_id
            )

            # Parser le résultat
            files = self._parse_ls_output(result)
            return files

        finally:
            # Supprimer le conteneur
            await self.docker.remove_container(container_id, force=True, env_id=env_id)

    async def read_file(self, volume_name: str, file_path: str, env_id: int = None) -> bytes:
        """Lire un fichier du volume"""
        container_id = await self._create_helper_container(volume_name, env_id)

        try:
            # Lire via cat
            result = await self.docker.exec_in_container(
                container_id,
                ["cat", file_path],
                env_id=env_id
            )
            return result.encode()

        finally:
            await self.docker.remove_container(container_id, force=True, env_id=env_id)

    async def write_file(self, volume_name: str, file_path: str, content: bytes, env_id: int = None):
        """Écrire un fichier dans le volume"""
        container_id = await self._create_helper_container(volume_name, env_id)

        try:
            # Créer un tar avec le fichier
            tar_buffer = self._create_tar(file_path, content)

            # Copier dans le conteneur
            await self.docker.copy_to_container(
                container_id,
                tar_buffer,
                path=str(Path(file_path).parent),
                env_id=env_id
            )

        finally:
            await self.docker.remove_container(container_id, force=True, env_id=env_id)

    async def delete_file(self, volume_name: str, file_path: str, env_id: int = None):
        """Supprimer un fichier du volume"""
        container_id = await self._create_helper_container(volume_name, env_id)

        try:
            await self.docker.exec_in_container(
                container_id,
                ["rm", "-rf", file_path],
                env_id=env_id
            )
        finally:
            await self.docker.remove_container(container_id, force=True, env_id=env_id)

    async def _create_helper_container(self, volume_name: str, env_id: int) -> str:
        """Créer un conteneur helper monté sur le volume"""
        result = await self.docker.create_container({
            "image": self.HELPER_IMAGE,
            "cmd": ["sleep", "300"],  # 5 minutes
            "volumes": {volume_name: {"bind": "/data", "mode": "rw"}},
            "auto_remove": False
        }, env_id)

        await self.docker.start_container(result["id"], env_id)
        return result["id"]

    def _parse_ls_output(self, output: str) -> list:
        """Parser la sortie de ls -la"""
        files = []
        for line in output.strip().split("\n")[1:]:  # Skip total
            parts = line.split()
            if len(parts) >= 9:
                files.append({
                    "name": parts[-1],
                    "size": parts[4],
                    "permissions": parts[0],
                    "modified": " ".join(parts[5:8]),
                    "is_dir": parts[0].startswith("d")
                })
        return files

    def _create_tar(self, file_path: str, content: bytes) -> bytes:
        """Créer un tar en mémoire"""
        buffer = io.BytesIO()

        with tarfile.open(fileobj=buffer, mode='w') as tar:
            info = tarfile.TarInfo(name=Path(file_path).name)
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))

        return buffer.getvalue()
```

## 2. API Routes

```python
from fastapi import APIRouter, UploadFile

router = APIRouter(prefix="/api/volumes", tags=["volumes"])

@router.get("/{volume_name}/files")
async def list_volume_files(
    volume_name: str,
    path: str = "/",
    env_id: int = Query(None)
):
    """Lister les fichiers d'un volume"""
    browser = VolumeBrowser(docker_client)
    files = await browser.list_files(volume_name, path, env_id)
    return {"volume": volume_name, "path": path, "files": files}

@router.get("/{volume_name}/files/{file_path:path}")
async def read_volume_file(
    volume_name: str,
    file_path: str,
    env_id: int = Query(None)
):
    """Lire un fichier d'un volume"""
    browser = VolumeBrowser(docker_client)
    content = await browser.read_file(volume_name, "/" + file_path, env_id)

    from fastapi.responses import Response
    return Response(content=content, media_type="application/octet-stream")

@router.put("/{volume_name}/files/{file_path:path}")
async def write_volume_file(
    volume_name: str,
    file_path: str,
    content: UploadFile,
    env_id: int = Query(None)
):
    """Écrire un fichier dans un volume"""
    browser = VolumeBrowser(docker_client)
    data = await content.read()
    await browser.write_file(volume_name, "/" + file_path, data, env_id)
    return {"status": "written"}
```

## 3. Frontend Vue 3

```vue
<!-- components/VolumeBrowser.vue -->
<template>
  <div class="volume-browser">
    <div class="toolbar">
      <button @click="goUp" :disabled="currentPath === '/'">↑ Up</button>
      <span class="path">{{ currentPath }}</span>
    </div>

    <div class="file-list">
      <div v-if="loading" class="loading">Loading...</div>

      <div v-else>
        <div
          v-for="file in files"
          :key="file.name"
          class="file-item"
          :class="{ directory: file.is_dir }"
          @click="file.is_dir ? navigate(file.name) : openFile(file)"
        >
          <span class="icon">{{ file.is_dir ? '📁' : '📄' }}</span>
          <span class="name">{{ file.name }}</span>
          <span class="size">{{ file.size }}</span>
          <span class="actions">
            <button @click.stop="downloadFile(file)" v-if="!file.is_dir">⬇</button>
            <button @click.stop="deleteFile(file)" class="danger">🗑</button>
          </span>
        </div>
      </div>
    </div>

    <!-- File Editor Modal -->
    <div v-if="editingFile" class="modal">
      <div class="modal-content">
        <h3>{{ editingFile.name }}</h3>
        <textarea v-model="fileContent" rows="20"></textarea>
        <div class="actions">
          <button @click="saveFile" class="primary">Save</button>
          <button @click="editingFile = null">Cancel</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const props = defineProps<{ volumeName: string; envId?: number }>();

const files = ref([]);
const currentPath = ref('/');
const loading = ref(false);
const editingFile = ref(null);
const fileContent = ref('');

async function loadFiles() {
  loading.value = true;
  const response = await fetch(`/api/volumes/${props.volumeName}/files?path=${currentPath.value}&env_id=${props.envId || ''}`);
  const data = await response.json();
  files.value = data.files;
  loading.value = false;
}

function navigate(dir: string) {
  currentPath.value = currentPath.value === '/' ? `/${dir}` : `${currentPath.value}/${dir}`;
  loadFiles();
}

function goUp() {
  const parts = currentPath.value.split('/').filter(Boolean);
  parts.pop();
  currentPath.value = '/' + parts.join('/');
  loadFiles();
}

async function openFile(file: any) {
  if (file.size > 1024 * 1024) {
    alert('File too large to edit');
    return;
  }

  const response = await fetch(`/api/volumes/${props.volumeName}/files/${currentPath.value}/${file.name}?env_id=${props.envId || ''}`);
  fileContent.value = await response.text();
  editingFile.value = file;
}

async function saveFile() {
  await fetch(`/api/volumes/${props.volumeName}/files/${currentPath.value}/${editingFile.value.name}?env_id=${props.envId || ''}`, {
    method: 'PUT',
    body: fileContent.value
  });
  editingFile.value = null;
}

async function deleteFile(file: any) {
  if (!confirm(`Delete ${file.name}?`)) return;

  await fetch(`/api/volumes/${props.volumeName}/files/${currentPath.value}/${file.name}?env_id=${props.envId || ''}`, {
    method: 'DELETE'
  });
  loadFiles();
}

onMounted(loadFiles);
</script>
```

---

[← Terminal WebSocket](11-TERMINAL-WEBSOCKET.md) | [Suivant : Background Processes →](13-BACKGROUND-PROCESSES.md)
