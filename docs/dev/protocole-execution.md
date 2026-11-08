# Protocole commun d'exécution de WindFlow

Aligné sur le harness PreviImmo (novembre 2026). Autonomie pour les choix locaux
et refactorings nécessaires, réexamen autonome d'une approche, arbitrage des
changements structurants ou sensibles. Sources normatives : règles
[01](../../.roo/rules/01-Project-management.md),
[02](../../.roo/rules/02-gouvernance-regles.md),
[20](../../.roo/rules/20-architecture-and-api.md),
[35](../../.roo/rules/35-testing-quality-gates.md) et
[50](../../.roo/rules/50-dev-workflow.md).

## Comprendre et choisir la profondeur utile

Lire le contrat, les sections de spécification pertinentes (`docs/general_specs/`,
`docs/technical_specs/`) et le code réel. Distinguer besoin approuvé, hypothèse et
état observé. Un exemple existant n'est un modèle qu'après vérification de sa
pertinence et de sa conformité. Un conflit spec/règle/code est qualifié avant toute
réalisation dépendante ; la présence du code ne prouve pas qu'il respecte le besoin.

Le contrat exécutable reste l'epic directe, la story ou le bug existant dans
`.backlog/`. Préserver ses identifiants, critères stables, liens et preuves.
Consigner résultat, inclus/exclus, invariants, décisions, scénarios observables,
contrôles et conditions de reprise. Ne pas recopier la spec ni créer de suivi
parallèle. Pour une demande exploratoire, une analyse dans le chat peut précéder
le contrat ; elle n'autorise pas une implémentation non cadrée.

| Changement | Analyse utile |
| --- | --- |
| Local, sans impact métier | Objectif, impact vérifié, contrôle ciblé ; pas de conception artificielle. |
| Métier | Exemples de comportement, refus et limites ; responsabilités, intégration et tests. |
| Structurant ou sensible | Options, invariants, contrats publics, transactions/effets, compatibilité, reprise et décisions humaines nécessaires. |

Adapter la profondeur aux impacts réels, pas au nombre de fichiers ou à un
format de rapport. Un plan décrit des étapes vérifiables ; il ne fige pas chaque
signature interne. Toute modification de besoin ou de critère requiert une
décision tracée ; le plan peut évoluer sans changer ce contrat.

## Réaliser et réexaminer

Appliquer l'autonomie et les déclencheurs de réexamen de la règle `01` §12.
Les extractions, simplifications et suppressions de duplication nécessaires
au résultat peuvent être faites dans le contrat courant. Consigner les choix
utiles à la reprise et préserver les comportements publics.

Quand une famille de défauts revient, qu'un correctif déplace l'erreur, que les
hypothèses sont successivement invalidées ou que les exceptions se dispersent :
suspendre les correctifs concernés et enquêter. Examiner les responsabilités,
les flux, la propriété des données/ressources, les transactions, la concurrence
et les effets selon le problème. Maintenir les contraintes approuvées.

Préparer les faits, les hypothèses réfutées, les options dont une simplification
si pertinent, la recommandation et l'expérience discriminante. Une nouvelle
tentative doit apporter une hypothèse ou une preuve nouvelle. Les limites
d'essais explicites restent applicables ; aucun nombre universel ne remplace
le diagnostic. Continuer les travaux indépendants autorisés.

Une décision structurante ou sensible suit la gouvernance (`02` §2) et est
consignée. Faire les investigations réversibles utiles avant de demander un avis
sur une proposition concrète. Le propriétaire décide avant l'implémentation
dépendante. Un second agent recherche les alternatives et invariants oubliés ;
son avis ne remplace pas l'accord humain requis.

## Vérifier au fil du travail

Préparer des exemples métier lisibles avant l'implémentation des comportements.
TDD ciblé : reproduction des bugs d'abord ; invariants de droits, transitions et
déploiements en priorité. Constater un échec pertinent avant le correctif
lorsqu'une reproduction automatisée est possible. Pour les bugs et comportements
critiques, préparer les tests à partir des AC et contrats publics avant
l'implémentation ; voir la skill
[write-acceptance-tests](../../.agents/skills/write-acceptance-tests/SKILL.md).

Exécuter les contrôles ciblés pendant la réalisation. À l'acceptation, appliquer
la définition de terminé (`01` §7) et la [matrice de validation](controles-validation.md).
Pour une modification purement documentaire, les contrôles du corpus
(`make check-harness`, `make backlog-check`) et une revue peuvent suffire ; toute
modification d'outillage est vérifiée par `make harness-test` et les linters
pertinents. Un nombre de tests, une couverture ou une suite verte ne prouvent
pas seuls un invariant métier.

Relier les preuves à la référence et à l'état de l'arbre évalués : commande,
environnement, résultat, contrôles ignorés/non exécutés et rapport. Réutiliser
une preuve encore valide ; relancer les contrôles affectés après modification.
Un blocage interdit le verdict conforme, pas les vérifications indépendantes.

## Revue, acceptation et reprise

La revue vérifie besoin, refus, frontières, maintenabilité et pertinence des
tests. Pour un changement structurant ou sensible, faire une passe distincte
par un second agent si l'outil le permet ; sinon consigner la limite et obtenir
une revue distincte humaine. Fournir contrat, faits, diff et preuves sans dicter
la conclusion. Vérifier les observations avant correction ; l'auteur ne se
déclare pas son propre relecteur distinct.

Les validations humaines de `02` §7 restent nécessaires (migrations, RBAC/auth,
déploiement production, harness). Distinguer réalisation prête à relire
(`REVIEW`), acceptation (`DONE`) et fusion/livraison. Une exigence manquante ou
un contrôle requis absent, ignoré ou non exécuté empêche l'acceptation, sauf
dérogation tracée selon `35` §8 ; un score ne compense pas ce manque. La clôture
conserve les contrats et preuves (`01` §10).

Conserver dans le contrat l'état réel, les décisions, les contrôles valides,
les limites et la prochaine action. Reprendre le travail restant ; ne pas
rejouer tout un workflow parce que le chat ou l'agent a changé.

## Synchronisation déterministe et retour intermédiaire

Après modification des statuts, liens et cases des contrats, `make backlog`
régénère uniquement le kanban ; `make backlog-check` vérifie les invariants et
la fraîcheur de la vue en lecture seule. Ne pas réparer une divergence en
éditant la vue, ni confondre cohérence du backlog et preuve d'acceptation.
Les contrats terminés et leurs identifiants restent conservés.

`make ci-fast` fournit un retour intermédiaire local : lint, types, corpus,
backlog et tests unitaires backend/frontend sans couverture. Exécuter les tests
réellement impactés pendant le travail ; cette commande ne remplace pas
`make check`, les seuils de couverture ni les portes supplémentaires requises
avant acceptation. Elle n'atteste pas l'exécution de la CI Gitea distante.
