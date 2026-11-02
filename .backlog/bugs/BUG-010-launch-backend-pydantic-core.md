# BUG-010 : Lancement backend : ModuleNotFoundError pydantic_core + module path uvicorn invalide

**Statut :** DONE
**Gravité :** Bloquant
**Epic Parent :** Aucune (bug outillage)
**Date :** 2026-11-02 (traçabilité rétroactive — diagnostiqué, corrigé et vérifié le même jour ; contrat consigné a posteriori)

## Reproduction

1. Environnement : PyCharm avec `.idea/windflow.iml` déclarant `.venv-test/lib/python3.11/site-packages` comme `<sourceFolder>` et `ADD_SOURCE_ROOTS=true` dans la run config ; venv principal `.venv` sous CPython 3.14.8.
2. Lancer le backend : `make backend` (ou lancement uvicorn via PyCharm, port 8010).
3. **Symptôme 1** : crash immédiat au démarrage avec `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`.
   - Reproduit expérimentalement : `PYTHONPATH=.venv-test/lib/python3.11/site-packages poetry run python -c "import fastapi"` → même erreur (le `pydantic_core` py3.11 est importé en priorité via PYTHONPATH mais son extension C cp311 est inchargeable sous CPython 3.14.8).
4. Après neutralisation du PYTHONPATH pollué (cause 1), relancer `make backend`.
5. **Symptôme 2** : uvicorn échoue avec `ERROR: Could not import module "backend.main"`.

## Comportement attendu

- `make backend` démarre uvicorn (port 8010) via le module `backend.app.main:app`, avec `--reload`.
- `GET /docs` répond HTTP 200 (Scalar) et l'OpenAPI est généré.
- `GET /api/v1/metrics` répond HTTP 200.
- Le lancement est résilient à un PYTHONPATH d'environnement pollué (injection par config IDE).

## Comportement actuel (avant correctif)

- Crash à l'import dès le démarrage : `ModuleNotFoundError: No module named 'pydantic_core._pydantic_core'`.
- Puis, PYTHONPATH assaini : `Could not import module "backend.main"` — au total, **le backend ne démarrait pas du tout** via `make backend` (ni via `make run`).

## Résolution

Corrigé le 2026-11-02. Traçabilité rétroactive : le cycle complet `NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE` a été parcouru lors de la session de debug (reproduction, cause racine identifiée, correctif appliqué, vérification HTTP) ; le contrat est consigné a posteriori au statut final `DONE`.

### Cause racine (2 problèmes distincts)

1. **PYTHONPATH contaminé par PyCharm** : `.idea/windflow.iml` déclarait `.venv-test/lib/python3.11/site-packages` comme `<sourceFolder>` ; avec `ADD_SOURCE_ROOTS=true` dans la run config, PyCharm injectait cette entrée dans PYTHONPATH. Sous CPython 3.14.8 (venv `.venv`), `pydantic_core` py3.11 était importé en priorité mais son extension C cp311 est inchargeable → `ModuleNotFoundError`.
2. **Bug préexistant du Makefile** : les cibles `backend:` (~ligne 183) et `run:` (~ligne 344) utilisaient `$(BACKEND_DIR).main:app` = `backend.main:app`, or `backend/` n'est pas un package (pas de `__init__.py`) — le module réel est `backend.app.main:app`. Après résolution du problème 1, `make backend` échouait donc avec `Could not import module "backend.main"`.

### Correctifs appliqués

- `Makefile`, cible `backend:` → `env -u PYTHONPATH poetry run uvicorn backend.app.main:app --reload ...` (sanitation PYTHONPATH + module path corrigé).
- `Makefile`, cible `run:` → même sanitation `env -u PYTHONPATH` + module `backend.app.main:app`.
- `.idea/windflow.iml` (fichier non suivi git, config IDE locale) : `<sourceFolder .../.venv-test/lib/python3.11/site-packages>` remplacé par `<excludeFolder .../.venv-test>`.

### Vérification

- Backend démarre avec succès : `GET /docs` → HTTP 200, `GET /api/v1/metrics` → HTTP 200, OpenAPI généré.
- Résilience validée : lancement testé même avec un PYTHONPATH volontairement pollué (la sanitation `env -u PYTHONPATH` protège le lancement).
- Aucun process résiduel, port 8010 libéré.

### Recommandations résiduelles

- À terme, `make purge` + `poetry install` pour reconstruire un venv homogène : le venv `.venv` mélange actuellement `lib/python3`, `python3.13` et `python3.14`.
