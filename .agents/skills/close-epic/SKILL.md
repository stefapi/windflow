---
name: close-epic
description: Clôture une epic terminée en conservant ses contrats, identifiants et preuves, et retire son suivi du kanban actif.
---

# close-epic

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Utiliser pour une demande de clôture d'epic. Les règles du projet font autorité : lire `01` (§3, §7, §10) et le gabarit `.backlog/_models/epic.md`. La clôture conserve les fichiers et leurs liens à leur chemin ; elle ne supprime aucun contrat ni identifiant.

## Préparer la clôture

Identifier l'epic demandée ; ne demander une précision que si la cible est ambiguë. Lire l'epic, ses stories, sous-stories et bugs liés, ainsi que `.backlog/identifiants.md` et le kanban.

Lire le mode de réalisation. En mode direct, vérifier les AC, le plan et les preuves du contrat EPIC ; la liste des stories indique « Sans objet ». En mode découpé, vérifier une couverture non vide et que toutes les stories et sous-stories sont `DONE`. Dans les deux modes, vérifier la définition commune de terminé (`01` §7), le rapport conforme sur la référence évaluée (`finalise-epic`), les validations requises (`02` §7) et les critères de succès avec leurs preuves. Un test non exécuté reste non validé ; appliquer les conditions de dérogation de `35` §8. Un bug ouvert qui empêche ces critères bloque la clôture. Ne pas cocher les AC ni déclarer les stories terminées pour rendre la clôture possible.

Contrôler les identifiants complets, suffixes compris (`STORY-401` et `STORY-401.1` sont distincts), les chemins et les liens vers les preuves. Compléter les attributions manquantes du registre à partir des contrats existants, sans réutilisation. Un fichier référencé mais absent impose de consulter registre et historique Git : restaurer le même contrat si sa version est identifiée, ou signaler l'anomalie et suspendre la clôture. Ne pas effacer sa référence.

Présenter le résultat des vérifications et les changements prévus. La demande explicite de clôture autorise cette clôture réversible ; une ambiguïté ou un écart aux critères demande un arbitrage, pas une seconde confirmation systématique. Zéro story est normal en mode direct ; seuls les AC et les preuves du contrat permettent sa clôture. En mode découpé, une liste vide reste une anomalie. Une epic sans mode explicite n'est pas prête à clôturer.

## Appliquer la clôture

- Conserver tous les contrats à leur chemin : epic, stories, sous-stories et bugs, avec AC, décisions, notes, preuves et identifiants.
- Conserver la « Liste des Stories liées » avec ses liens ; ne pas la vider.
- Marquer l'epic `DONE` et renseigner son « Historique de clôture » : date, décision, contrats conservés, rapport de finalisation, référence évaluée et preuves. Ne jamais inventer un SHA ou une validation.
- Régénérer le kanban par `make backlog` après mise à jour des contrats : les éléments terminés de l'epic clôturée sortent de la vue ; les bugs ouverts restent suivis. Vérifier `make backlog-check` ; ne pas supprimer ni éditer les contrats pour obtenir ce résultat.
- Conserver toutes les entrées du registre, y compris les réservations abandonnées. Ajouter l'entrée `CHANGELOG.md` (section « Unreleased ») selon les règles du projet.

Vérifier les liens, la concordance des statuts et l'absence de suppression de contrats ou de preuves. Si le kanban manque, le signaler et rétablir la vue à partir des statuts avant de déclarer la clôture complètement synchronisée.

## Rapport et reprise

Indiquer l'epic clôturée, les liens des contrats conservés, les preuves, les lignes sorties du suivi et les éventuelles anomalies. Si elle est déjà clôturée, vérifier les invariants sans créer un deuxième événement de clôture.

Une demande ultérieure de réouverture conserve les identifiants, les chemins et l'historique d'acceptation ; ajouter un événement daté, remettre les éléments concernés au suivi actif et appliquer les transitions autorisées par le projet. Ne pas lancer une réouverture dans le cadre d'une simple clôture.
