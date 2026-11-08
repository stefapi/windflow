"""Garde-fou anti-régression Celery (STORY-130.2 — arbitrage F1).

Le runtime d'exécution de WindFlow est asyncio unique : le double runtime
Celery fantôme a été purgé (celery_app.py, Dockerfile.worker, service
compose windflow-worker, cibles Makefile, jobs CI, monitoring, env).
Ces tests protègent contre la réintroduction du module ou de la
dépendance — la régression la plus probable.
"""

import importlib.util
import tomllib
from pathlib import Path

# Racine du dépôt (backend/tests/unit/ -> 3 niveaux au-dessus)
REPO_ROOT = Path(__file__).resolve().parents[3]
PYPROJECT_PATH = REPO_ROOT / "pyproject.toml"
DOCKERFILE_WORKER_PATH = REPO_ROOT / "infrastructure" / "docker" / "Dockerfile.worker"


def test_celery_app_module_absent() -> None:
    """Le module app.celery_app ne doit plus exister (runtime asyncio unique)."""
    assert importlib.util.find_spec("app.celery_app") is None


def test_no_celery_dependency_in_pyproject() -> None:
    """Aucune dépendance celery ne doit figurer dans pyproject.toml (PEP 621)."""
    with open(PYPROJECT_PATH, "rb") as fh:
        data = tomllib.load(fh)

    project_deps = data.get("project", {}).get("dependencies", [])
    for dep in project_deps:
        dep_name = dep.split(";")[0].split("[")[0].strip()
        assert "celery" not in dep_name.lower(), (
            f"Dépendance Celery réintroduite dans pyproject.toml : {dep_name} "
            "(arbitrage F1 — runtime asyncio unique, cf. STORY-130.2)"
        )


def test_dockerfile_worker_absent() -> None:
    """Le Dockerfile.worker ne doit plus exister sur le disque."""
    assert not DOCKERFILE_WORKER_PATH.exists()
