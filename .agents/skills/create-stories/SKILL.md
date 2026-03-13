---
name: create-stories
description: Crée toutes les stories d'une epic présente dans .backlog/epics
---

# create-stories

Cette skill permet de créer **toutes les stories** listées dans une epic du dossier `.backlog/epics/`. Elle génère des fichiers stories complets avec descriptions enrichies, critères d'acceptation pertinents et tâches techniques préliminaires.

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

## Étapes

### 1. Sélection de l'epic

Lister les fichiers dans `.backlog/epics/` et présenter les epics disponibles :

```
Quelle epic souhaitez-vous traiter ?

Epics disponibles :
- EPIC-001 : [Titre] (Statut)
- EPIC-002 : [Titre] (Statut)
- EPIC-003 : [Titre] (Statut)
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
- Risques et dépendances

**Liste des stories à créer :**
- Parser la section `## Liste des Stories liées`
- Extraire chaque item avec son titre
- Identifier les éventuels regroupements (sous-sections)

### 3. Détermination de la numérotation

Lister les fichiers existants dans `.backlog/stories/` pour déterminer le prochain numéro disponible.

```
Stories existantes : STORY-401, STORY-402, STORY-452, STORY-461, STORY-462
Prochain numéro disponible : STORY-463
```

**Règles de numérotation :**
- Format : `STORY-XXX` (numérotation séquentielle globale)
- Ignorer les numéros des stories déjà créées
- Si une story de l'epic a déjà un numéro (ex: STORY-401 dans l'epic), vérifier si le fichier existe :
  - Si oui → conserver, ne pas recréer
  - Si non → créer avec ce numéro

### 4. Présentation du résumé

Avant création, présenter un résumé complet :

```
## Résumé des stories à créer

**Epic source :** EPIC-XXX — [Titre]
**Nombre de stories :** X stories à créer

### Stories qui seront créées :
| Numéro | Titre | Slug |
|--------|-------|------|
| STORY-463 | Titre story 1 | titre-story-1 |
| STORY-464 | Titre story 2 | titre-story-2 |
...

### Stories déjà existantes (ignorées) :
- STORY-401 : Déjà créée

Confirmez-vous la création de ces stories ? (oui/non)
```

### 5. Génération du slug

Pour chaque story, créer un slug kebab-case à partir du titre :
- "Audit & suppression Marketplace frontend" → `audit-suppression-marketplace-frontend`
- "Vue Containers — liste avec actions inline" → `vue-containers-liste-actions-inline`
- "Gestion RBAC depuis la page Settings" → `gestion-rbac-settings`

**Règles de slug :**
- Minuscules uniquement
- Remplacer les espaces par des tirets
- Supprimer les caractères spéciaux (accents, ponctuation)
- Maximum 50 caractères

### 6. Inférence du rôle et bénéfice

Analyser le titre et le contexte de l'epic pour déterminer :

**Rôles possibles :**
- `Développeur` — Pour les tâches techniques, refactoring, cleanup
- `Administrateur` — Pour la gestion RBAC, settings, organisations
- `Utilisateur` — Pour les fonctionnalités générales (dashboard, navigation)
- `DevOps` — Pour les déploiements, containers, infrastructure
- `Utilisateur avancé` — Pour les fonctionnalités complexes (plugins, multi-target)

**Bénéfice à inférer depuis :**
- La valeur business de l'epic
- Les critères de succès
- Le contexte de la story

**Exemples d'inférence :**

| Titre story | Rôle inféré | Bénéfice inféré |
|-------------|-------------|-----------------|
| "Audit & suppression Marketplace frontend" | Développeur | nettoyer la base de code avant reconstruction |
| "Vue Containers — liste avec actions inline" | Utilisateur | gérer mes containers rapidement sans changer de page |
| "Gestion RBAC depuis la page Settings" | Administrateur | contrôler les accès et permissions de mon organisation |
| "Barre métriques système" | Utilisateur | monitorer l'état de mon infrastructure en un coup d'œil |

### 7. Génération des critères d'acceptation (AC)

Générer des AC pertinents basés sur :

**Sources d'inspiration :**
- Les critères de succès de l'epic
- Les notes de conception
- Les risques identifiés
- Le type de story (frontend, backend, DB, etc.)

**Patterns d'AC par type de story :**

**Story Frontend (vue/composant) :**
- AC 1 : La vue existe et est accessible via navigation
- AC 2 : Le layout respecte les specs UI (référence `11-UI-mockups.md`)
- AC 3 : Les interactions utilisateur fonctionnent (clic, formulaires)
- AC 4 : La vue est responsive (mobile/tablette/desktop)
- AC 5 : `pnpm build` passe sans erreur
- AC 6 : `pnpm lint` passe sans erreur
- AC 7 : Tests Vitest ≥ 80%

**Story Backend (API) :**
- AC 1 : L'endpoint API est documenté (OpenAPI)
- AC 2 : La validation Pydantic est en place
- AC 3 : Les codes HTTP appropriés sont retournés
- AC 4 : L'authentification/autorisation est vérifiée
- AC 5 : Tests pytest ≥ 80%
- AC 6 : Logs structurés avec correlation ID

**Story Base de données (migration) :**
- AC 1 : La migration Alembic est créée
- AC 2 : La migration `up` fonctionne
- AC 3 : La migration `down` est réversible
- AC 4 : Les modèles SQLAlchemy sont mis à jour
- AC 5 : Tests de migration passent

**Story Cleanup/Suppression :**
- AC 1 : Les fichiers/dossiers sont supprimés
- AC 2 : Aucun import orphelin ne subsiste
- AC 3 : `pnpm build` / `poetry build` passent
- AC 4 : Les routes supprimées retournent 404
- AC 5 : Tests de non-régression passent

### 8. Création du fichier story

Créer le fichier `.backlog/stories/STORY-XXX-[slug].md` avec la structure :

```markdown
# STORY-XXX : [Titre de la Story]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]

## Description
En tant que [Rôle inféré], je veux [Action extraite du titre] afin de [Bénéfice inféré].

## Contexte technique
[Bref extrait des notes de conception de l'epic si pertinent]

## Critères d'acceptation (AC)
- [ ] AC 1 : [AC généré selon le type]
- [ ] AC 2 : ...
- [ ] AC 3 : ...

## État d'avancement technique
- [ ] [Tâche 1 générée depuis le titre et contexte]
- [ ] [Tâche 2]
- [ ] [Tâche 3]

## Dépendances
- [Story précédente dans le groupe si applicable]
- [Autre dépendance identifiée dans l'epic]
```

### 9. Mise à jour de l'epic

Dans le fichier epic, mettre à jour la section `## Liste des Stories liées` :

**Avant :**
```markdown
- [ ] STORY-XXX : Vue Containers — liste avec actions inline
```

**Après :**
```markdown
- [ ] STORY-463 : Vue Containers — liste avec actions inline
```

Si la story avait déjà un numéro placeholder (ex: STORY-401), remplacer par le vrai numéro attribué.

### 10. Mise à jour du Kanban

Ajouter les stories créées dans la colonne **📋 BACKLOG** du fichier `.backlog/kanban.md` :

```markdown
### EPIC-XXX : [Titre de l'Epic]
- [ ] STORY-463 : [Titre story 1]
- [ ] STORY-464 : [Titre story 2]
...
```

Regrouper les stories sous l'epic correspondant.

## Règles de cohérence

Respecter les règles définies dans `.clinerules/01-Project-management.md` :

- **Numérotation :** `STORY-XXX` séquentielle globale (pas par epic)
- **Statut initial :** `TODO`
- **Lien epic :** Reference obligatoire dans l'en-tête
- **Format description :** "En tant que [Rôle], je veux [Action] afin de [Bénéfice]"
- **Kanban :** Toute story TODO doit apparaître dans le kanban

## Exemple d'utilisation

**Utilisateur :** "Crée les stories de l'EPIC-004"

**Actions :**
1. Lire `.backlog/epics/EPIC-004-ui-refacto-cleanup.md`
2. Extraire les 22 stories listées
3. Vérifier les stories existantes (STORY-401, 452, 461, 462 déjà créées)
4. Présenter le résumé des 18 stories à créer
5. Confirmer avec l'utilisateur
6. Générer chaque fichier story avec AC et tâches
7. Mettre à jour l'epic avec les vrais numéros
8. Mettre à jour le kanban

**Résultat :**
- 18 fichiers créés dans `.backlog/stories/`
- EPIC-004.md mis à jour
- kanban.md mis à jour

## Fichiers concernés

| Fichier | Action |
|---------|--------|
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + Mise à jour (numéros stories) |
| `.backlog/stories/STORY-XXX-*.md` | Création (multiple) |
| `.backlog/kanban.md` | Mise à jour (ajout stories dans BACKLOG) |
| `.backlog/story.md` | Référence (template) |

## Gestion des erreurs

| Erreur | Action |
|--------|--------|
| Epic non trouvée | Demander un numéro valide parmi les epics existantes |
| Aucune story listée dans l'epic | Informer l'utilisateur, proposer d'ajouter des items manuellement |
| Story déjà existante | Ignorer et passer à la suivante, signaler dans le résumé |
| Slug déjà utilisé | Ajouter un suffixe numérique (ex: `-2`) |
| Impossible d'inférer le rôle | Utiliser "Utilisateur" par défaut avec note pour review |
| Numéro STORY déjà utilisé | Incrémenter jusqu'au prochain libre |

## Checklist de fin

Avant de conclure, vérifier :
- [ ] Tous les fichiers story sont créés
- [ ] L'epic est mise à jour avec les bons numéros
- [ ] Le kanban contient toutes les nouvelles stories
- [ ] Aucun doublon de numéro
- [ ] Les descriptions suivent le format "En tant que..."
- [ ] Les AC sont pertinents par rapport au type de story
