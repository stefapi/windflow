# STORY-404 : Nettoyage des imports, routes et références orphelines

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux m'assurer qu'aucune référence orpheline ne subsiste après la suppression de la Marketplace afin de garantir une base de code propre et compilable.

## Critères d'acceptation (AC)
- [ ] AC 1 : `grep -r "marketplace" frontend/src/` ne retourne aucun résultat
- [ ] AC 2 : `grep -r "marketplace" backend/app/` ne retourne aucun résultat (hors commentaires explicites)
- [ ] AC 3 : `grep -r "stack_review\|user_favorite\|StackReview\|UserFavorite" backend/app/` ne retourne aucun résultat
- [ ] AC 4 : `grep -r "reviews\|favorites" backend/app/api/` ne retourne aucun résultat
- [ ] AC 5 : `pnpm build` passe sans erreur ni warning lié aux suppressions
- [ ] AC 6 : `pnpm lint` passe sans erreur
- [ ] AC 7 : `pytest` passe sans erreur
- [ ] AC 8 : `mypy` ne signale aucune erreur liée aux modules supprimés

## État d'avancement technique
- [ ] Grep global frontend pour références marketplace
- [ ] Grep global backend pour références marketplace, reviews, favorites, stack_review, user_favorite
- [ ] Correction de toute référence trouvée
- [ ] Vérification build frontend
- [ ] Vérification tests backend
- [ ] Vérification type checking (mypy)
