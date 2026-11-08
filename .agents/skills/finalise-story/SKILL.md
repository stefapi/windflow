---
name: finalise-story
description: Vérifie les critères, preuves et contrôles d'une story avant d'appliquer sa clôture autorisée.
---

# finalise-story

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Pour une cible EPIC, utiliser `finalise-epic` et terminer cette skill : aucune story miroir ni transition de story ne s'applique à une epic directe.

Lire le [protocole commun](../../../docs/dev/protocole-execution.md) pour les vérifications et preuves, le contrat, son parent, les spécifications pertinentes (`docs/general_specs/`, `docs/technical_specs/`) et le diff évalué. Cette finalisation vérifie le code sans le modifier ; les corrections relèvent de la réalisation autorisée.

## Vérifier la story

- Relier chaque AC stable aux exigences sources, au comportement effectivement livré et à une preuve pertinente. Vérifier les cas de refus, limites et droits selon le périmètre.
- Vérifier que les tâches encore pertinentes, les livrables et la documentation sont complets ; un plan devenu obsolète est expliqué, pas coché fictivement.
- Pour une parente, contrôler les contrats des enfants et leur intégration ; tous doivent avoir atteint leur état requis avant sa clôture.
- Appliquer la définition de terminé de `01` §7 et les contrôles adaptés à la nature du changement selon `35` et la [matrice de validation](../../../docs/dev/controles-validation.md) : `make check` et compléments requis pour l'applicatif, revue et contrôles du corpus pour le documentaire, tests et linters pertinents pour l'outillage. Réutiliser seulement les preuves encore valides selon le protocole commun.
- Vérifier la revue distincte, les validations humaines requises (`02` §7) et la cohérence des références, notes, statuts et liens du backlog.

Un écart bloque le verdict concerné ; poursuivre les vérifications indépendantes afin de présenter les anomalies ensemble. Ne pas relancer un contrôle inchangé sans raison ; tout changement susceptible d'invalider sa preuve exige une nouvelle vérification. Une suite vide, ignorée ou indisponible ne prouve rien.

## Conclure et synchroniser

Consigner un rapport court dans la story : référence du contrat et arbre évalué, AC et preuves, contrôles exécutés ou manquants, anomalies, revue et validations restantes. Une case cochée, un fichier présent ou un score agrégé ne prouve pas l'acceptation.

Passer à `DONE` uniquement si la clôture est autorisée, la définition de terminé satisfaite et toutes les validations requises acquises. Mettre à jour le kanban (`make backlog`), la case du parent et son état agrégé conformément à `01` §8, sans déclarer l'epic terminée ni supprimer de contrat. Une parente avec enfants incomplets ne passe pas `DONE`.

Sinon conserver `REVIEW` si seule l'acceptation reste attendue, revenir à `IN_PROGRESS` pour les corrections engagées, ou utiliser `BLOCKED` selon les dépendances réelles. Identifier la prochaine action sans perdre les preuves déjà acquises. Un audit demandé sur une story déjà terminée ne la rouvre pas automatiquement.
