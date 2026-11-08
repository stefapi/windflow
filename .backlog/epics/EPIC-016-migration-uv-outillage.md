# EPIC-016 : [DONE] Migration UV & outillage Python

**Statut :** DONE
**Priorité :** Haute

## Vision

Abandonner Poetry au profit d'UV pour la gestion des dépendances et environnements Python : résolution plus rapide, lock cross-platform (`uv.lock`), gestion native de l'interpréteur (`.python-version` 3.11) et alignement avec le standard PEP 621. L'épic couvre également la mise en conformité de l'outillage connexe : Makefile, Dockerfile, CI Gitea, scripts et docs.

## Liste des Stories liées

- [x] STORY-255 : Migration Poetry → UV (pyproject PEP 621, uv.lock, Makefile, Dockerfile, CI, scripts, docs, garde-fous)

## Critères de succès (Definition of Done)

- [x] Aucune référence Poetry active dans le dépôt (hors archives historiques : CHANGELOG, backlog, docs d'arbitrage)
- [x] `uv lock` + `uv sync` reproductibles (Python 3.11 épinglé)
- [x] CI Gitea, Dockerfile et Makefile 100 % UV
- [ ] Suite unitaire backend au vert (hors échec heartbeat préexistant — échec déterministe constaté aussi sous `.venv-test`, à tracer en BUG dédié)
