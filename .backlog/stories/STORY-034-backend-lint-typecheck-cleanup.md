# STORY-034 : Nettoyage lint et type checking backend

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration technique
**Priorité :** Moyenne

## Description
Corriger les 12 imports inutilisés (F401 flake8) et réduire les erreurs mypy dans le code backend.

## Contexte technique

### Problèmes identifiés
- 12 imports inutilisés (F401) détectés par flake8/ruff dans les fichiers liés à l'EPIC-008
- Erreurs mypy sur les schémas Docker et les handlers API

### Fichiers impactés
| Fichier | Import inutilisé |
|---------|-----------------|
| `backend/app/api/v1/deployments.py` | `typing.List` |
| `backend/app/api/v1/targets/capabilities.py` | `TargetResponse` |
| `backend/app/api/v1/targets/connectivity.py` | `HTTPException` |
| `backend/app/core/abstractions.py` | `AsyncContextManager` |
| `backend/app/models/target.py` | `CapabilityType` |
| `backend/app/services/target_scan_parsers.py` | `ContainerRuntimeInfo` |
| `backend/app/services/target_service.py` | `TargetType` |
| + les fichiers de tests concernés | |

## Critères d'acceptation (AC)
- [ ] AC 1 : `flake8` ou `ruff check` ne signale plus d'erreurs F401 (imports inutilisés)
- [ ] AC 2 : Les erreurs mypy sur les fichiers liés à l'EPIC-008 sont corrigées ou justifiées avec `# type: ignore`
- [ ] AC 3 : Tous les tests backend passent après les modifications

## Tâches d'implémentation
- [ ] Supprimer les imports inutilisés dans les fichiers signalés :
  - `backend/app/api/v1/deployments.py` — `typing.List`
  - `backend/app/api/v1/targets/capabilities.py` — `TargetResponse`
  - `backend/app/api/v1/targets/connectivity.py` — `HTTPException`
  - `backend/app/core/abstractions.py` — `AsyncContextManager`
  - `backend/app/models/target.py` — `CapabilityType`
  - `backend/app/services/target_scan_parsers.py` — `ContainerRuntimeInfo`
  - `backend/app/services/target_service.py` — `TargetType`
  - + les fichiers de tests concernés
- [ ] Corriger ou annoter les erreurs mypy les plus critiques dans les schémas Docker et les handlers API
- [ ] Exécuter lint et tests pour valider
