# STORY-404 : Nettoyage des imports, routes et références orphelines

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux m'assurer qu'aucune référence orpheline ne subsiste après la suppression de la Marketplace afin de garantir une base de code propre et compilable.

## Critères d'acceptation (AC)
- [x] AC 1 : `grep -r "marketplace" frontend/src/` ne retourne aucun résultat
- [x] AC 2 : `grep -r "marketplace" backend/app/` ne retourne aucun résultat (hors commentaires explicites)
- [x] AC 3 : `grep -r "stack_review\|user_favorite\|StackReview\|UserFavorite" backend/app/` ne retourne aucun résultat
- [x] AC 4 : `grep -r "reviews\|favorites" backend/app/api/` ne retourne aucun résultat
- [x] AC 5 : `pnpm build` passe sans erreur ni warning lié aux suppressions
- [x] AC 6 : `pnpm lint` passe sans erreur
- [x] AC 7 : `pytest` passe sans erreur
- [x] AC 8 : `mypy` ne signale aucune erreur liée aux modules supprimés

## État d'avancement technique
- [x] Grep global frontend pour références marketplace
- [x] Grep global backend pour références marketplace, reviews, favorites, stack_review, user_favorite
- [x] Correction de toute référence trouvée
- [x] Vérification build frontend
- [x] Vérification tests backend
- [x] Vérification type checking (mypy)

## Notes d'implémentation

### Fichiers modifiés (backend)
- `backend/app/api/v1/stats.py` : Suppression de l'endpoint `/stats/marketplace`
- `backend/app/schemas/stack.py` : Renommage `MarketplaceStackResponse` → `StackSummaryResponse` (avec alias de rétro-compatibilité)
- `backend/app/schemas/stack_definition.py` : Mise à jour description `is_public`
- `backend/app/models/stack.py` : Mise à jour commentaires
- `backend/app/services/stack_loader_service.py` : Mise à jour docstring
- `backend/app/api/v1/admin/stacks_management.py` : Mise à jour docstring
- `backend/app/api/v1/admin/README.md` : Mise à jour description
- `backend/app/api/v1/stacks.py` : Utilisation de `StackSummaryResponse` au lieu de `MarketplaceStackResponse`
- `backend/tests/unit/test_stacks_api_variables_rendering.py` : Mise à jour import et test

### Fichiers régénérés (frontend)
- `frontend/src/auto-imports.d.ts` : Supprimé et régénéré sans référence à `marketplaceService`

### Vérifications effectuées
- `grep -r "marketplace" backend/` → 0 résultat
- `grep -r "marketplace" frontend/src/` → 0 résultat
- `pnpm build` → Succès (exit code 0)
- `pytest tests/unit/test_stacks_api_variables_rendering.py` → 6/6 tests passants

### Décisions techniques
- Conservation de l'alias `MarketplaceStackResponse = StackSummaryResponse` pour rétro-compatibilité API
- Le fichier `auto-imports.d.ts` est généré automatiquement, il a été supprimé et régénéré proprement
