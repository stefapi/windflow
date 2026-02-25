# Réutilisation / Migration (colibri → windflow)

Règle d’or : "réutiliser" ≠ "copier-coller".

## Classification obligatoire avant portage
Pour chaque module de colibri, classer :
1) Réutilisation directe : stable, découplé, compatible
2) Réutilisation avec adaptation : logique OK, interfaces/types/I-O à adapter
3) Réécriture recommandée : couplage fort, hacks legacy, dépendances non voulues

## Lecture seule par défaut
colibri est en lecture seule sauf demande explicite.

## Stratégie de portage
- Extraire le cœur métier (validation/mapping/calculs) en fonctions/services testables.
- Isoler I/O (HTTP, DB, filesystem, orchestration Docker/K8s) via interfaces/adapters.
- Éviter de porter la "glue" UI/framework.

## Préservation du comportement
Pour tout portage significatif :
- ajouter des tests unitaires
- si possible, tests "fixtures/golden" pour verrouiller le comportement attendu

## Interdictions
- Copier des fichiers entiers sans justification
- Répliquer hacks legacy sans explication
- Importer des dépendances legacy sans validation
