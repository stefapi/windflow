# 50 — Workflow de développement et outillage

## 1. Makefile, point d'entrée unique

Toutes les commandes récurrentes sont des cibles du `Makefile` à la racine ; `make help` liste tout. Chaque cible porte un commentaire `## description`. Toute nouvelle commande récurrente devient une cible, jamais une simple ligne de documentation.

| Cible | Effet |
| --- | --- |
| `setup` | Dépendances (uv sync + pnpm install) et environnement |
| `dev` / `backend` / `frontend` / `cli` | Démarrer les services de développement |
| `format` / `lint` / `typecheck` | Qualité du code (backend + frontend + CLI) |
| `test` / `backend-test-*` / `frontend-test-*` / `cli-test` | Tests |
| `migrate` | Générer/appliquer une migration Alembic |
| `generate-api` / `generate-types` | Régénérer le client TS / les types partagés |
| `backlog` / `backlog-check` | Génération déterministe du kanban et contrôle des invariants (`01` §8) |
| `check-harness` / `harness-test` | Contrôle du corpus de pilotage et tests des garde-fous |
| `ci-fast` | Retour intermédiaire : lint, types, corpus, backlog et tests unitaires sans couverture ; ne remplace pas les portes d'acceptation |
| `ci-quick` / `ci-full` | CI rapide (lint) / CI complète (lint + tests + couverture + sécurité) |
| `check` | Portes locales complètes avant acceptation : `ci-full` + types + backlog + harness |
| `docker-*`, `minimal` / `dev-full` / `prod`, `enable-*` / `disable-*` | Conteneurs, profils de démarrage, extensions (database, cache, monitoring, secrets, SSO) |

## 2. Commandes soumises à accord explicite

L'agent ne lance jamais sans accord explicite du propriétaire : toute suppression de volume ou de données (`make clean-data`, `docker compose down -v`) ; `rm -rf` hors d'un dossier temporaire ; `git push --force` ou réécriture d'historique ; `alembic downgrade` hors base de test ; toute commande visant la production (`make prod`, `make docker-prod`, déploiements).

## 3. Paquets et lockfiles

`uv` pour Python, `pnpm` pour le frontend ; `uv.lock` et `pnpm-lock.yaml` commités. **Interdit** : `pip`, `npm`, `yarn`, `poetry`, installation globale, mélange de gestionnaires, édition manuelle d'un lockfile (`00` §5).

## 4. Fichiers de projet obligatoires

| Fichier | Contenu |
| --- | --- |
| `README.md` | Présentation, prérequis, démarrage, liens vers specs et règles |
| `CONTRIBUTING.md` | Workflow, commits, renvoi vers `.roo/rules/` |
| `SECURITY.md` | Politique de signalement (`40`) |
| `CHANGELOG.md` | Keep a Changelog, section « Unreleased » |
| `env.example`, `.env.prod.example` | Toutes les variables d'environnement (§6) |
| `COMMIT_CONVENTION.md` | Format des commits (§5) |

## 5. Commits et branches

- Conventional Commits 1.0 : `<type>(<portée>): <description>` (`COMMIT_CONVENTION.md`). Types : `feat`, `fix`, `refactor`, `perf`, `test`, `docs`, `build`, `ci`, `chore`, `revert`.
- Branches : travail sur `<type>/<ID>-<slug>` (ex. `feat/STORY-401-import-stacks-yaml`) ; pied de commit `Refs: <ID>` obligatoire (EPIC/STORY/BUG du contrat).
- L'agent crée ses commits sur sa branche ; il ne pousse jamais sur `main` et ne fusionne jamais.
- Hook `commit-msg` (husky) : validation du format Conventional Commits.

## 6. Variables d'environnement

Règle d'or : une variable ajoutée au code est ajoutée **dans le même commit** à `Settings` (`backend/app/config.py`, typée — `07` §5), à `env.example` (commentaire + valeur d'exemple non secrète) et, si elle concerne le déploiement, à `.env.prod.example` et aux compose concernés.

## 7. CI

Gitea Actions (`.gitea/workflows/`) : `ci.yml`, `test.yml`, `quality-gates.yml`, `build.yml`, `deploy.yml`. En local, la référence reste `make check` (et `make ci-fast` en intermédiaire). Le pipeline ne prouve ni le chargement du corpus d'agents ni les protections de fusion de la forge : voir [la matrice de validation](../../docs/dev/controles-validation.md).

## 8. Conteneurs

- Constructions multi-étapes ; images de base épinglées ; utilisateur non root quand c'est possible.
- Compose : `docker-compose.yml` (base), `docker-compose-dev.yml`, `docker-compose.minimal.yml`, `docker-compose.prod.yml`, `docker-compose.extensions.yml` ; `.dockerignore` tenu à jour.
- Extensions activables par `make enable-*` (database, cache, monitoring, secrets, SSO).
