---
name: create-boilerplate
description: Génère un boilerplate complet à partir d'une description libre, demande des précisions si nécessaire, et met à jour les .clinerules
---

# create-boilerplate

Cette skill génère un **squelette de projet prêt à être développé** à partir d'une description libre fournie par l'utilisateur. Elle conduit un **interview structuré** pour cerner précisément le besoin, génère la **structure, la configuration et l'outillage** appropriés en respectant les conventions du projet, puis synchronise les `.clinerules` via `update-rules`.

> ⚠️ **Règle fondamentale — Boilerplate ≠ Fonctionnel**
>
> Cette skill génère **uniquement** :
> - Fichiers de configuration (pyproject.toml, package.json, tsconfig.json, etc.)
> - Structure de répertoires et stubs de code vides
> - Outillage (CI, Docker, Makefile, linting, testing, observabilité)
> - Fichiers d'infrastructure (docker-compose, nginx, .env.sample, etc.)
>
> Elle ne génère **jamais** :
> - Logique métier
> - Endpoints implémentés (uniquement leur déclaration vide)
> - Services fonctionnels
> - Tout code qui appartient aux stories du backlog
>
> L'implémentation fonctionnelle est du ressort des skills `analyse-story` et `treat-story`.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de créer un boilerplate / squelette / setup pour un composant technique
- L'utilisateur décrit un type de projet à générer (frontend, backend, CLI, docker, CI/CD, etc.)
- L'utilisateur veut initialiser une nouvelle partie du projet

**Exemples de déclenchements :**
- `create-boilerplate frontend vue3, unocss, element-plus`
- `create-boilerplate backend python fastapi`
- `create-boilerplate docker dev, test, prod`
- `create-boilerplate cli bash`
- `create-boilerplate CI/CD github actions`
- `create-boilerplate un truc pour monitorer l'appli`
- `setup un boilerplate pour un microservice en go`

## Principes directeurs

1. **Interview avant de coder** : conduire une analyse structurée avant toute génération
2. **Pas de liste prédéfinie** : l'IA interprète la demande à partir du texte libre
3. **Questions ciblées et groupées** : poser toutes les questions pertinentes en une seule fois, regroupées par thème
4. **Référence aux `.clinerules`** : toujours lire et respecter les principes du projet
5. **Structure uniquement** : les fichiers de code source sont des stubs vides ou minimaux — pas d'implémentation fonctionnelle
6. **Synchronisation finale** : appeler `update-rules` en fin de génération pour garantir la cohérence des `.clinerules`
7. **Standards du marché** : utiliser les meilleures pratiques et patterns reconnus pour chaque technologie

---

## Phase 0 : Analyse approfondie du besoin

### 0.1 Déconstruction de la demande

Analyser le texte fourni par l'utilisateur pour extraire :

| Dimension | Questions à se poser |
|-----------|---------------------|
| **Type de composant** | Frontend, backend, CLI, infra, CI/CD, monitoring, base de données ? |
| **Domaine fonctionnel** | API REST, SPA, microservice, worker, pipeline, etc. ? |
| **Contraintes implicites** | La description mentionne-t-elle des contraintes (perf, sécurité, scale) ? |
| **Intégrations** | S'intègre-t-il avec des composants existants du projet (backend, frontend, BDD) ? |
| **Environnements** | Dev uniquement, ou dev + staging + prod ? |
| **Niveau de maturité** | Prototype rapide ou production-ready ? |

### 0.2 Consultation des `.clinerules` existants

Lire les fichiers `.clinerules/` pour identifier :
- La stack déjà en place (éviter les doublons, respecter les conventions)
- Les outils déjà décidés (ne pas redemander ce qui est déjà arbitré)
- Les contraintes non-négociables (sécurité, observabilité, etc.)

| Fichier | Informations utiles à extraire |
|---------|-------------------------------|
| `05-tech-stack.md` | Langages, frameworks, gestionnaires de paquets en place |
| `30-code-standards.md` | Conventions de nommage, type safety |
| `35-testing-quality-gates.md` | Outils de test et seuils déjà définis |
| `40-security.md` | Contraintes de sécurité obligatoires |
| `45-observability.md` | Outils de logging/métriques déjà arbitrés |
| `50-dev-workflow.md` | Makefile, gestion des environnements |
| `20-architecture-and-api.md` | Patterns d'architecture attendus |

### 0.3 Exploration de l'état actuel du projet

Vérifier les fichiers existants pour éviter les conflits :
- Répertoires déjà présents (`backend/`, `frontend/`, `cli/`, etc.)
- `pyproject.toml` ou `package.json` existants (ne pas écraser, merger)
- `.env.sample` existant (compléter, ne pas remplacer)
- `Makefile` existant (ajouter les cibles, ne pas écraser)

---

## Phase 1 : Interview structuré

Sur la base de l'analyse (Phase 0), formuler **toutes les questions pertinentes en une seule fois**, regroupées par thème. Ne pas poser de questions pour ce qui est déjà arbitré dans les `.clinerules` ou évident dans la demande.

### Format de l'interview

```
## create-boilerplate — Analyse du besoin

J'ai analysé ta demande : **[résumé de la demande en 1-2 phrases]**

Avant de générer le boilerplate, j'ai besoin de quelques précisions :

---

### 🏗️ Stack & Technologie
[Questions sur les choix techniques non précisés ou ambigus]
- Ex: « Quel langage ? Python, Go, Rust, TypeScript ? »
- Ex: « Framework web : FastAPI, Flask, Express, Gin ? »

### 🗄️ Persistance & Données
[Questions sur la base de données, le cache, le stockage]
- Ex: « Base de données : PostgreSQL, MySQL, SQLite, MongoDB ? »
- Ex: « Cache nécessaire ? Redis, Memcached, ou none ? »
- Ex: « Stockage de fichiers : S3, local, ou non concerné ? »

### 🔐 Authentification & Sécurité
[Questions sur la gestion des accès]
- Ex: « Authentification nécessaire ? JWT, session, OAuth2, API key ? »
- Ex: « RBAC ? Si oui, quels rôles prévus ? »
- Ex: « Rate limiting nécessaire ? »

### 🔌 Intégrations externes
[Questions sur les services tiers ou internes]
- Ex: « Quels services externes doit consommer ce composant ? »
- Ex: « S'intègre-t-il avec le backend existant ? Via API REST, WebSocket, message bus ? »
- Ex: « Providers LLM ? Notifications ? Email ? »

### 🧪 Tests & Qualité
[Questions sur la stratégie de test]
- Ex: « Quel niveau de couverture visé ? 80%, 90%, aucun pour commencer ? »
- Ex: « Tests unitaires seuls, ou aussi intégration / E2E ? »
- Ex: « Framework de test préféré si différent de la stack définie ? »

### 📦 Environnements & Déploiement
[Questions sur les environnements cibles]
- Ex: « Environnements nécessaires : dev seul, ou dev + staging + prod ? »
- Ex: « Dockerfile nécessaire ? Multi-stage ? »
- Ex: « Intégration dans le docker-compose existant ? »

### 📊 Observabilité
[Questions sur le logging et les métriques]
- Ex: « Logging structuré JSON nécessaire, ou basique pour commencer ? »
- Ex: « Métriques Prometheus à exposer ? »
- Ex: « Tracing OpenTelemetry ? »

### 🚀 CI/CD
[Questions sur le pipeline]
- Ex: « Ajouter des jobs au pipeline CI existant (Gitea Actions) ? »
- Ex: « Pipeline de déploiement automatique ? »

---

Tu peux répondre thème par thème, ou laisser vide les sections non concernées.
Pour les éléments déjà définis dans les `.clinerules`, je n'ai pas re-posé la question.
```

**Règles de l'interview :**
- **Ne pas demander** ce qui est déjà dans les `.clinerules` (stack par défaut, conventions, etc.)
- **Ne pas demander** par politesse — n'inclure que les questions dont la réponse change concrètement la génération
- **Proposer des options concrètes** avec des valeurs par défaut suggérées quand pertinent (ex: « PostgreSQL recommandé selon les `.clinerules`, autre choix ? »)
- **Organiser par thème** — jamais une liste plate de questions sans structure
- **Un seul round de questions** — formuler toutes les questions d'un coup, pas en plusieurs aller-retours

---

## Phase 2 : Synthèse des décisions

Après réception des réponses, formuler une **synthèse des décisions** avant de planifier les fichiers :

```
## Synthèse des choix retenus

| Dimension | Décision |
|-----------|----------|
| Langage | Python 3.13+ |
| Framework | FastAPI (async) |
| Base de données | PostgreSQL + SQLAlchemy 2.0 |
| Cache | Redis |
| Auth | JWT (access + refresh) |
| Tests | pytest + pytest-asyncio, couverture 85% |
| Environnements | dev + prod (Docker multi-stage) |
| Observabilité | structlog JSON + métriques Prometheus |
| CI | Job ajouté au pipeline Gitea Actions existant |

Ces choix sont-ils corrects ? (oui / corrections)
```

---

## Phase 3 : Lecture du contexte projet (complémentaire)

Vérifier aussi l'état actuel du projet pour préparer la génération :

- Fichiers existants à la racine et dans les répertoires concernés
- `pyproject.toml` ou `package.json` existants (ne pas écraser, merger)
- `.env.sample` existant (compléter, ne pas remplacer)
- `Makefile` existant (ajouter les cibles, ne pas écraser)
- `.gitea/workflows/ci.yml` existant (ajouter des jobs, ne pas écraser)

---

## Phase 4 : Planification des fichiers

À partir des décisions (Phase 2), déterminer :

**Fichiers à créer :**
- Lister chaque fichier avec son chemin complet
- Indiquer le contenu principal de chaque fichier

**Fichiers existants à compléter :**
- `Makefile` : ajouter les cibles pertinentes
- `.env.sample` : ajouter les variables d'environnement nécessaires
- `pyproject.toml` / `package.json` : ajouter les dépendances
- `.gitignore` : ajouter les patterns nécessaires
- CI/CD : ajouter les jobs

---

## Phase 5 : Confirmation

Présenter un résumé complet avant génération :

```
## Résumé du boilerplate

**Type :** [Type identifié]
**Stack :** [Technologies retenues]

### Fichiers à créer :
| Fichier | Description |
|---------|-------------|
| `path/to/file1` | Description courte |
| `path/to/file2` | Description courte |
| ... | ... |

### Fichiers existants à compléter :
| Fichier | Ajouts |
|---------|--------|
| `Makefile` | Cibles: X, Y, Z |
| `.env.sample` | Variables: A, B, C |
| ... | ... |

Confirmez-vous la génération ? (oui/non)
```

---

## Phase 6 : Génération des fichiers

Créer chaque fichier en respectant strictement la frontière **boilerplate / implémentation** :

### Fichiers de configuration & outillage (complets)
Ces fichiers doivent être **complets et prêts à l'emploi** :
- `pyproject.toml`, `package.json`, `tsconfig.json`, `vite.config.ts`, `.eslintrc`, etc.
- `Dockerfile`, `docker-compose.*.yml`, `nginx.conf`
- `.github/workflows/*.yml`, `.gitea/workflows/*.yml`
- `.env.sample`, `.editorconfig`, `.gitignore`
- `Makefile` (cibles d'installation, lint, test, build, dev, deploy)

### Fichiers de code source (stubs uniquement)
Ces fichiers doivent contenir **uniquement la structure — pas d'implémentation** :
- Point d'entrée (`main.py`, `main.ts`) : initialisation de l'app, montage des middlewares/routes — pas de logique métier
- Modules vides avec leurs `__init__.py` / `index.ts` déclarés
- Routeurs/composants avec des stubs `# TODO: implement` ou `pass`
- Modèles de données : structure des classes uniquement (champs, types) — pas de méthodes métier
- Schémas Pydantic / types TypeScript : déclarations de structure uniquement
- Services : classes vides avec signatures de méthodes commentées ou `pass`

### Fichiers de test (structure minimale)
- Un fichier de test de smoke / sanity check par composant (ex: `test_health.py`, `App.spec.ts`)
- Pas de tests fonctionnels complets — c'est le rôle des stories

**Règles communes :**
- **Respecter les conventions** du projet (nommage, structure, types)
- **Inclure les imports** nécessaires dans les fichiers de config
- **Ajouter des commentaires** pour indiquer ce qui reste à implémenter
- **Fournir des valeurs par défaut raisonnables** dans les fichiers de config

**Ordre de création recommandé :**
1. Fichiers de configuration racine (`package.json`, `pyproject.toml`, `tsconfig.json`, etc.)
2. Fichiers de build/outil (`vite.config.ts`, `.eslintrc`, `Dockerfile`, etc.)
3. Structure de répertoires + stubs de code source
4. Fichier(s) de test smoke minimal
5. Documentation (`README.md` du composant, etc.)
6. Complétion des fichiers existants (`Makefile`, `.env.sample`, `.gitignore`, CI)

---

## Phase 7 : Synchronisation des `.clinerules` via `update-rules`

Après la génération de tous les fichiers, déclencher automatiquement la skill **`update-rules`** sur les composants concernés :

```
## Synchronisation des .clinerules

Le boilerplate a été généré. Je lance maintenant `update-rules` pour synchroniser
les `.clinerules` avec le code réel créé.

Composants à analyser : [backend / frontend / cli — selon ce qui a été généré]
```

**La skill `update-rules` se charge de :**
- Lire les fichiers de configuration réellement créés (`pyproject.toml`, `package.json`, etc.)
- Comparer avec les `.clinerules` actuels
- Identifier les divergences (technologies ajoutées, seuils de couverture configurés, nouvelles cibles Makefile, etc.)
- Présenter le rapport de divergences
- Appliquer les mises à jour confirmées

**Note :** La synchronisation via `update-rules` est **plus fiable** qu'une mise à jour manuelle car elle se base sur le code réellement généré, pas sur les intentions.

---

## Phase 8 : Vérification post-génération

Après génération et synchronisation, effectuer les vérifications possibles :

- [ ] Tous les fichiers déclarés ont été créés
- [ ] Les `.clinerules` sont cohérents et à jour (via `update-rules`)
- [ ] Le `.env.sample` contient toutes les nouvelles variables
- [ ] Le Makefile contient les nouvelles cibles (si applicable)
- [ ] Pas de conflit avec les fichiers existants
- [ ] Si possible, lancer un `make lint` ou équivalent pour valider

---

## Gestion des erreurs

| Situation | Action |
|-----------|--------|
| Demande trop floue | Conduire l'interview structuré (Phase 1) |
| Technologie non reconnue | Demander des précisions, proposer des alternatives connues |
| Fichier existant risque d'être écrasé | Avertir l'utilisateur, proposer un merge plutôt qu'un overwrite |
| Dépendance en conflit avec `.clinerules` | Avertir et demander confirmation avant de diverger |
| Impossible de déterminer la structure | Présenter 2-3 options et laisser l'utilisateur choisir |
| Erreur pendant la génération | Annuler les modifications partielles, informer l'utilisateur |
| `update-rules` détecte des divergences non attendues | Présenter le rapport et demander confirmation avant d'appliquer |

---

## Checklist de fin

- [ ] L'interview structuré a été conduit (Phase 1)
- [ ] Les décisions ont été synthétisées et confirmées (Phase 2)
- [ ] Tous les fichiers boilerplate sont créés : config complets, code source en stubs (Phase 6)
- [ ] Aucune logique métier n'a été implémentée (uniquement la structure et la configuration)
- [ ] `update-rules` a été exécuté sur les composants concernés (Phase 7)
- [ ] Les `.clinerules` sont synchronisés avec le code réel
- [ ] Le `.env.sample` est complété avec les nouvelles variables
- [ ] Le `Makefile` est complété avec les nouvelles cibles (si applicable)
- [ ] Pas de conflit avec les fichiers existants
- [ ] Le récapitulatif final est présenté à l'utilisateur

---

## Exemples d'utilisation

### Exemple 1 : Frontend Vue 3

**Utilisateur :** `create-boilerplate frontend vue3, unocss, element-plus`

**Phase 0 — Analyse :**
- Type : Frontend SPA
- Stack précisée : Vue 3 + UnoCSS + Element Plus
- Contraintes implicites : TypeScript (`.clinerules`), Vite (`.clinerules`)
- Questions nécessaires : routing ? state management ? auth ? tests ? environnements Docker ?

**Phase 1 — Interview :**
```
### 🔌 Intégrations
- Ce frontend consomme-t-il le backend FastAPI existant ? Si oui, URL du proxy de dev ?

### 🔐 Authentification
- Gestion des tokens JWT côté frontend ? (stockage localStorage / cookie)

### 🧪 Tests
- Tests E2E Playwright en plus des tests Vitest ?

### 📦 Environnements
- Dockerfile multi-stage (dev + prod nginx) ?
```

**Phase 6 — Fichiers générés :**
- `frontend/package.json` — pnpm + Vue 3 + UnoCSS + Element Plus
- `frontend/vite.config.ts` — Vite + proxy API
- `frontend/tsconfig.json` — TypeScript strict
- `frontend/uno.config.ts` — UnoCSS config
- `frontend/src/main.ts` — Point d'entrée
- `frontend/src/App.vue` — Composant racine
- `frontend/src/router/index.ts` — Vue Router
- `frontend/src/stores/` — Pinia stores
- `frontend/src/components/` — Composants exemple
- `frontend/src/views/` — Vues exemple
- `frontend/.eslintrc.cjs` — ESLint
- `frontend/.prettierrc` — Prettier
- `frontend/env.d.ts` — Types env

**Phase 7 — `update-rules` :** Synchronisation des `.clinerules` sur le composant `frontend`.

---

### Exemple 2 : Backend FastAPI

**Utilisateur :** `create-boilerplate backend fastapi, postgres, redis`

**Phase 0 — Analyse :**
- Type : Backend API REST
- Stack précisée : FastAPI + PostgreSQL + Redis
- Conventions implicites : SQLAlchemy 2.0 async, Pydantic v2, Uvicorn (`.clinerules`)
- Questions nécessaires : auth JWT ? agents IA ? message bus ? observabilité ?

**Phase 1 — Interview :**
```
### 🔐 Authentification & Sécurité
- Auth JWT avec refresh tokens ? (recommandé par les `.clinerules`)
- RBAC avec quels rôles initiaux ? (admin, user ?)

### 🔌 Intégrations
- MessageBus Redis Streams à prévoir dès maintenant ?
- Intégration LiteLLM pour les agents IA ?

### 📊 Observabilité
- structlog avec format JSON ? (recommandé)
- Endpoint /metrics Prometheus à exposer ?

### 🚀 CI/CD
- Job de migration Alembic dans le pipeline CI ?
```

**Phase 6 — Fichiers générés :**
- `backend/pyproject.toml` — Poetry config
- `backend/src/main.py` — FastAPI app
- `backend/src/api/` — Routes API
- `backend/src/models/` — Modèles SQLAlchemy
- `backend/src/schemas/` — Schémas Pydantic
- `backend/src/services/` — Logique métier
- `backend/src/core/` — Config, security, dependencies
- `backend/alembic/` — Migrations
- `backend/alembic.ini` — Config Alembic
- `backend/tests/` — Tests pytest

**Phase 7 — `update-rules` :** Synchronisation des `.clinerules` sur le composant `backend`.

---

### Exemple 3 : Demande floue

**Utilisateur :** `create-boilerplate un truc pour monitorer l'appli`

**Phase 0 — Analyse :**
- Type : Observabilité / Monitoring
- Aucune stack précisée
- Composants existants : backend FastAPI, frontend Vue 3
- Questions nécessaires : toutes (rien n'est précisé)

**Phase 1 — Interview :**
```
### 🏗️ Type de monitoring
- Health checks simples (/health, /ready) déjà présents ?
- Métriques Prometheus + dashboards Grafana ?
- Tracing distribué OpenTelemetry ?
- Les trois ?

### 📦 Portée
- Backend FastAPI uniquement ?
- Backend + infrastructure Docker (node-exporter, cAdvisor) ?
- Backend + frontend (métriques Web Vitals) ?

### 🚀 Déploiement
- Service Prometheus/Grafana dans le docker-compose existant ?
- Alertmanager pour les notifications ?
```

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.agents/skills/create-boilerplate/SKILL.md` | Référence (ce fichier) |
| `.clinerules/*.md` | Lecture contextuelle (Phase 0) |
| `.agents/skills/update-rules/SKILL.md` | Invoqué en Phase 7 |
| Fichiers boilerplate | Création (Phase 6) |
| `Makefile` | Complétion (si existant) |
| `.env.sample` | Complétion (si existant) |
| `.gitignore` | Complétion (si existant) |
| `pyproject.toml` / `package.json` | Complétion (si existant) |
| `.gitea/workflows/ci.yml` | Complétion (si existant) |
