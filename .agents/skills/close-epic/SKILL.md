---
name: close-epic
description: Ferme une epic en supprimant toutes ses stories et en la marquant comme DONE
---

# close-epic

Cette skill permet de fermer définitivement une epic en supprimant toutes les stories associées (fichiers et références), puis en marquant l'epic comme terminée (`DONE`).

## Usage

Utilise cette skill quand :
- L'utilisateur demande de "fermer une epic" ou "clôturer une epic"
- L'utilisateur veut marquer une epic comme terminée et nettoyer ses stories
- Une epic est complètement terminée et ne nécessite plus de suivi
- L'utilisateur mentionne "close epic" ou "finaliser une epic"

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/epics/` existe et contient au moins une epic
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le fichier `.backlog/kanban.md` existe

## Étapes

### 1. Lister les epics disponibles

Lister les fichiers dans `.backlog/epics/` pour présenter les epics disponibles à l'utilisateur.

### 2. Demander l'epic à fermer

Demander à l'utilisateur quelle epic il souhaite fermer :

```
Quelle epic souhaitez-vous fermer ?

Epics disponibles :
- EPIC-XXX : [Titre] ([statut])
- EPIC-YYY : [Titre] ([statut])
...

Indiquez le numéro de l'epic (ex: EPIC-001) ou son titre.
```

### 3. Analyser l'epic ciblée

Lire le fichier epic sélectionné et identifier :
- Le titre et le statut actuel de l'epic
- Toutes les références à des stories (pattern regex : `STORY-\d{3}`)
- La section "## Liste des Stories liées"

### 4. Identifier les fichiers stories existants

Pour chaque story référencée dans l'epic, vérifier si le fichier correspondant existe dans `.backlog/stories/`.

Exemple : `STORY-401` → vérifier `.backlog/stories/STORY-401-*.md`

### 5. Présenter le résumé des modifications

Avant de procéder, afficher un résumé des modifications proposées :

```
## Résumé de la fermeture pour EPIC-XXX - [Titre]

### Statut actuel
- Statut : [IN_PROGRESS/BLOCKED/TODO]
- Stories référencées : X stories

### Stories qui seront supprimées
| Story | Fichier | Action |
|-------|---------|--------|
| STORY-401 | Existant | Fichier supprimé + références nettoyées |
| STORY-402 | Existant | Fichier supprimé + références nettoyées |
| STORY-403 | Absent | Références nettoyées uniquement |
...

### Actions prévues
1. Suppression de X fichiers stories dans `.backlog/stories/`
2. Nettoyage de la section "Liste des Stories liées" dans l'epic
3. Suppression des références dans le kanban
4. Mise à jour du statut de l'epic à `DONE`

⚠️ Cette action est irréversible. Les fichiers stories seront définitivement supprimés.

Confirmez-vous la fermeture de l'epic ? (oui/non)
```

Si l'epic ne contient aucune story :
```
⚠️ L'epic EPIC-XXX ne contient aucune story.
Voulez-vous simplement marquer l'epic comme DONE ? (oui/non)
```

### 6. Supprimer les fichiers stories

Si l'utilisateur confirme, supprimer chaque fichier story existant dans `.backlog/stories/`.

Utiliser la commande appropriée pour supprimer les fichiers identifiés.

### 7. Nettoyer l'epic

Modifier le fichier epic pour :
1. Vider la section "## Liste des Stories liées" (remplacer par un message indiquant que l'epic est fermée)
2. Mettre à jour le statut à `DONE`

**Avant :**
```markdown
# EPIC-XXX : [Titre]

**Statut :** IN_PROGRESS
...

## Liste des Stories liées
- [x] STORY-401 : Titre story 1
- [ ] STORY-402 : Titre story 2
...
```

**Après :**
```markdown
# EPIC-XXX : [Titre]

**Statut :** DONE
...

## Liste des Stories liées

> ⚠️ Cette epic est fermée. Toutes les stories ont été supprimées le [DATE].

## Historique de clôture

- **Date de fermeture :** [DATE]
- **Stories supprimées :** STORY-401, STORY-402, ...
- **Raison :** Epic terminée
```

### 8. Nettoyer le kanban

Lire `.backlog/kanban.md` et supprimer toute référence aux stories de l'epic :

**Formats de lignes à supprimer :**
```markdown
- [ ] STORY-XXX : [Titre]
- [~] STORY-XXX : [Titre]
- [?] STORY-XXX : [Titre]
- [!] STORY-XXX : [Titre]
- [x] STORY-XXX : [Titre]
```

Si l'epic apparaît dans une section du kanban, la supprimer également ou la déplacer vers la section "✅ DONE" si elle n'y est pas déjà.

### 9. Rapport final

Afficher un rapport des modifications effectuées :

```
## ✅ Epic EPIC-XXX fermée avec succès

### Fichiers stories supprimés
- `.backlog/stories/STORY-401-titre.md`
- `.backlog/stories/STORY-402-titre.md`
...

### Modifications dans l'epic
- Statut mis à jour : IN_PROGRESS → DONE
- Section "Liste des Stories liées" vidée
- Historique de clôture ajouté

### Modifications dans le kanban
- X stories supprimées du kanban
- Epic déplacée/supprimée du kanban (si applicable)

### Résumé
- Epic : EPIC-XXX - [Titre]
- Statut final : DONE
- Stories supprimées : X
```

## Règles de cohérence

Respecter les règles définies dans `.clinerules/01-Project-management.md` :
- Ne jamais supprimer un fichier qui n'appartient pas à l'epic ciblée
- Préserver la structure globale du fichier epic
- Documenter la fermeture avec la date et les stories supprimées
- Le statut `DONE` est un état final (pas de transition possible après)

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic non trouvée | Demander à l'utilisateur de vérifier le numéro |
| Epic déjà DONE | Informer l'utilisateur que l'epic est déjà fermée |
| Erreur de suppression de fichier | Reporter l'erreur et demander comment procéder |
| Kanban non trouvé | Continuer sans modifier le kanban et informer l'utilisateur |
| Permission refusée | Informer l'utilisateur du problème de permissions |

## Exemple d'utilisation

**Utilisateur :** "Ferme l'epic EPIC-001"

**Action :**
1. Lire EPIC-001 → stories STORY-401 à STORY-410
2. Vérifier les fichiers existants
3. Présenter le résumé avec les 10 stories à supprimer
4. Confirmer avec l'utilisateur
5. Supprimer les fichiers stories
6. Vider la section "Liste des Stories liées" et ajouter l'historique
7. Mettre le statut à DONE
8. Nettoyer le kanban
9. Afficher le rapport final

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Modification |
| `.backlog/stories/STORY-YYY-*.md` | Suppression |
| `.backlog/kanban.md` | Lecture + Modification |
