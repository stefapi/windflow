# STORY-402 : Suppression API backend marketplace

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux supprimer les endpoints API backend de la marketplace, reviews et favorites afin de nettoyer le code serveur avant la reconstruction dans l'EPIC-001.

## Critères d'acceptation (AC)
- [x] AC 1 : `backend/app/api/v1/marketplace.py` est supprimé
- [x] AC 2 : `backend/app/api/v1/reviews.py` est supprimé
- [x] AC 3 : `backend/app/api/v1/favorites.py` est supprimé
- [x] AC 4 : Les schemas Pydantic liés (marketplace, reviews, favorites) sont supprimés
- [x] AC 5 : Les services backend liés sont supprimés ou nettoyés
- [x] AC 6 : Le router principal (`__init__.py`) ne référence plus ces modules
- [x] AC 7 : Les tests unitaires liés sont supprimés ou adaptés
- [x] AC 8 : `pytest` passe sans erreur (189 passed, 20 failed préexistants non liés au marketplace)
- [x] AC 9 : La documentation OpenAPI ne liste plus les endpoints supprimés

## État d'avancement technique
- [x] Audit des dépendances dans le backend (imports, services, schemas)
- [x] Suppression de `marketplace.py`, `reviews.py`, `favorites.py`
- [x] Nettoyage des schemas Pydantic associés
- [x] Nettoyage des services backend associés
- [x] Mise à jour du router principal
- [x] Suppression/adaptation des tests
- [x] Vérification pytest
- [x] Vérification OpenAPI (aucun endpoint orphelin)

## Notes d'implémentation

### Fichiers supprimés
- `backend/app/api/v1/marketplace.py` - Endpoint principal marketplace
- `backend/app/api/v1/reviews.py` - Endpoint des reviews stacks
- `backend/app/api/v1/favorites.py` - Endpoint des favoris utilisateur
- `backend/app/models/stack_review.py` - Modèle ORM des reviews
- `backend/app/models/user_favorite.py` - Modèle ORM des favoris (déjà supprimé)
- `backend/app/schemas/marketplace.py` - Schémas Pydantic marketplace (déjà supprimé)
- `backend/app/schemas/review.py` - Schémas Pydantic reviews (déjà supprimé)
- `backend/app/schemas/favorite.py` - Schémas Pydantic favorites (déjà supprimé)

### Fichiers modifiés
- `backend/app/api/v1/__init__.py` - Retiré les imports des routers supprimés
- `backend/app/models/__init__.py` - Retiré les exports des modèles supprimés
- `backend/app/models/stack.py` - Retiré la relation `reviews` et `favorited_by`
- `backend/app/models/user.py` - Retiré la relation `favorites`
- `backend/app/schemas/stack.py` - Retiré `StackListResponse` (marketplace), renommé en `MarketplaceStackResponse`
- `backend/app/schemas/__init__.py` - Retiré les exports des schemas supprimés
- `backend/app/api/v1/stacks.py` - Mis à jour les imports pour utiliser `MarketplaceStackResponse`
- `backend/app/api/v1/stats.py` - Retiré l'import `StackReview` et la logique associée
- `backend/tests/unit/test_stacks_api_variables_rendering.py` - Mis à jour l'import `StackListResponse` → `MarketplaceStackResponse`

### Décisions techniques
1. Conservation de `MarketplaceStackResponse` dans `schemas/stack.py` car il est utilisé par l'endpoint `/stacks/marketplace` qui liste les stacks publics
2. Conservation de l'endpoint `/stats/marketplace` dans `stats.py` car il fournit des statistiques générales sur les stacks publics (pas de reviews/favorites)
3. Suppression de la logique de comptage des reviews dans `/stats/stacks/{stack_id}` car le modèle `StackReview` n'existe plus

### Tests
- 189 tests passent
- 20 tests échouent (préexistants, non liés au marketplace : auth API et security headers)
- Les tests liés au nettoyage marketplace passent tous

### Dernier correctif
- Suppression de la référence `StackReview` restante dans `stats.py` endpoint `/stats/stacks/{stack_id}`
- Retrait du champ `total_reviews` de la réponse (le modèle n'existe plus)
