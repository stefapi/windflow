---
name: treat-story
description: Effectue l'implémentation complète d'une story du backlog
---

# treat-story

Cette skill guide l'implémentation **complète** d'une story : de la lecture des tâches pré-analysées jusqu'à la validation finale et la mise à jour du backlog. Elle exploite le travail de `analyse-story` pour une exécution **ciblée, séquentielle et mécanique**, minimisant les tokens IA et les hallucinations.

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

## Phase 1 : Lecture de la story et détection du plan

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
- **État d'avancement technique** (tâches et leur état)

### 1.2 Détection du plan d'implémentation

**Vérifier si la story a été analysée par `analyse-story`** en cherchant la section `## Tâches d'implémentation détaillées`.

#### Cas A : Story analysée (section présente) ✅ — Mode nominal

La story contient déjà :
- `## Tâches d'implémentation détaillées` avec des `### Tâche N` ordonnées
- `## Tests à écrire` avec fichiers et cas de test
- `## État d'avancement technique` aligné avec les tâches

**Action :** Lire toutes les tâches et présenter un résumé express :

```
## STORY-XXX : [Titre] — Prête à implémenter

**Tâches pré-analysées :** N tâches
1. [x/○] Tâche 1 : [Titre] — [N fichiers]
2. [x/○] Tâche 2 : [Titre] — [N fichiers]
...

**Tests prévus :**
- Backend : [N fichiers de test]
- Frontend : [N fichiers de test]

**Tâches déjà complétées :** X/N
**Prochaine tâche :** Tâche Y — [Titre]

On lance l'implémentation ? (oui/non)
```

**Pas d'exploration du codebase supplémentaire.** Tout est déjà décrit dans les tâches. Passer directement à la Phase 2.

#### Cas B : Story non analysée (section absente) ⚠️ — Mode dégradé

La story n'a pas été pré-analysée.

**Action :** Proposer à l'utilisateur :

```
⚠️ Cette story n'a pas été analysée par `analyse-story`.

Options :
1. **Recommandé** : Lancer d'abord `analyse-story` pour préparer les tâches détaillées
2. Continuer quand même (analyse rapide à la volée — moins précis, plus de tokens)

Que préférez-vous ?
```

**Si l'utilisateur choisit l'option 2** (mode dégradé), effectuer une analyse légère :
- Lire l'epic parent pour le contexte
- Explorer rapidement le code concerné
- Identifier les fichiers à modifier/créer
- Planifier l'ordre d'implémentation
- Présenter le plan pour confirmation

**Note :** En mode dégradé, l'analyse est moins détaillée et plus sujette aux erreurs.

### 1.3 Lecture de l'epic parent (rapide)

Lire le fichier epic dans `.backlog/epics/EPIC-XXX-*.md` pour comprendre :
- La vision globale (en survol rapide)
- Les stories déjà terminées (contexte)
- Les contraintes mentionnées

**Si la story est analysée (Cas A)**, cette lecture est optionnelle — juste un survol pour le contexte.

---

## Phase 2 : Implémentation séquentielle des tâches

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

### 2.2 Exécution séquentielle des tâches

**Principe fondamental :** Exécuter chaque tâche **dans l'ordre**, en suivant **exactement** les instructions détaillées dans la story. Ne pas freelance ni réinventer.

Pour chaque `### Tâche N` dans `## Tâches d'implémentation détaillées` :

#### A. Lire la tâche
- Lire l'**Objectif** pour comprendre le but
- Lire la liste des **Fichiers** avec les actions précises décrites
- Vérifier les **Dépendances** (la tâche précédente doit être terminée si dépendance)

#### B. Implémenter fichier par fichier
Pour chaque fichier listé dans la tâche :
- **Créer** : Créer le fichier avec exactement les classes/méthodes/types décrits. Si un fichier de référence (pattern) est mentionné, le lire d'abord et s'en inspirer.
- **Modifier** : Effectuer exactement les modifications décrites (ajout de méthode, modification de paramètre, ajout d'import, etc.)
- **Supprimer** : Supprimer le fichier et nettoyer les références cassées

**Règle stricte :** S'en tenir à ce qui est décrit. Si pendant l'implémentation une tâche supplémentaire semble nécessaire, la **noter** mais ne pas la faire spontanément — informer l'utilisateur.

#### C. Cocher la tâche
Après implémentation de tous les fichiers d'une tâche :
1. Cocher dans `## État d'avancement technique` :
   ```markdown
   - [x] Tâche N : [Titre]
   ```
2. Cocher les AC correspondants si cette tâche les valide :
   ```markdown
   - [x] AC X : ...
   ```

#### D. Passer à la tâche suivante
Répéter pour chaque tâche restante, dans l'ordre.

**Standards de code à respecter** (référence `.clinerules/30-code-standards.md`) :
- Python : type hints complets, fonctions courtes (~30 lignes), snake_case
- TypeScript : strict, pas de `any`, camelCase, fichiers kebab-case
- Validation : Pydantic côté backend, props typées côté frontend

**Règles API-first** (si applicable, référence `.clinerules/20-architecture-and-api.md`) :
- Documenter les endpoints (OpenAPI)
- Utiliser des schémas Pydantic
- Pagination pour les listes > 20 éléments

### 2.3 Implémentation des tests

Après toutes les tâches d'implémentation, passer à la section `## Tests à écrire` de la story.

Pour chaque fichier de test listé :
1. Lire les **cas de test** décrits
2. Créer le fichier de test en suivant les patterns de test existants du projet
3. Lancer les commandes de validation listées dans la story

Si la section `## Tests à écrire` n'existe pas (mode dégradé), créer les tests appropriés selon les conventions :
- Backend : `pytest` dans `backend/tests/unit/`
- Frontend : Vitest dans `frontend/tests/unit/`

### 2.4 Gestion des blocages

Si un blocage survient pendant le développement :

1. **Mettre à jour le statut** de la story à `BLOCKED`
2. **Ajouter une note** explicative dans le fichier story :
   ```markdown
   ## Blocage
   **Date :** [Date]
   **Tâche bloquée :** Tâche N — [Titre]
   **Raison :** [Description du blocage]
   **Action requise :** [Ce qu'il faut pour débloquer]
   ```
3. **Mettre à jour le Kanban** avec le marqueur `- [!]` et une annotation
4. **Informer l'utilisateur** et demander de l'aide si nécessaire

Une fois débloqué, remettre le statut à `IN_PROGRESS`.

### 2.5 Gestion des divergences

Si pendant l'implémentation, les instructions d'une tâche s'avèrent **incorrectes ou impossibles** :

1. **Ne pas improviser silencieusement**
2. **Informer l'utilisateur** avec :
   ```
   ⚠️ Divergence détectée sur Tâche N :
   - **Prévu :** [Ce que la tâche décrit]
   - **Réalité :** [Ce qui se passe réellement]
   - **Proposition :** [Une solution alternative]
   
   Voulez-vous que je continue avec la proposition, ou ajuster le plan ?
   ```
3. Après décision, mettre à jour la tâche dans la story avec une note de divergence si nécessaire

---

## Phase 3 : Validation et Critères de Succès

### 3.1 Tests

**Lancer les commandes de la section `## Tests à écrire`** de la story si elles existent. Sinon, utiliser les commandes standards :

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
1. Identifier les lignes manquantes
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

Toutes les commandes doivent passer sans erreur.

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

### Fichiers modifiés/créés
- `path/to/file1.py` : [Description de la modification]
- `path/to/file2.vue` : [Description de la modification]

### Décisions techniques
- [Décision 1] : [Raison]
- [Décision 2] : [Raison]

### Divergences par rapport à l'analyse
- [Tâche N] : [Ce qui a changé et pourquoi] (si applicable)

### Difficultés rencontrées
- [Difficulté 1] : [Solution apportée]

### Tests ajoutés
- `tests/unit/test_xxx.py` : [Couverture]
- `tests/yyy.spec.ts` : [Couverture]
```

### 3.6 Vérification de la Definition of Done (DoD)

Avant de passer à REVIEW, vérifier la **DoD complète** :

```markdown
## Definition of Done (DoD) Checklist
- [ ] Tous les critères d'acceptation (AC) sont cochés
- [ ] Toutes les tâches d'implémentation sont cochées dans "État d'avancement technique"
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
   
   ### Tâches complétées
   - [x] Tâche 1 : [Titre]
   - [x] Tâche 2 : [Titre]
   ...
   
   ### AC validés
   - [x] AC 1 : ...
   - [x] AC 2 : ...
   
   ### Tests
   - Couverture : XX%
   - Tous les tests passent : ✅
   
   ### Build/Lint
   - Build : ✅
   - Lint : ✅
   
   ### Divergences (si applicable)
   - [Tâche N] : [Changement]
   
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
| Story pas analysée | Proposer de lancer `analyse-story` d'abord |
| Story déjà DONE | Informer l'utilisateur, demander confirmation pour modification |
| Story BLOCKED | Proposer de résoudre le blocage ou de changer de story |
| Divergence tâche/réalité | Informer l'utilisateur, proposer une alternative |
| Échec de build | Corriger les erreurs avant de continuer |
| Échec de tests | Corriger les tests ou le code, ne pas passer à REVIEW |
| Couverture insuffisante | Ajouter des tests jusqu'à atteindre 80% |
| Dépendance non terminée | Informer l'utilisateur, proposer de traiter la dépendance d'abord |

---

## Checklist de Fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] Toutes les tâches d'implémentation sont cochées dans "État d'avancement technique"
- [ ] Le code est implémenté et fonctionnel
- [ ] Tous les AC sont cochés dans le fichier story
- [ ] Les tests sont écrits et passent (≥ 80% couverture)
- [ ] `pnpm build` / `poetry build` passent
- [ ] `pnpm lint` / lint Python passent
- [ ] La documentation est mise à jour si nécessaire
- [ ] Les notes d'implémentation sont ajoutées (avec divergences si applicable)
- [ ] Le statut de la story est à `DONE` (ou `REVIEW` si attente validation)
- [ ] Le Kanban est à jour
- [ ] L'epic parent est à jour (case cochée, statut si applicable)

---

## Exemple d'utilisation

### Exemple 1 : Story pré-analysée (mode nominal) ✅

**Utilisateur :** "Implémente STORY-446"

**Actions de la skill :**

1. **Phase 1 - Lecture :**
   - Lire `STORY-446-container-detail-stats.md`
   - Détecter : `## Tâches d'implémentation détaillées` présente ✅
   - 4 tâches identifiées, 0 complétées
   - "4 tâches à implémenter. On y va ?"

2. **Phase 2 - Implémentation séquentielle :**
   - **Tâche 1 :** Lire objectif → Créer `container_stats.py`, modifier `websockets.py`, modifier `docker.py` → ✅ Cocher
   - **Tâche 2 :** Lire objectif → Créer `useContainerStats.ts`, modifier `api.ts` → ✅ Cocher
   - **Tâche 3 :** Lire objectif → Créer `ContainerStats.vue` → ✅ Cocher
   - **Tâche 4 :** Lire objectif → Modifier `ContainerDetail.vue` → ✅ Cocher
   - **Tests :** Créer `test_container_stats.py`, `ContainerStats.spec.ts` → ✅ Cocher

3. **Phase 3 - Validation :**
   - Lancer commandes de test de la story → OK
   - `pnpm build` → OK
   - `pnpm lint` → OK
   - Notes d'implémentation → ajoutées
   - REVIEW → DONE

### Exemple 2 : Story non analysée (mode dégradé) ⚠️

**Utilisateur :** "Implémente STORY-500"

**Actions de la skill :**

1. **Phase 1 - Lecture :**
   - Lire `STORY-500-xxx.md`
   - Détecter : Pas de section `## Tâches d'implémentation détaillées` ⚠️
   - "Story non analysée. Recommandation : lancer `analyse-story` d'abord. Continuer quand même ?"

2. **Si l'utilisateur insiste :**
   - Analyse rapide (exploration légère du codebase)
   - Planification à la volée
   - Implémentation (moins ciblée, plus de risque d'erreur)

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Lecture + Mise à jour (statut, AC, tâches cochées, notes) |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Mise à jour (case story, statut) |
| `.backlog/kanban.md` | Mise à jour (déplacement selon statut) |
| Fichiers de code | Création/Modification/Suppression (selon tâches) |
| Fichiers de tests | Création/Modification (selon section Tests) |
| Documentation | Mise à jour si nécessaire |
