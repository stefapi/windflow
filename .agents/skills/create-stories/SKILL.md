---
name: create-stories
description: Crée les stories nécessaires à une epic découpée avec couverture complète des exigences ; aucune story imposée à une epic directe.
---

# create-stories

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

## Conditions de découpage

Cette skill s'applique aux epics en mode `découpée`. Une demande explicite de créer leurs stories autorise le choix de ce mode avec justification ; sinon, une epic directe continue sans story miroir. La règle `01` §2 définit le choix : résultats, dépendances, validations et capacité de revue, jamais un seuil de fichiers ou de tâches.

Pour passer du mode direct au mode découpé, conserver l'identifiant EPIC, ses AC stables, le travail et les preuves acquis ; tracer le changement et répartir tout le reste dans une matrice exigences → AC → stories. Ne pas rejouer le travail déjà accepté ni le perdre. Une epic en cours peut être découpée ; une epic clôturée exige une réouverture autorisée.

Si aucune story n'est encore listée, proposer une répartition cohérente à partir du contrat, sans inventer de périmètre. Utiliser la cible déjà fournie ; la demande de création suffit sans nouvelle confirmation, sauf arbitrage manquant. Générer le kanban s'il manque par `make backlog`.

Cette skill permet de créer **toutes les stories** listées dans une epic du dossier `.backlog/epics/`. Elle génère des fichiers stories **légers** : description, contexte, critères d'acceptation, dépendances. Les tâches d'implémentation détaillées seront ajoutées ultérieurement par `analyse-story`.

**Principe : rester proportionné.** Créer seulement les contrats utiles à des livraisons ou validations distinctes ; conserver toutes les exigences et les cas limites déjà définis.

## Usage

Utilise cette skill quand :
- L'utilisateur demande de créer les stories d'une epic
- L'utilisateur veut générer les stories à partir d'une epic existante
- L'utilisateur référence une epic et demande de « matérialiser » les stories

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] L'epic cible existe et n'est pas clôturée
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le fichier `.backlog/kanban.md` existe (sinon `make backlog`)
- [ ] Le contrat permet de définir les résultats à répartir et leur couverture

## Étapes

### 1. Sélection de l'epic

Si la cible manque, lister les epics disponibles dans `.backlog/epics/` avec leur statut et demander laquelle traiter.

### 2. Lecture et analyse de l'epic

Lire le fichier epic sélectionné et extraire : titre et numéro, vision et valeur business, utilisateurs cibles, notes de conception, critères de succès globaux, source roadmap, et la liste des stories à créer (section `## Liste des Stories liées`).

### 2.5 Lecture obligatoire des documents de spécification

> **Objectif** : garantir que les stories créées couvrent **toutes les exigences** des spécifications, et pas seulement celles listées dans l'epic.

1. **Lire la roadmap** (`docs/Roadmap.md`), cibler la section correspondant à la source de l'epic.
2. **Lire les documents pertinents** de `docs/general_specs/` et `docs/technical_specs/` en croisant les mots-clés de la vision de l'epic.
3. **Extraire les exigences** : modèles de données, comportements attendus, contrats d'API, canaux WebSocket, métriques/seuils, principes opérationnels.
4. **Croiser** avec les stories prévues : chaque exigence relevant du périmètre doit être couverte par au moins une story.
5. **Si des exigences ne sont couvertes par aucune story** : enrichir les AC de la story la plus pertinente, ou créer une story supplémentaire si l'exigence constitue un livrable distinct.

Cette vérification doit être effectuée **avant** la présentation du résumé.

### 3. Détermination de la numérotation

Consulter `.backlog/identifiants.md` et les fichiers conservés, puis appliquer `01` §3 : réserver le prochain identifiant au-delà du maximum attribué du même type, et inscrire chemin/date/motif dans le même changement. Un numéro n'est jamais réutilisé.

Si une story de l'epic a déjà un numéro, vérifier si le fichier existe : si oui → conserver, ne pas recréer ; si non → vérifier le registre : créer seulement si ce numéro est réservé à ce même contrat encore à créer ; restaurer un contrat perdu plutôt que le réinventer.

### 4. Présentation du résumé

Avant création : epic source, nombre de stories, tableau numéro/titre des stories à créer, stories déjà existantes (ignorées). Signaler seulement les arbitrages encore nécessaires.

### 5. Génération du slug

Pour chaque story, slug kebab-case (minuscules sans accents, 5-6 mots au plus).

### 6. Inférence du rôle et bénéfice

Analyser le titre et le contexte pour déterminer le rôle (`Administrateur`, `Opérateur`, `Utilisateur`, `DevOps`, `Développeur`) et le bénéfice de la description « En tant que… ».

### 7. Création du fichier story

Créer `.backlog/stories/STORY-XXX-[slug].md` en suivant le gabarit `.backlog/_models/story.md` (structure légère) :

```markdown
# STORY-XXX : [Titre de la Story]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]

## Description
En tant que [Rôle], je veux [Action] afin de [Bénéfice].

## Contexte technique
<!-- Bref extrait des notes de conception de l'epic si pertinent -->

## Critères d'acceptation (AC)
- [ ] AC 1 : [Critère fonctionnel principal]
- [ ] AC 2 : [Critère fonctionnel secondaire — refus, limites]
- [ ] AC 3 : [Critère technique : make check / lint / tests passent]

## Dépendances
- [Story précédente si applicable, ou « Aucune »]

## Tâches d'implémentation détaillées
<!-- Rempli par analyse-story -->
...
```

**Règles pour les AC :**
- AC observables et stables, aussi nombreux que nécessaires pour couvrir le besoin.
- Inclure les cas de refus, erreurs et limites déjà définis dans la spécification.
- Les contrôles techniques complètent les AC métier ; ils ne les remplacent pas.

**Ne PAS générer :** tâches techniques détaillées, tests à écrire, plan de non-régression — tout cela relève de `analyse-story`.

### 8. Mise à jour de l'epic

Dans le fichier epic, mettre à jour la section `## Liste des Stories liées` avec les vrais numéros attribués.

### 9. Synchronisation du suivi

Compléter listes liées, statuts et registre ; exécuter `make backlog` puis `make backlog-check`. Corriger les sources si un invariant échoue, sans éditer la vue ni retirer une référence pour rendre le contrôle vert.

## Gestion des erreurs

| Erreur | Action |
| --- | --- |
| Epic non trouvée | Demander un numéro valide |
| Aucune story listée | Définir la répartition depuis le contrat en mode découpé ; aucune création en mode direct |
| Story déjà existante | Ignorer et signaler |
| Slug déjà utilisé | Ajouter un suffixe numérique |
| Impossible d'inférer le rôle | Utiliser « Utilisateur » par défaut |

## Étape suivante

Après la création des stories : « ✅ X stories créées pour EPIC-XXX. **Prochaine étape :** pour chaque story, lancer `analyse-story` afin de détailler les tâches d'implémentation avant `treat-story`. Pipeline : create-stories ✅ → analyse-story → treat-story ».

## Fichiers concernés

| Fichier | Action |
| --- | --- |
| `.backlog/epics/EPIC-XXX-*.md` | Lecture + mise à jour (numéros stories) |
| `.backlog/stories/STORY-XXX-*.md` | Création (multiple) |
| `.backlog/identifiants.md` | Mise à jour (réservations) |
| `.backlog/_models/story.md` | Référence (gabarit) |
| `docs/general_specs/*.md`, `docs/technical_specs/*.md` | Lecture seule (couverture des exigences) |
