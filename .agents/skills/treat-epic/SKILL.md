---
name: treat-epic
description: Traite une epic directe ou découpée jusqu'à sa vérification et sa clôture autorisée, avec conservation des contrats et preuves.
---

# treat-epic

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Lire `01`, le contrat cible, ses dépendances et le [protocole commun](../../../docs/dev/protocole-execution.md). Le besoin et les critères approuvés restent stables ; les choix locaux, le réexamen des hypothèses et la revue distincte suivent la règle `01` §12 et le protocole commun.

## Choisir et reprendre le chemin

Lire le mode de réalisation et sa justification. Un mode absent est établi selon `01` §2 ; des stories existantes impliquent par défaut le mode découpé, sans fusion ou suppression implicite. Vérifier référence Git du contrat, AC, inclus/exclus, décisions, dépendances, validations et état réel du travail.

Reprendre à partir des preuves et du diff actuel ; ne pas rejouer les unités `DONE` ni rouvrir un contrat terminé sans demande. Poursuivre le travail indépendant autorisé lorsqu'une dépendance bloque. Une ambiguïté de besoin ne se résout pas par une découpe.

## Chemin direct

1. Appliquer `analyse-story` sur l'epic si son analyse manque ou doit évoluer.
2. Appliquer `treat-story` sur la même epic jusqu'à réalisation prête en `REVIEW`.
3. Appliquer `finalise-epic`, sans story miroir ni fausse preuve « zéro story restante ».

Si des résultats ou validations distincts justifient une découpe, documenter le changement de mode puis utiliser `create-stories` en conservant AC, travail et preuves.

## Chemin découpé

Vérifier la couverture exigences → AC → stories, compléter les contrats manquants selon `create-stories` si nécessaire. Suivre les dépendances ; appliquer `analyse-story → treat-story → finalise-story` aux unités restantes. Une parente avec enfants coordonne leur couverture sans réimplémenter leur travail.

Synchroniser statuts, liens, cases et kanban (`make backlog`) ; contrôler l'intégration globale puis appliquer `finalise-epic`. Les preuves valides des enfants sont réutilisées, sans remplacer la revue d'ensemble ni les portes requises.

## Corriger, accepter et clôturer

Corriger les anomalies dans le périmètre autorisé, appliquer le réexamen prévu par la règle `01` §12 et le protocole commun quand les faits l'exigent, puis relancer les contrôles affectés et actualiser les preuves. Un contrôle absent, vide, ignoré ou non exécuté reste non validé.

Lorsque le rapport est conforme et toutes les validations requises acquises, appliquer `close-epic` si la demande couvre la clôture, notamment un traitement complet. Sinon conserver `REVIEW` et identifier l'acceptation restante. La clôture conserve tous les contrats, identifiants, liens et preuves ; seules les lignes terminées sortent du suivi actif.

Conclure avec l'état réel, les résultats vérifiés, les limites et la prochaine action. Une décision sensible en attente interdit de présenter l'epic comme terminée.
