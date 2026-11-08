---
name: create-epic
description: Crée une epic à partir d'un item de la roadmap de WindFlow, avec choix du mode de réalisation (directe ou découpée).
---

# create-epic

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

## Choisir le mode de réalisation

Appliquer la règle `01` §2 : sélectionner `directe` pour une livraison bornée, vérifiable et révisable ; `découpée` si des résultats, dépendances ou validations distincts justifient les stories. Inscrire le mode et sa justification dans le résumé puis le contrat (métadonnée `**Mode de réalisation :**`). Ne pas déduire une découpe du seul nombre de fichiers, couches, tâches ou AC.

Pour une epic directe, renseigner les AC stables et la section « Exécution directe » du gabarit ; la liste des stories indique « Sans objet — réalisation directe ». Pour une epic découpée, décrire les résultats à répartir et leurs dépendances ; `create-stories` matérialisera les contrats si nécessaire. Aucun besoin déjà défini ne doit disparaître.

La demande de création autorise le travail dans son périmètre : utiliser l'item déjà indiqué et présenter le résumé sans nouvelle confirmation systématique. Demander seulement les informations ou arbitrages réellement manquants. Si le kanban manque, le générer depuis les contrats par `make backlog`.

Cette skill permet de créer **une et une seule epic** à partir d'un item sélectionné dans la feuille de route du projet (`docs/Roadmap.md`, jamais recopiée ailleurs).

## Usage

Utilise cette skill quand :
- L'utilisateur demande de créer une epic à partir de la roadmap
- L'utilisateur veut transformer un item de phase en epic
- L'utilisateur référence une fonctionnalité de la roadmap à planifier

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] `docs/Roadmap.md` existe et est lisible
- [ ] Le dossier `.backlog/epics/` existe
- [ ] Le fichier `.backlog/kanban.md` existe (sinon `make backlog`)

## Étapes

### 1. Lecture de la roadmap

Lire `docs/Roadmap.md` pour identifier les items disponibles.

### 2. Sélection de l'item

Si la cible n'est pas fournie ou déductible de la demande, demander quel item transformer, en proposant les sujets prioritaires.

### 3. Lecture croisée des documents de spécification

> **Objectif** : enrichir le contenu de l'epic en croisant la roadmap avec les spécifications. C'est la **première ligne de défense** contre les omissions : si une exigence des specs n'est pas capturée à la création de l'epic, elle sera manquante dans tout le pipeline en aval.

1. **Lire la roadmap** (`docs/Roadmap.md`), cibler la section de l'item sélectionné.
2. **Lire les documents pertinents** de `docs/general_specs/` (index `00-index.md`) et `docs/technical_specs/`, en croisant les thèmes de l'item avec leur contenu.
3. **Extraire les exigences** de chaque document pertinent : modèles de données (champs, relations, contraintes), comportements attendus (règles, principes), contrats d'API, canaux WebSocket, dimensions/métriques/seuils, principes opérationnels.
4. **Déterminer le périmètre** de chaque exigence : IN_SCOPE (relève de l'item) ou OUT_OF_SCOPE (phase ultérieure).
5. **Pour chaque exigence IN_SCOPE**, vérifier si elle est couverte par le contenu prévu de l'epic ; sinon l'ajouter au contenu de l'epic avant de présenter le résumé.

### 4. Résumé de l'item

Avant création, présenter un résumé de ce qui sera inclus dans l'epic, enrichi des exigences issues des spécifications : source (section roadmap), titre proposé, priorité, vision, contenu principal, critères de succès. Signaler seulement les arbitrages encore nécessaires.

### 5. Détermination du numéro d'epic

Consulter `.backlog/identifiants.md` et les fichiers conservés, puis appliquer `01` §3 : réserver le prochain identifiant au-delà du maximum attribué du même type, et inscrire chemin/date/motif dans le même changement. Les contrats terminés et abandonnés restent attribués. Un fichier manquant appelle une recherche dans le registre et Git, jamais une réutilisation.

### 6. Génération du slug

Slug kebab-case à partir du titre (minuscules sans accents, 5-6 mots au plus).

### 7. Création du fichier epic

Créer `.backlog/epics/EPIC-XXX-[slug].md` en suivant le gabarit `.backlog/_models/epic.md` : statut initial `TODO`, priorité, mode de réalisation et justification, vision, description, contenu, liste des stories liées, notes de conception, critères de succès, risques, dépendances, source roadmap.

Les sections d'analyse, d'exécution et de preuves sont complétées au stade correspondant ; aucune valeur fictive ne vaut validation.

### 8. Synchronisation du suivi

Renseigner les contrats, modes, listes liées, statuts et registre puis exécuter `make backlog` et `make backlog-check`. Le générateur contrôle les invariants ; il ne crée ni ne répare les contrats.

## Gestion des erreurs

| Erreur | Action |
| --- | --- |
| Item non trouvé dans la roadmap | Demander une clarification à l'utilisateur |
| Numéro d'epic déjà utilisé | Incrémenter jusqu'au prochain numéro libre |
| Epic déjà existante pour cet item | Informer l'utilisateur et demander confirmation |
| Slug déjà utilisé | Ajouter un suffixe différenciateur |
| Document de spécification introuvable | Signaler l'absence, continuer avec les autres documents |
| Exigences IN_SCOPE non couvertes par la roadmap | Ajouter au contenu de l'epic et signaler dans le résumé |

## Fichiers concernés

| Fichier | Action |
| --- | --- |
| `docs/Roadmap.md` | Lecture (source principale) |
| `docs/general_specs/*.md`, `docs/technical_specs/*.md` | Lecture (vérification croisée) |
| `.backlog/epics/EPIC-XXX-[slug].md` | Création |
| `.backlog/identifiants.md` | Mise à jour (réservation) |
| `.backlog/_models/epic.md` | Référence (gabarit) |
