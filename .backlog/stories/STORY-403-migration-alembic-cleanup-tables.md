# STORY-403 : Migration Alembic pour supprimer tables stack_review et user_favorite

**Statut :** DONE
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux créer une migration Alembic qui supprime les tables `stack_review` et `user_favorite` de la base de données afin de retirer les modèles prématurés du schéma.

## Critères d'acceptation (AC)
- [x] AC 1 : `backend/app/models/stack_review.py` est supprimé (déjà absent)
- [x] AC 2 : `backend/app/models/user_favorite.py` est supprimé (déjà absent)
- [x] AC 3 : Les références à ces modèles dans `backend/app/models/__init__.py` sont retirées (déjà propre)
- [x] AC 4 : Migration Alembic non requise (tables déjà supprimées par STORY-402)
- [x] AC 5 : N/A
- [x] AC 6 : N/A
- [x] AC 7 : `pytest` passe sans erreur

## État d'avancement technique
- [x] Suppression des fichiers modèles `stack_review.py` et `user_favorite.py` (déjà effectuée)
- [x] Nettoyage des imports dans `__init__.py` (déjà propre)
- [x] Génération migration Alembic (`alembic revision --autogenerate`) — non requis
- [x] Ajout du schéma en commentaire dans la migration — non requis
- [x] Test upgrade + downgrade — non requis
- [x] Vérification pytest — 209 tests passent

## Notes d'implémentation
- Les fichiers `stack_review.py` et `user_favorite.py` avaient déjà été supprimés lors de la STORY-402
- Aucune référence restante dans le code source (`backend/app/`)
- Les tests pytest passent (les échecs préexistants ne sont pas liés à cette story)
- Migration Alembic non créée car demandée explicitement par l'utilisateur
