---
name: update-rules
description: Compare les règles de WindFlow au code et aux contrôles réels, distingue écarts et décisions, puis prépare les corrections autorisées.
---

# update-rules

Appliquer le [protocole commun](../../../docs/dev/protocole-execution.md) dans le périmètre de cette skill.

Lire la gouvernance `02`, le workflow `50` et les sources normatives du périmètre demandé. Les règles décrivent des obligations et des choix acceptés ; le code décrit un état constaté. Cette skill ne rend jamais une implémentation conforme en abaissant sa norme.

## Comparer avec des preuves

Identifier les composants et fichiers concernés par la demande. Lire les règles et spécifications applicables (`docs/general_specs/`, `docs/technical_specs/`), puis inspecter le code, les manifestes, configurations, commandes et CI nécessaires. Un audit général couvre les composants présents ; une demande ciblée n'impose pas un inventaire intégral du dépôt.

Pour chaque divergence utile, citer la source normative, le fait observé, sa preuve, l'impact et l'action proposée. Distinguer :

- documentation descriptive périmée ou lien/commande incorrect ;
- obligation non respectée par le code ou un contrôle ;
- cible acceptée encore non implémentée ;
- choix normatif à revoir par le propriétaire ;
- constat incertain faute de preuve ou d'accès.

La présence d'un module, d'un test ou d'une configuration ne démontre ni son comportement ni sa conformité. Ne pas cocher une fonctionnalité sur cette seule base. Une divergence de seuil n'autorise pas à aligner la règle sur le seuil le plus faible ; une dépendance observée ne devient pas une décision acceptée.

## Préparer les corrections autorisées

Proposer de corriger la documentation descriptive, l'implémentation ou la décision normative selon le diagnostic. Conserver les cibles et décisions intentionnelles ; ne pas les effacer parce qu'elles ne sont pas encore réalisées.

Si l'utilisateur a autorisé les modifications, préparer le diff révisable dans le périmètre convenu, avec les adaptations cohérentes et contrôles utiles (`make check-harness` après un changement du corpus, `make backlog-check` après un changement de contrat ou de gabarit). Une modification normative non encore décidée reste une proposition explicite. Une autorisation existante n'est pas redemandée pour chaque correction locale.

Respecter la validation du propriétaire avant fusion des règles (`02` §5 et §7). Cette exigence de fusion n'interdit pas la préparation du changement autorisé. Sans autorisation de modifier le corpus, livrer le diagnostic et les propositions, sans appliquer de nouvelle norme.

## Restituer

Présenter les écarts importants, les fichiers modifiés ou proposés, les décisions restantes et les vérifications effectuées. Vérifier les liens, la cohérence des références et les contrôles applicables au diff ; préserver les modifications préexistantes. Ne pas annoncer toutes les règles conformes si seule une partie a été examinée ou si des preuves manquent.
