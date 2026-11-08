---
name: create-improvement
description: Crée une story d'amélioration d'une fonctionnalité existante avec description, contexte et critères d'acceptation.
---

# create-improvement

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

## Compatibilité avec le mode de l'epic

Les stories sont facultatives (règle `01` §2). Si la demande porte explicitement sur une story, la rattacher à une epic découpée. Pour une epic directe active, décider et justifier le passage au mode découpé via `create-stories`, en conservant AC, travail et preuves ; ne pas ajouter silencieusement une story tout en gardant un suivi exécutable EPIC concurrent. Si la demande porte seulement sur une amélioration ou un refactoring borné, une epic directe peut porter le contrat via `create-epic`. Ne pas rouvrir ni modifier le périmètre d'une epic terminée sans autorisation ; créer un contrat successeur référencé si nécessaire. Aucun identifiant ni contrat historique n'est supprimé.

Cette skill guide la création d'une story d'**amélioration** d'une fonctionnalité existante. Elle crée une story **légère** avec description, contexte et critères d'acceptation. L'analyse profonde du code, des impacts et le plan de non-régression seront réalisés par `analyse-story`.

**Principe : rester léger.** Ne pas explorer le code en profondeur ni détailler les tâches techniques. Juste cadrer la story pour qu'elle soit prête à analyser.

## Usage

Utilise cette skill quand :
- L'utilisateur demande d'améliorer une fonctionnalité existante (ex. « Améliore le formulaire de connexion »)
- L'utilisateur veut optimiser ou enrichir une feature déjà en place
- L'utilisateur signale un problème UX/performance sur une fonctionnalité existante
- L'utilisateur demande d'ajouter une option à un composant existant

## Prérequis

Avant d'exécuter cette skill, vérifier :
- [ ] Le dossier `.backlog/stories/` existe
- [ ] Le dossier `.backlog/epics/` existe (pour trouver l'epic parent)
- [ ] Le fichier `.backlog/kanban.md` existe (sinon `make backlog`)

## Pipeline complet

```
create-improvement  →  analyse-story  →  treat-story
(Description+AC)      (Tâches+Impacts+Tests)  (Implémentation)
```

## Phase 1 : Clarification

Si la demande est vague, poser seulement les questions dont la réponse n'est pas évidente depuis le prompt :

1. **Fonctionnalité cible** : quelle fonctionnalité précise doit être améliorée ?
2. **Problème ou bénéfice** : quel est le problème actuel ou le bénéfice attendu ?
3. **Type d'amélioration** : performance / UX-UI / fonctionnelle / technique (dette) / sécurité

## Phase 2 : Création de la Story

### 2.1 Détermination du numéro

Consulter `.backlog/identifiants.md` et les fichiers conservés, puis appliquer `01` §3 : réserver le prochain identifiant au-delà du maximum attribué du même type, et inscrire chemin/date/motif dans le même changement. Les contrats terminés et abandonnés restent attribués.

### 2.2 Identification de l'epic parent

Chercher l'epic la plus pertinente dans `.backlog/epics/` : si l'amélioration concerne une epic existante, l'utiliser ; sinon, demander à l'utilisateur.

### 2.3 Génération du slug

Slug kebab-case à partir du titre (max 5-6 mots).

### 2.4 Création du fichier story

Créer `.backlog/stories/STORY-XXX-[slug].md` en suivant le gabarit `.backlog/_models/story.md` :

```markdown
# STORY-XXX : [Titre de l'amélioration]

**Statut :** TODO
**Epic Parent :** EPIC-XXX — [Titre de l'Epic]

## Description
En tant que [Rôle], je veux [Amélioration souhaitée] afin de [Bénéfice].

## Contexte technique

### Comportement actuel
[Description du comportement avant amélioration — ce qu'on sait sans explorer le code]

### Comportement attendu
[Description du comportement après amélioration]

## Critères d'acceptation (AC)
- [ ] AC 1 : [Critère fonctionnel principal]
- [ ] AC 2 : [Cas de refus/limite si connu]
- [ ] AC 3 : L'amélioration ne casse pas les fonctionnalités existantes
- [ ] AC 4 : make check / lint / tests passent

## Dépendances
- [Dépendances connues, ou « Aucune »]
...
```

**Règles pour les AC :** AC observables aussi nombreux que nécessaire pour couvrir les exigences et cas limites connus ; 1-2 AC fonctionnels, 1 AC de non-régression, 1 AC technique.

**Ne PAS générer :** exploration du code (recherche plein texte, lecture de fichiers source), mapping de dépendances, tableau de risques de régression, tâches techniques détaillées, plan de non-régression, commandes de test.

## Phase 3 : Mise à jour du backlog

### 3.1 Synchronisation du suivi

Après la mise à jour du parent ci-dessous, exécuter `make backlog` puis `make backlog-check`. Le statut des contrats est la source de la vue.

### 3.2 Mise à jour de l'epic parent

Ajouter la story dans la section `## Liste des Stories liées` de l'epic parent : `- [ ] STORY-XXX : [Titre]`.

## Gestion des erreurs

| Erreur | Action |
| --- | --- |
| Fonctionnalité non trouvée | Demander des précisions |
| Impossible d'identifier l'epic parent | Demander à l'utilisateur |
| Numéro de story déjà utilisé | Incrémenter jusqu'au prochain libre |

## Checklist de fin

- [ ] La demande d'amélioration est clairement décrite
- [ ] Le fichier story est créé avec description + AC
- [ ] Le comportement actuel et attendu sont décrits
- [ ] Le suivi est à jour (`make backlog`, `make backlog-check`)
- [ ] L'epic parent est à jour
- [ ] Aucune analyse de code profonde n'a été effectuée

## Fichiers concernés

| Fichier | Action |
| --- | --- |
| `.backlog/stories/STORY-XXX-*.md` | Création |
| `.backlog/epics/EPIC-XXX-*.md` | Mise à jour (ajout story) |
| `.backlog/identifiants.md` | Mise à jour (réservation) |
| `.backlog/_models/story.md` | Référence (gabarit) |
