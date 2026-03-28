---
name: create-boilerplate
description: Génère un boilerplate complet à partir d'une description libre, demande des précisions si nécessaire, et met à jour les .clinerules
---

# create-boilerplate

Cette skill génère un **boilerplate complet et fonctionnel** à partir d'une description libre fournie par l'utilisateur. Elle n'a **pas de liste prédéfinie** de types de projets : elle analyse le texte, interprète la demande, demande des précisions si nécessaire, puis génère les fichiers appropriés en respectant les conventions du projet.

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

1. **Pas de liste prédéfinie** : l'IA interprète la demande à partir du texte libre
2. **Questions ciblées si ambiguë** : ne pas inventer, demander
3. **Référence aux `.clinerules`** : toujours lire et respecter les principes du projet
4. **Code complet et fonctionnel** : les fichiers générés doivent être prêts à l'emploi, pas de placeholders vides
5. **Remplissage des `.clinerules`** : les fichiers `.clinerules` contiennent des principes et des placeholders `__À_COMPLÉTER__`. La skill doit **remplacer ces placeholders** par les choix technologiques concrets effectués pour le boilerplate
6. **Standards du marché** : utiliser les meilleures pratiques et patterns reconnus pour chaque technologie

## Étapes

### 1. Analyse de la demande

Analyser le texte fourni par l'utilisateur pour identifier :
- **Le type de composant** : frontend, backend, CLI, infrastructure, CI/CD, monitoring, base de données, etc.
- **Le langage/framework** : Python, TypeScript, Bash, Go, Rust, etc.
- **Les options/librairies** : CSS framework, UI library, ORM, broker, etc.
- **L'environnement cible** : dev, test, prod, ou les trois
- **La portée** : fichiers à créer, répertoires, configuration

### 2. Clarification (si nécessaire)

Si la demande est ambiguë, incomplète ou manque de détails critiques, **poser des questions ciblées** avant de poursuivre. Maximum 2-3 questions par round.

**Exemples de clarifications :**
- « Tu veux du Python ou du Node pour le backend ? »
- « Quelle base de données ? PostgreSQL, MySQL, SQLite ? »
- « Tu as une préférence pour l'outil de test ? Vitest, Jest ? »
- « Le CLI doit interagir avec quelle API ou quel service ? »
- « Tu penses à quel type de monitoring ? Prometheus/Grafana, health checks simples, OpenTelemetry ? »

**Ne pas demander** ce qui est déjà dans les `.clinerules` (stack par défaut, conventions, etc.).

### 3. Lecture du contexte projet

Lire les fichiers `.clinerules/` pertinents pour contextualiser la génération :

| Fichier | Pourquoi |
|---------|----------|
| `10-project-requirements.md` | Exigences du projet, nature, utilisateurs cibles |
| `05-tech-stack.md` | Stack technique actuelle, gestionnaires de paquets |
| `30-code-standards.md` | Conventions de nommage, type safety |
| `35-testing-quality-gates.md` | Outils de test et couverture attendus |
| `40-security.md` | Contraintes de sécurité |
| `45-observability.md` | Métriques et logging attendus |
| `50-dev-workflow.md` | Makefile, structure opensource, .env.sample |
| `20-architecture-and-api.md` | Architecture cible (modular monolith, API-first) |

Vérifier aussi l'état actuel du projet :
- Fichiers existants à la racine et dans les répertoires concernés
- `pyproject.toml` ou `package.json` existants (ne pas écraser, merger)
- `.env.sample` existant (compléter, ne pas remplacer)
- `Makefile` existant (ajouter les cibles, ne pas écraser)

### 4. Planification des fichiers

À partir de l'analyse et du contexte, déterminer :

**Fichiers à créer :**
- Lister chaque fichier avec son chemin complet
- Indiquer le contenu principal de chaque fichier

**Fichiers `.clinerules` à mettre à jour :**
- Identifier les sections impacted dans chaque fichier
- Décrire les modifications à apporter

**Fichiers existants à compléter :**
- `Makefile` : ajouter les cibles pertinentes
- `.env.sample` : ajouter les variables d'environnement nécessaires
- `pyproject.toml` / `package.json` : ajouter les dépendances
- `.gitignore` : ajouter les patterns nécessaires

### 5. Confirmation

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

### .clinerules à mettre à jour :
| Fichier | Section modifiée | Changement |
|---------|------------------|------------|
| `05-tech-stack.md` | Backend / Frontend | Ajout de [techno] |
| `35-testing-quality-gates.md` | Outils | Ajout de [outil] |
| ... | ... | ... |

Confirmez-vous la génération ? (oui/non)
```

### 6. Génération des fichiers

Créer chaque fichier avec du **code complet et fonctionnel** :

- **Pas de TODOs ou placeholders vides** — chaque fichier doit être utilisable immédiatement
- **Respecter les conventions** du projet (nommage, structure, types)
- **Inclure les imports** et dépendances nécessaires
- **Ajouter des commentaires** pour les sections non évidentes
- **Fournir des valeurs par défaut raisonnables** (avec commentaires pour la personnalisation)

**Ordre de création recommandé :**
1. Fichiers de configuration racine (`package.json`, `pyproject.toml`, `tsconfig.json`, etc.)
2. Fichiers de build/outil (`vite.config.ts`, `.eslintrc`, `Dockerfile`, etc.)
3. Code source (structure de répertoires + fichiers)
4. Fichiers de test (structure minimale + exemples)
5. Documentation (`README.md` du composant, etc.)

### 7. Mise à jour des `.clinerules`

Pour chaque fichier `.clinerules` identifié à l'étape 4, appliquer les modifications :

**Règles de mise à jour :**
- **Remplir les placeholders** : remplacer les `__À_COMPLÉTER__` par les choix technologiques concrets
- **Ajouter, ne pas remplacer** : compléter les sections existantes, ne pas supprimer les principes
- **Cohérence** : vérifier que les ajouts sont cohérents avec les principes existants
- **Pas de doublons** : vérifier qu'une information n'est pas déjà présente

**Sections typiquement modifiées :**
- `05-tech-stack.md` : ajouter les technologies nouvellement introduites
- `35-testing-quality-gates.md` : ajouter les outils de test/couverture pertinents
- `30-code-standards.md` : ajouter les conventions spécifiques au nouveau composant
- `40-security.md` : ajouter les considérations de sécurité si nécessaire
- `45-observability.md` : ajouter les métriques/logging du nouveau composant
- `50-dev-workflow.md` : mettre à jour le Makefile et `.env.sample` si nécessaire

### 8. Mise à jour des fichiers projet

**Makefile** : Ajouter les cibles pertinentes pour le nouveau boilerplate (si un Makefile existe déjà).

**`.env.sample`** : Ajouter toutes les variables d'environnement nécessaires au nouveau composant, avec des commentaires explicatifs et des valeurs placeholder.

**`.gitignore`** : Ajouter les patterns d'exclusion pertinents.

**`pyproject.toml` / `package.json`** : Ajouter les dépendances nécessaires si le fichier existe déjà.

### 9. Vérification post-génération

Après génération, effectuer les vérifications possibles :

- [ ] Tous les fichiers déclarés ont été créés
- [ ] Les `.clinerules` sont cohérents et à jour
- [ ] Le `.env.sample` contient toutes les nouvelles variables
- [ ] Le Makefile contient les nouvelles cibles (si applicable)
- [ ] Pas de conflit avec les fichiers existants
- [ ] Si possible, lancer un `make lint` ou équivalent pour valider

## Exemples d'utilisation

### Exemple 1 : Frontend Vue 3

**Utilisateur :** `create-boilerplate frontend vue3, unocss, element-plus`

**Analyse :** Frontend Vue 3 + TypeScript + Vite + UnoCSS + Element Plus

**Fichiers typiques :**
- `frontend/package.json` — Dépendances pnpm
- `frontend/vite.config.ts` — Config Vite + plugins
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

**.clinerules modifiés :** `05-tech-stack.md`, `35-testing-quality-gates.md`

### Exemple 2 : Backend FastAPI

**Utilisateur :** `create-boilerplate backend fastapi, postgres, redis`

**Analyse :** Backend Python async + FastAPI + SQLAlchemy + PostgreSQL + Redis

**Fichiers typiques :**
- `backend/pyproject.toml` — Poetry config
- `backend/src/main.py` — FastAPI app
- `backend/src/routes/` — Routes API
- `backend/src/models/` — Modèles SQLAlchemy
- `backend/src/schemas/` — Schémas Pydantic
- `backend/src/services/` — Logique métier
- `backend/src/core/` — Config, security, dependencies
- `backend/alembic/` — Migrations
- `backend/alembic.ini` — Config Alembic
- `backend/tests/` — Tests pytest

**.clinerules modifiés :** `05-tech-stack.md`, `35-testing-quality-gates.md`, `30-code-standards.md`

### Exemple 3 : Docker

**Utilisateur :** `create-boilerplate docker pour dev, test et prod`

**Analyse :** Dockerfile multi-stage + docker-compose par environnement

**Questions possibles :**
- « Quels services ? (backend, frontend, base de données, redis...) »
- « PostgreSQL ou MySQL ? »
- « Nginx comme reverse proxy en prod ? »

**Fichiers typiques :**
- `Dockerfile` — Multi-stage (dev/test/prod)
- `docker-compose.yml` — Services de base
- `docker-compose.dev.yml` — Overrides dev
- `docker-compose.test.yml` — Overrides test
- `docker-compose.prod.yml` — Overrides prod
- `.dockerignore` — Exclusions

**.clinerules modifiés :** `05-tech-stack.md`, `50-dev-workflow.md`

### Exemple 4 : Demande floue

**Utilisateur :** `create-boilerplate un truc pour monitorer l'appli`

**Clarification :**
```
Je peux t'aider à mettre en place le monitoring. Quelques précisions :

1. **Type de monitoring :**
   - Health checks simples (endpoints /health, /ready) ?
   - Métriques Prometheus + dashboards Grafana ?
   - Tracing distribué OpenTelemetry ?
   - Les trois ?

2. **Portée :**
   - Backend uniquement ?
   - Backend + infrastructure (Docker) ?
   - Backend + frontend ?
```

## Gestion des erreurs

| Situation | Action |
|-----------|--------|
| Demande trop floue | Poser des questions ciblées (max 2-3 par round) |
| Technologie non reconnue | Demander des précisions, proposer des alternatives connues |
| Fichier existant risque d'être écrasé | Avertir l'utilisateur, proposer un merge plutôt qu'un overwrite |
| Dépendance en conflit avec `.clinerules` | Avertir et demander confirmation avant de diverger |
| Impossible de déterminer la structure | Présenter 2-3 options et laisser l'utilisateur choisir |
| Erreur pendant la génération | Annuler les modifications partielles, informer l'utilisateur |

## Checklist de fin

- [ ] Tous les fichiers boilerplate sont créés avec du code fonctionnel
- [ ] Les `.clinerules` sont mis à jour pour refléter les choix techniques
- [ ] Le `.env.sample` est complété avec les nouvelles variables
- [ ] Le `Makefile` est complété avec les nouvelles cibles (si applicable)
- [ ] Pas de conflit avec les fichiers existants
- [ ] Le récapitulatif final est présenté à l'utilisateur

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.agents/skills/create-boilerplate/SKILL.md` | Référence (ce fichier) |
| `.clinerules/*.md` | Lecture contextuelle + Mise à jour |
| Fichiers boilerplate | Création |
| `Makefile` | Complétion (si existant) |
| `.env.sample` | Complétion (si existant) |
| `.gitignore` | Complétion (si existant) |
| `pyproject.toml` / `package.json` | Complétion (si existant) |
