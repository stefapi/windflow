# Auto-Updates - Mises à jour automatiques

[← Git Integration](05-GIT-INTEGRATION.md) | [Suivant : Vulnerability Scanning →](07-VULNERABILITY-SCANNING.md)

## 🔄 Vue d'ensemble

Système de mise à jour automatique des conteneurs avec scan de vulnérabilités intégré.

## 🏗️ Flow de mise à jour

```
Schedule → Check Registry → Pull Image → Scan Vulns → Apply Criteria → Recreate Container → Rollback if Failed
```

## 1. Vérification de mise à jour

```python
# auto_updates/checker.py
import httpx
import json
from typing import Optional

class UpdateChecker:
    """Vérifier les mises à jour d'images"""

    async def check_update_available(self, image_name: str, current_image_id: str) -> dict:
        """Vérifier si une mise à jour est disponible"""
        # Récupérer le digest du registry
        registry_digest = await self._get_registry_digest(image_name)

        # Récupérer le digest local
        local_digest = await self._get_local_digest(current_image_id)

        if not registry_digest:
            return {"has_update": False, "error": "Could not fetch registry digest"}

        has_update = registry_digest != local_digest

        return {
            "has_update": has_update,
            "current_digest": local_digest,
            "registry_digest": registry_digest if has_update else None
        }

    async def _get_registry_digest(self, image_name: str) -> Optional[str]:
        """Récupérer le digest depuis le registry"""
        # Parser l'image
        parts = image_name.split(":")
        repo = parts[0]
        tag = parts[1] if len(parts) > 1 else "latest"

        # Déterminer le registry
        if "/" in repo and not repo.startswith("library/"):
            registry = repo.split("/")[0]
            repo_path = "/".join(repo.split("/")[1:])
        else:
            registry = "index.docker.io"
            repo_path = f"library/{repo}" if "/" not in repo else repo

        # Obtenir token
        token = await self._get_registry_token(registry, repo_path)

        # HEAD request pour obtenir digest
        url = f"https://{registry}/v2/{repo_path}/manifests/{tag}"
        headers = {
            "Accept": "application/vnd.docker.distribution.manifest.list.v2+json",
            "Authorization": f"Bearer {token}"
        }

        async with httpx.AsyncClient() as client:
            response = await client.head(url, headers=headers)
            return response.headers.get("Docker-Content-Digest")

    async def _get_registry_token(self, registry: str, repo: str) -> str:
        """Obtenir token d'authentification registry"""
        auth_url = f"https://{registry}/v2/"
        async with httpx.AsyncClient() as client:
            response = await client.get(auth_url)
            www_auth = response.headers.get("WWW-Authenticate", "")

            # Parser realm
            if 'realm="' in www_auth:
                realm_start = www_auth.index('realm="') + 7
                realm_end = www_auth.index('"', realm_start)
                realm = www_auth[realm_start:realm_end]

                token_url = f"{realm}?service={registry}&scope=repository:{repo}:pull"
                token_response = await client.get(token_url)
                return token_response.json().get("token", "")

        return ""
```

## 2. Processus de mise à jour

```python
# auto_updates/executor.py
from typing import Optional
import asyncio

class AutoUpdateExecutor:
    """Exécuteur de mises à jour automatiques"""

    def __init__(self, docker_client, scanner, notifier):
        self.docker = docker_client
        self.scanner = scanner
        self.notifier = notifier

    async def execute_update(
        self,
        container_name: str,
        image_name: str,
        vulnerability_criteria: str = "never",
        env_id: int = None
    ) -> dict:
        """
        Exécuter une mise à jour de conteneur

        Args:
            container_name: Nom du conteneur
            image_name: Image à utiliser
            vulnerability_criteria: never, critical, high, medium, low
            env_id: ID de l'environnement
        """
        logs = []

        try:
            # 1. Inspecter le conteneur actuel
            logs.append(f"Inspecting container {container_name}...")
            old_inspect = await self.docker.inspect_container_by_name(container_name, env_id)
            old_container_id = old_inspect["Id"]
            was_running = old_inspect["State"]["Running"]

            # 2. Pull nouvelle image avec tag temporaire
            logs.append(f"Pulling image {image_name}...")
            temp_tag = f"{image_name.split(':')[0]}:Colibri-pending"
            await self.docker.pull_image(image_name, None, env_id)

            # 3. Scan de vulnérabilités
            if vulnerability_criteria != "never":
                logs.append(f"Scanning for vulnerabilities...")
                scan_result = await self.scanner.scan_image(image_name, env_id)

                if not self._passes_criteria(scan_result, vulnerability_criteria):
                    logs.append(f"Vulnerability criteria not met, skipping update")
                    await self.docker.remove_image(temp_tag, True, env_id)
                    return {"status": "skipped", "reason": "vulnerability_criteria", "logs": logs}

                logs.append(f"Scan passed: {scan_result['critical_count']} critical, {scan_result['high_count']} high")

            # 4. Arrêter le conteneur
            if was_running:
                logs.append("Stopping container...")
                await self.docker.stop_container(old_container_id, env_id)

            # 5. Renommer l'ancien conteneur
            logs.append("Renaming old container...")
            await self.docker.rename_container(old_container_id, f"{container_name}-backup", env_id)

            # 6. Créer le nouveau conteneur
            logs.append("Creating new container...")
            new_container_id = await self._recreate_container(old_inspect, image_name, env_id)

            # 7. Démarrer le nouveau conteneur
            if was_running:
                logs.append("Starting new container...")
                await self.docker.start_container(new_container_id, env_id)

                # Vérifier qu'il démarre correctement
                await asyncio.sleep(5)
                new_inspect = await self.docker.inspect_container(new_container_id, env_id)
                if not new_inspect["State"]["Running"]:
                    raise Exception("Container failed to start")

            # 8. Supprimer l'ancien conteneur
            logs.append("Removing old container...")
            await self.docker.remove_container(old_container_id, True, env_id)

            # 9. Notification
            await self.notifier.send("auto_update.success", {
                "container": container_name,
                "image": image_name
            })

            return {"status": "success", "new_container_id": new_container_id, "logs": logs}

        except Exception as e:
            logs.append(f"Error: {str(e)}")

            # Rollback
            logs.append("Attempting rollback...")
            await self._rollback(container_name, old_container_id, was_running, env_id)

            await self.notifier.send("auto_update.failed", {
                "container": container_name,
                "error": str(e)
            })

            return {"status": "failed", "error": str(e), "logs": logs}

    def _passes_criteria(self, scan_result: dict, criteria: str) -> bool:
        """Vérifier si le scan passe les critères"""
        thresholds = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        threshold = thresholds.get(criteria, 0)

        if threshold <= 0 and scan_result.get("critical_count", 0) > 0:
            return False
        if threshold <= 1 and scan_result.get("high_count", 0) > 0:
            return False
        if threshold <= 2 and scan_result.get("medium_count", 0) > 0:
            return False

        return True

    async def _recreate_container(self, old_inspect: dict, new_image: str, env_id: int) -> str:
        """Recréer un conteneur avec la nouvelle image"""
        config = self._extract_container_config(old_inspect)
        config["image"] = new_image

        new_container = await self.docker.create_container(config, env_id)
        return new_container["id"]

    async def _rollback(self, container_name: str, old_id: str, was_running: bool, env_id: int):
        """Rollback en cas d'échec"""
        try:
            # Renommer l'ancien conteneur
            await self.docker.rename_container(old_id, container_name, env_id)

            if was_running:
                await self.docker.start_container(old_id, env_id)
        except:
            pass
```

## 3. Scheduler Cron

```python
# auto_updates/scheduler.py
from croner import Cron
from datetime import datetime

class AutoUpdateScheduler:
    """Planificateur de mises à jour"""

    def __init__(self, db, executor):
        self.db = db
        self.executor = executor
        self.schedules = {}  # schedule_id -> next_run

    async def start(self):
        """Démarrer le scheduler"""
        # Charger les schedules actifs
        settings = await self._load_active_settings()

        for setting in settings:
            await self._schedule_update(setting)

    async def _schedule_update(self, setting: dict):
        """Planifier une mise à jour"""
        schedule_id = setting["id"]

        # Parser l'expression cron
        cron = Cron(setting["cron_expression"] or "0 3 * * *")

        # Calculer la prochaine exécution
        next_run = cron.next()
        self.schedules[schedule_id] = {
            "next_run": next_run,
            "setting": setting
        }

    async def run_pending(self):
        """Exécuter les mises à jour en attente"""
        now = datetime.utcnow()

        for schedule_id, schedule in list(self.schedules.items()):
            if schedule["next_run"] <= now:
                # Exécuter
                setting = schedule["setting"]

                await self.executor.execute_update(
                    container_name=setting["container_name"],
                    image_name=setting.get("image_name"),  # Récupéré depuis inspect
                    vulnerability_criteria=setting["vulnerability_criteria"],
                    env_id=setting["environment_id"]
                )

                # Replanifier
                await self._schedule_update(setting)

    def get_next_run(self, cron_expr: str) -> datetime:
        """Obtenir la prochaine exécution"""
        cron = Cron(cron_expr)
        return cron.next()
```

## 4. API Routes

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/auto-updates", tags=["auto-updates"])

@router.get("")
async def list_auto_updates(db = Depends(get_db)):
    """Lister toutes les configurations auto-update"""
    return await db.execute("SELECT * FROM auto_update_settings")

@router.post("")
async def create_auto_update(
    request: AutoUpdateRequest,
    user = Depends(require_permission("schedules:create")),
    db = Depends(get_db)
):
    """Créer une configuration auto-update"""
    # Valider cron expression
    try:
        Cron(request.cron_expression)
    except:
        raise HTTPException(status_code=400, detail="Invalid cron expression")

    await db.execute("""
        INSERT INTO auto_update_settings (environment_id, container_name, enabled,
                                          schedule_type, cron_expression, vulnerability_criteria)
        VALUES (?, ?, ?, ?, ?, ?)
    """, [request.environment_id, request.container_name, request.enabled,
          request.schedule_type, request.cron_expression, request.vulnerability_criteria])

    return {"status": "created"}

@router.post("/{id}/run")
async def run_now(id: int, db = Depends(get_db)):
    """Exécuter immédiatement une mise à jour"""
    setting = await db.execute("SELECT * FROM auto_update_settings WHERE id = ?", [id])
    if not setting:
        raise HTTPException(status_code=404, detail="Not found")

    result = await executor.execute_update(
        container_name=setting["container_name"],
        vulnerability_criteria=setting["vulnerability_criteria"],
        env_id=setting["environment_id"]
    )

    return result
```

## 🎨 Frontend Vue 3

```vue
<!-- components/AutoUpdateConfig.vue -->
<template>
  <form @submit.prevent="save">
    <div class="form-group">
      <label>Container</label>
      <select v-model="form.container_name" required>
        <option v-for="c in containers" :key="c.name" :value="c.name">{{ c.name }}</option>
      </select>
    </div>

    <div class="form-group">
      <label>Schedule</label>
      <select v-model="form.schedule_type">
        <option value="daily">Daily</option>
        <option value="weekly">Weekly</option>
        <option value="custom">Custom</option>
      </select>
    </div>

    <div v-if="form.schedule_type === 'custom'" class="form-group">
      <label>Cron Expression</label>
      <input v-model="form.cron_expression" placeholder="0 3 * * *" />
      <small>{{ cronDescription }}</small>
    </div>

    <div class="form-group">
      <label>Vulnerability Criteria</label>
      <select v-model="form.vulnerability_criteria">
        <option value="never">Never scan</option>
        <option value="critical">Block if Critical</option>
        <option value="high">Block if High+</option>
        <option value="medium">Block if Medium+</option>
        <option value="low">Block if any vulnerability</option>
      </select>
    </div>

    <div class="actions">
      <button type="submit" class="primary">Save</button>
    </div>
  </form>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import cronstrue from 'cronstrue';

const props = defineProps(['containers']);
const emit = defineEmits(['save']);

const form = reactive({
  container_name: '',
  schedule_type: 'daily',
  cron_expression: '0 3 * * *',
  vulnerability_criteria: 'never'
});

const cronDescription = computed(() => {
  try {
    return cronstrue.toString(form.cron_expression);
  } catch {
    return 'Invalid cron expression';
  }
});

async function save() {
  await fetch('/api/auto-updates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(form)
  });
  emit('save');
}
</script>
```

---

[← Git Integration](05-GIT-INTEGRATION.md) | [Suivant : Vulnerability Scanning →](07-VULNERABILITY-SCANNING.md)
