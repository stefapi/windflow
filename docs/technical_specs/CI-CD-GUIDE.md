# Guide CI/CD WindFlow — Gitea Actions

> **Statut** : Spécification technique · Partiellement implémenté (workflows et cibles `make ci-*` livrés ; jobs `deploy-*` de `ci.yml` = notifications seulement ; multi-arch et SonarQube déclarés mais non activés sur ce dépôt — voir §3 et §8)
> **Périmètre** : Runbook CI/CD Gitea Actions et équivalent local via Makefile (workflows, jobs, images, dépannage).
> **Référence de fond** : [general_specs — ch. 05 stack technologique](../general_specs/05-stack-technologique.md) · [ch. 16 déploiement](../general_specs/16-deploiement.md)
> **Dernière mise à jour** : 2026-08-23 — **refondu vague 6** ([PLAN-REFONTE-TECHNICAL-SPECS.md](../../PLAN-REFONTE-TECHNICAL-SPECS.md)) · traçabilité : R9, R10, P4, G31-G35

Ce document décrit le **COMMENT** du CI/CD (workflows réels du dépôt, cibles Makefile, jobs). Les choix de fond — outillage cible, principe multi-arch, profils de déploiement — sont définis aux chapitres [05](../general_specs/05-stack-technologique.md) et [16](../general_specs/16-deploiement.md) et ne sont pas repris ici. Le CI est **Gitea Actions** (répertoire `.gitea/workflows/`), pas GitHub Actions ni GitLab CI.

## Sommaire

1. [Vue d'ensemble](#1-vue-densemble)
2. [Architecture du pipeline](#2-architecture-du-pipeline)
3. [Inventaire réel des workflows](#3-inventaire-réel-des-workflows)
4. [Outillage lint réel vs cible ruff (G31)](#4-outillage-lint-réel-vs-cible-ruff-g31)
5. [Configuration Gitea (runner, secrets)](#5-configuration-gitea-runner-secrets)
6. [Pipeline local `make ci-*`](#6-pipeline-local-make-ci-)
7. [Détails des jobs](#7-détails-des-jobs)
8. [Multi-arch (G33)](#8-multi-arch-g33)
9. [Monitoring et rapports](#9-monitoring-et-rapports)
10. [Dépannage](#10-dépannage)
11. [Bonnes pratiques](#11-bonnes-pratiques)
12. [Table des commandes](#12-table-des-commandes)
13. [Intégration IDE et hooks Git](#13-intégration-ide-et-hooks-git)

---

## 1. Vue d'ensemble

WindFlow utilise **Gitea Actions** pour l'intégration continue et le build des images. Chaque vérification du pipeline est reproductible en local via les cibles `make ci-*` du [`Makefile`](../../Makefile) — le CI ne doit jamais être une boîte noire : **toujours exécuter `make ci-quick` avant de pusher**.

L'outillage effectivement branché aujourd'hui (backend) : **Black, isort, Flake8, Pylint, Bandit, mypy, Safety** ; frontend : **ESLint, Stylelint (css-check), vue-tsc (typecheck), Vitest, pnpm audit**. Voir §4 pour l'écart avec la cible `ruff` du ch. 05.

## 2. Architecture du pipeline

Le workflow principal [`ci.yml`](../../.gitea/workflows/ci.yml) se déclenche sur **push** et **pull request** vers `main` et `develop` :

```
┌─────────────────┐     ┌─────────────────┐
│  Lint Backend   │     │  Lint Frontend  │
│   (Python)      │     │  (TypeScript)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
    ┌─────────┐            ┌─────────┐
    │  Test   │            │  Test   │
    │ Backend │            │Frontend │
    └────┬────┘            └────┬────┘
         │                      │
         └──────────┬───────────┘
                    ▼
          ┌───────────────┐     ┌─────────────┐
          │  Build Docker │     │  Security   │
          │    Images     │     │   Audit     │
          └───────┬───────┘     └──────┬──────┘
                  └──────────┬─────────┘
                             ▼
                    ┌───────────────┐
                    │ Deploy (dev / │
                    │   staging)    │
                    └───────────────┘
```

Points factuels importants (état actuel du code) :

- `build-docker` ne s'exécute que sur **push** vers `main`/`develop` (pas sur les PR) ;
- `security-audit` tourne **en parallèle** des builds, sans dépendance ;
- les jobs `deploy-dev` / `deploy-staging` de `ci.yml` ne font aujourd'hui qu'afficher une **notification** (echo) — le déploiement réel vit dans [`deploy.yml`](../../.gitea/workflows/deploy.yml) (§3) ;
- Pylint (`--fail-under=8.0 || true`), Bandit et Safety sont en mode **non bloquant** dans `ci.yml` (rapport généré, job non échoué) ; Black, isort, Flake8 et le seuil coverage 80 % sont **bloquants**.

## 3. Inventaire réel des workflows

Le répertoire [`.gitea/workflows/`](../../.gitea/workflows/) contient **5 workflows** (les 4 additionnels n'étaient pas documentés avant cette refonte — R10/G34) :

| Workflow | Déclencheurs | Contenu |
|---|---|---|
| [`ci.yml`](../../.gitea/workflows/ci.yml) | push/PR `main`, `develop` | Pipeline complet : lint backend/frontend → tests (PG 15 + Redis 7 en services) → build images locales → security audit → jobs deploy (notifications ⚠️) |
| [`test.yml`](../../.gitea/workflows/test.yml) | push/PR `main`, `develop` | `backend-tests` (flake8 bloquant ; pylint, mypy `continue-on-error` ; cache venv Poetry), `frontend-tests` (cache pnpm, Vitest + coverage), `integration-tests` (stack `docker compose` réelle + health check sur `:8080/health`) ; upload Codecov `continue-on-error` |
| [`build.yml`](../../.gitea/workflows/build.yml) | push `main`/`develop` + tags `v*`, PR `main` | Build **et push registre** (login `GITEA_TOKEN`) des 3 images via `docker/build-push-action@v5`, tags `docker/metadata-action` (branch, semver, sha, `latest`), **`platforms: linux/amd64,linux/arm64`**, cache GHA, job `build-summary` qui agrège |
| [`quality-gates.yml`](../../.gitea/workflows/quality-gates.yml) | push/PR + `schedule` dimanche 00:00 | `sonarqube` (scan + quality gate `continue-on-error`), `code-quality` (Black/isort/Flake8/Pylint/Bandit), `dependency-check` (Safety + pnpm audit), `coverage-check` (rejoue les tests, seuil 80 % explicite), `docker-security-scan` (Trivy sur l'image API, SARIF), `quality-summary` |
| [`deploy.yml`](../../.gitea/workflows/deploy.yml) | `workflow_run` après « Tests »/« Build Docker Images » + `workflow_dispatch` | Déploiement SSH réel (`webfactory/ssh-agent`) : dev (branche `develop`), staging (`main`, backup `pg_dump` + smoke tests), production (**manuel uniquement**, maintenance mode + backup + smoke tests) ; notifications Slack `continue-on-error` |

> **⚠️ À adapter à votre instance** : `build.yml` référence `REGISTRY: gitea.yourdomain.com` et `deploy.yml` des URLs `*.windflow.example.com` — ces workflows sont des gabarits à configurer (secrets, hôtes) avant activation réelle. Les URLs/secrets sont listés en §5.

**Chevauchement assumé** : `ci.yml` et `test.yml` recouvrent en partie les mêmes vérifications (lint + tests backend/frontend), et `ci.yml`/`build.yml` buildent tous deux les images (localement vs avec push registre). C'est l'état actuel du dépôt ; une convergence (un seul pipeline d'entrée) est souhaitable — tracée pour la Roadmap.

## 4. Outillage lint réel vs cible ruff (G31)

> **⚠️ Écart connu (G31)** : le [ch. 05](../general_specs/05-stack-technologique.md) fixe la cible « ruff (remplace flake8 + isort) et ruff-format via pre-commit ». **Ruff n'est pas branché aujourd'hui** : `ruff = "^0.15.13"` figure dans les dev-dépendances de [`pyproject.toml`](../../pyproject.toml) (et un `.ruff_cache/` existe), mais il n'y a **aucune section `[tool.ruff]`**, aucun appel à ruff dans le [`Makefile`](../../Makefile) ni dans les workflows. La migration est à inscrire au backlog — tracée ici.

Outillage **réellement actif** (source : Makefile + workflows) :

| Outil | Rôle | Bloquant ? | Config |
|---|---|---|---|
| Black | Formatage | Oui (`--check`) | défaut |
| isort | Imports | Oui (`--check-only`) | `[tool.isort]` profile black ([`pyproject.toml`](../../pyproject.toml)) |
| Flake8 | Lint PEP 8 | Oui | [`.flake8`](../../.flake8) (`ignore = E501,E402,W503,E203,E712`) |
| Pylint | Qualité | Non (`|| true` / `--exit-zero`) | [`.pylintrc`](../../.pylintrc) (`fail-under=10.0`) ; seuil 8.0 passé en argument Makefile/CI |
| Bandit | Sécurité | Non (rapport JSON) | `-ll` en local |
| mypy | Typage | Non (`continue-on-error`) | `[tool.mypy]` + overrides |
| Safety | Dépendances Python | Non (`|| true`) | — |
| ESLint / Stylelint / vue-tsc | Lint frontend | ESLint+CSS+TS bloquants dans `ci.yml` ; `continue-on-error` dans `test.yml` | [`frontend/package.json`](../../frontend/package.json) scripts |

Frontend : `pnpm lint-check`, `pnpm css-check`, `pnpm typecheck`, `pnpm test:ci`, `pnpm audit --audit-level=moderate`.

## 5. Configuration Gitea (runner, secrets)

### 5.1 Activer Gitea Actions et le runner

```ini
# app.ini (instance Gitea)
[actions]
ENABLED = true
```

```bash
# Enregistrer et démarrer un runner (act_runner)
./act_runner register --no-interactive \
  --instance https://votre-gitea.example.com \
  --token VOTRE_RUNNER_TOKEN \
  --name windflow-runner
./act_runner daemon
```

### 5.2 Secrets requis par workflow

| Workflow | Secrets | Usage |
|---|---|---|
| `build.yml` | `GITEA_TOKEN` | Login au registre de conteneurs (push des images) |
| `deploy.yml` | `DEV_/STAGING_/PROD_SSH_PRIVATE_KEY`, `*_SERVER_HOST`, `*_SERVER_USER`, `*_DEPLOY_PATH` | Déploiement SSH par environnement |
| `deploy.yml` | `SLACK_WEBHOOK` | Notifications de déploiement |
| `quality-gates.yml` | `SONAR_TOKEN`, `SONAR_HOST_URL` | Analyse SonarQube |
| `test.yml` | `CODECOV_TOKEN` (si utilisé) | Upload coverage |

## 6. Pipeline local `make ci-*`

Les cibles `ci-*` du [`Makefile`](../../Makefile) rejouent les mêmes vérifications que le CI, localement :

```bash
make ci-quick   # lint backend + frontend seulement
make ci-full    # lint + tests + security (backend + frontend)
```

Workflow recommandé :

```bash
# 1. Branche de feature
git checkout -b feature/ma-nouvelle-feature && make setup

# 2. Pendant le développement (itératif)
make ci-quick

# 3. Avant de commit/push
make ci-full

# 4. PR dans Gitea → le pipeline automatique s'exécute
```

## 7. Détails des jobs

### 7.1 `lint-backend` (ci.yml)

Vérifie le code Python : **Black** (`--check`), **isort** (`--check-only`), **Flake8**, **Pylint** (`--fail-under=8.0 || true` — non bloquant), **Bandit** (rapport `bandit-report.json` uploadé en artifact). Échoue si : code mal formaté, erreurs Flake8.

### 7.2 `lint-frontend` (ci.yml)

**ESLint** (`pnpm lint-check`), **Stylelint** (`pnpm css-check`), **vue-tsc** (`pnpm typecheck`). Python 3.11 / Node 20 / pnpm 9 partout.

### 7.3 `test-backend` (ci.yml)

Services **PostgreSQL 15** + **Redis 7-alpine** (health checks). `pytest backend/tests/` avec `--cov=backend --cov-report=xml,html,term` et **`--cov-fail-under=80`** (bloquant — [ci.yml:167](../../.gitea/workflows/ci.yml)). Artifacts : `coverage.xml`, `htmlcov/`.

> **Cible general_specs** : couverture > 85 % ([ch. 05](../general_specs/05-stack-technologique.md)) ; le seuil CI actuel est 80 % (G32).

### 7.4 `test-frontend` (ci.yml)

Vitest via `pnpm test:ci` ; artifact `frontend/coverage/`.

### 7.5 `build-docker` (ci.yml) & `build.yml`

Trois images, une par Dockerfile d'[`infrastructure/docker/`](../../infrastructure/docker/) : `windflow/api` ([Dockerfile.api](../../infrastructure/docker/Dockerfile.api)), `windflow/worker` ([Dockerfile.worker](../../infrastructure/docker/Dockerfile.worker)), `windflow/frontend` ([Dockerfile.frontend](../../infrastructure/docker/Dockerfile.frontend)).

- `ci.yml` : build local seulement, tags `:${{ github.sha }}` et `:latest` ;
- `build.yml` : build + **push** vers le registre, tags `metadata-action` (branch, `vX.Y.Z` sur tags, `{{branch}}-{{sha}}`, `latest` sur la branche par défaut), **multi-arch amd64/arm64**, cache GHA.

### 7.6 `security-audit` (ci.yml) & `dependency-check`/`docker-security-scan` (quality-gates.yml)

**Safety** (dépendances Python, `|| true`), **pnpm audit** (`--audit-level=moderate`, `|| true`), **Trivy** sur l'image API (format SARIF, artifact). Non bloquants à ce jour.

### 7.7 Jobs `deploy-*`

Voir §3 (`deploy.yml` = déploiement SSH réel avec backup/maintenance/smoke tests ; jobs `deploy-*` de `ci.yml` = simples notifications ⚠️). Le détail des procédures de déploiement (install, mise à jour, sauvegarde) relève du [ch. 16](../general_specs/16-deploiement.md) — non dupliqué ici.

## 8. Multi-arch (G33)

Le principe fondateur est **amd64 + arm64** (compatibilité ARM/Raspberry Pi — [ch. 04](../general_specs/04-architecture.md), [ch. 05](../general_specs/05-stack-technologique.md)). État réel :

- **Build** : couvert — `build.yml` passe `platforms: linux/amd64,linux/arm64` aux trois images (extrait réel) :

```yaml
# .gitea/workflows/build.yml (extrait, job build-api)
      - name: Build and push API image
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./infrastructure/docker/Dockerfile.api
          push: ${{ github.event_name != 'pull_request' }}
          platforms: linux/amd64,linux/arm64
```

- **Tests** : ⚠️ **non couverts** — aucun workflow n'utilise la matrice `arch: [amd64, arm64]` illustrée au ch. 05 ; les jobs tournent sur `ubuntu-latest` (amd64) uniquement. Comblement à planifier (backlog).

## 9. Monitoring et rapports

- **Onglet Actions** du dépôt Gitea : logs par job, téléchargement des artifacts (coverage, `bandit-report.json`, rapports Safety/npm audit/Trivy SARIF).
- **Coverage local** : `make backend-test-coverage` (ouvre `htmlcov/index.html`), `coverage report --show-missing` pour les fichiers non couverts.
- **Notifications** : à configurer côté Gitea (profil → notifications) ; les workflows `deploy.yml` notifient aussi via Slack (`SLACK_WEBHOOK`, `continue-on-error`).

## 10. Dépannage

### Pipeline bloqué / runner indisponible

```bash
./act_runner list        # vérifier les runners actifs
./act_runner daemon &    # (re)démarrer un runner
```

### Tests qui échouent

```bash
make ci-test-backend     # reproduire localement (même seuil coverage 80 %)
make ci-test-frontend
```

### Build Docker échoue

```bash
make ci-build-docker     # build local des 3 images
docker build -f infrastructure/docker/Dockerfile.api .   # une seule image
```

### Coverage insuffisant

```bash
make backend-test-coverage
coverage report --show-missing   # identifier les fichiers non couverts
```

## 11. Bonnes pratiques

1. **`make ci-quick` avant chaque push, `make ci-full` avant chaque PR** — le CI ne doit jamais découvrir une erreur reproduisible localement.
2. **Commits atomiques** suivant la convention Conventional Commits (validée par le hook Git — §13) : `feat(api): …`, `fix(frontend): …`.
3. **PR de qualité** : description claire, tests pour toute nouvelle fonctionnalité, coverage maintenu ≥ 80 %, documentation à jour.
4. **En cas d'échec CI** : consulter les logs Gitea Actions → reproduire en `make ci-*` → corriger → re-tester → pusher la correction.

## 12. Table des commandes

| Commande | Description |
|---|---|
| `make ci-quick` | Lint rapide (backend + frontend) |
| `make ci-full` | Pipeline complet local (lint + tests + security) |
| `make ci-lint-backend` | Black, isort, Flake8, Pylint (seuil 8.0, non bloquant) |
| `make ci-lint-frontend` | ESLint + css-check + typecheck |
| `make ci-test-backend` | Tests backend, coverage (seuil 80 %) |
| `make ci-test-frontend` | Tests frontend (Vitest) |
| `make ci-security-backend` | Bandit + Safety (non bloquants) |
| `make ci-security-frontend` | pnpm audit (`--audit-level=moderate`, non bloquant) |
| `make ci-build-docker` | Build local des 3 images Docker |
| `make help` | Liste de toutes les cibles |

## 13. Intégration IDE et hooks Git

### Hooks Git (réels)

Le dépôt utilise **husky comme répertoire de hooks** (`git config core.hooksPath .husky`, via `dev/scripts/setup_git_hooks.sh`). À ce jour, un seul hook est livré — **`commit-msg`** — qui valide le **message de commit** via [`dev/scripts/validate_commit_msg.py`](../../dev/scripts/validate_commit_msg.py) (Conventional Commits). ⚠️ Contrairement à une pratique répandue, **aucun lint de code ne tourne au commit** : la qualité passe par `make ci-*` et le CI.

### IDE

- **VS Code** : tâche shell `make ci-quick` (à ajouter dans `.vscode/tasks.json` si souhaité) ;
- **PyCharm** : External Tool → Program `make`, Arguments `ci-quick`, Working directory `$ProjectFileDir$`.

---

## Voir aussi

- [Ch. 05 — Stack technologique](../general_specs/05-stack-technologique.md) — outillage cible (ruff), couverture cible, multi-arch
- [Ch. 16 — Déploiement](../general_specs/16-deploiement.md) — procédures d'installation/mise à jour (référence)
- [Ch. 04 — Architecture](../general_specs/04-architecture.md) — principe multi-arch fondateur, profils de déploiement
- [ARCHITECTURE-MODULAIRE.md](ARCHITECTURE-MODULAIRE.md) — profils compose et cibles `make` d'infrastructure
