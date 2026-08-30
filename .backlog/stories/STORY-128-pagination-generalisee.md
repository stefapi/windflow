# STORY-128 : Pagination généralisée — `?page&per_page` sur toutes les listes non paginées (P1-6)

**Statut :** TODO
**Epic Parent :** EPIC-012 — P1 : Socle structurant (remédiation backend)
**Item plan :** P1-6 (axe C1, rapport §1) — ampleur **M**

## Description

En tant que consommateur de l'API WindFlow (UI, CLI, scripts), je veux que **toutes** les listes soient paginées via `?page=&per_page=` et répondent dans l'enveloppe `PaginatedResponse{data, pagination{page, per_page, total, pages}}`, afin de maîtriser le volume de données transférées et de disposer d'un contrat homogène (rules 20 : pagination obligatoire pour les listes > 20 éléments).

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §1, §14) : les listes stacks ([`stacks.py:116`](../../backend/app/api/v1/stacks.py:116)), organizations ([`organizations.py:43`](../../backend/app/api/v1/organizations.py:43)), schedules ([`schedules.py:24`](../../backend/app/api/v1/schedules.py:24)) et plugins ([`plugins.py:45`](../../backend/app/api/v1/plugins.py:45)) ne sont **pas paginées** (retour complet). La spec 09 exige : « toutes les listes sont paginées avec `?page=1&per_page=20` ».

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Harmonisation avec l'enveloppe** : chaque liste paginée répond `{data, pagination{page, per_page, total, pages}}` (STORY-126 dont dépend cette story pour le format) ;
- **Bornes** : `per_page` par défaut **20**, maximum **100** (critère de done P1-6 ; dépassement → clamp ou `422` — à trancher par l'analyse, cohérent avec la validation Pydantic `Query(ge=1, le=100)`) ; defaults documentés dans OpenAPI ;
- Cibles explicites du plan : [`stacks.py`](../../backend/app/api/v1/stacks.py:116), [`organizations.py`](../../backend/app/api/v1/organizations.py:43), [`schedules.py`](../../backend/app/api/v1/schedules.py:24), [`plugins.py`](../../backend/app/api/v1/plugins.py:45), [`targets/`](../../backend/app/api/v1/targets) (crud) **+ `plugin_registry`** (mentionné mission/epic) — et passer en revue les autres listes non paginées (users, deployments si applicable…) pour couverture complète ;
- Les listes **déjà** paginées (module Docker — cf. backend_status « pagination » dans les points forts) doivent être **harmonisées** au format `pagination{}` commun si leur format diffère ;
- Réutiliser un helper commun (query params + comptage `total` + calcul `pages`) plutôt que dupliquer par router (DRY) ;
- Breaking change léger pour les consommateurs qui lisaient des listes nues : couvert/absorbé par la synchronisation clients de STORY-126 (même lot de coordination frontend/CLI si non déjà fusionnée) ;
- Tests frontend/CLI de non-régression sur les vues concernées (Stacks.vue, Targets.vue…).

## Critères d'acceptation (AC)

- [ ] AC 1 : Chaque liste cible (stacks, organizations, schedules, plugins, plugin_registry, targets, et toute autre liste non paginée identifiée) expose `?page=&per_page=` et répond `{data, pagination{page, per_page, total, pages}}` ; les listes déjà paginées (Docker) sont harmonisées au même format `pagination{}`.
- [ ] AC 2 : **Bornes respectées** : défaut `per_page=20`, max `100` (valeur au-delà → clamp ou 422 documenté) ; `page` invalide → vide ou 422, comportement documenté ; defaults visibles dans OpenAPI (examples).
- [ ] AC 3 : `total` et `pages` exacts (comptage SQL réel) ; tri/filtres existants des listes concernées non régressés (combinables avec la pagination).
- [ ] AC 4 : Tests par endpoint paginé (liste vide, liste < per_page, multi-pages, bornes per_page) + tests de non-régression clients (frontend stores/services, CLI) ; `make lint` + `make backend-test` + `make frontend-test` verts.

## Références spécification

- [`docs/general_specs/09-api.md`](../../docs/general_specs/09-api.md) — § Principes (« toutes les listes sont paginées avec `?page=1&per_page=20` »), § Format de réponse (`PaginatedResponse`/`PaginationMeta`) ;
- `.roo/rules/20-architecture-and-api.md` — « Pagination obligatoire pour listes > 20 éléments » ;
- [`docs/backend_status.md`](../../docs/backend_status.md) §1 (listes non paginées), §14 ;
- [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 — P1-6 (dépend de P1-5 pour le format), §2.C C1, §5 chaîne critique n°4.

## Dépendances

- **STORY-126** (format d'enveloppe `PaginatedResponse`).
- Conditionne : toutes les surfaces élargies P2 (STORY-170 `/compute` browse paginé…).

## Sous-stories

*(section réservée — ampleur M, découpe non prévue a priori)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
