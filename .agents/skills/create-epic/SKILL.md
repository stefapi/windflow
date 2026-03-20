---
name: create-epic
description: Crée une epic à partir d'un item de la roadmap doc/general_specs/18-roadmap.md
---

# create-epic

Cette skill permet de créer **une et une seule epic** à partir d'un item sélectionné dans la roadmap du projet(`doc/general_specs/18-roadmap.md`).

## Usage

Utilise cette skill quand :
- L'utilisateur demande de créer une epic à partir de la roadmap
- L'utilisateur veut transformer un item de phase (Phase 2, 3, 4...) en epic
- L'utilisateur référence une fonctionnalité de la roadmap à planifier

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le fichier `doc/general_specs/18-roadmap.md` existe et est lisible
- [ ] Le dossier `.backlog/epics/` existe
- [ ] Le fichier `.backlog/kanban.md` existe

## Étapes

### 1. Lecture de la roadmap
Lire le fichier `doc/general_specs/18-roadmap.md` pour identifier les items disponibles.

### 2. Sélection de l'item
Demander à l'utilisateur quel item de la roadmap doit être transformé en epic et proposant les sujets les plus prioritaires en premier.
Format de la demande :
```
Quel item de la roadmap souhaitez-vous transformer en epic ?

Items disponibles dans la Phase X :
- [Nom de l'item] : [brève description]
- [Nom de l'item] : [brève description]
...

Indiquez le nom de l'item ou la phase/section exacte.
```

### 3. Résumé de l'item
Avant création, présenter un résumé de ce qui sera inclus dans l'epic :
```
## Résumé de l'epic à créer

**Source :** Phase X - [Section]
**Titre proposé :** EPIC-XXX - [Titre]
**Priorité :** [Haute/Moyenne/Basse] (selon phase)

### Vision
[Extrait de la roadmap - description de la fonctionnalité]

### Contenu principal
- [Élément 1]
- [Élément 2]
- ...

### Critères de succès (depuis la roadmap)
- [Critère 1]
- [Critère 2]
- ...

Confirmez-vous la création de cette epic ? (oui/non)
```

### 4. Détermination du numéro d'epic
Lister les fichiers existants dans `.backlog/epics/` pour déterminer le prochain numéro disponible.
- Format : `EPIC-XXX` (numérotation séquentielle globale)
- Exemple : si EPIC-001 à EPIC-004 existent, le prochain est EPIC-005

### 5. Génération du slug
Créer un slug kebab-case à partir du titre :
- "Plugin System & Marketplace" → `plugin-system-marketplace`
- "Gestion des Machines Virtuelles" → `gestion-machines-virtuelles`
- "Multi-Target & Git" → `multi-target-git`

### 6. Création du fichier epic
Créer le fichier `.backlog/epics/EPIC-XXX-[slug].md` avec la structure suivante :

```markdown
# EPIC-XXX : [Titre de l'Epic]

**Statut :** TODO
**Priorité :** [Haute/Moyenne/Basse]
**Phase Roadmap :** [Phase X — QX YYYY]
**Version cible :** [X.X]

## Vision
[Description extraite de la roadmap - valeur ajoutée et objectifs]

### Valeur Business
[Valeur business extraite ou déduite de la roadmap]

### Utilisateurs cibles
[Utilisateurs cibles identifiés]

## Contenu de l'Epic

### [Section 1 de la roadmap]
- [ ] [Item 1]
- [ ] [Item 2]

### [Section 2 de la roadmap]
- [ ] [Item 1]
- [ ] [Item 2]

## Liste des Stories liées
*À créer ultérieurement*

- [ ] STORY-XXX : [Première story suggérée]
- [ ] STORY-XXX : [Deuxième story suggérée]
...

## Notes de conception
[Notes techniques extraites de la roadmap ou à compléter]

## Critères de succès (Definition of Done)
- [ ] [Critère 1 extrait de la roadmap]
- [ ] [Critère 2 extrait de la roadmap]
- [ ] Tous les éléments du contenu implémentés
- [ ] Tests passants (couverture ≥ 80%)

## Risques
| Risque | Impact | Mitigation |
|--------|--------|------------|
| [Risque 1] | [Élevé/Moyen/Faible] | [Mitigation] |

## Dépendances
- [Dépendance 1]
- [Dépendance 2]
```

### 7. Mise à jour du Kanban
Ajouter l'epic dans la colonne **📋 BACKLOG** du fichier `.backlog/kanban.md` :

```markdown
### EPIC-XXX : [Titre de l'Epic]
```

Ne pas ajouter de stories (elles seront créées ultérieurement).

## Règles de cohérence

Respecter les règles définies dans `.clinerules/01-Project-management.md` :
- Numérotation séquentielle globale (`EPIC-XXX`)
- Statut initial : `TODO`
- Référence à la phase roadmap
- Mise à jour obligatoire du kanban

## Exemple d'utilisation

**Utilisateur :** "Crée une epic pour le Plugin System de la Phase 2"

**Action :**
1. Lire la roadmap → identifier "Système de Plugins" dans Phase 2
2. Présenter le résumé
3. Confirmer avec l'utilisateur
4. Créer `EPIC-005-plugin-system-marketplace.md`
5. Mettre à jour le kanban

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `doc/general_specs/18-roadmap.md` | Lecture (source) |
| `.backlog/epics/EPIC-XXX-[slug].md` | Création |
| `.backlog/kanban.md` | Mise à jour (ajout epic dans BACKLOG) |
| `.backlog/epic.md` | Référence (template) |

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Item non trouvé dans la roadmap | Demander une clarification à l'utilisateur |
| Numéro d'epic déjà utilisé | Incrémenter jusqu'au prochain numéro libre |
| Epic déjà existante pour cet item | Informer l'utilisateur et demander confirmation |
| Slug déjà utilisé | Ajouter un suffixe différenciateur |
