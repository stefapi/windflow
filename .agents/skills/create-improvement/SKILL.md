---
name: create-improvement
description: Crée une story d'amélioration d'une fonctionnalité existante avec description, contexte et critères d'acceptation
---

# create-improvement

Cette skill guide la création d'une story d'**amélioration** d'une fonctionnalité existante. Elle crée une story **légère** avec description, contexte et critères d'acceptation. L'analyse profonde du code, des impacts et le plan de non-régression seront réalisés par `analyse-story`.

**Principe : rester léger.** Ne pas explorer le code en profondeur ni détailler les tâches techniques. Juste cadrer la story pour qu'elle soit prête à analyser.

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

## Pipeline complet

```
create-improvement  →  analyse-story  →  treat-story
(Description+AC)       (Tâches+Impacts+Tests)  (Implémentation)
```

---

## Phase 1 : Clarification

Si la demande est vague, poser les questions nécessaires :

```
## Clarification nécessaire

1. **Fonctionnalité cible** : Quelle fonctionnalité précise doit être améliorée ?
2. **Problème ou bénéfice** : Quel est le problème actuel ou le bénéfice attendu ?
3. **Type d'amélioration** :
   - [ ] Performance
   - [ ] UX/UI
   - [ ] Fonctionnelle (nouvelle option, extension)
   - [ ] Technique (dette technique)
   - [ ] Sécurité
```

Ne poser que les questions dont la réponse n'est pas évidente depuis le prompt de l'utilisateur.

---

## Phase 2 : Création de la Story

### 2.1 Détermination du numéro

Lister les fichiers existants dans `.backlog/stories/` pour déterminer le prochain numéro disponible (`STORY-XXX` séquentiel global).

### 2.2 Identification de l'epic parent

Chercher l'epic la plus pertinente dans `.backlog/epics/` :
- Si l'amélioration concerne une epic existante, l'utiliser
- Sinon, demander à l'utilisateur

### 2.3 Génération du slug

Créer un slug kebab-case à partir du titre (max 50 caractères).

### 2.4 Création du fichier story

Créer `.backlog/stories/STORY-XXX-[slug].md` :

```markdown
# STORY-XXX : [Titre de l'amélioration]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]
**Type :** Amélioration

## Description
En tant que [Rôle], je veux [Amélioration souhaitée] afin de [Bénéfice].

## Contexte technique

### Comportement actuel
[Description du comportement avant amélioration — ce qu'on sait sans explorer le code]

### Comportement attendu
[Description du comportement après amélioration]

## Critères d'acceptation (AC)
- [ ] AC 1 : [Critère fonctionnel principal]
- [ ] AC 2 : [Critère fonctionnel secondaire]
- [ ] AC 3 : L'amélioration ne casse pas les fonctionnalités existantes
- [ ] AC 4 : Build, lint et tests passent

## Dépendances
- [Dépendances connues, ou "Aucune"]

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story — inclura :
- Analyse du code existant
- Fichiers impactés et risques de régression
- Plan de non-régression
- Tâches d'implémentation ordonnées
-->

## Tests à écrire
<!-- Rempli par analyse-story -->
```

**Règles pour les AC :**
- **3 à 5 AC maximum** (rester concis)
- 1-2 AC fonctionnels décrivant le résultat attendu
- 1 AC de non-régression ("ne casse pas l'existant")
- 1 AC technique (build/lint/tests)

**Ne PAS générer :**
- ❌ D'exploration du code (grep, lecture de fichiers source)
- ❌ De mapping de dépendances
- ❌ De tableau de risques de régression
- ❌ De tâches techniques détaillées
- ❌ De plan de non-régression
- ❌ De commandes de test

---

## Phase 3 : Mise à jour du Backlog

### 3.1 Mise à jour du Kanban

Ajouter la story dans la colonne **📋 BACKLOG** du fichier `.backlog/kanban.md` :

```markdown
### EPIC-XXX : [Titre de l'Epic]
- [ ] STORY-XXX : [Titre]
```

### 3.2 Mise à jour de l'epic parent

Ajouter la story dans la section `## Liste des Stories liées` de l'epic parent :

```markdown
- [ ] STORY-XXX : [Titre]
```

---

## Étape suivante

Après création, informer l'utilisateur :

```
✅ Story créée : STORY-XXX — [Titre]

**Prochaine étape :** Lancer `analyse-story STORY-XXX` pour :
- Explorer le code existant et les dépendances
- Identifier les risques de régression
- Détailler les tâches d'implémentation
- Définir le plan de non-régression et les tests

Pipeline : create-improvement ✅ → analyse-story → treat-story
```

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Fonctionnalité non trouvée | Demander des précisions |
| Impossible d'identifier l'epic parent | Demander à l'utilisateur |
| Numéro de story déjà utilisé | Incrémenter |

---

## Checklist de fin

- [ ] La demande d'amélioration est clairement décrite
- [ ] Le fichier story est créé avec description + AC
- [ ] Le comportement actuel et attendu sont décrits
- [ ] Le Kanban est à jour
- [ ] L'epic parent est à jour
- [ ] Aucune analyse de code profonde n'a été effectuée

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Création |
| `.backlog/epics/EPIC-XXX-*.md` | Mise à jour (ajout story) |
| `.backlog/kanban.md` | Mise à jour (ajout dans BACKLOG) |
