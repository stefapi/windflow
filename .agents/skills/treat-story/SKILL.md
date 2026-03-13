---
name: treat-story
description: Effectue l'implémentation complète d'une story du backlog
---

# treat-story

Cette skill guide l'implémentation **complète** d'une story : de l'analyse initiale jusqu'à la validation finale et la mise à jour du backlog. Elle assure le respect des critères d'acceptation, des standards de code et de la Definition of Done.

## Usage

Utilise cette skill quand :
- L'utilisateur demande d'implémenter une story (ex: "Implémente STORY-401")
- L'utilisateur veut traiter/exécuter une story du backlog
- L'utilisateur demande de "faire" ou "développer" une story identifiée

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le fichier story existe dans `.backlog/stories/`
- [ ] La story est à l'état `TODO` ou `IN_PROGRESS`
- [ ] L'environnement de développement est opérationnel (backend et/ou frontend)

---

## Phase 1 : Réflexion et Analyse

### 1.1 Sélection et lecture de la story

Si l'utilisateur n'a pas spécifié de story, lister les stories disponibles dans `.backlog/stories/` avec statut `TODO` :

```
Quelle story souhaitez-vous implémenter ?

Stories disponibles (TODO) :
- STORY-XXX : [Titre] (EPIC-YYY)
- STORY-XXX : [Titre] (EPIC-YYY)
...
```

Une fois la story identifiée, lire le fichier `.backlog/stories/STORY-XXX-*.md` et extraire :
- **Titre et numéro**
- **Epic parent**
- **Description** (format "En tant que...")
- **Critères d'acceptation (AC)**
- **État d'avancement technique** (tâches)
- **Dépendances** éventuelles

### 1.2 Lecture de l'epic parent

Lire le fichier epic dans `.backlog/epics/EPIC-XXX-*.md` pour comprendre :
- La vision globale et la valeur business
- Les notes de conception
- Les risques identifiés
- Les critères de succès de l'epic
- Le contexte technique plus large

### 1.3 Exploration du codebase

Avant de planifier, **explorer le code existant** :

**Pour une story frontend :**
- Lister `frontend/src/views/` pour identifier les vues existantes
- Lister `frontend/src/components/` pour les composants réutilisables
- Lire `frontend/src/router/index.ts` pour les routes
- Lire `frontend/src/stores/` pour les stores Pinia liés
- Vérifier `frontend/src/types/` pour les types TypeScript
- Consulter `doc/general_specs/11-UI-mockups.md` pour les specs UI

**Pour une story backend :**
- Lister `backend/app/api/v1/` pour les endpoints existants
- Lister `backend/app/models/` pour les modèles SQLAlchemy
- Lister `backend/app/schemas/` pour les schémas Pydantic
- Lister `backend/app/services/` pour les services
- Vérifier `backend/tests/` pour les patterns de test existants
- Consulter `doc/general_specs/07-api-design.md` pour les conventions API

**Pour une story de cleanup/suppression :**
- Faire un `grep` global pour identifier toutes les références
- Lister les imports dans les fichiers dépendants
- Identifier les routes, stores, services liés

### 1.4 Analyse des dépendances et impacts

Identifier :
- **Dépendances amont** : Stories qui doivent être terminées avant celle-ci
- **Dépendances aval** : Stories qui dépendent de celle-ci
- **Fichiers impactés** : Liste estimée des fichiers à modifier/créer/supprimer
- **Risques techniques** : Complexité, points d'attention

### 1.5 Planification détaillée

Présenter un résumé de la planification :

```
## Plan d'implémentation : STORY-XXX

### Contexte
- **Epic :** EPIC-XXX — [Titre]
- **Description :** En tant que [Rôle], je veux [Action] afin de [Bénéfice]

### Analyse technique
**Fichiers existants à modifier :**
- [Fichier 1] : [Modification prévue]
- [Fichier 2] : [Modification prévue]

**Fichiers à créer :**
- [Nouveau fichier 1] : [Description]

**Fichiers à supprimer :**
- [Fichier 1]

### Risques identifiés
- [Risque 1] → Mitigation : [Action]

### Ordre d'implémentation proposé
1. [Étape 1]
2. [Étape 2]
3. [Étape 3]
...

Confirmez-vous ce plan ? (oui/non/modifications)
```

---

## Phase 2 : Implémentation

### 2.1 Mise à jour du statut → IN_PROGRESS

**Avant de coder**, mettre à jour le statut de la story :

1. **Dans le fichier story** (`.backlog/stories/STORY-XXX-*.md`) :
   ```markdown
   **Statut :** IN_PROGRESS
   ```

2. **Dans le Kanban** (`.backlog/kanban.md`) :
   - Déplacer la story de `📋 BACKLOG` vers `🏗️ IN PROGRESS`
   - Changer le marqueur `- [ ]` en `- [~]`

3. **Dans l'epic parent** (si première story en cours) :
   - Mettre à jour le statut de l'epic à `IN_PROGRESS`

### 2.2 Développement itératif

Implémenter la solution en suivant l'ordre planifié. Pour chaque étape :

1. **Coder** la fonctionnalité/modification
2. **Tester manuellement** si applicable
3. **Cocher** la tâche correspondante dans "État d'avancement technique"
4. **Cocher** l'AC correspondant si validé

**Standards de code à respecter** (référence `.clinerules/30-code-standards.md`) :
- Python : type hints complets, fonctions courtes (~30 lignes), snake_case
- TypeScript : strict, pas de `any`, camelCase, fichiers kebab-case
- Validation : Pydantic côté backend, props typées côté frontend

**Règles API-first** (si applicable, référence `.clinerules/20-architecture-and-api.md`) :
- Documenter les endpoints (OpenAPI)
- Utiliser des schémas Pydantic
- Pagination pour les listes > 20 éléments

### 2.3 Gestion des blocages

Si un blocage survient pendant le développement :

1. **Mettre à jour le statut** de la story à `BLOCKED`
2. **Ajouter une note** explicative dans le fichier story :
   ```markdown
   ## Blocage
   **Date :** [Date]
   **Raison :** [Description du blocage]
   **Action requise :** [Ce qu'il faut pour débloquer]
   ```
3. **Mettre à jour le Kanban** avec le marqueur `- [!]` et une annotation
4. **Informer l'utilisateur** et demander de l'aide si nécessaire

Une fois débloqué, remettre le statut à `IN_PROGRESS`.

---

## Phase 3 : Validation et Critères de Succès

### 3.1 Tests

**Tests unitaires (obligatoire)** :
- Backend : `pytest backend/tests/unit/` avec couverture ≥ 80%
- Frontend : `pnpm test` (Vitest) avec couverture ≥ 80%

**Tests d'intégration (si applicable)** :
- Backend : `pytest backend/tests/integration/`

**Commandes de test** :
```bash
# Backend
make test                    # Tous les tests
make test-cov                # Avec rapport de couverture
pytest backend/tests/unit/test_xxx.py -v   # Tests spécifiques

# Frontend
pnpm test                    # Tous les tests
pnpm test:coverage           # Avec couverture
```

### 3.2 Vérification de la couverture

**Objectifs de couverture** (référence `.clinerules/35-testing-quality-gates.md`) :
- Minimum : 80% pour tout nouveau composant
- Backend : 85%+
- Frontend : 80%+
- Chemins critiques : 95% si raisonnable

Si la couverture est insuffisante :
1. Identifier les lignes/manquantes
2. Ajouter les tests manquants
3. Re-vérifier

### 3.3 Build et Lint

**Backend** :
```bash
poetry build                 # Build du package
mypy backend/                # Type checking
ruff check backend/          # Linting (ou flake8/pylint)
```

**Frontend** :
```bash
pnpm build                   # Build de production
pnpm lint                    # ESLint
pnpm typecheck               # TypeScript strict
```

Tous les commandes doivent passer sans erreur.

### 3.4 Mise à jour de la documentation

Si la story implique des changements impactant la documentation :

- [ ] Mettre à jour `doc/general_specs/` si les specs changent
- [ ] Mettre à jour les docstrings Python
- [ ] Mettre à jour les commentaires JSDoc/TSDoc
- [ ] Mettre à jour le README si nécessaire
- [ ] Mettre à jour les schémas OpenAPI si API modifiée

### 3.5 Notes d'implémentation

**À la fin du développement**, ajouter une section "Notes d'implémentation" au fichier story :

```markdown
## Notes d'implémentation

**Date :** [Date de fin]
**Durée estimée :** [X heures/jours]

### Fichiers modifiés/créés
- `path/to/file1.py` : [Description de la modification]
- `path/to/file2.vue` : [Description de la modification]

### Décisions techniques
- [Décision 1] : [Raison]
- [Décision 2] : [Raison]

### Difficultés rencontrées
- [Difficulté 1] : [Solution apportée]
- [Difficulté 2] : [Solution apportée]

### Tests ajoutés
- `tests/unit/test_xxx.py` : [Couverture]
- `tests/yyy.test.ts` : [Couverture]
```

### 3.6 Vérification de la Definition of Done (DoD)

Avant de passer à REVIEW, vérifier la **DoD complète** :

```markdown
## Definition of Done (DoD) Checklist
- [ ] Tous les critères d'acceptation (AC) sont validés
- [ ] Code revu et approuvé (self-review minimalement)
- [ ] Tests unitaires écrits et passants (couverture ≥ 80%)
- [ ] Pas de régression sur les tests existants
- [ ] Documentation technique mise à jour si nécessaire
- [ ] Section "Notes d'implémentation" ajoutée au fichier story
- [ ] Build passe sans erreur
- [ ] Lint passe sans erreur
```

### 3.7 Passage à REVIEW puis DONE

**Passage à REVIEW** :

1. **Dans le fichier story** :
   ```markdown
   **Statut :** REVIEW
   ```

2. **Dans le Kanban** :
   - Déplacer vers `🚧 REVIEW`
   - Marqueur `- [?]`

3. **Présenter un résumé** à l'utilisateur pour validation :
   ```
   ## STORY-XXX prête pour review
   
   ### Résumé des changements
   - [Changement 1]
   - [Changement 2]
   
   ### AC validés
   - [x] AC 1 : ...
   - [x] AC 2 : ...
   
   ### Tests
   - Couverture : XX%
   - Tous les tests passent : ✅
   
   ### Build/Lint
   - Build : ✅
   - Lint : ✅
   
   Voulez-vous valider cette story ? (oui/non)
   ```

**Passage à DONE** (après validation) :

1. **Dans le fichier story** :
   ```markdown
   **Statut :** DONE
   ```

2. **Dans le Kanban** :
   - Déplacer vers `✅ DONE`
   - Marqueur `- [x]`

3. **Dans l'epic parent** :
   - Cocher la story dans la section `## Liste des Stories liées` :
     ```markdown
     - [x] STORY-XXX : [Titre]
     ```

4. **Si toutes les stories de l'epic sont DONE** :
   - Mettre à jour le statut de l'epic à `DONE`

---

## Règles de Cohérence

Respecter strictement les règles définies dans `.clinerules/01-Project-management.md` :

### Statuts et transitions
- `TODO` → `IN_PROGRESS` → `REVIEW` → `DONE`
- `IN_PROGRESS` → `BLOCKED` → `IN_PROGRESS` (si blocage)
- `REVIEW` → `IN_PROGRESS` (si rejet)

### Synchronisation obligatoire
| Élément | Fichier | Action |
|---------|---------|--------|
| Statut story | `.backlog/stories/STORY-XXX-*.md` | Mettre à jour à chaque transition |
| Colonne Kanban | `.backlog/kanban.md` | Déplacer selon le statut |
| Case epic | `.backlog/epics/EPIC-XXX-*.md` | Cocher à DONE |
| Statut epic | `.backlog/epics/EPIC-XXX-*.md` | Mettre à jour si toutes stories DONE |

### Marqueurs Kanban
| Statut | Marqueur |
|--------|----------|
| TODO | `- [ ]` |
| IN_PROGRESS | `- [~]` |
| BLOCKED | `- [!]` |
| REVIEW | `- [?]` |
| DONE | `- [x]` |

---

## Gestion des Erreurs

| Erreur | Action |
|--------|--------|
| Story non trouvée | Demander un numéro valide |
| Story déjà DONE | Informer l'utilisateur, demander confirmation pour modification |
| Story BLOCKED | Proposer de résoudre le blocage ou de changer de story |
| Échec de build | Corriger les erreurs avant de continuer |
| Échec de tests | Corriger les tests ou le code, ne pas passer à REVIEW |
| Couverture insuffisante | Ajouter des tests jusqu'à atteindre 80% |
| Dépendance non terminée | Informer l'utilisateur, proposer de traiter la dépendance d'abord |

---

## Checklist de Fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] Le code est implémenté et fonctionnel
- [ ] Tous les AC sont cochés dans le fichier story
- [ ] Les tests sont écrits et passent (≥ 80% couverture)
- [ ] `pnpm build` / `poetry build` passent
- [ ] `pnpm lint` / lint Python passent
- [ ] La documentation est mise à jour si nécessaire
- [ ] Les notes d'implémentation sont ajoutées
- [ ] Le statut de la story est à `DONE` (ou `REVIEW` si attente validation)
- [ ] Le Kanban est à jour
- [ ] L'epic parent est à jour (case cochée, statut si applicable)

---

## Exemple d'utilisation

**Utilisateur :** "Implémente STORY-401"

**Actions de la skill :**

1. **Phase 1 - Analyse :**
   - Lire `STORY-401-cleanup-marketplace-frontend.md`
   - Lire `EPIC-004-ui-refacto-cleanup.md`
   - Explorer `frontend/src/views/Marketplace.vue`
   - Explorer `frontend/src/components/marketplace/`
   - Faire un grep pour les références marketplace
   - Présenter le plan d'implémentation

2. **Phase 2 - Implémentation :**
   - Mettre à jour statut → IN_PROGRESS
   - Supprimer les composants marketplace
   - Supprimer la vue Marketplace.vue
   - Nettoyer le router
   - Nettoyer les stores, services, types
   - Cocher les AC au fur et à mesure

3. **Phase 3 - Validation :**
   - Lancer `pnpm build` → OK
   - Lancer `pnpm lint` → OK
   - Vérifier les tests existants → OK
   - Ajouter les notes d'implémentation
   - Passer à REVIEW
   - Après validation utilisateur → DONE
   - Mettre à jour Kanban et Epic

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Lecture + Mise à jour (statut, AC, notes) |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Mise à jour (case story, statut) |
| `.backlog/kanban.md` | Mise à jour (déplacement selon statut) |
| Fichiers de code | Création/Modification/Suppression |
| Fichiers de tests | Création/Modification |
| Documentation | Mise à jour si nécessaire |
