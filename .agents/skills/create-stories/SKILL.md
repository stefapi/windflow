---
name: create-stories
description: Crée toutes les stories d'une epic présente dans .backlog/epics
---

# create-stories

Cette skill permet de créer **toutes les stories** listées dans une epic du dossier `.backlog/epics/`. Elle génère des fichiers stories **légers** : description, contexte et critères d'acceptation uniquement. Les tâches d'implémentation détaillées seront ajoutées ultérieurement par `analyse-story`.

**Principe : rester léger.** Cette skill peut créer 10-20 stories d'un coup. Chaque story doit être créée rapidement avec le strict minimum pour être compréhensible et prête à analyser.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de créer les stories d'une epic
- L'utilisateur veut générer les stories à partir d'une epic existante
- L'utilisateur référence une epic et demande de "matérialiser" les stories

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/epics/` contient au moins une epic à l'état TODO
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le fichier `.backlog/kanban.md` existe
- [ ] L'epic cible a une section `## Liste des Stories liées` avec des items

## Pipeline complet

```
create-stories  →  analyse-story  →  treat-story
(Description+AC)   (Tâches détaillées)  (Implémentation)
```

---

## Étapes

### 1. Sélection de l'epic

Lister les fichiers dans `.backlog/epics/` et présenter les epics disponibles :

```
Quelle epic souhaitez-vous traiter ?

Epics disponibles :
- EPIC-001 : [Titre] (Statut)
- EPIC-002 : [Titre] (Statut)
...

Indiquez le numéro ou le nom de l'epic.
```

### 2. Lecture et analyse de l'epic

Lire le fichier epic sélectionné et extraire :

**Informations de contexte :**
- Titre et numéro de l'epic
- Vision et valeur business
- Utilisateurs cibles
- Notes de conception
- Critères de succès globaux

**Liste des stories à créer :**
- Parser la section `## Liste des Stories liées`
- Extraire chaque item avec son titre
- Identifier les éventuels regroupements (sous-sections)

### 3. Détermination de la numérotation

Lister les fichiers existants dans `.backlog/stories/` pour déterminer le prochain numéro disponible.

**Règles de numérotation :**
- Format : `STORY-XXX` (numérotation séquentielle globale)
- Si une story de l'epic a déjà un numéro, vérifier si le fichier existe :
  - Si oui → conserver, ne pas recréer
  - Si non → créer avec ce numéro

### 4. Présentation du résumé

Avant création, présenter un résumé :

```
## Résumé des stories à créer

**Epic source :** EPIC-XXX — [Titre]
**Nombre de stories :** X stories à créer

### Stories qui seront créées :
| Numéro | Titre |
|--------|-------|
| STORY-463 | Titre story 1 |
| STORY-464 | Titre story 2 |
...

### Stories déjà existantes (ignorées) :
- STORY-401 : Déjà créée

Confirmez-vous la création ? (oui/non)
```

### 5. Génération du slug

Pour chaque story, créer un slug kebab-case à partir du titre :
- Minuscules uniquement
- Remplacer les espaces par des tirets
- Supprimer les caractères spéciaux (accents, ponctuation)
- Maximum 50 caractères

### 6. Inférence du rôle et bénéfice

Analyser le titre et le contexte de l'epic pour déterminer le rôle et le bénéfice.

**Rôles possibles :**
- `Développeur` — Tâches techniques, refactoring, cleanup
- `Administrateur` — Gestion RBAC, settings, organisations
- `Utilisateur` — Fonctionnalités générales (dashboard, navigation)
- `DevOps` — Déploiements, containers, infrastructure

### 7. Création du fichier story

Créer le fichier `.backlog/stories/STORY-XXX-[slug].md` avec la structure **légère** :

```markdown
# STORY-XXX : [Titre de la Story]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]

## Description
En tant que [Rôle inféré], je veux [Action extraite du titre] afin de [Bénéfice inféré].

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->

## Critères d'acceptation (AC)
- [ ] AC 1 : [Critère fonctionnel principal]
- [ ] AC 2 : [Critère fonctionnel secondaire]
- [ ] AC 3 : [Critère technique : build/lint/tests passent]

## Dépendances
- [Story précédente si applicable, ou "Aucune"]

## État d'avancement technique
<!-- Rempli par analyse-story -->

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->

## Tests à écrire
<!-- Rempli par analyse-story -->
```

**Règles pour les AC :**
- **3 à 5 AC maximum** par story (rester concis)
- 1-2 AC fonctionnels (ce que l'utilisateur voit/fait)
- 1 AC technique minimum (build + lint + tests passent)
- Ne pas détailler les cas particuliers (ce sera fait dans `analyse-story`)

**Ne PAS générer :**
- ❌ De tâches techniques dans "État d'avancement technique"
- ❌ De tâches d'implémentation détaillées
- ❌ De tests à écrire
- ❌ De plan de non-régression
- ❌ De risques de régression détaillés

### 8. Mise à jour de l'epic

Dans le fichier epic, mettre à jour la section `## Liste des Stories liées` avec les vrais numéros attribués.

### 9. Mise à jour du Kanban

Ajouter les stories créées dans la colonne **📋 BACKLOG** du fichier `.backlog/kanban.md` :

```markdown
### EPIC-XXX : [Titre de l'Epic]
- [ ] STORY-463 : [Titre story 1]
- [ ] STORY-464 : [Titre story 2]
...
```

---

## Règles de cohérence

Respecter les règles définies dans `.clinerules/01-Project-management.md` :

- **Numérotation :** `STORY-XXX` séquentielle globale (pas par epic)
- **Statut initial :** `TODO`
- **Lien epic :** Référence obligatoire dans l'en-tête
- **Format description :** "En tant que [Rôle], je veux [Action] afin de [Bénéfice]"
- **Kanban :** Toute story TODO doit apparaître dans le kanban

---

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic non trouvée | Demander un numéro valide |
| Aucune story listée dans l'epic | Informer l'utilisateur |
| Story déjà existante | Ignorer et signaler |
| Slug déjà utilisé | Ajouter un suffixe numérique |
| Impossible d'inférer le rôle | Utiliser "Utilisateur" par défaut |
| Numéro STORY déjà utilisé | Incrémenter jusqu'au prochain libre |

---

## Étape suivante

Après la création des stories, informer l'utilisateur :

```
✅ X stories créées pour EPIC-XXX.

**Prochaine étape :** Pour chaque story, lancer `analyse-story` afin de détailler 
les tâches d'implémentation avant de passer à `treat-story`.

Pipeline : create-stories ✅ → analyse-story → treat-story
```

---

## Checklist de fin

- [ ] Tous les fichiers story sont créés
- [ ] L'epic est mise à jour avec les bons numéros
- [ ] Le kanban contient toutes les nouvelles stories
- [ ] Aucun doublon de numéro
- [ ] Les descriptions suivent le format "En tant que..."
- [ ] Les AC sont concis (3-5 par story)
- [ ] Aucune tâche technique prématurée n'est générée

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Mise à jour (numéros stories) |
| `.backlog/stories/STORY-XXX-*.md` | Création (multiple) |
| `.backlog/kanban.md` | Mise à jour (ajout stories dans BACKLOG) |
| `.backlog/story.md` | Référence (template) |
