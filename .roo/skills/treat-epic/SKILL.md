---
name: treat-epic
description: Traite entièrement une epic en orchestrant le pipeline complet de création, analyse, implémentation et finalisation de toutes ses stories
---

# treat-epic

Cette skill orchestre le **traitement complet d'une epic** en enchaînant séquentiellement les skills existantes du pipeline. Elle agit comme un **coordinateur** : elle ne produit aucun code ni aucune analyse elle-même, mais délègue chaque étape à la skill spécialisée correspondante.

**Principe clé : cette skill est un orchestrateur pur.** Chaque skill fille (`create-stories`, `analyse-story`, `treat-story`, `finalise-story`, `finalise-epic`) est responsable de son propre domaine. Le rôle de `treat-epic` est d'assurer la séquence, la progression et la reprise après interruption.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de "traiter une epic", "implémenter une epic" ou "lancer une epic"
- L'utilisateur veut exécuter le pipeline complet d'une epic (création → analyse → implémentation → finalisation)
- L'utilisateur demande de reprendre le traitement d'une epic interrompue
- L'utilisateur mentionne "pipeline epic", "orchestrer epic", "traitement complet epic"

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/epics/` existe et contient au moins une epic
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le fichier `.backlog/kanban.md` existe
- [ ] L'epic cible n'est pas déjà au statut `DONE`
- [ ] Les skills filles sont disponibles : `create-stories`, `analyse-story`, `treat-story`, `finalise-story`, `finalise-epic`

## Pipeline complet

```
┌─────────────────────────────────────────────────────────────────────┐
│                        treat-epic                                   │
│                                                                     │
│  Phase 1 : Sélection et validation de l'epic                       │
│      │                                                              │
│      ▼                                                              │
│  Phase 2 : create-stories                                          │
│      │                                                              │
│      ▼                                                              │
│  Phase 3 : Pour chaque story ──────────────────────────┐           │
│      │                                                  │           │
│      ├── 3.1 analyse-story                              │           │
│      │        │                                         │           │
│      │        ▼                                         │           │
│      ├── 3.2 treat-story                                │           │
│      │        │                                         │           │
│      │        ▼                                         │           │
│      ├── 3.3 finalise-story                             │           │
│      │        │                                         │           │
│      │        ▼                                         │           │
│      └── 3.4 Bilan intermédiaire ─── story suivante ───┘           │
│                                                                     │
│      ▼                                                              │
│  Phase 4 : finalise-epic                                            │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Phase 1 : Sélection et validation de l'epic

### 1.1 Lister les epics disponibles

Lister les fichiers dans `.backlog/epics/` et présenter les epics disponibles :

```
Quelle epic souhaitez-vous traiter ?

Epics disponibles :
- EPIC-XXX : [Titre] ([statut]) — [N] stories
- EPIC-YYY : [Titre] ([statut]) — [N] stories
...

Indiquez le numéro de l'epic (ex: EPIC-009) ou son titre.
```

### 1.2 Validation de l'epic

Lire le fichier epic sélectionné et vérifier :

- **L'epic existe** dans `.backlog/epics/`
- **Le statut** n'est pas `DONE` (une epic DONE ne peut pas être retraitée)

#### Cas A : Epic valide et prête ✅

- Extraire les métadonnées : titre, statut, priorité, vision
- Extraire la liste des stories attendues (section `## Liste des Stories liées`)
- Afficher un résumé et demander confirmation :

```
Epic sélectionnée : EPIC-XXX — [Titre]
Statut : [statut]
Stories attendues : [N]
Stories déjà existantes : [M]

Confirmez le traitement de cette epic ? (oui/non)
```

#### Cas B : Epic déjà DONE ⚠️

- Informer l'utilisateur que l'epic est déjà terminée
- Proposer de choisir une autre epic ou de lancer `close-epic` si souhaité

#### Cas C : Epic introuvable ❌

- Afficher la liste des epics disponibles
- Demander un identifiant valide

---

## Phase 2 : Création des stories (`create-stories`)

### 2.1 Exécution de `create-stories`

Exécuter la skill `create-stories` pour l'epic sélectionnée. Cette skill crée les fichiers stories dans `.backlog/stories/` à partir de la liste définie dans l'epic.

### 2.2 Vérification de la création

Après l'exécution de `create-stories` :

1. Lister les fichiers créés dans `.backlog/stories/` correspondant à l'epic
2. Comparer avec la liste attendue dans l'epic
3. Présenter le bilan à l'utilisateur :

```
Stories créées par create-stories :
- ✅ STORY-XXX : [Titre]
- ✅ STORY-YYY : [Titre]
- ✅ STORY-ZZZ : [Titre]

3 stories créées. Poursuivre avec le traitement séquentiel ? (oui/non)
```

#### Cas A : Toutes les stories créées ✅

- Confirmer et passer à la Phase 3

#### Cas B : Aucune story créée ❌

- Arrêter le pipeline
- Signaler l'anomalie à l'utilisateur
- Proposer de vérifier l'epic et de relancer `create-stories`

#### Cas C : Stories partiellement créées ⚠️

- Lister les stories manquantes
- Demander à l'utilisateur s'il souhaite continuer avec les stories existantes ou arrêter

---

## Phase 3 : Traitement séquentiel de chaque story

Pour chaque story rattachée à l'epic, **dans l'ordre de priorité** (tel que défini dans l'epic) :

**Mécanisme de reprise :** Avant de traiter une story, vérifier son statut. Si la story est déjà `DONE`, la **skipper automatiquement** et passer à la suivante. Cela permet de reprendre un traitement interrompu sans refaire le travail accompli.

### 3.1 Analyse de la story (`analyse-story`)

Exécuter la skill `analyse-story` sur la story courante.

**Actions :**
1. Lancer `analyse-story` pour la story
2. Vérifier que les tâches détaillées ont été rédigées dans le fichier story (section `## Tâches d'implémentation détaillées`)
3. Si l'analyse produit des sous-stories → les ajouter à la file de traitement de l'epic

#### Cas A : Analyse réussie ✅

- Les tâches détaillées sont présentes dans le fichier story
- Passer à l'étape 3.2

#### Cas B : Analyse échouée ❌

- Documenter l'erreur rencontrée
- Proposer à l'utilisateur :
  - 🔄 Relancer `analyse-story`
  - ⏭️ Passer à la story suivante
  - 🛑 Arrêter le pipeline

#### Cas C : Sous-stories détectées 🔄

- Les sous-stories sont ajoutées à la file de traitement
- Elles seront traitées séquentiellement après les stories principales

### 3.2 Implémentation de la story (`treat-story`)

Exécuter la skill `treat-story` sur la story courante (ou sous-story).

**Actions :**
1. Lancer `treat-story` pour la story
2. Vérifier que toutes les tâches sont cochées (statut DONE) dans le fichier story
3. Vérifier que les tests passent

#### Cas A : Implémentation réussie ✅

- Toutes les tâches sont cochées
- Passer à l'étape 3.3

#### Cas B : Blocage technique ❌

- Documenter le blocage (erreur, dépendance manquante, etc.)
- Demander la décision de l'utilisateur :
  - 🔄 Relancer `treat-story` après correction
  - ⏭️ Passer à la story suivante (story marquée comme bloquée)
  - 🛑 Arrêter le pipeline

### 3.3 Finalisation de la story (`finalise-story`)

Exécuter la skill `finalise-story` sur la story courante.

**Actions :**
1. Lancer `finalise-story` pour la story
2. Lire le verdict produit par la skill

#### Cas A : Verdict CONFORME ✅

- La story est validée et marquée comme traitée avec succès
- Passer au bilan intermédiaire (3.4)

#### Cas B : Verdict NON CONFORME ❌

- Présenter les non-conformités à l'utilisateur
- Proposer les options :
  - 🔄 Relancer `treat-story` pour corriger les anomalies, puis re-finaliser
  - ⏭️ Passer à la story suivante (story marquée comme non conforme)
  - 🛑 Arrêter le pipeline

### 3.4 Bilan intermédiaire

Après chaque story traitée, afficher un résumé de progression :

```
━━━ Bilan intermédiaire ━━━

Story traitée : STORY-XXX — [Titre] ✅
Progression : 3/8 stories traitées

Stories restantes :
- STORY-ZZZ : [Titre] (suivante)
- STORY-WWW : [Titre]
- ...

Poursuivre avec STORY-ZZZ ? (oui/non)
```

**Si l'utilisateur répond non :**
- Sauvegarder l'état de progression
- Indiquer comment reprendre (relancer `treat-epic` — les stories DONE seront skippées)

---

## Phase 4 : Finalisation de l'epic (`finalise-epic`)

### 4.1 Exécution de `finalise-epic`

Exécuter la skill `finalise-epic` sur l'epic. Cette skill audite exhaustivement l'epic, ses stories, le code produit et sa conformité.

### 4.2 Présentation du rapport consolidé

Présenter le rapport de `finalise-epic` à l'utilisateur :

```
━━━ Rapport de finalisation — EPIC-XXX ━━━

Stories conformes : 6/8
Stories non conformes : 2
Critères epic validés : 9/10
Verdict global : [CONFORME / CORRECTIONS NÉCESSAIRES]
```

#### Cas A : Toutes les stories conformes ✅

- Proposer à l'utilisateur de lancer `close-epic` comme étape suivante
- Afficher : "Epic prête pour clôture. Souhaitez-vous lancer `close-epic` ?"

#### Cas B : Non-conformités détectées ⚠️

- Lister les stories non conformes avec les anomalies
- Proposer les options :
  - 🔄 Traiter les stories non conformes (retour Phase 3 pour les stories concernées)
  - 📝 Clôturer avec réserves (documenter les écarts)
  - 🛑 Arrêter et corriger manuellement

---

## Règles de la skill

### Ce que cette skill fait ✅

- Orchestre le pipeline complet de traitement d'une epic de bout en bout
- Coordination séquentielle des skills filles dans l'ordre correct
- Suivi de progression story par story avec bilan intermédiaire
- Gestion des blocages et des erreurs avec escalation à l'utilisateur
- Mécanisme de reprise : les stories déjà DONE sont skippées automatiquement
- Rapport final consolidé après traitement de toutes les stories
- Propose `close-epic` comme étape suivante quand l'epic est conforme

### Ce que cette skill ne fait PAS ❌

- N'écrit pas de code directement (délégué à `treat-story`)
- N'analyse pas le codebase directement (délégué à `analyse-story`)
- Ne crée pas de stories de toutes pièces (délégué à `create-stories`)
- Ne valide pas la qualité technique (délégué à `finalise-story` et `finalise-epic`)
- Ne modifie pas les fichiers epic/story en dehors du workflow défini par les skills filles
- Ne prend pas de décision technique ou d'architecture (rôle de l'utilisateur)

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic introuvable | Demander un identifiant valide parmi les epics disponibles |
| Aucune story créée par `create-stories` | Arrêter le pipeline et signaler l'anomalie |
| `analyse-story` échoue sur une story | Documenter l'erreur, proposer de passer à la story suivante ou d'arrêter |
| `treat-story` échoue (blocage technique) | Documenter le blocage, demander la décision utilisateur (continuer/arrêter) |
| `finalise-story` verdict NON CONFORME | Proposer de relancer `treat-story` ou de passer à la suite |
| `finalise-epic` révèle des non-conformités | Proposer de traiter les stories non conformes ou de clôturer avec réserves |
| Story file manquante après création | Vérifier le système de fichiers, signaler l'incohérence |

---

## Checklist de fin

Avant de conclure l'exécution de cette skill, vérifier :

- [ ] L'epic a été sélectionnée et validée
- [ ] `create-stories` a été exécuté avec succès
- [ ] Chaque story a été traitée par `analyse-story` → `treat-story` → `finalise-story`
- [ ] Les stories déjà DONE ont été skippées (reprise)
- [ ] Les bilans intermédiaires ont été présentés après chaque story
- [ ] Les blocages éventuels ont été documentés et escaladés à l'utilisateur
- [ ] `finalise-epic` a été exécuté et le rapport consolidé présenté
- [ ] Le statut final de l'epic est clair (conforme / non conforme avec réserves)
- [ ] La proposition de `close-epic` a été faite si l'epic est conforme
- [ ] Le kanban a été régénéré via `make backlog` (statuts des contrats à jour)

---

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture (sélection, métadonnées, statut) |
| `.backlog/stories/STORY-XXX-*.md` | Lecture / Modification (via skills filles) |
| `.backlog/kanban.md` | Lecture (suivi des statuts) — régénération via `make backlog` |
