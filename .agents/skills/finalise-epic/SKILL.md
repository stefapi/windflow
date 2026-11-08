---
name: finalise-epic
description: Vérifie une epic directe ou découpée et ses preuves de conformité avant clôture, sans modifier le code.
---

# finalise-epic

Le kanban est une vue générée : modifier les contrats et leurs listes liées, puis `make backlog` et `make backlog-check` ; ne pas éditer `.backlog/kanban.md` à la main.

Lire le [protocole commun](../../../docs/dev/protocole-execution.md) pour les vérifications et preuves, le contrat cible, ses sources de spécification (`docs/general_specs/`, `docs/technical_specs/`) et les règles applicables. Cette skill audite le code en lecture seule et consigne son rapport dans l'epic ; elle ne réalise pas les corrections et ne clôture pas l'epic.

## Identifier le périmètre

Établir le mode selon `01` §2 s'il manque. Les stories existantes impliquent par défaut une epic découpée ; aucune fusion ou suppression implicite.

- Directe : vérifier les AC et la section « Exécution directe » de l'epic, son diff et ses preuves. Aucun fichier story requis ; zéro story n'est pas une preuve de complétude.
- Découpée : vérifier tous les contrats liés, les sous-stories, leurs preuves et l'intégration globale. Une référence manquante ou une liste vide reste une anomalie ; tous les enfants doivent être terminés avant clôture.

## Évaluer la conformité

Croiser les exigences pertinentes des spécifications, les décisions consignées (`02` §2), le périmètre approuvé et les AC. Distinguer exigence couverte, partielle, manquante, hors périmètre justifié ou ambiguë. Une exigence ambiguë ne devient pas hors périmètre par décision unilatérale. Toute exigence requise manquante ou partielle bloque la conformité.

Vérifier les parcours d'ensemble et risques transverses, la maintenabilité, les frontières d'architecture (`20`), la sécurité (`40`) et les critères de succès. Les revues des stories ne remplacent pas cette revue d'intégration. Appliquer `01` §12 et le protocole commun si les anomalies révèlent un problème de conception ; ne pas transformer le rapport en liste indéfinie de patchs.

Contrôler la définition de terminé (`01` §7), les portes applicables (`35`, [matrice de validation](../../../docs/dev/controles-validation.md) — `make check` pour l'applicatif), la revue distincte et les validations humaines requises (`02` §7). Réutiliser les preuves valides selon le protocole commun, y compris celles des stories. Les exigences de couverture, construction, migrations, sécurité et parcours restent applicables selon le changement ; aucune porte n'est supprimée par l'allègement du rapport.

Poursuivre les vérifications indépendantes lorsqu'un écart est trouvé, tout en bloquant le verdict. Après correction, réexaminer les preuves et relancer les contrôles affectés ; recommencer tout l'audit seulement si l'ampleur du changement le justifie.

## Rapport et suite

Écrire dans l'epic un rapport proportionné : mode, référence du contrat, commit et modifications non commitées évaluées, couverture des exigences/AC, preuves, anomalies avec sources, contrôles manquants, revue distincte, validations humaines et prochaine action. Un score ne compense jamais une exigence ou une porte manquante.

Une dérogation respecte `35` §8 : décideur, motif, périmètre et expiration ; elle n'est pas présentée comme une réussite du contrôle. Conserver les contrats et toutes leurs preuves historiques.

Une epic prête reste `REVIEW` jusqu'aux validations et à `close-epic`. Si le traitement complet est autorisé, l'orchestrateur peut enchaîner la clôture après conformité et validations acquises. Si des corrections sont nécessaires, les transmettre à la réalisation autorisée sans les effectuer sous couvert de cet audit.
