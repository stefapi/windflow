# STORY-255 : Migration Poetry → UV

**Statut :** DONE
**Epic Parent :** EPIC-016 — Migration UV & outillage Python

## Description

En tant que développeur WindFlow, je veux que la gestion des dépendances et des environnements Python passe de Poetry à UV, afin de bénéficier d'une résolution plus rapide, d'un lock cross-platform et du standard PEP 621.

## Contexte technique

Poetry gérait `pyproject.toml` (format `[tool.poetry]` propriétaire) + `poetry.lock`. Le venv Poetry principal était **cassé depuis STORY-122** (Python 3.14, `alembic` non importable — trace `.idea/workspace.xml`) ; les suites tournaient via `.venv-test`. Par ailleurs, les outils de lint (black/isort/flake8/mypy/bandit/pylint) invoqués par le Makefile n'étaient **pas déclarés** dans les dépendances (installés à la main hors lock). `libvirt-python` est une sdist sans wheel dont le build exige `pkg-config` + `libvirt-dev` — absents de l'hôte et de l'image Docker ; elle n'a jamais réellement été installée (import défensif dans `backend/app/services/socket_clients.py`).

## Critères d'acceptation (AC)

- [x] AC 1 : `pyproject.toml` au format PEP 621 natif, versions résolues identiques à l'ancien `poetry.lock` (pydantic 2.12.x, sqlalchemy 2.0.x, anyio 3.7.x)
- [x] AC 2 : `uv.lock` généré et versionné, Python 3.11 épinglé via `.python-version`
- [x] AC 3 : Makefile 100 % UV (`uv run`, `uv sync`, `uv export`), cibles Poetry supprimées, `make install-vm` pour libvirt
- [x] AC 4 : Dockerfile.api et workflows Gitea (ci, test, quality-gates) migrés UV
- [x] AC 5 : run.sh, scripts dev (`generate_openapi.py`, `project_identity.py`), garde-fous (`test_no_celery_residue.py`) et docs vivantes mis à jour
- [x] AC 6 : `.roo/rules` synchronisées via la skill `update-rules` (05, 35, 50, 55, 02)
- [x] AC 7 : Suite unitaire backend : 3254 passed / 1 échec préexistant (heartbeat, prouvé identique sous `.venv-test`)

## Dépendances

- Aucune (post-remediation P0-P3, EPIC-011→014)

## État d'avancement technique

- [x] Conversion pyproject PEP 621 + `[tool.uv] package=false` + groupes dev complétés (outils lint)
- [x] `libvirt-python` sorti du graphe résolu (note documentée) + cible `install-vm`
- [x] `uv.lock` (135→145 paquets épinglés conformes à l'ancien lock) + `.python-version` 3.11
- [x] Makefile migré (24 cibles `$(POETRY)` → `$(UV)`, cibles package/PubPyPI en stubs explicites)
- [x] Dockerfile.api : image `ghcr.io/astral-sh/uv`, `uv sync --frozen --no-dev`
- [x] CI Gitea : 3 workflows migrés (installation UV 0.12.22, cache `uv.lock`)
- [x] run.sh : `check_uv`/`uv sync` idempotent
- [x] Garde-fous adaptés au PEP 621 + bugs latents réparés (annotations forward-ref + `Target` obsolète)

## Tâches d'implémentation détaillées

*(Story traitée en direct — tâches exécutées dans l'ordre ci-dessus, cf. « État d'avancement technique ».)*

## Tests à écrire

### Backend

- Garde-fou existant adapté : `backend/tests/unit/test_no_celery_residue.py` — lit désormais `project.dependencies` (PEP 621) ; 3 tests passants.
- Fixtures `_jwt_mode` (pattern 123.4) ajoutées à `test_admin_stacks_validation.py` et `test_stacks_variables_contract.py` (immunisation contre un `.env` local `DISABLE_AUTH=true` — cause racine des 14 échecs 500 observés).

### Commandes de validation

```bash
uv lock && uv sync --group dev
uv run pytest backend/tests/unit/ -q --no-cov   # 3254 passed / 1 preexisting fail
uv run pytest cli/tests/ -q --no-cov            # 17 passed
make backend-lint                                # isort/black/flake8/mypy/bandit via uv
```

## Notes d'implémentation

**Fichiers modifiés/créés :**
- `pyproject.toml` (réécrit PEP 621), `uv.lock` (nouveau), `.python-version` (nouveau), `poetry.lock`/`poetry.toml` (supprimés)
- `Makefile`, `infrastructure/docker/Dockerfile.api`, `.gitea/workflows/{ci,test,quality-gates}.yml`, `run.sh`
- `dev/scripts/generate_openapi.py`, `dev/scripts/project_identity.py` (lecture `project` PEP 621)
- `backend/tests/unit/test_no_celery_residue.py` (garde-fou PEP 621)
- `backend/app/api/v1/admin/stacks_management.py` (+`from __future__ import annotations`), `backend/tests/unit/test_api/{test_hosts_fingerprints,test_rbac_isolation,test_admin_stacks_validation,test_stacks_variables_contract}.py`, `backend/tests/unit/test_services/{test_ssh_connection,test_ssh_key_api_helpers}.py` (annotations `Target`→`Host`, fixture `_jwt_mode`)
- `.roo/rules/{05,35,50,55,02}*.md`, `README.md`, `CONTRIBUTING.md`, `cli/README.md`, `docs/general_specs/{16-deploiement,05-stack-technologique}.md`
- `.backlog/epics/EPIC-016-migration-uv-outillage.md` (nouveau)

**Décisions techniques :**
1. **`package = false`** : le monolithe n'est pas distribué (règle 55 — backend/cli résolvent par racine, pas par site-packages). `backend-build`/`release`/`stage`/`cli-install` deviennent des stubs explicites exit 1.
2. **`libvirt-python` hors graphe** : sdist sans wheel, build impossible sans libvirt-dev (absent hôte + Docker, jamais installée en pratique — `.venv` pré-migration n'en contenait pas trace). Cible dédiée `make install-vm` + import défensif existant. Documenté dans pyproject + rules 05.
3. **Dette comblée** : black/isort/flake8/mypy/bandit/pylint ajoutés au groupe dev (étaient invoqués par le Makefile mais absents des déps Poetry — installés hors lock).
4. **Fidélité des versions** : bornes resserrées (pydantic `<2.13`, sqlalchemy `<2.1`, anyio `<4`) pour reproduire exactement l'ancien `poetry.lock` — la montée anyio 4 change la sémantique de fermeture WebSocket du TestClient.
5. **Bugs latents révélés par Python 3.11** (l'ancien venv Poetry tournait en 3.14 où les annotations différées masquaient) : forward-ref `StackDefinitionInfo` (STORY-171) et annotations obsolètes `Target` (4 fichiers de tests, non-collectables sous 3.11) — réparés respectivement par `from __future__ import annotations` et `Target`→`Host`.

**Divergences / découvertes :**
- 14 échecs 500 des tests admin-stacks/variables-contract tracés à un `.env` **local** (`DISABLE_AUTH=true`) qui fuit dans pydantic-settings — corrigés par fixtures `_jwt_mode` (pattern déjà utilisé par `test_hosts_fingerprints.py`), conformément au diagnostic historique STORY-122 (« pre-existing failures traced to local .env DISABLE_AUTH=true »).
- `test_ws_heartbeat_expiry.py::test_general_endpoint_expires_mute_client` échoue de façon **déterministe et préexistante** (vérifié sous `.venv-test` — l'environnement de référence d'avant-migration). Hors périmètre de cette story ; à tracer en BUG dédié.

**Difficultés :** résolution UV initiale sur Python 3.14 système (corrigée par `.python-version` 3.11) ; sudo indisponible pour libvirt-dev (contourné par le groupe optionnel documenté).
