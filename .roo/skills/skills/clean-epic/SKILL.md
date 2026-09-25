---
name: clean-epic
description: Nettoie une epic en supprimant les références aux stories qui n'existent plus dans .backlog/stories/
---

# clean-epic

Cette skill permet de nettoyer une epic en supprimant toutes les références aux stories qui n'ont pas de fichier correspondant dans `.backlog/stories/`. Elle met également à jour le kanban pour supprimer ces mêmes références.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de "nettoyer une epic"
- L'utilisateur veut synchroniser une epic avec les stories réellement existantes
- Après suppression manuelle de fichiers stories
- L'utilisateur mentionne des "stories orphelines" ou des "références mortes"

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/epics/` existe et contient au moins une epic
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le fichier `.backlog/kanban.md` existe

## Étapes

### 1. Lister les epics disponibles

Lister les fichiers dans `.backlog/epics/` pour présenter les epics disponibles à l'utilisateur.

### 2. Demander l'epic à nettoyer

Demander à l'utilisateur quelle epic il souhaite nettoyer :

```
Quelle epic souhaitez-vous nettoyer ?

Epics disponibles :
- EPIC-XXX : [Titre] ([statut])
- EPIC-YYY : [Titre] ([statut])
...

Indiquez le numéro de l'epic (ex: EPIC-001) ou son titre.
```

### 3. Lister les stories existantes

Lister tous les fichiers dans `.backlog/stories/` et extraire les numéros de stories (STORY-XXX) depuis les noms de fichiers.

Exemple : `STORY-401-cleanup-marketplace-frontend.md` → `STORY-401`

### 4. Analyser l'epic ciblée

Lire le fichier epic sélectionné et identifier toutes les références à des stories :
- Dans la section "## Liste des Stories liées"
- Dans toute autre section qui pourrait contenir des références STORY-XXX

Utiliser une recherche par pattern regex : `STORY-\d{3}`

### 5. Identifier les stories orphelines

Comparer les stories référencées dans l'epic avec les stories réellement existantes :

```
Stories référencées dans l'epic : [STORY-101, STORY-102, ...]
Stories existantes : [STORY-401, STORY-402, ...]
Stories orphelines : [STORY-101, STORY-102, ...] ← à supprimer
```

### 6. Présenter le résumé des modifications

Avant de procéder, afficher un résumé des modifications proposées :

```
## Résumé du nettoyage pour EPIC-XXX

### Stories orphelines détectées (fichiers inexistants)
- STORY-101 : Format manifest YAML
- STORY-102 : API REST Plugin Manager
- STORY-103 : Gestion des dépendances entre plugins
...

### Actions prévues
1. Suppression de X références dans l'epic EPIC-XXX
2. Suppression des références correspondantes dans le kanban (si présentes)

Confirmez-vous le nettoyage ? (oui/non)
```

Si aucune story orpheline n'est détectée :
```
✅ Aucune story orpheline détectée dans EPIC-XXX.
Toutes les stories référencées ont un fichier correspondant.
```

### 7. Nettoyer l'epic

Si l'utilisateur confirme, modifier le fichier epic pour supprimer les lignes contenant les stories orphelines dans la section "## Liste des Stories liées".

**Format de ligne à supprimer :**
```markdown
- [ ] STORY-XXX : [Titre de la story]
```

ou

```markdown
- [x] STORY-XXX : [Titre de la story]
```

### 8. Nettoyer le kanban

Lire `.backlog/kanban.md` et supprimer toute référence aux stories orphelines identifiées.

**Format de ligne à supprimer dans le kanban :**
```markdown
- [ ] STORY-XXX : [Titre]
- [~] STORY-XXX : [Titre]
- [?] STORY-XXX : [Titre]
- [!] STORY-XXX : [Titre]
- [x] STORY-XXX : [Titre]
```

### 9. Rapport final

Afficher un rapport des modifications effectuées :

```
## ✅ Nettoyage terminé pour EPIC-XXX

### Modifications dans l'epic
- X stories orphelines supprimées de la section "Liste des Stories liées"

### Modifications dans le kanban
- X références supprimées (si applicable)

### Stories supprimées
- STORY-101, STORY-102, STORY-103...
```

## Règles de cohérence

Respecter les règles définies dans `.clinerules/01-Project-management.md` :
- Ne jamais supprimer une story qui a un fichier existant
- Préserver la structure et le formatage du fichier epic
- Préserver les autres sections de l'epic inchangées

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic non trouvée | Demander à l'utilisateur de vérifier le numéro |
| Aucune story dans l'epic | Informer l'utilisateur qu'il n'y a rien à nettoyer |
| Erreur de lecture/écriture | Reporter l'erreur et demander comment procéder |
| Kanban non trouvé | Nettoyer uniquement l'epic et informer l'utilisateur |

## Exemple d'utilisation

**Utilisateur :** "Nettoie l'epic EPIC-001"

**Action :**
1. Lister les stories existantes → STORY-401 à STORY-462
2. Lire EPIC-001 → référence STORY-101 à STORY-134
3. Identifier les orphelines → toutes (101-134 n'existent pas)
4. Présenter le résumé
5. Confirmer avec l'utilisateur
6. Supprimer les références dans l'epic
7. Supprimer les références dans le kanban (si présentes)
8. Afficher le rapport final

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Modification |
| `.backlog/kanban.md` | Lecture + Modification |
| `.backlog/stories/` | Lecture seule (référence) |
