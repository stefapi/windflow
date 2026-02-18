# Intégration Git - CI/CD Intégré

[← Authentification](04-AUTHENTICATION.md) | [Suivant : Auto-Updates →](06-AUTO-UPDATES.md)

## 🔄 Vue d'ensemble

Windflow-sample intègre une solution CI/CD pour déployer des stacks Docker Compose depuis Git.

## 🏗️ Architecture

```
Git Repo → Webhook/API → Clone & Parse → Apply Env Vars → Docker Deploy → Notify
```

## 1. Credentials Git

```python
# git/credentials.py
from enum import Enum
from typing import Optional
import tempfile
import os

class GitAuthType(str, Enum):
    NONE = "none"
    HTTPS = "https"
    SSH = "ssh"

class GitCredentialManager:
    """Gestionnaire de credentials Git"""
    
    def __init__(self, encryption_service):
        self.encryption = encryption_service
    
    async def setup_auth(self, credential, repo_url: str) -> dict:
        """Configurer l'authentification Git"""
        if credential.auth_type == GitAuthType.HTTPS:
            return self._setup_https(credential, repo_url)
        elif credential.auth_type == GitAuthType.SSH:
            return self._setup_ssh(credential)
        return {"env": {}, "ssh_key_path": None}
    
    def _setup_https(self, credential, repo_url: str) -> dict:
        """Configurer auth HTTPS"""
        password = self.encryption.decrypt(credential.password)
        auth_url = repo_url.replace("https://", f"https://{credential.username}:{password}@")
        return {"env": {"GIT_TERMINAL_PROMPT": "0"}, "auth_url": auth_url}
    
    def _setup_ssh(self, credential) -> dict:
        """Configurer auth SSH"""
        private_key = self.encryption.decrypt(credential.ssh_private_key)
        ssh_key_path = tempfile.mktemp(prefix="git_ssh_key_")
        
        with open(ssh_key_path, "w") as f:
            f.write(private_key)
        os.chmod(ssh_key_path, 0o600)
        
        return {
            "env": {"GIT_SSH_COMMAND": f"ssh -i {ssh_key_path} -o StrictHostKeyChecking=no"},
            "ssh_key_path": ssh_key_path
        }
```

## 2. Opérations Git

```python
# git/operations.py
import subprocess
from pathlib import Path

class GitOperations:
    """Clone et pull de repositories"""
    
    async def clone_or_pull(self, repo_url: str, branch: str, credential, target_dir: str = None) -> dict:
        """Cloner ou mettre à jour un repository"""
        # Setup auth
        auth_config = await self.credential_manager.setup_auth(credential, repo_url)
        
        if not target_dir:
            target_dir = tempfile.mkdtemp(prefix="windflow_git_")
        
        repo_path = Path(target_dir)
        
        try:
            if repo_path.exists() and (repo_path / ".git").exists():
                result = await self._pull(repo_path, branch, auth_config)
            else:
                result = await self._clone(repo_url, branch, repo_path, auth_config)
            return result
        finally:
            self.credential_manager.cleanup(auth_config.get("ssh_key_path"))
    
    async def _clone(self, repo_url, branch, target_path, auth_config) -> dict:
        """Cloner un repository"""
        env = os.environ.copy()
        env.update(auth_config.get("env", {}))
        
        cmd = ["git", "clone", "--branch", branch, "--depth", "1", "--single-branch",
               auth_config.get("auth_url", repo_url), str(target_path)]
        
        result = subprocess.run(cmd, env=env, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Git clone failed: {result.stderr}")
        
        commit = await self._get_current_commit(target_path)
        return {"path": str(target_path), "commit": commit, "changed": True}
    
    async def _pull(self, repo_path, branch, auth_config) -> dict:
        """Pull les derniers changements"""
        env = os.environ.copy()
        env.update(auth_config.get("env", {}))
        
        old_commit = await self._get_current_commit(repo_path)
        
        for cmd in [["git", "fetch", "origin", branch], ["git", "reset", "--hard", f"origin/{branch}"]]:
            result = subprocess.run(cmd, cwd=str(repo_path), env=env, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"Git pull failed: {result.stderr}")
        
        new_commit = await self._get_current_commit(repo_path)
        return {"path": str(repo_path), "commit": new_commit, "changed": old_commit != new_commit}
    
    async def _get_current_commit(self, repo_path) -> str:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(repo_path), capture_output=True, text=True)
        return result.stdout.strip()
```

## 3. Webhooks

```python
# git/webhooks.py
import hmac
import hashlib
import json

class WebhookHandler:
    """Gestionnaire de webhooks Git"""
    
    def __init__(self, secret: str):
        self.secret = secret.encode()
    
    def verify_github_signature(self, payload: bytes, signature: str) -> bool:
        """Vérifier signature GitHub (X-Hub-Signature-256: sha256=<hex>)"""
        if not signature.startswith("sha256="):
            return False
        expected = signature[7:]
        computed = hmac.new(self.secret, payload, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, computed)
    
    def parse_push_event(self, payload: bytes, provider: str = "github") -> dict:
        """Parser événement push"""
        data = json.loads(payload)
        
        if provider == "github":
            ref = data.get("ref", "")
            branch = ref.replace("refs/heads/", "") if ref.startswith("refs/heads/") else ref
            return {
                "provider": "github",
                "repository": data.get("repository", {}).get("full_name"),
                "branch": branch,
                "after": data.get("after"),
                "commits": [{"id": c["id"], "message": c["message"]} for c in data.get("commits", [])],
                "modified_files": [f for c in data.get("commits", []) for f in c.get("modified", [])]
            }
        return {}

# FastAPI endpoint
from fastapi import APIRouter, Request, Header

router = APIRouter(prefix="/api/git/webhook", tags=["git-webhook"])

@router.post("/{stack_id}")
async def handle_webhook(
    stack_id: int,
    request: Request,
    x_hub_signature_256: str = Header(None)
):
    """Endpoint webhook pour Git push"""
    stack = await get_git_stack(stack_id)
    if not stack or not stack.webhook_enabled:
        raise HTTPException(status_code=404, detail="Stack not found or webhook disabled")
    
    payload = await request.body()
    
    handler = WebhookHandler(stack.webhook_secret)
    if not handler.verify_github_signature(payload, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")
    
    event = handler.parse_push_event(payload, "github")
    
    if event.get("branch") != stack.branch:
        return {"message": f"Ignored branch: {event.get('branch')}"}
    
    # Déclencher déploiement
    deployment = await trigger_deployment(stack_id, "webhook", event.get("after"))
    return {"message": "Deployment triggered", "deployment_id": deployment.id}
```

## 4. Déploiement Stack

```python
# git/deploy.py
import subprocess
from pathlib import Path

class StackDeployer:
    """Déployeur de stacks Docker Compose"""
    
    async def deploy(self, stack_name: str, compose_content: str, env_vars: dict) -> dict:
        """Déployer une stack"""
        work_dir = Path(tempfile.mkdtemp(prefix=f"stack_{stack_name}_"))
        
        try:
            # Écrire compose file
            (work_dir / "docker-compose.yml").write_text(compose_content)
            
            # Écrire .env
            env_content = "\n".join(f"{k}={v}" for k, v in env_vars.items())
            (work_dir / ".env").write_text(env_content)
            
            # Lancer docker compose up
            full_env = {**os.environ, **env_vars, "COMPOSE_PROJECT_NAME": stack_name}
            result = subprocess.run(
                "docker compose up -d --remove-orphans",
                shell=True, cwd=str(work_dir), env=full_env,
                capture_output=True, text=True
            )
            
            if result.returncode != 0:
                raise Exception(f"Compose failed: {result.stderr}")
            
            return {"status": "success", "output": result.stdout}
        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
    
    async def undeploy(self, stack_name: str, remove_volumes: bool = False) -> dict:
        """Supprimer une stack"""
        work_dir = Path(tempfile.mkdtemp())
        try:
            (work_dir / "docker-compose.yml").write_text("version: '3.8'\nservices: {}")
            cmd = f"docker compose down{' -v' if remove_volumes else ''}"
            subprocess.run(cmd, shell=True, cwd=str(work_dir), 
                          env={**os.environ, "COMPOSE_PROJECT_NAME": stack_name})
            return {"status": "success"}
        finally:
            import shutil
            shutil.rmtree(work_dir, ignore_errors=True)
```

## 🎨 Frontend Vue 3

```vue
<!-- components/GitStackList.vue -->
<template>
  <div class="git-stacks">
    <div class="header">
      <h2>Git Stacks</h2>
      <button @click="showAddModal = true" class="primary">
        <PlusIcon /> Add Stack
      </button>
    </div>

    <div class="stacks-grid">
      <div v-for="stack in stacks" :key="stack.id" class="stack-card">
        <div class="stack-header">
          <h3>{{ stack.stack_name }}</h3>
          <span :class="`status ${stack.sync_status}`">{{ stack.sync_status }}</span>
        </div>
        
        <div class="stack-info">
          <p><RepoIcon /> {{ stack.repository_name }}</p>
          <p><BranchIcon /> {{ stack.branch }}</p>
          <p><ClockIcon /> Last sync: {{ formatDate(stack.last_sync) }}</p>
        </div>

        <div class="stack-actions">
          <button @click="deployStack(stack)" :disabled="deploying === stack.id">
            <PlayIcon /> Deploy
          </button>
          <button @click="syncStack(stack)">
            <RefreshIcon /> Sync
          </button>
          <button @click="copyWebhookUrl(stack)" title="Copy webhook URL">
            <LinkIcon />
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';

const stacks = ref([]);
const deploying = ref(null);
const showAddModal = ref(false);

async function loadStacks() {
  const response = await fetch('/api/git/stacks');
  stacks.value = await response.json();
}

async function deployStack(stack) {
  deploying.value = stack.id;
  try {
    await fetch(`/api/git/stacks/${stack.id}/deploy`, { method: 'POST' });
    // Show success notification
  } finally {
    deploying.value = null;
  }
}

async function syncStack(stack) {
  await fetch(`/api/git/stacks/${stack.id}/sync`, { method: 'POST' });
  await loadStacks();
}

function copyWebhookUrl(stack) {
  const url = `${window.location.origin}/api/git/webhook/${stack.id}`;
  navigator.clipboard.writeText(url);
  // Show notification
}

onMounted(loadStacks);
</script>
```

---

[← Authentification](04-AUTHENTICATION.md) | [Suivant : Auto-Updates →](06-AUTO-UPDATES.md)
