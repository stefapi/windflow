# STORY-402 : Suppression API backend marketplace

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux supprimer les endpoints API backend de la marketplace, reviews et favorites afin de nettoyer le code serveur avant la reconstruction dans l'EPIC-001.

## Critères d'acceptation (AC)
- [ ] AC 1 : `backend/app/api/v1/marketplace.py` est supprimé
- [ ] AC 2 : `backend/app/api/v1/reviews.py` est supprimé
- [ ] AC 3 : `backend/app/api/v1/favorites.py` est supprimé
- [ ] AC 4 : Les schemas Pydantic liés (marketplace, reviews, favorites) sont supprimés
- [ ] AC 5 : Les services backend liés sont supprimés ou nettoyés
- [ ] AC 6 : Le router principal (`__init__.py`) ne référence plus ces modules
- [ ] AC 7 : Les tests unitaires liés sont supprimés ou adaptés
- [ ] AC 8 : `pytest` passe sans erreur
- [ ] AC 9 : La documentation OpenAPI ne liste plus les endpoints supprimés

## État d'avancement technique
- [ ] Audit des dépendances dans le backend (imports, services, schemas)
- [ ] Suppression de `marketplace.py`, `reviews.py`, `favorites.py`
- [ ] Nettoyage des schemas Pydantic associés
- [ ] Nettoyage des services backend associés
- [ ] Mise à jour du router principal
- [ ] Suppression/adaptation des tests
- [ ] Vérification pytest
- [ ] Vérification OpenAPI (aucun endpoint orphelin)
