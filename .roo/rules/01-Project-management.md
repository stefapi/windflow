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
- **Bugs** : `BUG-XXX` (numérotation séquentielle globale, ex: BUG-001, BUG-002...)

**Registre obligatoire** : toute création d'epic, de story, de sous-story ou de bug réserve d'abord son numéro dans `.backlog/identifiants.md` (chemin + date + motif) **dans le même changement** que la création du contrat. Les numéros ne sont **jamais réutilisés**, les entrées du registre ne sont **jamais retirées** (un abandon se traduit par un changement de statut, pas par une suppression de ligne). Les abandons historiques non inscrits font l'objet d'une rétro-inscription. La numérotation continue au plus haut numéro déjà attribué + 1.

**Sous-stories** : `STORY-XXX.N` = compteur propre à chaque parent (démarrant à 1), tracées au registre comme les stories.

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

**Le kanban est une vue GÉNÉRÉE.** Le statut de référence est le champ `**Statut :**` des contrats (`.backlog/epics/`, `.backlog/stories/`, `.backlog/bugs/`). Le fichier `.backlog/kanban.md` est régénéré intégralement par `make backlog` (`scripts/backlog.py generate`, qui vérifie d'abord les invariants), contrôlé en lecture seule par `make backlog-check`, et **son édition manuelle est interdite** — toute évolution passe par les contrats puis `make backlog`.

**Présence obligatoire dans le Kanban :**
- Toute story avec un statut `TODO`, `IN_PROGRESS`, `REVIEW`, ou `BLOCKED` DOIT apparaître dans `.backlog/kanban.md`
- Tout bug avec un statut `CONFIRMED`, `IN_PROGRESS`, ou `REVIEW` DOIT apparaître dans `.backlog/kanban.md`

**Correspondance statut ↔ colonne Kanban :**

| Statut Story/Bug | Colonne Kanban | Marqueur case |
|------------------|----------------|---------------|
| `TODO` | 📋 BACKLOG | `- [ ]` |
| `IN_PROGRESS` | 🏗️ IN PROGRESS | `- [~]` |
| `REVIEW` | 🚧 REVIEW | `- [?]` |
| `BLOCKED` | 🏗️ IN PROGRESS (avec annotation) | `- [!]` |
| `DONE` | ✅ DONE | `- [x]` |

**Structure du fichier kanban.md (format généré — vue epic-centric) :**
```markdown
# KANBAN BOARD

> ⚠️ **Vue générée automatiquement** par `make backlog` — **ne pas éditer à la main**.

## 📋 BACKLOG

### EPIC-XXX : [Titre de l'Epic] (X/Y stories DONE)
- [ ] STORY-YYY : [Titre de la Story]

### Bugs
- [ ] BUG-ZZZ : [Titre du Bug]

## 🏗️ IN PROGRESS

### EPIC-XXX : [Titre de l'Epic] (X/Y stories DONE)
- [~] STORY-YYY : [Titre]   # en cours
- [!] STORY-ZZZ : [Titre]   # bloqué

## 🚧 REVIEW

- [?] STORY-YYY : [Titre de la Story]

## ✅ DONE

- [x] EPIC-XXX : [Titre de l'Epic] (X/Y stories DONE)   # vue compacte : les epics DONE
- [x] BUG-ZZZ : [Titre du Bug]                          # ne listent pas chaque story DONE
```

La colonne ✅ DONE est **compacte** : les epics terminées y figurent avec leur compteur d'avancement, sans listage individuel des stories DONE ; les stories/parents `ABANDONED` n'apparaissent pas individuellement (seulement dans les compteurs d'epic).

### 4.3 Checklist de Synchronisation

Avant de clôturer une session de travail, vérifier :
- [ ] Le statut dans le fichier story/bug est à jour
- [ ] La story/bug est dans la bonne colonne du kanban
- [ ] Si la story est terminée, elle est cochée dans l'epic parent
- [ ] Si toutes les stories d'une epic sont terminées, le statut de l'epic est `DONE`

## 5. Protocole d'Exécution

### 5.1 Pipeline de Skills

Le traitement d'une story suit un pipeline dont les étapes peuvent varier selon la complexité détectée ou les difficultés d'implémentation :

```
create-*  →  analyse-story  ──────────────────────────►  treat-story  →  finalise-story
                  │                                           │
                  ▼ (si complexité détectée)                 ▼ (si échecs répétés)
             split-story (proactif)                     split-story (réactif)
                  │                                           │
                  ▼                                           ▼
            treat-story ×N                             treat-story ×N
            (sous-stories)                             (sous-stories)
```

| Étape | Skill | Produit | Statut story |
|-------|-------|---------|--------------|
| 1. Création | `create-stories`, `create-improvement`, `create-refactoring` | Fichier story avec description + AC | `TODO` |
| 2. Analyse | `analyse-story` | Tâches d'implémentation détaillées, tests à écrire ; délègue à `split-story` si la story est trop complexe | `TODO` |
| 2b. Découpe *(si nécessaire)* | `split-story` | Sous-stories autonomes remplaçant la story originale | `TODO` |
| 3. Implémentation | `treat-story` | Code, tests, documentation | `TODO` → `IN_PROGRESS` → `REVIEW` → `DONE` |
| 3b. Re-découpe *(si blocage)* | `split-story` | Sous-stories créées à partir d'une story `IN_PROGRESS` ou `BLOCKED` | `TODO` |

**Règles du pipeline :**
- Les skills de création (étape 1) ne génèrent **que** la description et les AC — pas de tâches techniques
- L'analyse (étape 2) explore le code, identifie les patterns et écrit les tâches détaillées dans la story — **sans coder** ; si elle détecte une complexité excessive, elle délègue la découpe à `split-story` au lieu de continuer
- La découpe (étape 2b) crée des sous-stories autonomes dans `.backlog/stories/` et referme la story mère — l'implémentation se fait ensuite sur les sous-stories
- L'implémentation (étape 3) exécute les tâches **dans l'ordre**, fichier par fichier, en suivant exactement les instructions de l'analyse
- Si l'implémentation échoue de façon répétée ou reste bloquée, `split-story` peut être invoquée en mode réactif (étape 3b) pour découper la story en cours et repartir sur des périmètres plus petits

### 5.1.1 Skills utilitaires

En complément du pipeline de stories, des skills autonomes sont disponibles pour des tâches récurrentes :

| Skill | Usage | Produit |
|-------|-------|---------|
| `create-boilerplate` | Génère la structure, la configuration et l'outillage d'un composant (sans implémenter de logique métier) | Squelette projet + mise à jour `.roo/rules` |
| `create-epic` | Crée une epic à partir d'un item de la roadmap | Fichier epic dans `.backlog/epics/` |
| `clean-epic` | Nettoie une epic en supprimant les références aux stories inexistantes | Epic nettoyée |
| `close-epic` | Ferme une epic en supprimant ses stories et en la marquant DONE | Epic et stories fermées |
| `split-story` | Découpe une story en sous-stories autonomes — **mode proactif** (appelé par `analyse-story` si complexité détectée, story `TODO`) ou **mode réactif** (appelé manuellement après échecs répétés sur une story `IN_PROGRESS`/`BLOCKED`) | Sous-stories créées dans `.backlog/stories/`, story mère fermée (`ABANDONED`) |
| `update-rules` | Met à jour les `.roo/rules` en analysant le code réel (backend, frontend, cli) | `.roo/rules` synchronisés avec le code |

**`create-boilerplate`** est une skill générique qui analyse une demande en texte libre, demande des précisions si nécessaire, génère la **structure, la configuration et l'outillage** du composant (fichiers de config, Makefile, Docker, CI, stubs de code vides) et met à jour les `.roo/rules` pour refléter les choix technologiques. Elle ne génère **jamais** de logique métier — l'implémentation est du ressort des stories. Elle n'est pas liée au cycle de vie des stories.

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
- **Epic** : `.backlog/_models/epic.md`
- **Story** : `.backlog/_models/story.md`
- **Sous-story** : `.backlog/_models/sub-story.md`
- **Bug** : `.backlog/_models/bug.md`

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

La documentation du projet est présente dans le dossier `docs/`.
Les spécifications sont disponibles dans le dossier `docs/general_specs`.
La Roadmap long terme est dans `docs/Roadmap.md`

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
