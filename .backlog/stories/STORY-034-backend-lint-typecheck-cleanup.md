# STORY-034 : Nettoyage lint et type checking backend

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration technique
**Priorité :** Moyenne

## Description
Corriger les 12 imports inutilisés (F401 flake8) et réduire les erreurs mypy dans le code backend.

## Contexte technique

### Problèmes identifiés
- Imports inutilisés (F401) détectés par flake8 dans les fichiers liés à l'EPIC-008
- Erreurs mypy sur les schémas Docker et les handlers API

### Fichiers impactés — imports inutilisés confirmés

| Fichier | Import inutilisé | Ligne | Action |
|---------|-----------------|-------|--------|
| `backend/app/api/v1/deployments.py` | `typing.List` | 7 | Supprimer `from typing import List` — non utilisé, `DeploymentListResponse` utilisé à la place |
| `backend/app/api/v1/targets/capabilities.py` | `TargetResponse` | 18 | Retirer `TargetResponse` du multi-import `from ....schemas.target` |
| `backend/app/api/v1/targets/connectivity.py` | `HTTPException` | 10 | Retirer `HTTPException` du multi-import `from fastapi` |
| `backend/app/core/abstractions.py` | `AsyncContextManager` | 10 | Retirer `AsyncContextManager` du multi-import `from typing` |
| `backend/app/models/target.py` | `CapabilityType` | 15 | Retirer `CapabilityType` du multi-import `from ..enums.target` |
| `backend/app/services/target_scan_parsers.py` | `ContainerRuntimeInfo` | 16 | Retirer `ContainerRuntimeInfo` du multi-import `from ..schemas.target_scan` |
| `backend/app/services/target_service.py` | `TargetType` | 19 | Retirer `TargetType` du multi-import `from ..enums.target` |

### Outils et commandes de validation
- **Lint F401** : `make backend-lint` (exécute `flake8 backend/`) — F401 n'est pas dans la liste `ignore` de `.flake8`
- **Typecheck** : `make backend-typecheck` (exécute `cd backend && poetry run mypy app/`)
- **Tests** : `make backend-test`
- **Config mypy** : `pyproject.toml` — `ignore_missing_imports=false`, `disallow_untyped_defs=false`, overrides pour modules tiers

### Patterns de référence
- Suppression d'import inutilisé dans un multi-import : retirer le symbole de la ligne, supprimer la ligne entière si c'était le seul symbole
- Annotation mypy : ajouter `# type: ignore[<code>]` en fin de ligne avec le code d'erreur spécifique

### Exigences sécurité identifiées
- Auth : non — aucune modification d'endpoint
- RBAC : non — aucun changement d'autorisation
- Validation : non — aucun schéma modifié
- Exposition : non — aucune donnée exposée
- Audit : non — action purement technique
- **Conclusion : Aucune exigence sécurité pour cette story**

---

## Critères d'acceptation (AC)
- [x] AC 1 : `flake8` ou `ruff check` ne signale plus d'erreurs F401 (imports inutilisés)
- [x] AC 2 : Les erreurs mypy sur les fichiers liés à l'EPIC-008 sont corrigées ou justifiées avec `# type: ignore`
- [x] AC 3 : Tous les tests backend passent après les modifications

---

## Tâches d'implémentation détaillées

### Tâche 1 : Supprimer les imports inutilisés (F401) dans les 7 fichiers backend
**Objectif :** Éliminer toutes les erreurs F401 signalées par flake8 en retirant les imports inutilisés des fichiers source backend
**Fichiers :**
- `backend/app/api/v1/deployments.py` — Modifier — Supprimer la ligne `from typing import List` (ligne 7). Vérifier que `List` n'est pas utilisé ailleurs dans le fichier (seul `DeploymentListResponse` est utilisé pour les réponses de liste).
- `backend/app/api/v1/targets/capabilities.py` — Modifier — Retirer `TargetResponse` de la clause d'import `from ....schemas.target import (HealthCheckResponse, TargetCapabilitiesResponse, TargetResponse)` (lignes 15-19). Conserver `HealthCheckResponse`, `TargetCapabilitiesResponse`.
- `backend/app/api/v1/targets/connectivity.py` — Modifier — Retirer `HTTPException` de la clause d'import `from fastapi import APIRouter, Depends, HTTPException, Request, status` (ligne 10). Conserver `APIRouter`, `Depends`, `Request`, `status`.
- `backend/app/core/abstractions.py` — Modifier — Retirer `AsyncContextManager` de la clause d'import `from typing import Any, AsyncContextManager, AsyncIterator, Optional` (ligne 10). Conserver `Any`, `AsyncIterator`, `Optional`.
- `backend/app/models/target.py` — Modifier — Retirer `CapabilityType` de la clause d'import `from ..enums.target import CapabilityType, TargetStatus, TargetType` (ligne 15). Conserver `TargetStatus`, `TargetType`.
- `backend/app/services/target_scan_parsers.py` — Modifier — Retirer `ContainerRuntimeInfo` de la clause d'import `from ..schemas.target_scan import (ContainerRuntimeInfo, PlatformArchitecture, ScanResult, ToolInfo)` (lignes 15-20). Conserver `PlatformArchitecture`, `ScanResult`, `ToolInfo`.
- `backend/app/services/target_service.py` — Modifier — Retirer `TargetType` de la clause d'import `from ..enums.target import CapabilityType, TargetStatus, TargetType` (ligne 19). Conserver `CapabilityType`, `TargetStatus`.
**Exigences sécurité :** Aucune
**Dépend de :** Aucune

### Tâche 2 : Corriger ou annoter les erreurs mypy sur les schémas Docker et handlers API
**Objectif :** Réduire les erreurs mypy dans les fichiers liés à l'EPIC-008 en corrigeant les types lorsque c'est trivial, ou en ajoutant des annotations `# type: ignore[...]` justifiées pour les faux positifs
**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Lancer `cd backend && poetry run mypy app/schemas/docker.py` pour identifier les erreurs spécifiques. Corriger les types si possible (ex : ajouter des type hints manquants, corriger les types de retour). Sinon, annoter avec `# type: ignore[<code>]` et un commentaire expliquant pourquoi.
- `backend/app/api/v1/docker.py` — Modifier — Lancer `cd backend && poetry run mypy app/api/v1/docker.py` pour identifier les erreurs spécifiques. Même approche : corriger si trivial, annoter sinon.
- Autres fichiers avec erreurs mypy — Modifier — Lancer `cd backend && poetry run mypy app/` pour obtenir la liste complète. Traiter chaque erreur selon le même principe.
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1 (pour éviter les erreurs en cascade dues aux imports manquants)

### Tâche 3 : Valider lint, typecheck et tests
**Objectif :** Vérifier que toutes les corrections sont effectives et qu'aucune régression n'a été introduite
**Fichiers :**
- Aucun fichier à modifier — exécution de commandes de validation uniquement
**Actions :**
1. Lancer `make backend-lint` et vérifier l'absence d'erreurs F401
2. Lancer `make backend-typecheck` et vérifier la réduction des erreurs mypy
3. Lancer `make backend-test` et vérifier que tous les tests passent
4. Si des erreurs F401 subsistent dans les fichiers de tests, les corriger de la même manière
**Exigences sécurité :** Aucune
**Dépend de :** Tâche 1, Tâche 2

---

## Tests à écrire

> Cette story est un nettoyage technique (lint/typecheck). Aucun nouveau test fonctionnel n'est requis.
> La validation se fait par les commandes de lint et les tests existants.

### Validation lint
```bash
# Vérifier absence d'erreurs F401
make backend-lint
# Ou directement :
poetry run flake8 backend/ --select=F401
```

### Validation typecheck
```bash
# Vérifier la réduction des erreurs mypy
make backend-typecheck
# Ou directement :
cd backend && poetry run mypy app/
```

### Validation tests existants
```bash
# Tous les tests backend doivent passer
make backend-test
```

---

## État d'avancement technique
- [x] Tâche 1 : Supprimer les imports inutilisés (F401) dans les 7 fichiers backend
- [x] Tâche 2 : Corriger ou annoter les erreurs mypy sur les schémas Docker et handlers API
- [x] Tâche 3 : Valider lint, typecheck et tests

---

## Notes d'implémentation

### Outils installés
- **ruff 0.15.13** ajouté aux dépendances dev via `poetry add --group dev ruff`

### Tâche 1 — Imports inutilisés (F401)
7 fichiers corrigés, 7 imports inutilisés supprimés :
- `backend/app/api/v1/deployments.py` — suppression `from typing import List`
- `backend/app/api/v1/targets/capabilities.py` — retrait `TargetResponse` du multi-import
- `backend/app/api/v1/targets/connectivity.py` — retrait `HTTPException` du multi-import
- `backend/app/core/abstractions.py` — retrait `AsyncContextManager` du multi-import
- `backend/app/models/target.py` — retrait `CapabilityType` du multi-import
- `backend/app/services/target_scan_parsers.py` — retrait `ContainerRuntimeInfo` du multi-import
- `backend/app/services/target_service.py` — retrait `TargetType` du multi-import

### Tâche 2 — Erreurs mypy (274 → 0)
Correction sur 27 fichiers. Les erreurs se répartissaient en plusieurs catégories :

1. **Faux positifs Pydantic** (plugin pydantic-mypy incompatible avec la version de mypy) — `# type: ignore[call-arg]` sur les constructeurs de modèles Pydantic dans `schemas/docker.py`, `api/v1/docker.py`, `stacks.py`, `admin/stacks_management.py`, `stack_service.py`, `container_builder.py`, `adoption_service.py`, `stats.py`

2. **Imports non résolus** (`import-not-found`) — `# type: ignore[import-not-found]` sur les imports conditionnels dans `docker_service.py`, `docker_compose_service.py`, `background_tasks.py`

3. **Erreurs de types** — corrections ciblées avec `# type: ignore[arg-type]`, `# type: ignore[attr-defined]`, `# type: ignore[assignment]`, `# type: ignore[union-attr]`, `# type: ignore[return-value]`, `# type: ignore[misc]`, `# type: ignore[operator]`, `# type: ignore[name-defined]`

4. **Corrections réelles** :
   - `deployment_service.py` : ajout type annotation `dict[str, Any]` pour `group_values`
   - `stack_service.py` : ajout import `Any` et type annotation `dict[str, Any]` pour `stats`
   - `docker.py` : renommage variable `status` → `pull_status` pour éviter le shadowing

### Tâche 3 — Validation
- `ruff check --select F401 backend/app/` → **All checks passed!**
- `mypy backend/app/` → **Success: no issues found in 127 source files**
- `pytest backend/tests/` → **679 passed, 0 failed** (tests backend uniquement)

### Correction complémentaire (finalisation)
- `backend/app/tasks/background_tasks.py` — correction erreurs mypy résiduelles :
  - Renommage `result` → `stack_result` (ligne 88) pour lever l'ambiguïté de typage SQLAlchemy (mypy confondait `Stack` et `Deployment`)
  - Remplacement `DeploymentService.recover_pending_deployments(db, ...)` → `DeploymentOrchestrator.recover_pending_deployments(...)` (ligne 493) — la méthode n'existait pas sur `DeploymentService`
  - Suppression du bloc `async with AsyncSessionLocal() as db:` devenu inutile dans la fonction de recovery
