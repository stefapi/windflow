# BUG-001 : 35 échecs préexistants suite unitaire backend (herméticité DISABLE_AUTH + enveloppes spec-09)

**Statut :** DONE
**Gravité :** Majeur

> Détectés lors de la clôture de STORY-131.3, diagnostiqués et corrigés dans une session de debug dédiée.

## Reproduction

1. Disposer d'un environnement de développement avec un `.env` local (git-ignored) contenant `DISABLE_AUTH=true`
2. Lancer `poetry run pytest backend/tests/unit`
3. Résultat observé : **1783 passed / 35 failed**, répartis ainsi :
   - `backend/tests/unit/test_stack_actions.py` : 19 échecs
   - `backend/tests/unit/test_stacks_archive.py` : 9 échecs
   - `backend/tests/unit/test_api/test_users.py` : 3 échecs
   - `backend/tests/unit/test_api/test_auth_isolation.py` : 2 échecs
   - `backend/tests/unit/test_stacks_duplicate.py` : 1 échec
   - `backend/tests/unit/test_api/test_debug_story1033.py` : 1 échec

## Comportement attendu

- `poetry run pytest backend/tests/unit` → **0 failed**, quelle que soit la valeur de `DISABLE_AUTH` dans l'environnement local (herméticité des tests).
- Les assertions de contrat HTTP respectent l'enveloppe spec-09 en vigueur : `{"data": ...}` / `{"error": {"message"}}`.

## Comportement actuel

35 échecs, conséquence de deux causes racines distinctes :

### Cause racine n°1 (25 échecs) — Tests non-hermétiques au `DISABLE_AUTH` ambiant

Le `.env` local (git-ignored) contient `DISABLE_AUTH=true`. `SettingsConfigDict` (`backend/app/config.py`) le charge, `get_current_user()` court-circuite alors la vérification JWT et `get_first_superadmin()` échoue (aucun superadmin en base de test) → erreurs 500 en chaîne. 6 fichiers de test ne forçaient pas `disable_auth=False`, contrairement aux ~30 fichiers frères qui utilisent la fixture autouse `_jwt_mode` (pattern STORY-122.2/123.4).

Fichiers concernés :

- `backend/tests/unit/test_stack_actions.py`
- `backend/tests/unit/test_stacks_archive.py`
- `backend/tests/unit/test_stacks_duplicate.py`
- `backend/tests/unit/test_api/test_users.py`
- `backend/tests/unit/test_api/test_auth_isolation.py`
- `backend/tests/unit/test_api/test_debug_story1033.py`

### Cause racine n°2 (10 échecs) — `test_stack_actions.py` jamais migré vers les enveloppes spec-09

Fichier créé avant l'introduction des enveloppes (STORY-126.2, commit 44c9c0e) et seul de la famille stacks non migré. Il lisait `response.json()["success"]` / `["detail"]` alors que le contrat actuel est `{"data": ...}` / `{"error": {"message"}}` via les helpers `unwrap()` / `error_message()` de `backend/tests/conftest.py`.

## Résolution

### Corrections apportées (décision : « fix test »)

- **Cause n°1** : ajout de la fixture autouse `_jwt_mode` aux 6 fichiers listés ci-dessus (alignement sur le pattern des fichiers frères).
- **Cause n°2** : migration de 9 assertions de `test_stack_actions.py` vers le contrat spec-09 via `unwrap()` / `error_message()` (`backend/tests/conftest.py`), + nettoyage des imports F401.

### Justification de la décision « fix test » (et non « fix code »)

- Le pattern `_jwt_mode` est déjà celui des ~30 fichiers frères (introduit en STORY-122.2/123.4) : les 6 fichiers étaient en retard sur la convention, le code de production est correct.
- Le contrat d'enveloppe spec-09 est la norme depuis STORY-126.2 (commit 44c9c0e, vérifié via historique git) : `test_stack_actions.py` était le seul fichier stacks non migré.

### Fichiers modifiés

- `backend/tests/unit/test_stack_actions.py` — fixture `_jwt_mode` + migration enveloppes spec-09 + nettoyage imports F401
- `backend/tests/unit/test_stacks_archive.py` — fixture `_jwt_mode`
- `backend/tests/unit/test_stacks_duplicate.py` — fixture `_jwt_mode`
- `backend/tests/unit/test_api/test_users.py` — fixture `_jwt_mode`
- `backend/tests/unit/test_api/test_auth_isolation.py` — fixture `_jwt_mode`
- `backend/tests/unit/test_api/test_debug_story1033.py` — fixture `_jwt_mode`

### Validation finale

- `pytest backend/tests/unit` → **1818 passed / 0 failed**
- `make backend-lint` → exit 0
- Herméticité vérifiée : la suite a été repassée avec le `.env` local dégradé (`DISABLE_AUTH=true`) toujours actif.

## Voir aussi

- BUG-002 : anomalie Makefile `.ONESHELL:` découverte pendant ce debug (gate lint faussé), non corrigée ici.
