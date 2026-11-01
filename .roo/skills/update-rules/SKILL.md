---
name: update-rules
description: Met à jour les documents .roo/rules en analysant le contenu réel du code (backend, frontend, cli)
---

# update-rules

Cette skill analyse le **code source réel** du projet (backend, frontend, CLI) et met à jour les fichiers `.roo/rules/` pour qu'ils reflètent fidèlement l'état actuel du codebase. Elle détecte les divergences entre la documentation et la réalité, puis applique les corrections nécessaires.

## Usage

Utilise cette skill quand :
- Du nouveau code a été ajouté et les `.roo/rules` n'ont pas été mis à jour
- On vient de finaliser un boilerplate et on veut synchroniser la documentation
- Les `.roo/rules` semblent obsolètes ou inexacts par rapport au code réel
- On veut un audit rapide de la cohérence documentation ↔ code

**Exemples de déclenchements :**
- `update-rules`
- `update-rules backend`
- `update-rules frontend`
- `update-rules cli`
- `mets à jour les roo/rules en fonction du code`
- `synchronise les règles avec le code actuel`

## Périmètre

| Composant | Déclenché si |
|-----------|-------------|
| `backend` | Le répertoire `backend/` existe |
| `frontend` | Le répertoire `frontend/` existe |
| `cli` | Le répertoire `cli/` existe |

Si aucun composant n'est précisé, la skill analyse **tous les composants présents**.

## Fichiers `.roo/rules` concernés

| Fichier | Contenu                                                              | Composants sources |
|---------|----------------------------------------------------------------------|-------------------|
| `05-tech-stack.md` | Stack technique, dépendances, gestionnaires de paquets               | backend, frontend, cli |
| `20-architecture-and-api.md` | Patterns d'architecture réellement utilisés                          | backend |
| `30-code-standards.md` | Conventions de nommage, type safety, linting                         | backend, frontend, cli |
| `35-testing-quality-gates.md` | Outils de test, seuils de couverture, commandes                      | backend, frontend |
| `40-security.md` | Mécanismes de sécurité en place                                      | backend, frontend |
| `45-observability.md` | Outils de logging, métriques, tracing                                | backend |
| `50-dev-workflow.md` | Makefile (cibles), `.env.sample`, CI pipeline, structure open-source | all |
| `55-project-structure.md` | Organisation des répertoires cibles   | all |

**Fichiers `.roo/rules` NON modifiés par cette skill :**
- `00-project-context.md` — contexte projet haut niveau, invariant
- `01-Project-management.md` — règles de gestion de backlog, invariant

---

## Phase 1 : Détection du périmètre

### 1.1 Identifier les composants présents

Vérifier l'existence des répertoires :
- `backend/` → analyser le backend
- `frontend/` → analyser le frontend
- `cli/` → analyser le CLI (si présent)

### 1.2 Annoncer le périmètre

```
## update-rules — Démarrage

Composants détectés :
- ✅ backend/
- ✅ frontend/
- ❌ cli/ (absent)

Fichiers .roo/rules à analyser :
- 05-tech-stack.md
- 20-architecture-and-api.md
- 30-code-standards.md
- 35-testing-quality-gates.md
- 40-security.md
- 45-observability.md
- 50-dev-workflow.md

Lancement de l'analyse...
```

---

## Phase 2 : Extraction des faits par composant

### 2.1 Backend (`backend/`)

Lire et analyser dans l'ordre :

#### `backend/pyproject.toml`
Extraire :
- **Python version** requis (`tool.poetry.dependencies.python`)
- **Dépendances principales** : framework web, ORM, base de données, cache, validation, async, ASGI
- **Dépendances de dev** : linter, formateur, test runner, coverage, sécurité
- **Scripts** définis (`[tool.poetry.scripts]`)
- **Configuration Ruff** (`[tool.ruff]`) : rules actives, target version
- **Configuration pytest** (`[tool.pytest.ini_options]`) : répertoires, options, couverture
- **Configuration coverage** (`[tool.coverage]`) : seuils, exclusions

#### `backend/src/main.py` et `backend/src/core/`
Extraire :
- **Pattern applicatif** : structure FastAPI, middlewares, lifespan
- **Logging** : outil utilisé (module `logging` standard, loguru, etc.)
- **Configuration** : mécanisme (pydantic-settings, dotenv, etc.)

#### `backend/src/` (exploration structurelle)
Identifier les modules présents :
- `api/` → endpoints REST
- `models/` → ORM (SQLAlchemy)
- `schemas/` → validation (Pydantic)
- `services/` → logique métier
- `core/` → infra (config, db, deps, security)
- `agents/` → agents IA (si présent)
- `bus/` → messagerie (si présent)

#### `backend/Dockerfile`
Extraire :
- Image de base Python (version)
- Stages multi-target (dev/prod)
- Utilisateur non-root

#### `backend/tests/`
Identifier :
- **Framework** : pytest, pytest-asyncio
- **Client HTTP** : httpx, TestClient
- **Structure** : unit/, integration/, e2e/
- **Commandes** de lancement documentées dans `pyproject.toml`

---

### 2.2 Frontend (`frontend/`)

Lire et analyser dans l'ordre :

#### `frontend/package.json`
Extraire :
- **Framework** : Vue version, React, etc.
- **Langage** : TypeScript (version), JavaScript
- **Dépendances principales** : router, state management, UI lib, HTTP client, etc.
- **Dépendances de dev** : Vite, ESLint, Prettier, TypeScript, test runner, coverage
- **Scripts** npm/pnpm définis (`scripts`)

#### `frontend/vite.config.ts`
Extraire :
- **Outil de build** : Vite version, plugins
- **Alias** de chemins
- **Proxy** de développement (API backend)

#### `frontend/tsconfig.json` (et `tsconfig.app.json`)
Extraire :
- **Strict mode** activé ou non
- Options strictes : `noUnusedLocals`, `noUnusedParameters`, `noUncheckedIndexedAccess`
- **Target** ES

#### `frontend/eslint.config.ts` (ou `.eslintrc.*`)
Extraire :
- **Rules ESLint** actives
- **Plugins** : eslint-plugin-vue, @typescript-eslint, etc.
- **Intégration Prettier**

#### `frontend/vitest.config.ts` (ou dans `vite.config.ts`)
Extraire :
- **Framework de test** : Vitest
- **Environnement** : jsdom, happy-dom
- **Seuils de couverture**
- **Provider de couverture** : v8, istanbul

#### `frontend/playwright.config.ts` (si présent)
Extraire :
- **Navigateurs** testés : Chromium, Firefox, WebKit
- **Base URL**
- **Répertoire E2E**

#### `frontend/Dockerfile`
Extraire :
- Image de base Node (version)
- Image nginx (version)
- Stages multi-target (dev/prod)

---

### 2.3 CLI (`cli/`)

Si le répertoire `cli/` existe, lire et analyser :

#### Fichier de configuration de dépendances
- `cli/pyproject.toml` → dépendances, outils (click, typer, argparse, rich...)
- `cli/package.json` → si CLI Node.js (commander, oclif, ink...)
- `cli/Cargo.toml` → si CLI Rust (clap, etc.)

#### Point d'entrée
- Identifier le framework CLI utilisé
- Identifier les commandes disponibles (structure des modules)

---

### 2.4 Fichiers racine

Lire dans l'ordre :

#### `Makefile`
Extraire toutes les **cibles définies** avec leur description (commentaire `##`).

#### `.env.sample`
Extraire toutes les **variables d'environnement** documentées avec leurs sections.

#### `.gitea/workflows/ci.yml` (ou `.github/workflows/`)
Extraire :
- **Jobs** et leur rôle
- **Commandes** de lint, test, build, coverage
- **Seuils** de couverture appliqués

#### `.editorconfig`
Extraire :
- Indentation par type de fichier
- Encoding, line endings

---

## Phase 3 : Lecture des `.roo/rules` actuels

Lire tous les fichiers `.roo/rules/` concernés (liste à la Phase 1) pour identifier leur contenu actuel.

**Objectif :** Préparer le diff entre les faits extraits (Phase 2) et la documentation actuelle.

---

## Phase 4 : Identification des divergences

Pour chaque fichier `.roo/rules/`, comparer les faits extraits avec le contenu documenté.

### Types de divergences

| Type | Description | Exemple |
|------|-------------|---------|
| **Manquant** | Technologie/outil présent dans le code, absent des `.roo/rules` | `aiosqlite` utilisé mais non documenté dans `05-tech-stack.md` |
| **Obsolète** | Information dans les `.roo/rules` qui ne correspond plus au code | Python 3.11 documenté mais pyproject.toml dit 3.12+ |
| **Inexact** | Information partiellement incorrecte | Seuil de couverture 70% documenté mais configuré à 85% dans pytest |
| **Manque de détail** | Information présente mais incomplète | Mention de Ruff sans lister les rules actives |

### Règles de divergence

**NE PAS signaler comme divergence :**
- Les décisions d'architecture futures (ex: "migration prévue vers PostgreSQL") — c'est intentionnel
- Les règles de principe (ex: "ne pas logger de données sensibles") — ce ne sont pas des faits de code
- Les technologies cibles (prod) documentées mais pas encore en place (ex: Redis Streams en prod)

**SIGNALER comme divergence :**
- Versions incorrectes (Python, Node, dépendances majeures)
- Outils présents dans le code mais absents de la doc
- Commandes Makefile documentées mais inexistantes (ou inversement)
- Seuils de couverture différents entre la doc et la configuration réelle
- Outils de lint/format différents entre la doc et la configuration réelle

---

## Phase 5 : Présentation du rapport de divergences

Avant toute modification, présenter un rapport complet :

```
## update-rules — Rapport de divergences

### 05-tech-stack.md
| Type | Élément | Actuel dans .roo/rules | Réel dans le code |
|------|---------|------------------------|-------------------|
| Manquant | `aiohttp` | Non documenté | Utilisé dans `backend/pyproject.toml` |
| Obsolète | Python version | "3.11+" | "3.12+" (pyproject.toml) |

### 35-testing-quality-gates.md
| Type | Élément | Actuel dans .roo/rules | Réel dans le code |
|------|---------|------------------------|-------------------|
| Inexact | Seuil coverage backend | 85% | 90% (pyproject.toml) |

### 50-dev-workflow.md
| Type | Élément | Actuel dans .roo/rules | Réel dans le code |
|------|---------|------------------------|-------------------|
| Manquant | `make migrate` | Non documenté | Présent dans Makefile |

---

**Total : X divergences sur Y fichiers .roo/rules**

Voulez-vous appliquer ces mises à jour ? (oui/non/sélection)
```

**Options de réponse :**
- `oui` → Appliquer toutes les mises à jour
- `non` → Annuler
- `sélection` → L'utilisateur indique quels fichiers mettre à jour (ex: "seulement 05 et 50")

---

## Phase 6 : Application des mises à jour

Pour chaque fichier `.roo/rules/` ayant des divergences confirmées :

### Règles d'application

1. **Ajouter, ne pas supprimer** : ne jamais effacer une décision documentée intentionnellement
2. **Mettre à jour les versions** : remplacer les versions incorrectes par les versions réelles
3. **Compléter les sections** : ajouter les technologies/outils manquants dans la section appropriée
4. **Corriger les inexactitudes** : ajuster les seuils, noms d'outils, commandes
5. **Préserver le style** : respecter le format Markdown existant (tableaux, listes, titres)
6. **Pas de contenu inventé** : n'ajouter que ce qui est prouvé par le code source

### Ordre d'application recommandé

1. `05-tech-stack.md` — Fondation de la stack
2. `35-testing-quality-gates.md` — Outils et seuils de test
3. `30-code-standards.md` — Conventions de code
4. `50-dev-workflow.md` — Makefile et workflow
5. `55-project-structure.md` — Répertoires cibles et contenus par périmètre
6. `20-architecture-and-api.md` — Patterns d'architecture
7. `45-observability.md` — Logging et métriques
8. `40-security.md` — Sécurité

### Actions par section

#### `05-tech-stack.md`
- Mettre à jour les versions des langages et frameworks
- Ajouter les nouvelles dépendances significatives (pas les micro-libs)
- Corriger les gestionnaires de paquets si changés
- Mettre à jour les images Docker (base image, version)

#### `35-testing-quality-gates.md`
- Mettre à jour les seuils de couverture (selon pyproject.toml / vitest.config.ts)
- Ajouter les outils de test manquants
- Corriger/compléter les commandes (`make test-backend`, etc.)
- Mettre à jour les navigateurs Playwright si changés

#### `30-code-standards.md`
- Mettre à jour les configurations black/isort/flake8/mypy actives
- Corriger les conventions si elles ont évolué
- Ajouter les patterns nouvellement établis

#### `50-dev-workflow.md`
- Mettre à jour le tableau des cibles Makefile (ajouter les nouvelles, retirer les obsolètes)
- Mettre à jour les variables `.env.sample` (ajouter celles manquantes)
- 
#### `55-project-structure.md`
- lister les modules logiciels (backend, frontend, documentation, data, dev, tests ...)
- Mettre à jour la structure racine avec les éléments importants et répertoires (ajouter les nouvelles, retirer les obsolètes)
- Mettre à jour chaque sous répertoire avec ses éléments importants et les sous-sous répertoires éventuellement (ajouter les nouvelles, retirer les obsolètes)
- Indiquer les conventions de nommage et de mise à jour des éléments générés dans les répertoires en fonction de leur typologie
- Indiquer les typologies de tests et les répertoires cibles pour chaque typologie dans les différents modules logiciels

#### `20-architecture-and-api.md`
- Mettre à jour les patterns réellement utilisés (si différents de la doc)
- Ajouter les nouvelles librairies de résilience (tenacity, pybreaker, etc.) si présentes dans le code

#### `45-observability.md`
- Mettre à jour l'outil de logging réellement utilisé (module `logging` standard, loguru, etc.)
- Corriger les outils de métriques/tracing si ils ont changé

#### `40-security.md`
- Mettre à jour les mécanismes d'auth en place
- Corriger les outils de scan si changés

---

## Phase 7 : Récapitulatif post-mise à jour

Après application des modifications, afficher un récapitulatif (exemple):

```
## update-rules — Mise à jour terminée

### Fichiers .roo/rules modifiés
| Fichier | Modifications |
|---------|--------------|
| `05-tech-stack.md` | Python 3.11+ → 3.12+, ajout aiohttp |
| `35-testing-quality-gates.md` | Seuil coverage 85% → 90% |
| `50-dev-workflow.md` | Ajout cible `make migrate` |

### Fichiers .roo/rules inchangés
- `20-architecture-and-api.md` — Aucune divergence
- `30-code-standards.md` — Aucune divergence
- `40-security.md` — Aucune divergence
- `45-observability.md` — Aucune divergence

### Aucune divergence détectée pour
- (liste si applicable)

✅ Les .roo/rules sont maintenant synchronisés avec le code réel.
```

---

## Cas particuliers

### Cas 1 : Composant absent

Si un composant demandé n'existe pas :
```
⚠️ Le répertoire `cli/` n'existe pas dans le projet.
Aucune analyse CLI ne sera effectuée.
```

### Cas 2 : Aucune divergence

Si tout est déjà synchronisé :
```
✅ Aucune divergence détectée.
Les .roo/rules sont déjà à jour avec le code réel.
```

### Cas 3 : Divergence ambiguë

Si une divergence n'est pas certaine (ex: une technologie est documentée mais son usage dans le code n'est pas confirmé) :
```
⚠️ Divergence incertaine sur [élément] dans [fichier] :
- Documenté dans .roo/rules : [valeur]
- Non trouvé dans le code (peut-être prévu mais pas encore implémenté)

Souhaitez-vous le retirer de la documentation ? (oui/non)
```

### Cas 4 : Nouvelle technologie majeure inconnue

Si une dépendance importante est trouvée dans le code mais que son rôle n'est pas clair :
```
⚠️ Nouvelle dépendance détectée : `nom-lib` (v1.2.3)
Je n'ai pas pu déterminer son rôle précis automatiquement.

Quel est le rôle de `nom-lib` dans le projet ?
(Ex: "client S3", "moteur de template", "client SMTP"...)
```

---

## Gestion des erreurs

| Situation | Action |
|-----------|--------|
| `pyproject.toml` non lisible | Informer, sauter l'analyse backend |
| `package.json` non lisible | Informer, sauter l'analyse frontend |
| Fichier `.roo/rules` absent | Créer le fichier avec un contenu minimal |
| Divergence sur un fichier `.roo/rules` non modifiable | Informer l'utilisateur sans modifier |
| Erreur pendant la mise à jour | Rollback partiel, informer l'utilisateur |

---

## Checklist de fin

- [ ] Tous les composants présents ont été analysés
- [ ] Toutes les divergences ont été identifiées et présentées
- [ ] L'utilisateur a confirmé les mises à jour
- [ ] Tous les fichiers `.roo/rules` concernés ont été mis à jour
- [ ] Aucune information intentionnelle n'a été supprimée
- [ ] Le récapitulatif final a été présenté

---
