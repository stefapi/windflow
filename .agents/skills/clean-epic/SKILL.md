---
name: clean-epic
description: Réconcilie les références d'une epic et son kanban sans supprimer les contrats terminés ni leurs preuves.
---

# clean-epic

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Lire le mode de réalisation : une epic directe sans story est normale (liste « Sans objet — réalisation directe »). Une epic découpée est un regroupement de stories ; une liste de stories vide n'est pas une preuve de complétude. Un mode absent doit être établi selon `01` §2, sans fusion implicite des contrats existants.

Utiliser pour nettoyer les références d'une epic, synchroniser son suivi ou rechercher une story manquante. Lire `01` (§3 et §10) et `.backlog/identifiants.md`. Les contrats terminés restent à leur chemin ; l'absence d'une ligne du kanban actif ne rend pas leur référence orpheline.

Identifier la cible depuis la demande ; demander une précision seulement si elle est ambiguë. Lire les références de l'epic, les fichiers, les attributions du registre et le kanban. Comparer les identifiants complets, suffixes de sous-stories compris.

## Réconcilier sans perdre l'historique

| Situation | Action |
| --- | --- |
| Contrat présent, terminé | Conserver son fichier et son lien dans l'epic ; appliquer les règles du kanban actif |
| Contrat présent, lien ou libellé erroné | Corriger le lien ou libellé avec motif, sans changer l'identité du contrat |
| Même référence répétée | Dédupliquer la liste de suivi sans retirer une preuve ni l'historique des décisions |
| Contrat inscrit au registre mais fichier manquant | Rechercher dans Git ; restaurer le contrat identifié à son chemin ou signaler l'anomalie non résolue ; garder l'identifiant réservé et la référence historique |
| Réservation sans fichier | Conserver l'attribution ; distinguer un contrat réservé à créer d'un contrat perdu ; une réservation annulée reste dans le registre |
| Référence jamais attribuée, erreur confirmée | Corriger le renvoi avec motif vers la bonne cible ; si aucune cible n'est établie, consigner la question plutôt qu'effacer un besoin |

Un contrat restauré est le même contrat, avec ses preuves ; ne pas réinventer son contenu. Ne pas traiter un numéro absent comme libre. Aucune suppression de fichier, de décision ou de preuve au titre du nettoyage.

Corriger le suivi selon les statuts et les clôtures enregistrées (`make backlog`) : les éléments terminés d'une epic clôturée sortent du suivi actif ; les contrats et leur liste liée restent accessibles ; les bugs ouverts demeurent suivis. Une anomalie irrésolue est signalée, pas masquée par le nettoyage.

Terminer par les références corrigées, les contrats éventuellement restaurés, les modifications de suivi et les anomalies restantes. Vérifier les liens et le registre (`make backlog-check`). Une seconde exécution sans nouvelle anomalie ne doit pas modifier les contrats.
