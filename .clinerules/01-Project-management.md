# Règles de Gestion de Projet (Epics, Stories, Bugs)

Tu es responsable de la tenue à jour du dossier `.backlog/`. Chaque modification de code doit être reflétée dans la documentation de suivi.

## 1. Structure du Backlog
Le projet suit cette hiérarchie de fichiers :
- `.backlog/epics/` : Objectifs de haut niveau (ex: EPIC-001-auth.md).
- `.backlog/stories/` : Tâches unitaires (ex: STORY-001-login-form.md).
- `.backlog/bugs/` : Anomalies signalées (ex: BUG-001-fix-header.md).
- `.backlog/kanban.md` : Vue d'ensemble de l'état d'avancement.

## 2. Règles de Numérotation
- **Epics** : `EPIC-XXX` (numérotation séquentielle globale, ex: EPIC-001, EPIC-002...)
- **Stories** : `STORY-XXX` (numérotation séquentielle globale, pas par epic, ex: STORY-401, STORY-402...)
- **Sous-stories** : `STORY-XXX.N` (numérotation séquentielle au sein de la story parente, ex: STORY-026.1, STORY-026.2, STORY-026.3)
- **Bugs** : `BUG-XXX` (numérotation séquentielle globale, ex: BUG-001, BUG-002...)

Réutilise les numéros libres si besoin

### 2.1 Conventions des Sous-stories

Les sous-stories sont des subdivisions d'une story parente, créées par `analyse-story` lorsque la complexité le justifie (cf. section 5.1.1).

**Nomming des fichiers :**
- Fichier : `STORY-XXX.N-titre-court.md` dans `.backlog/stories/`
- Exemple : `STORY-026.1-etat-healthcheck.md`, `STORY-026.2-config-ressources.md`

**Relations de référence :**
- Chaque sous-story référence sa story parente **et** l'epic de plus haut niveau
- La story parente liste ses sous-stories mais ne contient **pas** de tâches d'implémentation
- Les sous-stories ne sont **pas** listées dans l'epic parent (uniquement dans la story parente)

## 3. Cycle de Vie des Éléments

### 3.1 Cycle de vie des Epics

| Statut        | Définition                                       | Transitions valides              |
|---------------|--------------------------------------------------|----------------------------------|
| `TODO`        | Epic créée, aucune story commencée               | → `IN_PROGRESS`                  |
| `IN_PROGRESS` | Au moins une story en cours de développement     | → `DONE`, `BLOCKED`, `ABANDONED` |
| `BLOCKED`     | Dépendance externe bloquante identifiée          | → `IN_PROGRESS`, `ABANDONED`     |
| `DONE`        | Toutes les stories terminées (DONE ou ABANDONED) | — (état final)                   |
| `ABANDONED`   | Epic annulée, conservée pour historique          | — (état final)                   |

**Règle de statut dérivé :** Le statut d'une epic est automatiquement déduit de ses stories :
- `TODO` : Aucune story n'est `IN_PROGRESS`, `REVIEW`, ou `DONE`
- `IN_PROGRESS` : Au moins une story est `IN_PROGRESS` ou `REVIEW`
- `DONE` : Toutes les stories sont `DONE` ou `ABANDONED`

### 3.2 Cycle de vie des Stories

| Statut        | Définition                                      | Transitions valides           |
|---------------|-------------------------------------------------|-------------------------------|
| `TODO`        | Story créée, prête à développer                 | → `IN_PROGRESS`               |
| `IN_PROGRESS` | Développement en cours                          | → `REVIEW`, `BLOCKED`, `TODO` |
| `REVIEW`      | Développement terminé, en attente de validation | → `DONE`, `IN_PROGRESS`       |
| `BLOCKED`     | Blocage technique ou dépendance externe         | → `IN_PROGRESS`               |
| `DONE`        | Critères d'acceptation validés, tests passants  | — (état final)                |
| `ABANDONED`   | Story annulée, conservée pour historique        | — (état final)                |

**Definition of Done (DoD) pour une Story :**
- [ ] Tous les critères d'acceptation (AC) sont validés
- [ ] Toutes les tâches d'implémentation sont cochées dans "État d'avancement technique"
- [ ] Code revu et approuvé
- [ ] Tests unitaires écrits et passants (couverture ≥ 80%)
- [ ] Pas de régression sur les tests existants
- [ ] Documentation technique mise à jour si nécessaire
- [ ] Section "Notes d'implémentation" ajoutée au fichier story

### 3.3 Cycle de vie des Bugs

| Statut        | Définition                                         | Transitions valides         |
|---------------|----------------------------------------------------|-----------------------------|
| `NEW`         | Bug signalé, non analysé                           | → `CONFIRMED`, `WONT_FIX`   |
| `CONFIRMED`   | Bug reproduit et validé                            | → `IN_PROGRESS`, `WONT_FIX` |
| `IN_PROGRESS` | Correction en cours                                | → `REVIEW`                  |
| `REVIEW`      | Correction terminée, en attente de validation      | → `DONE`, `IN_PROGRESS`     |
| `DONE`        | Bug corrigé et validé                              | — (état final)              |
| `WONT_FIX`    | Bug accepté mais non corrigé (low priority/impact) | — (état final)              |
| `ABANDONED`   | Bug annulé (non reproduit, obsolète)               | — (état final)              |

**Definition of Done (DoD) pour un Bug :**
- [ ] Bug reproduit et compris
- [ ] Cause racine identifiée
- [ ] Correction implémentée
- [ ] Tests de non-régression écrits
- [ ] Section "Résolution" ajoutée au fichier bug

## 4. Règles de Cohérence Obligatoires

### 4.1 Cohérence Epic ↔ Stories

**Règle de référence croisée :**
- Chaque story DOIT référencer son epic parent dans l'en-tête :
  ```markdown
  **Epic Parent :** EPIC-XXX — [Titre de l'Epic]
  ```
- Chaque epic DOIT lister toutes ses stories dans la section `## Liste des Stories liées` :
  ```markdown
  ## Liste des Stories liées
  - [ ] STORY-XXX : [Titre]
  - [x] STORY-YYY : [Titre]  # si terminée
  ```

**Règle de mise à jour :**
- Quand une story passe à `DONE`, cocher la case correspondante dans l'epic
- Quand toutes les stories d'une epic sont `DONE`, mettre à jour le statut de l'epic à `DONE`

### 4.2 Cohérence Stories/Bugs ↔ Kanban

**Présence obligatoire dans le Kanban :**
- Toute story avec un statut `TODO`, `IN_PROGRESS`, `REVIEW`, ou `BLOCKED` DOIT apparaître dans `.backlog/kanban.md`
- Toute sous-story avec un statut `TODO`, `IN_PROGRESS`, `REVIEW`, ou `BLOCKED` DOIT apparaître dans `.backlog/kanban.md` (individuellement, au même titre qu'une story)
- Tout bug avec un statut `CONFIRMED`, `IN_PROGRESS`, ou `REVIEW` DOIT apparaître dans `.backlog/kanban.md`

**Correspondance statut ↔ colonne Kanban :**

| Statut Story/Bug | Colonne Kanban | Marqueur case |
|------------------|----------------|---------------|
| `TODO` | 📋 BACKLOG | `- [ ]` |
| `IN_PROGRESS` | 🏗️ IN PROGRESS | `- [~]` |
| `REVIEW` | 🚧 REVIEW | `- [?]` |
| `BLOCKED` | 🏗️ IN PROGRESS (avec annotation) | `- [!]` |
| `DONE` | ✅ DONE | `- [x]` |

**Structure du fichier kanban.md :**
```markdown
# KANBAN BOARD

## 📋 BACKLOG (À faire)

### EPIC-XXX : [Titre de l'Epic]
- [ ] STORY-YYY : [Titre de la Story]
- [ ] BUG-ZZZ : [Titre du Bug]

## 🏗️ IN PROGRESS (En cours)

### EPIC-XXX : [Titre de l'Epic]
- [~] STORY-YYY : [Titre]  # en cours
- [!] BUG-ZZZ : [Titre]     # bloqué

## 🚧 REVIEW (En attente de validation)

- [?] STORY-YYY : [Titre de la Story]

## ✅ DONE (Terminé)

- [x] STORY-YYY : [Titre de la Story]
- [x] BUG-ZZZ : [Titre du Bug]
```

### 4.3 Checklist de Synchronisation

Avant de clôturer une session de travail, vérifier :
- [ ] Le statut dans le fichier story/bug est à jour
- [ ] La story/bug est dans la bonne colonne du kanban
- [ ] Si la story est terminée, elle est cochée dans l'epic parent
- [ ] Si toutes les stories d'une epic sont terminées, le statut de l'epic est `DONE`

## 5. Protocole d'Exécution

### 5.1 Pipeline de Skills

Le traitement d'une story suit un pipeline en 3 étapes, chacune gérée par une skill dédiée :

```
create-*        →  analyse-story    →  treat-story
(Description+AC)   (Tâches détaillées)  (Implémentation)
```

| Étape | Skill | Produit | Statut story |
|-------|-------|---------|--------------|
| 1. Création | `create-stories`, `create-improvement`, `create-refactoring` | Fichier story avec description + AC | `TODO` |
| 2. Analyse | `analyse-story` | Tâches d'implémentation détaillées, tests à écrire | `TODO` |
| 3. Implémentation | `treat-story` | Code, tests, documentation | `TODO` → `IN_PROGRESS` → `REVIEW` → `DONE` |

**Règles du pipeline :**
- Les skills de création (étape 1) ne génèrent **que** la description et les AC — pas de tâches techniques
- L'analyse (étape 2) explore le code, identifie les patterns et écrit les tâches détaillées dans la story — **sans coder**
- L'implémentation (étape 3) exécute les tâches **dans l'ordre**, fichier par fichier, en suivant exactement les instructions de l'analyse

### 5.1.1 `analyse-story` — Évaluation de complexité et découpe en sous-stories

Lors de l'étape d'analyse (étape 2), la skill `analyse-story` DOIT évaluer la complexité de la story avant de produire les tâches d'implémentation. Si la story est trop complexe pour être traitée en une seule session par un LLM (context window ~200k tokens), elle doit être découpée en sous-stories.

#### Critères de complexité

Une story est considérée **complexe** si elle remplit **au moins un** des critères suivants :
- **Plus de 5 tâches d'implémentation** identifiées lors de l'analyse
- **Plus de 6 fichiers** à modifier/créer
- **Mélange backend + frontend** (couche full-stack avec modifications des deux côtés)
- **Plus de 8 critères d'acceptation** (AC)

Si la story est complexe, procéder à la découpe (cf. processus ci-dessous).
Si la story n'est pas complexe, procéder à l'analyse classique (tâches détaillées dans la story).

#### Processus de découpe

1. **Analyser** les domaines fonctionnels/techniques de la story pour identifier des groupes de tâches cohérents
2. **Proposer un découpage** à l'utilisateur avec :
   - Nombre de sous-stories proposées
   - Titre et périmètre de chaque sous-story
   - AC couverts par chaque sous-story
   - Dépendances entre sous-stories (ordre séquentiel)
3. **Attendre la validation** de l'utilisateur avant de créer les fichiers
4. **Créer les fichiers de sous-stories** en utilisant le template `.backlog/sub-story.md`
5. **Transformer la story parente** : retirer les tâches d'implémentation, ajouter la section `## Sous-stories` listant les sous-stories créées

#### Principes de découpe

- **Cohésion fonctionnelle** : chaque sous-story doit couvrir un domaine cohérent (ex: backend API, frontend composant, helpers/utils, styles)
- **Autonomie** : chaque sous-story doit pouvoir être implémentée et testée indépendamment (dans la mesure du possible)
- **Ordre logique** : les sous-stories sont numérotées séquentiellement (.1, .2, .3...) dans l'ordre d'implémentation recommandé
- **AC répartis** : chaque AC de la story parente doit être couvert par exactement une sous-story
- **Taille cible** : chaque sous-story doit viser 2-4 tâches d'implémentation et rester traitable en une session LLM

#### Structure résultante après découpe

**Story parente (transformée) :**
```markdown
# STORY-XXX : Titre de la Story
**Statut :** TODO
**Epic Parent :** EPIC-YYY — Titre de l'Epic

## Description
[Description inchangée]

## Critères d'acceptation (AC)
[Liste complète des AC — cochée quand la sous-story correspondante est DONE]

## Sous-stories
- [ ] STORY-XXX.1 : [Titre sous-story 1] — Couvre AC 1, AC 2, AC 3
- [ ] STORY-XXX.2 : [Titre sous-story 2] — Couvre AC 4, AC 5
- [ ] STORY-XXX.3 : [Titre sous-story 3] — Couvre AC 6, AC 7, AC 8

## Dépendances
STORY-XXX.2 dépend de STORY-XXX.1
STORY-XXX.3 dépend de STORY-XXX.2
```

**Sous-story (fichier individuel) :**
```markdown
# STORY-XXX.N : [Titre de la sous-story]
**Statut :** TODO
**Story Parente :** STORY-XXX — [Titre de la Story]
**Epic Parent :** EPIC-YYY — [Titre de l'Epic]

## Description
[Sous-ensemble de la description parente, spécifique à cette sous-story]

## Critères d'acceptation (AC)
- [ ] AC X : [Critère hérité de la story parente]
- [ ] AC Y : [Critère hérité de la story parente]

## Contexte technique
[Spécifique à cette sous-story : fichiers concernés, patterns, prérequis]

## Dépendances
- STORY-XXX.(N-1) : [si dépendance sur la sous-story précédente]

## Tâches d'implémentation détaillées
[Remplies par analyse-story — 2 à 4 tâches ciblées]

## Tests à écrire
[Spécifiques à cette sous-story]

## État d'avancement technique
- [ ] Tâche 1 ...
- [ ] Tâche 2 ...
```

### 5.1.2 `treat-story` — Traitement des sous-stories

Quand `treat-story` est appelée sur une story qui a été découpée en sous-stories :
1. Vérifier la présence de la section `## Sous-stories` dans la story parente
2. **Traiter les sous-stories séquentiellement** (.1, puis .2, puis .3...)
3. Pour chaque sous-story :
   - Suivre le même protocole que pour une story classique (§5.2 à §5.4)
   - Mettre à jour le statut de la sous-story
   - Cocher la case correspondante dans la section `## Sous-stories` de la story parente
   - Cocher les AC validés dans la story parente
4. Quand toutes les sous-stories sont `DONE`, la story parente passe automatiquement à `DONE`

### 5.2 Avant le développement

1. **Lecture :** Analyse le fichier STORY ou BUG correspondant pour comprendre les critères d'acceptation (AC).
2. **Vérification :** Vérifie que la section `## Tâches d'implémentation détaillées` est présente (remplie par `analyse-story`). Si absente, lancer `analyse-story` d'abord.
3. **Mise à jour Kanban :** Déplace la story de "BACKLOG" à "IN PROGRESS" dans `.backlog/kanban.md`.
4. **Mise à jour Statut :** Change le statut de la story de `TODO` à `IN_PROGRESS` dans son fichier.

### 5.3 Pendant le développement

1. **Exécution séquentielle :** Implémente chaque tâche dans l'ordre défini dans `## Tâches d'implémentation détaillées`.
2. **Cochage tâches :** Coche les cases dans `## État d'avancement technique` après chaque tâche terminée.
3. **Cochage AC :** Coche les AC correspondants au fur et à mesure de la progression.
4. **Divergence :** Si une tâche s'avère incorrecte, signaler la divergence à l'utilisateur avant d'improviser.
5. **Blocage :** Si bloqué, mets à jour le statut à `BLOCKED` et ajoute une note explicative.

### 5.4 Après le développement

1. **Tests :** Implémente les tests décrits dans `## Tests à écrire` et lance les commandes de validation.
2. **Review :** Change le statut à `REVIEW` et déplace dans la colonne correspondante du kanban.
3. **Validation :** Une fois les tests validés, change le statut à `DONE`.
4. **Clôture Kanban :** Déplace la story dans "DONE" dans le kanban.
5. **Notes :** Ajoute une section "Notes d'implémentation" à la fin du fichier story avec :
   - Fichiers modifiés/créés
   - Décisions techniques prises
   - Divergences par rapport à l'analyse (si applicable)
   - Difficultés rencontrées (le cas échéant)

## 6. Format des Fichiers

### Templates
- **Epic** : `.backlog/epic.md`
- **Story** : `.backlog/story.md`
- **Sous-story** : `.backlog/sub-story.md`
- **Bug** : `.backlog/bug.md`

### Sections obligatoires par type

**Epic :**
- Statut (TODO/IN_PROGRESS/BLOCKED/DONE/ABANDONED)
- Priorité (Haute/Moyenne/Basse)
- Vision
- Liste des Stories liées
- Critères de succès (Definition of Done)

**Story :**
- Statut (TODO/IN_PROGRESS/REVIEW/BLOCKED/DONE/ABANDONED)
- Epic Parent
- Description (format "En tant que...")
- Critères d'acceptation (AC)
- Contexte technique (rempli par `analyse-story` : patterns existants, fichiers de référence)
- Dépendances (rempli par `analyse-story` : stories pré-requises, services externes)
- Tâches d'implémentation détaillées (rempli par `analyse-story` : liste ordonnée des tâches avec fichiers et objectifs)
- Tests à écrire (rempli par `analyse-story` : tests unitaires, intégration, E2E à implémenter)
- État d'avancement technique (cochage progressif pendant `treat-story`)
- Notes d'implémentation (ajoutées à la clôture par `treat-story`)

**Bug :**
- Statut (NEW/CONFIRMED/IN_PROGRESS/REVIEW/DONE/WONT_FIX/ABANDONED)
- Gravité (Bloquant/Majeur/Mineur)
- Reproduction (étapes)
- Comportement attendu vs actuel
- Résolution (ajoutée à la clôture)

## 7. Règle d'Or

**Ne supprime jamais un fichier de backlog.**

Si un élément doit être annulé :
1. Change son statut en `ABANDONED` dans le titre du fichier : `# STORY-XXX : [ABANDONED] Titre`
2. Ajoute une note explicative dans le corps du fichier
3. Retire-le du kanban (uniquement si en BACKLOG, sinon garde-le visible avec le statut ABANDONED)

## 8. Documentation et Spécification

La documentation du projet est présente dans le dossier `doc/`.
Les spécifications sont disponibles dans le dossier `doc/general_specs`.
La Roadmap long terme est dans `doc/IMPLEMENTATION_ROADMAP.md`

## 9. Résumé des Transitions (Aide-mémoire)

```
┌─────────────────────────────────────────────────────────────────┐
│                        CYCLE EPIC                                │
│  TODO ──► IN_PROGRESS ──► DONE                                  │
│              │                                                  │
│              ▼                                                  │
│           BLOCKED ──► IN_PROGRESS (ou ABANDONED)                │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                       CYCLE STORY                                │
│  TODO ──► IN_PROGRESS ──► REVIEW ──► DONE                       │
│              │               │                                  │
│              ▼               │                                  │
│           BLOCKED ──────────►│                                  │
│                              │                                  │
│                              ▼                                  │
│                          IN_PROGRESS (si rejet)                 │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                        CYCLE BUG                                 │
│  NEW ──► CONFIRMED ──► IN_PROGRESS ──► REVIEW ──► DONE          │
│    │         │                                          │       │
│    │         ▼                                          │       │
│    │      WONT_FIX                                      │       │
│    │                                                    │       │
│    └────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────┘
