---
name: create-refactoring
description: Crée une story de refactoring technique avec description, motivation et critères d'acceptation
---

# create-refactoring

Cette skill guide la création d'une story de **refactoring technique** dans WindFlow. Elle crée une story **légère** avec description, motivation et critères d'acceptation. L'analyse profonde de l'architecture, l'identification des impacts et le plan de non-régression seront réalisés par `analyse-story`.

**Principe : rester léger.** Ne pas explorer le code en profondeur, ne pas choisir la méthode de refactoring en détail, ni détailler les tâches techniques. Juste cadrer la story pour qu'elle soit prête à analyser.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de refactorer du code (ex: "Refactor le service de déploiement")
- L'utilisateur veut améliorer la structure/architecture sans changer le comportement
- L'utilisateur identifie de la dette technique à éliminer
- L'utilisateur demande d'appliquer un pattern de conception (SOLID, DRY, etc.)
- L'utilisateur veut réorganiser des modules/composants

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le dossier `.backlog/epics/` existe (pour trouver l'epic parent)
- [ ] Le fichier `.backlog/kanban.md` existe

## Pipeline complet

```
create-refactoring  →  analyse-story  →  treat-story
(Description+AC)       (Méthode+Tâches+Tests)  (Implémentation)
```

---

## Phase 1 : Clarification

Si la demande est vague, poser les questions nécessaires :

```
## Clarification nécessaire

1. **Code cible** : Quel code/module/composant doit être refactoré ?
2. **Motivation** : Pourquoi ce refactoring ? (dette technique, violation SOLID, duplication, complexité, performance, préparation future feature)
3. **Type de refactoring** :
   - [ ] Extraction (méthode, classe, module)
   - [ ] Renommage
   - [ ] Déplacement
   - [ ] Simplification
   - [ ] Introduction de pattern
   - [ ] Suppression de code mort
   - [ ] Réorganisation de structure
4. **Contrainte** : Doit-il être incrémental ou peut-il être fait en un bloc ?
```

Ne poser que les questions dont la réponse n'est pas évidente depuis le prompt de l'utilisateur.

---

## Phase 2 : Création de la Story

### 2.1 Détermination du numéro

Lister les fichiers existants dans `.backlog/stories/` pour déterminer le prochain numéro disponible (`STORY-XXX` séquentiel global).

### 2.2 Identification de l'epic parent

Chercher l'epic la plus pertinente dans `.backlog/epics/` :
- Si le refactoring concerne une epic existante, l'utiliser
- Sinon, demander à l'utilisateur

### 2.3 Génération du slug

Créer un slug kebab-case à partir du titre (max 50 caractères).

### 2.4 Création du fichier story

Créer `.backlog/stories/STORY-XXX-[slug].md` :

```markdown
# STORY-XXX : [Titre du refactoring]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]
**Type :** Refactoring

## Description
En tant que développeur, je veux [Description du refactoring] afin de [Bénéfice attendu].

## Contexte technique

### Motivation
[Pourquoi ce refactoring est nécessaire — référence aux principes SOLID/DRY/KISS si applicable]

### Contrainte principale
Ce refactoring ne doit **pas** changer le comportement externe de l'application.

## Critères d'acceptation (AC)
- [ ] AC 1 : [Objectif principal du refactoring — ex: "Le service respecte SRP"]
- [ ] AC 2 : Le comportement externe est inchangé
- [ ] AC 3 : Tous les tests existants passent
- [ ] AC 4 : La couverture de tests est maintenue ou améliorée (≥ 80%)
- [ ] AC 5 : Build, lint et type checking passent

## Dépendances
- [Dépendances connues, ou "Aucune"]

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story — inclura :
- Analyse de l'architecture existante
- Choix de la méthode de refactoring
- Fichiers impactés et risques de régression
- Comportement à préserver (entrées/sorties/effets de bord)
- Plan de non-régression
- Tâches d'implémentation ordonnées
-->

## Tests à écrire
<!-- Rempli par analyse-story -->
```

**Règles pour les AC :**
- **4 à 6 AC maximum** (rester concis)
- 1 AC décrivant l'objectif du refactoring
- 1 AC de non-régression ("comportement inchangé")
- 1 AC sur les tests existants
- 1-2 AC techniques (couverture, build, lint, type checking)

**Ne PAS générer :**
- ❌ D'exploration du code (grep, lecture de fichiers source)
- ❌ De choix détaillé de méthode de refactoring (Strategy vs extraction, etc.)
- ❌ De mapping de dépendances
- ❌ De documentation du comportement à préserver (entrées/sorties/edge cases)
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
- Explorer l'architecture existante du code cible
- Choisir la méthode de refactoring optimale
- Documenter le comportement à préserver
- Identifier les risques de régression
- Détailler les tâches d'implémentation
- Définir le plan de non-régression et les tests

Pipeline : create-refactoring ✅ → analyse-story → treat-story
```

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Code non trouvé | Demander des précisions |
| Impossible d'identifier l'epic parent | Demander à l'utilisateur |
| Numéro de story déjà utilisé | Incrémenter |
| Demande ambiguë (amélioration vs refactoring) | Clarifier : refactoring = même comportement, amélioration = nouveau comportement |

---

## Checklist de fin

- [ ] La demande de refactoring est clairement décrite
- [ ] La motivation est documentée
- [ ] Le fichier story est créé avec description + AC
- [ ] Le Kanban est à jour
- [ ] L'epic parent est à jour
- [ ] Aucune analyse de code profonde n'a été effectuée

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/stories/STORY-XXX-*.md` | Création |
| `.backlog/epics/EPIC-XXX-*.md` | Mise à jour (ajout story) |
| `.backlog/kanban.md` | Mise à jour (ajout dans BACKLOG) |
