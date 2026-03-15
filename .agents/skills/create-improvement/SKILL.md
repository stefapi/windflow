---
name: create-improvement
description: Crée une story d'amélioration d'une fonctionnalité existante avec analyse d'impact et plan de non-régression
---

# create-improvement

Cette skill guide la création d'une story d'**amélioration** d'une fonctionnalité existante dans l'application WindFlow. Elle assure une analyse approfondie du code existant, l'identification des risques de régression, et la planification des vérifications de non-régression.

## Usage

Utilise cette skill quand :
- L'utilisateur demande d'améliorer une fonctionnalité existante (ex: "Améliore le formulaire de login")
- L'utilisateur veut optimiser ou enrichir une feature déjà en place
- L'utilisateur signale un problème UX/performance sur une fonctionnalité existante
- L'utilisateur demande d'ajouter une option à un composant existant

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le dossier `.backlog/epics/` existe (pour trouver l'epic parent)
- [ ] Le fichier `.backlog/kanban.md` existe
- [ ] La fonctionnalité à améliorer existe réellement dans le codebase

---

## Phase 1 : Clarification

Si la fonctionnalité n'est pas clairement identifiée ou si la demande est vague, poser les questions suivantes :

### Questions obligatoires (si information manquante)

```
## Clarification nécessaire

Pour créer cette story d'amélioration, j'ai besoin des informations suivantes :

1. **Fonctionnalité cible** : Quelle fonctionnalité précise doit être améliorée ?
   - [ ] Nom du composant/vue/service
   - [ ] Localisation dans l'application (menu, page, section)

2. **Problème ou bénéfice** : Quel est le problème actuel ou le bénéfice attendu ?
   - [ ] Description du comportement actuel
   - [ ] Description du comportement souhaité

3. **Type d'amélioration** :
   - [ ] Performance (temps de réponse, chargement)
   - [ ] UX/UI (ergonomie, accessibilité, visuel)
   - [ ] Fonctionnelle (nouvelle option, extension)
   - [ ] Technique (refactoring, dette technique)
   - [ ] Sécurité

4. **Contraintes particulières** :
   - [ ] Y a-t-il des contraintes de compatibilité (navigateurs, versions) ?
   - [ ] Cette amélioration doit-elle être rétrocompatible ?
   - [ ] Y a-t-il une deadline ?

5. **Impact potentiel** :
   - [ ] Cette amélioration impacte-t-elle d'autres fonctionnalités ?
   - [ ] Y a-t-il des utilisateurs/métiers spécifiquement concernés ?

Merci de fournir ces informations pour que je puisse analyser l'existant et créer une story adaptée.
```

---

## Phase 2 : Analyse de l'Existant

Une fois la fonctionnalité identifiée, explorer le codebase pour comprendre l'implémentation actuelle.

### 2.1 Exploration du code

**Pour une amélioration frontend :**
```bash
# Identifier les fichiers liés à la fonctionnalité
frontend/src/views/           # Vues
frontend/src/components/      # Composants
frontend/src/composables/     # Composables
frontend/src/stores/          # Stores Pinia
frontend/src/services/        # Services API
frontend/src/types/           # Types TypeScript
```

**Pour une amélioration backend :**
```bash
# Identifier les fichiers liés à la fonctionnalité
backend/app/api/v1/           # Endpoints
backend/app/models/           # Modèles SQLAlchemy
backend/app/schemas/          # Schémas Pydantic
backend/app/services/         # Services métier
backend/app/tasks/            # Tâches Celery
```

### 2.2 Recherche des dépendances

Utiliser `grep` ou `search_files` pour identifier :
- Les imports du composant/service
- Les usages dans d'autres fichiers
- Les tests existants

```bash
# Exemple de recherche
grep -r "ComponentName" frontend/src/
grep -r "service_name" backend/app/
```

### 2.3 Identification des tests existants

Lister les tests qui couvrent actuellement la fonctionnalité :
- `frontend/tests/unit/` - Tests unitaires frontend
- `frontend/tests/e2e/` - Tests E2E
- `backend/tests/unit/` - Tests unitaires backend
- `backend/tests/integration/` - Tests d'intégration

### 2.4 Documentation existante

Consulter :
- `doc/general_specs/` - Spécifications générales
- Commentaires dans le code
- README des modules si disponibles

---

## Phase 3 : Identification des Impacts

Analyser les risques de régression et les fonctionnalités potentiellement impactées.

### 3.1 Mapping des dépendances

Créer un tableau des dépendances :

| Fichier | Type | Impact | Risque |
|---------|------|--------|--------|
| Composant A | Utilise la fonctionnalité | Direct | Élevé |
| Service B | Appel API | Indirect | Moyen |
| Store C | État partagé | Direct | Faible |

### 3.2 Identification des risques de régression

Lister les risques potentiels :

```markdown
## Risques de régression identifiés

### Risques élevés
- [ ] Le composant X utilise la même API : vérifier la compatibilité des paramètres
- [ ] Le store Y partage l'état : s'assurer que les mutations restent compatibles

### Risques moyens
- [ ] Le test Z teste le comportement actuel : mettre à jour si comportement change

### Risques faibles
- [ ] Le composant W affiche les mêmes données : vérifier l'affichage
```

### 3.3 Fonctionnalités annexes à vérifier

Identifier les fonctionnalités qui devront être testées après l'amélioration :
- Fonctionnalités utilisant le même composant/service
- Fonctionnalités partageant le même état (store, cache)
- Fonctionnalités avec des flux utilisateur similaires

---

## Phase 4 : Création de la Story

### 4.1 Détermination du numéro de story

Lister les fichiers existants dans `.backlog/stories/` pour déterminer le prochain numéro disponible.
- Format : `STORY-XXX` (numérotation séquentielle globale)
- Exemple : si STORY-422 est le dernier, le prochain est STORY-423

### 4.2 Identification de l'epic parent

Chercher l'epic la plus pertinente dans `.backlog/epics/` :
- Si l'amélioration concerne une epic existante, l'utiliser
- Sinon, créer une epic "Améliorations diverses" ou demander à l'utilisateur

### 4.3 Génération du slug

Créer un slug kebab-case à partir du titre :
- "Amélioration formulaire login" → `amelioration-formulaire-login`
- "Optimisation chargement images" → `optimisation-chargement-images`

### 4.4 Création du fichier story

Créer le fichier `.backlog/stories/STORY-XXX-[slug].md` avec la structure suivante :

```markdown
# STORY-XXX : [Titre de l'amélioration]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]
**Type :** Amélioration

## Description
En tant que [Rôle], je veux [Amélioration souhaitée] afin de [Bénéfice].

### Contexte
Cette story améliore une fonctionnalité existante : [Description de la fonctionnalité actuelle].

### Comportement actuel
[Description du comportement avant amélioration]

### Comportement attendu
[Description du comportement après amélioration]

## Critères d'acceptation (AC)
- [ ] AC 1 : [Critère fonctionnel]
- [ ] AC 2 : [Critère fonctionnel]
- [ ] AC 3 : L'amélioration ne casse pas les fonctionnalités existantes
- [ ] AC 4 : Les tests existants passent toujours
- [ ] AC 5 : [Critère de performance/UX si applicable]

## État d'avancement technique
- [ ] Analyse du code existant
- [ ] Implémentation de l'amélioration
- [ ] Mise à jour des tests unitaires
- [ ] Vérification de non-régression

## Risques de régression

### Fichiers impactés
| Fichier | Impact | Action requise |
|---------|--------|----------------|
| [Fichier 1] | [Description] | [Vérification/Mise à jour] |

### Fonctionnalités annexes à vérifier
- [ ] [Fonctionnalité 1] : Vérifier que [comportement attendu]
- [ ] [Fonctionnalité 2] : Vérifier que [comportement attendu]

### Tests existants à maintenir
- [ ] `[Fichier de test 1]` : Tests liés à [fonctionnalité]
- [ ] `[Fichier de test 2]` : Tests liés à [fonctionnalité]

## Plan de non-régression

### Tests à exécuter avant modification
```bash
# Commandes pour vérifier l'état initial
[Commande de test backend]
[Commande de test frontend]
```

### Tests à exécuter après modification
```bash
# Commandes pour vérifier la non-régression
[Commande de test backend]
[Commande de test frontend]
[Commande de build]
[Commande de lint]
```

### Vérifications manuelles
- [ ] [Vérification manuelle 1]
- [ ] [Vérification manuelle 2]
```

---

## Phase 5 : Mise à jour du Backlog

### 5.1 Mise à jour du Kanban

Ajouter la story dans la colonne **📋 BACKLOG** du fichier `.backlog/kanban.md` :

```markdown
### EPIC-XXX : [Titre de l'Epic]
- [ ] STORY-XXX : [Titre de la story d'amélioration]
```

### 5.2 Mise à jour de l'epic parent

Ajouter la story dans la section `## Liste des Stories liées` de l'epic parent :

```markdown
- [ ] STORY-XXX : [Titre de la story d'amélioration]
```

---

## Résumé de la Skill

### Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] La fonctionnalité à améliorer a été clairement identifiée
- [ ] Le code existant a été analysé (fichiers, dépendances, tests)
- [ ] Les risques de régression ont été identifiés
- [ ] Le fichier story a été créé avec le template standard
- [ ] La section "Risques de régression" est renseignée
- [ ] Le plan de non-régression est défini
- [ ] Le Kanban est à jour
- [ ] L'epic parent est à jour

### Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Création |
| `.backlog/epics/EPIC-XXX-*.md` | Mise à jour (ajout story) |
| `.backlog/kanban.md` | Mise à jour (ajout dans BACKLOG) |
| Fichiers de code | Lecture seule (analyse) |
| Fichiers de tests | Lecture seule (identification) |

---

## Gestion des Erreurs

| Erreur | Action |
|--------|--------|
| Fonctionnalité non trouvée | Demander des précisions à l'utilisateur |
| Impossible d'identifier l'epic parent | Demander à l'utilisateur de spécifier une epic |
| Numéro de story déjà utilisé | Incrémenter jusqu'au prochain numéro libre |
| Risques de régression trop élevés | Alerter l'utilisateur et proposer une alternative |
| Tests existants insuffisants | Recommander d'ajouter des tests avant l'amélioration |

---

## Exemple d'utilisation

**Utilisateur :** "Améliore le temps de chargement de la liste des containers"

**Actions de la skill :**

1. **Phase 1 - Clarification** (si nécessaire) :
   - Demander des précisions sur le contexte (page Dashboard ? Containers view ?)

2. **Phase 2 - Analyse** :
   - Explorer `frontend/src/views/Containers.vue`
   - Explorer `backend/app/api/v1/containers.py`
   - Identifier les appels API et le rendu
   - Lister les tests existants

3. **Phase 3 - Impacts** :
   - Identifier les composants qui utilisent la liste des containers
   - Identifier les risques de régression (pagination, filtres, etc.)

4. **Phase 4 - Création** :
   - Créer `STORY-423-optimisation-chargement-containers.md`
   - Inclure les risques de régression et le plan de vérification

5. **Phase 5 - Backlog** :
   - Ajouter dans le Kanban
   - Lier à l'epic parent

**Résultat :**
```
Story créée : STORY-423 - Optimisation du chargement de la liste des containers

Fichiers analysés :
- frontend/src/views/Containers.vue
- backend/app/api/v1/containers.py
- backend/tests/unit/test_containers.py

Risques de régression identifiés :
- Pagination existante à maintenir
- Filtres de recherche à vérifier

Plan de non-régression :
- Tests backend : pytest backend/tests/unit/test_containers.py
- Tests frontend : pnpm test containers
- Build : pnpm build

La story est prête dans le backlog. Utilise la skill `treat-story` pour l'implémenter.
