---
name: split-story
description: Découpe une story en sous-stories lorsque des résultats, dépendances, risques ou validations distincts le justifient, avant ou pendant l'implémentation, sans perte de contrat ni de preuve.
---

# split-story

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Cette skill modifie seulement le backlog ; elle n'écrit aucun code. Lire la règle `01`, le contrat cible, son epic, le gabarit `.backlog/_models/sub-story.md`, le registre `.backlog/identifiants.md` et le kanban. Pour une cible EPIC, utiliser `create-stories` avec choix du mode découpé ; ne pas fabriquer une story parente.

## Diagnostiquer et justifier

Utiliser la cible déjà fournie, sinon identifier la story avec l'utilisateur. Lire ses AC, analyse, tâches, tests, notes, preuves et dépendances, ainsi que ses éventuelles sous-stories. Une story `DONE` n'est pas redécoupée ; une réouverture doit être demandée explicitement.

- **Proactif** : story `TODO`, besoin de découpage identifié avant réalisation.
- **Réactif** : story `IN_PROGRESS` ou `BLOCKED`, avec travail acquis et difficultés à diagnostiquer.

Justifier le découpage par des résultats ou validations indépendants, des dépendances, des risques de reprise ou une revue trop large. Le nombre de fichiers, couches, tâches, AC, tentatives ou la durée d'une session n'est jamais à lui seul un déclencheur. S'il manque une analyse suffisante, utiliser `analyse-story` avant de redistribuer le travail ; une ambiguïté métier exige un arbitrage, pas une découpe automatique.

Présenter la répartition concrète et son motif. Une demande explicite de découpage autorise sa mise en œuvre dans le périmètre établi ; demander seulement les arbitrages encore nécessaires. Une annulation laisse les contrats inchangés.

## Répartir sans perdre le travail

Définir des sous-ensembles cohérents et vérifiables, avec dépendances et ordre de réalisation. Conserver dans la parente les tâches et AC déjà acceptés, leurs preuves et leurs identifiants. Ne pas les rejouer dans les enfants.

Chaque AC restant garde son identifiant et son texte, avec un responsable de couverture explicite dans une sous-story. Si un AC transverse exige plusieurs contributions, détailler les contributions et la preuve d'intégration dans la parente ; aucune attribution ambiguë ni couverture perdue. Ne pas marquer un AC acquis parce que les tâches ont seulement été réparties.

Pour chaque sous-story, copier le gabarit `.backlog/_models/sub-story.md`. Adapter le contexte technique, les tâches restantes, les tests et exigences de sécurité (`40` §8) à son périmètre. Renseigner `Story Parente` et `Epic Parent`, statut initial `TODO`. Le nombre de tâches est proportionné au résultat, sans quota.

Réserver les suffixes `STORY-XXX.N` au-delà du maximum déjà attribué à la parente dans le registre et les fichiers conservés, y compris terminés ou abandonnés. Inscrire chemin/date/motif avec la création, vérifier les collisions ; ne jamais recommencer à `.1`, réutiliser un identifiant ni écraser un fichier. Un contrat manquant est recherché dans le registre et Git, puis restauré ou signalé.

## Mettre à jour la parente et le suivi

- Conserver identité, description, AC stables, décisions, dépendances, contexte utile, notes et preuves acquises.
- Ajouter les liens réels sous « Sous-stories », avec couverture et état. Les sous-stories sont liées depuis leur parente, pas ajoutées comme stories principales à l'epic (convention du dépôt : après découpe, le parent est représenté par ses sous-stories dans la liste de l'epic).
- Remplacer le plan actif par le travail acquis et les renvois précis vers les étapes redistribuées. Garder les tests d'intégration et de couverture globale dans la parente ; ne pas effacer une preuve lors du transfert.
- Mettre l'avancement à jour depuis les statuts réels. Une parente ne devient `DONE` qu'après acceptation de tous ses enfants et validation de ses propres AC et critères d'intégration par `finalise-story`.
- En mode proactif, conserver `TODO` : l'analyse et la découpe ne démarrent pas l'implémentation. En mode réactif, conserver `IN_PROGRESS`, ou `BLOCKED` tant que sa cause subsiste. Lever un blocage uniquement sur preuve, avec motif et date ; conserver son historique.
- Ajouter les nouvelles sous-stories au BACKLOG sous le bloc de l'epic (`make backlog`). Synchroniser la ligne de la parente selon son statut réel, sans doublon.

## Reprise d'un découpage

Conserver toutes les sous-stories existantes, leurs identifiants et leur historique. Pour du travail restant à redistribuer, ajouter de nouveaux suffixes au même niveau ; le format du projet ne prévoit pas `STORY-XXX.N.M`. Tracer le transfert dans les contrats concernés, sans présenter un abandon comme une réalisation `DONE`. Ne pas dupliquer un travail déjà attribué à un enfant actif.

## Vérifier et rendre compte

Vérifier couverture complète des AC et exigences, liens parent/enfants, absence de double attribution, conservation des acquis et preuves, registre, statuts et kanban (`make backlog`, `make backlog-check`). Les contrôles d'acceptation restent ceux du contrat, quel que soit le nombre de sous-stories.

Indiquer le motif, les contrats créés, l'ordre de dépendance, le statut réel de la parente, les blocages restants et la prochaine unité à analyser ou implémenter. Ne pas annoncer une résolution obtenue par la seule réorganisation du backlog.
