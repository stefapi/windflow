---
name: close-epic
description: Ferme une epic en conservant toutes ses stories (aucune suppression de fichier), ajoute une section « Historique de clôture » et marque l'epic comme DONE
---

# close-epic

Cette skill permet de fermer une epic en la marquant comme terminée (`DONE`) **sans supprimer aucun fichier** : toutes les stories sont conservées sur disque pour l'historique (règle d'or §7 de `.roo/rules/01-Project-management.md` — « ne supprime jamais un fichier de backlog »).

## Usage

Utilise cette skill quand :
- L'utilisateur demande de "fermer une epic" ou "clôturer une epic"
- L'utilisateur veut marquer une epic comme terminée et archiver son périmètre
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
- Toutes les références à des stories (pattern regex : `STORY-\d{3}(?:\.\d+)?` — couvre les stories `STORY-XXX` et les sous-stories `STORY-XXX.N`)
- La section "## Liste des Stories liées"

### 4. Identifier les fichiers stories existants et leur état

Pour chaque story référencée dans l'epic, vérifier si le fichier correspondant existe dans `.backlog/stories/` et lire son statut.

Exemple : `STORY-401` → vérifier `.backlog/stories/STORY-401-*.md` ; `STORY-130.1` → vérifier `.backlog/stories/STORY-130.1-*.md`

**Règle : aucune story ne doit être supprimée.** Toutes les stories doivent être dans un état **final** (`DONE` ou `ABANDONED`) avant fermeture :

- Story `DONE` ou `ABANDONED` → éligible à la clôture de l'epic
- Story `TODO`, `IN_PROGRESS`, `REVIEW` ou `BLOCKED` → **bloquant** : proposer à l'utilisateur de la passer en `ABANDONED` (avec note explicative dans le fichier story, conformément à la règle d'or §7) ou d'annuler la fermeture
- Story référencée sans fichier existant → proposer de nettoyer la référence via la skill `clean-epic` avant la fermeture

### 5. Présenter le résumé des modifications

Avant de procéder, afficher un résumé des modifications proposées :

```
## Résumé de la fermeture pour EPIC-XXX - [Titre]

### Statut actuel
- Statut : [IN_PROGRESS/BLOCKED/TODO]
- Stories référencées : X stories

### État des stories (aucun fichier ne sera supprimé)
| Story | Fichier | Statut |
|-------|---------|--------|
| STORY-401 | Existant | DONE |
| STORY-402 | Existant | ABANDONED |
| STORY-403 | Absent | Référence orpheline (cf. clean-epic) |
...

### Actions prévues
1. Vérification que toutes les stories sont dans un état final (DONE/ABANDONED) — aucune suppression
2. Ajout d'une section « Historique de clôture » dans l'epic (date, périmètre livré, stories terminées/abandonnées)
3. Mise à jour de la section "Liste des Stories liées" (cases cochées pour les stories DONE)
4. Mise à jour du statut de l'epic à `DONE`
5. Régénération du kanban via `make backlog` (l'epic passe en "✅ DONE", les stories ne sont plus listées individuellement — colonne compacte)

⚠️ Conformément à la règle d'or §7 de `.roo/rules/01-Project-management.md`, tous les fichiers stories sont CONSERVÉS.

Confirmez-vous la fermeture de l'epic ? (oui/non)
```

Si l'epic ne contient aucune story :
```
⚠️ L'epic EPIC-XXX ne contient aucune story.
Voulez-vous simplement marquer l'epic comme DONE ? (oui/non)
```

### 6. Vérifier l'état final des stories

Si l'utilisateur confirme :

1. Pour chaque story non finale (`TODO`, `IN_PROGRESS`, `REVIEW`, `BLOCKED`), demander la décision de l'utilisateur :
   - Passer la story en `ABANDONED` : mettre à jour le titre du fichier (`# STORY-XXX : [ABANDONED] Titre`), ajouter une note explicative dans le corps, **conserver le fichier**
   - Annuler la fermeture de l'epic
2. Ne **jamais** supprimer un fichier story, quelle que soit la circonstance.

### 7. Mettre à jour l'epic

Modifier le fichier epic pour :
1. Mettre à jour le statut à `DONE`
2. Mettre à jour la section "## Liste des Stories liées" : cocher les cases des stories `DONE` (`- [x]`), laisser visibles les stories `ABANDONED` (historique conservé)
3. Ajouter une section « Historique de clôture »

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
- [x] STORY-401 : Titre story 1
- [x] STORY-402 : Titre story 2
- [ ] STORY-403 : Titre story 3  # ABANDONED — voir Historique de clôture
...

## Historique de clôture

- **Date de fermeture :** [DATE]
- **Périmètre livré :** [résumé de ce que l'epic a livré]
- **Stories terminées :** STORY-401, STORY-402, ...
- **Stories abandonnées :** STORY-403 (motif), ...
- **Raison :** Epic terminée
```

### 8. Régénérer le kanban

Le kanban est une vue générée (règle 01 §4.2 — édition manuelle interdite). Ne pas modifier `.backlog/kanban.md` à la main : lancer `make backlog` après les mises à jour des contrats.

Résultat attendu dans le kanban régénéré : l'epic apparaît en "✅ DONE" (vue compacte, avec son compteur de stories DONE) et ses stories ne sont plus listées individuellement dans les colonnes actives — c'est le comportement normal de la colonne compacte.

### 9. Rapport final

Afficher un rapport des modifications effectuées :

```
## ✅ Epic EPIC-XXX fermée avec succès

### Stories conservées (aucune suppression)
- `.backlog/stories/STORY-401-titre.md` — DONE (conservé)
- `.backlog/stories/STORY-402-titre.md` — ABANDONED (conservé)
...

### Modifications dans l'epic
- Statut mis à jour : IN_PROGRESS → DONE
- Section "Liste des Stories liées" mise à jour (cases cochées)
- Section « Historique de clôture » ajoutée (date, périmètre livré, stories terminées/abandonnées)

### Modifications dans le kanban
- Kanban régénéré via `make backlog` : epic en "✅ DONE" (vue compacte), stories DONE/ABANDONED couvertes par le compteur de l'epic

### Résumé
- Epic : EPIC-XXX - [Titre]
- Statut final : DONE
- Stories conservées : X (aucun fichier supprimé)
```

## Règles de cohérence

Respecter les règles définies dans `.roo/rules/01-Project-management.md` :
- **Règle d'or §7 : ne jamais supprimer un fichier de backlog** — toutes les stories sont conservées sur disque
- Ne jamais modifier une story qui n'appartient pas à l'epic ciblée
- Préserver la structure globale du fichier epic
- Documenter la fermeture avec la date et le périmètre livré (section « Historique de clôture »)
- Le statut `DONE` est un état final (pas de transition possible après)
- Une story annulée passe en `ABANDONED` (titre + note explicative), jamais supprimée

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic non trouvée | Demander à l'utilisateur de vérifier le numéro |
| Epic déjà DONE | Informer l'utilisateur que l'epic est déjà fermée |
| Story non finale (TODO/IN_PROGRESS/REVIEW/BLOCKED) | Proposer de la passer en `ABANDONED` (fichier conservé) ou d'annuler |
| Référence orpheline (fichier story absent) | Proposer d'exécuter la skill `clean-epic` avant la fermeture |
| Erreur de lecture/écriture | Reporter l'erreur et demander comment procéder |
| Kanban non trouvé | Continuer et informer l'utilisateur — le kanban sera (re)généré par `make backlog` |
| Permission refusée | Informer l'utilisateur du problème de permissions |

## Exemple d'utilisation

**Utilisateur :** "Ferme l'epic EPIC-001"

**Action :**
1. Lire EPIC-001 → stories STORY-401 à STORY-410
2. Vérifier les fichiers existants et leur statut
3. Présenter le résumé (aucune suppression, stories à abandonner éventuelles)
4. Confirmer avec l'utilisateur
5. Passer les stories non finales en `ABANDONED` si demandé (fichiers conservés)
6. Mettre à jour la section "Liste des Stories liées" et ajouter l'« Historique de clôture »
7. Mettre le statut à DONE
8. Régénérer le kanban via `make backlog` (epic en "✅ DONE")
9. Afficher le rapport final

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Modification (statut, stories liées, historique de clôture) |
| `.backlog/stories/STORY-YYY-*.md` | Lecture + Modification éventuelle (passage ABANDONED) — **jamais suppression** |
| `.backlog/kanban.md` | Lecture (audit) — régénération via `make backlog`, jamais d'édition manuelle |
