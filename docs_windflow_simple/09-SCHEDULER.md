# Scheduler - Tâches programmées

[← Hawser Proxy](08-HAWSER-PROXY.md) | [Retour à l'accueil →](README.md)

## ⏰ Vue d'ensemble

Scheduler unifié pour exécuter des tâches récurrentes (auto-updates, git sync, cleanup).

## 1. Scheduler Principal

```python
# scheduler/core.py
from croner import Cron
from datetime import datetime
import asyncio

class Scheduler:
    """Scheduler de tâches avec expressions cron"""

    def __init__(self):
        self.jobs = {}  # job_id -> {cron, callback, next_run}
        self.running = False

    def schedule(self, job_id: str, cron_expr: str, callback, *args):
        """Planifier une tâche"""
        cron = Cron(cron_expr)
        self.jobs[job_id] = {
            "cron": cron,
            "callback": callback,
            "args": args,
            "next_run": cron.next()
        }

    def unschedule(self, job_id: str):
        """Annuler une tâche"""
        self.jobs.pop(job_id, None)

    async def start(self):
        """Démarrer le scheduler"""
        self.running = True

        while self.running:
            now = datetime.utcnow()

            for job_id, job in list(self.jobs.items()):
                if job["next_run"] <= now:
                    try:
                        await job["callback"](*job["args"])
                    except Exception as e:
                        print(f"Job {job_id} failed: {e}")

                    # Replanifier
                    job["next_run"] = job["cron"].next()

            # Attendre 1 seconde avant de revérifier
            await asyncio.sleep(1)

    def stop(self):
        """Arrêter le scheduler"""
        self.running = False

    def get_next_run(self, job_id: str) -> datetime:
        """Obtenir la prochaine exécution"""
        job = self.jobs.get(job_id)
        return job["next_run"] if job else None
```

## 2. Jobs Intégrés

```python
# scheduler/jobs.py

async def job_auto_update(container_name: str, env_id: int):
    """Job de mise à jour automatique"""
    executor = AutoUpdateExecutor(docker, scanner, notifier)
    await executor.execute_update(container_name, None, "never", env_id)

async def job_git_sync(stack_id: int):
    """Job de synchronisation Git"""
    git_ops = GitOperations(credential_manager)
    # ... clone/pull and deploy

async def job_cleanup_metrics():
    """Job de nettoyage des métriques anciennes"""
    # Supprimer métriques > 30 jours
    await db.execute("DELETE FROM host_metrics WHERE timestamp < datetime('now', '-30 days')")

async def job_cleanup_sessions():
    """Job de nettoyage des sessions expirées"""
    await db.execute("DELETE FROM sessions WHERE expires_at < datetime('now')")

# Configuration des jobs
def setup_scheduled_jobs(scheduler: Scheduler):
    # Jobs système
    scheduler.schedule("cleanup_metrics", "0 2 * * *", job_cleanup_metrics)
    scheduler.schedule("cleanup_sessions", "0 * * * *", job_cleanup_sessions)  # Toutes les heures
```

## 3. API Routes

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/schedules", tags=["schedules"])

@router.get("")
async def list_schedules():
    """Lister toutes les tâches programmées"""
    return {
        "jobs": [
            {
                "id": job_id,
                "next_run": job["next_run"].isoformat()
            }
            for job_id, job in scheduler.jobs.items()
        ]
    }

@router.post("/run/{job_id}")
async def run_job_now(job_id: str):
    """Exécuter une tâche immédiatement"""
    job = scheduler.jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    await job["callback"](*job["args"])
    return {"status": "executed"}
```

---

[← Hawser Proxy](08-HAWSER-PROXY.md) | [Retour à l'accueil →](README.md)
