# STORY-033 : Correction des tests backend défaillants

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Correction de bugs
**Priorité :** Haute (bloquant)

## Description
Corriger les 2 tests backend qui échouent ou génèrent des erreurs de collection.

## Contexte technique

### Couches impactées
- **Backend uniquement** (tests unitaires)

### Problèmes identifiés

#### Problème 1 — `test_compute_service.py` : `ImportError` sur `_classify_containers` et `_format_memory`

Le fichier [`test_compute_service.py`](backend/tests/unit/test_services/test_compute_service.py:15) importe deux symboles inexistantes depuis `compute_service` :

```python
from app.services.compute_service import (
    _classify_containers,  # ❌ n'existe pas — c'est classify_containers (sans underscore)
    _format_memory,        # ❌ n'existe pas — c'est format_memory dans compute_helpers.py
    get_compute_global,
    get_compute_stats,
)
```

**Analyse détaillée :**

1. **`_classify_containers`** → La fonction réelle est [`classify_containers`](backend/app/services/container_classifier.py:61) (sans underscore), définie dans [`container_classifier.py`](backend/app/services/container_classifier.py). Elle **est** ré-exportée depuis [`compute_service.py`](backend/app/services/compute_service.py:30) (ligne 30-34) pour compatibilité, mais sous le nom `classify_containers` (sans underscore).

2. **`_format_memory`** → La fonction réelle est [`format_memory`](backend/app/helper/compute_helpers.py:18) (sans underscore), définie dans [`compute_helpers.py`](backend/app/helper/compute_helpers.py). Elle **n'est pas** ré-exportée depuis `compute_service.py`.

**Correction attendue :**
- Remplacer `_classify_containers` par `classify_containers` dans l'import
- Remplacer l'import de `_format_memory` depuis `compute_service` par `format_memory` depuis `app.helper.compute_helpers`
- Mettre à jour les appels dans les tests (classe `TestFormatMemory` et classe `TestClassifyContainers`)

#### Problème 2 — `test_stacks_api_variables_rendering.py` : champs manquants dans `expected_fields`

Le test [`test_stack_summary_response_fields`](backend/tests/unit/test_stacks_api_variables_rendering.py:15) compare les champs du schéma [`StackSummaryResponse`](backend/app/schemas/stack.py:429) avec un set `expected_fields` qui ne contient pas les champs `is_archived` et `archived_at`, ajoutés ultérieurement au schéma (lignes 504-513 de [`stack.py`](backend/app/schemas/stack.py:504)).

**Champs actuels de `StackSummaryResponse`** (dans l'ordre du fichier) :
`id`, `name`, `description`, `version`, `category`, `tags`, `icon_url`, `screenshots`, `author`, `license`, `downloads`, `is_archived`, `archived_at`, `rating`, `created_at`, `updated_at`

**Correction attendue :**
- Ajouter `"is_archived"` et `"archived_at"` au set `expected_fields` dans le test

### Fichiers de référence (patterns)
- Pattern de test unitaire service : [`test_container_classifier.py`](backend/tests/unit/test_services/test_container_classifier.py) — imports corrects depuis le module source
- Pattern de test API : [`test_stacks_api_variables_rendering.py`](backend/tests/unit/test_stacks_api_variables_rendering.py) — vérification de champs Pydantic
- Fixtures partagées : [`conftest.py`](backend/tests/conftest.py)

### Exigences sécurité
- **Aucune exigence sécurité** — Cette story corrige uniquement des fichiers de test. Aucun endpoint, aucune donnée sensible, aucune authentification impliquée.

### Dépendances
- Aucune dépendance envers d'autres stories
- Story bloquante pour la validation de la pipeline CI (tests doivent passer)

---

## Critères d'acceptation (AC)
- [x] AC 1 : `test_compute_service.py` ne génère plus d'ImportError pour `_classify_containers` et `_format_memory` — tous les tests du fichier passent
- [x] AC 2 : `test_stacks_api_variables_rendering.py` — le test `test_stack_summary_response_fields` passe (ajouter `archived_at` et `is_archived` au set attendu)
- [x] AC 3 : Tous les tests backend passent (0 failed, 0 errors)

---

## Tâches d'implémentation détaillées

### Tâche 1 : Corriger les imports dans `test_compute_service.py`
**Objectif :** Remplacer les imports cassés `_classify_containers` et `_format_memory` par les noms corrects.

| Fichier | Action | Description |
|---------|--------|-------------|
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 16 : remplacer `_classify_containers` par `classify_containers` dans l'import depuis `compute_service` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 17 : remplacer l'import de `_format_memory` depuis `compute_service` par `from app.helper.compute_helpers import format_memory` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 72 : remplacer `_format_memory(0)` par `format_memory(0)` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 75 : remplacer `_format_memory(-100)` par `format_memory(-100)` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 79 : remplacer `_format_memory(512 * 1024)` par `format_memory(512 * 1024)` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 84 : remplacer `_format_memory(100 * 1024 * 1024)` par `format_memory(100 * 1024 * 1024)` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Ligne 89 : remplacer `_format_memory(2 * 1024 * 1024 * 1024)` par `format_memory(2 * 1024 * 1024 * 1024)` |
| `backend/tests/unit/test_services/test_compute_service.py` | Modifier | Lignes 101, 109, 115, 125, 134, 144 : remplacer `_classify_containers` par `classify_containers` dans tous les appels |

**Exigences sécurité :** Aucune
**Dépendances :** Aucune

---

### Tâche 2 : Ajouter `is_archived` et `archived_at` au set `expected_fields`
**Objectif :** Aligner le set de champs attendus avec le schéma `StackSummaryResponse` actuel.

| Fichier | Action | Description |
|---------|--------|-------------|
| `backend/tests/unit/test_stacks_api_variables_rendering.py` | Modifier | Ligne 18-33 : ajouter `"is_archived"` et `"archived_at"` au set `expected_fields` dans le test `test_stack_summary_response_fields` |

**Détail de la modification :**
```python
expected_fields = {
    "id",
    "name",
    "description",
    "version",
    "category",
    "tags",
    "icon_url",
    "screenshots",
    "author",
    "license",
    "downloads",
    "is_archived",    # ← ajout
    "archived_at",    # ← ajout
    "rating",
    "created_at",
    "updated_at",
}
```

**Exigences sécurité :** Aucune
**Dépendances :** Aucune

---

### Tâche 3 : Valider que tous les tests backend passent
**Objectif :** Exécuter la suite de tests complète et vérifier 0 failed, 0 errors.

| Fichier | Action | Description |
|---------|--------|-------------|
| N/A (exécution) | Exécuter | Lancer `cd backend && python -m pytest tests/ -v --tb=short` et vérifier que tous les tests passent |

**Commande de validation :**
```bash
cd backend && python -m pytest tests/ -v --tb=short
```

**Critère de succès :** `0 failed, 0 errors, 0 warnings` dans le résumé pytest.

**Exigences sécurité :** Aucune
**Dépendances :** Tâche 1 + Tâche 2

---

## Tests à écrire

> **Note :** Cette story est une correction de tests existants. Aucun nouveau test n'est requis. La validation se fait par l'exécution de la suite existante.

### Validation des corrections

| Test | Fichier | Validation |
|------|---------|------------|
| `TestFormatMemory` (5 tests) | `test_compute_service.py` | Passe après correction import `format_memory` |
| `TestClassifyContainers` (6 tests) | `test_compute_service.py` | Passe après correction import `classify_containers` |
| `TestGetComputeStats` (3 tests) | `test_compute_service.py` | Passe (déjà correct, pas d'impact) |
| `TestGetComputeGlobal` (5 tests) | `test_compute_service.py` | Passe (déjà correct, pas d'impact) |
| `test_stack_summary_response_fields` | `test_stacks_api_variables_rendering.py` | Passe après ajout des 2 champs |

### Commandes de validation
```bash
# Tests spécifiques impactés
cd backend && python -m pytest tests/unit/test_services/test_compute_service.py tests/unit/test_stacks_api_variables_rendering.py -v

# Suite complète
cd backend && python -m pytest tests/ -v --tb=short
```

---

## État d'avancement technique
- [x] Tâche 1 : Corriger les imports `_classify_containers` → `classify_containers` et `_format_memory` → `format_memory` dans `test_compute_service.py`
- [x] Tâche 2 : Ajouter `is_archived` et `archived_at` au set `expected_fields` dans `test_stacks_api_variables_rendering.py`
- [x] Tâche 3 : Valider que tous les tests backend passent (0 failed, 0 errors)

---

## Notes d'implémentation

### Fichiers modifiés
- `backend/tests/unit/test_services/test_compute_service.py` — Correction des imports et appels
- `backend/tests/unit/test_stacks_api_variables_rendering.py` — Ajout de 2 champs au set `expected_fields`

### Décisions techniques
- **Import `format_memory`** : Importé directement depuis `app.helper.compute_helpers` (module source) plutôt que depuis `compute_service` qui ne le ré-exporte pas.
- **Import `classify_containers`** : Conservé depuis `app.services.compute_service` (ré-export existant), seul le nom a été corrigé (suppression du préfixe `_`).
- **Aucun fichier source modifié** : Conformément aux instructions, seuls les fichiers de test ont été corrigés.

### Divergences
- Aucune divergence détectée. Les corrections appliquées correspondent exactement aux tâches décrites.

### Résultat des tests
- **679 passed, 0 failed, 0 errors** en 13.32s
- Les 19 tests des 2 fichiers corrigés passent tous (5 `TestFormatMemory` + 6 `TestClassifyContainers` + 8 autres `test_compute_service` + 6 `test_stacks_api_variables_rendering`)
- Lint ruff non applicable (module non installé dans le venv)
