# STORY-403 : Migration Alembic pour supprimer tables stack_review et user_favorite

**Statut :** TODO
**Epic Parent :** EPIC-004 — Refonte UI, Navigation & Nettoyage Marketplace

## Description
En tant que développeur, je veux créer une migration Alembic qui supprime les tables `stack_review` et `user_favorite` de la base de données afin de retirer les modèles prématurés du schéma.

## Critères d'acceptation (AC)
- [ ] AC 1 : `backend/app/models/stack_review.py` est supprimé
- [ ] AC 2 : `backend/app/models/user_favorite.py` est supprimé
- [ ] AC 3 : Les références à ces modèles dans `backend/app/models/__init__.py` sont retirées
- [ ] AC 4 : Une migration Alembic `down` est créée (réversible — le schéma des tables supprimées est conservé en commentaire dans la migration)
- [ ] AC 5 : `alembic upgrade head` passe sans erreur sur une base existante
- [ ] AC 6 : `alembic downgrade -1` restaure les tables si besoin
- [ ] AC 7 : `pytest` passe sans erreur après la migration

## État d'avancement technique
- [ ] Suppression des fichiers modèles `stack_review.py` et `user_favorite.py`
- [ ] Nettoyage des imports dans `__init__.py`
- [ ] Génération migration Alembic (`alembic revision --autogenerate`)
- [ ] Ajout du schéma en commentaire dans la migration (pour réversibilité documentée)
- [ ] Test upgrade + downgrade
- [ ] Vérification pytest
