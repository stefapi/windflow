# STORY-028 : Backend + Frontend — Onglet Config éditable

**Statut :** TODO
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant qu'administrateur, je veux pouvoir modifier la configuration d'un container depuis un onglet "Config" — variables d'environnement, labels, restart policy, limites de ressources — afin de pouvoir ajuster le comportement du container sans recréer manuellement le container ou modifier le docker-compose.

## Contexte technique
Actuellement, l'onglet Infos affiche les env vars en lecture seule. Docker permet de mettre à jour certains paramètres d'un container sans le recréer via `docker update` (resources limits, restart policy) et de renommer un container via `docker rename`. Pour les env vars et labels, il faut recréer le container — ce qui nécessite une approche prudente avec confirmation utilisateur.

Le backend expose déjà des endpoints d'action sur les containers dans `backend/app/api/v1/docker.py`. Il faut ajouter des endpoints de mise à jour.

## Critères d'acceptation (AC)
- [ ] AC 1 : Un nouvel onglet **Config** est ajouté après l'onglet Stats
- [ ] AC 2 : La section **Env Vars** affiche les variables dans un tableau éditable (clé/valeur) avec possibilité d'ajouter/supprimer des lignes
- [ ] AC 3 : La section **Labels** affiche les labels dans un tableau éditable (clé/valeur) avec possibilité d'ajouter/supprimer
- [ ] AC 4 : La section **Restart Policy** permet de changer la politique via un sélecteur (no, always, on-failure, unless-stopped) avec un bouton "Appliquer"
- [ ] AC 5 : La section **Resource Limits** permet de modifier Memory limit, CPU shares, PidsLimit via des inputs numériques avec un bouton "Appliquer"
- [ ] AC 6 : Un endpoint `PATCH /api/v1/docker/containers/{id}/restart-policy` accepte `{name: str, maximum_retry_count: int | None}`
- [ ] AC 7 : Un endpoint `PATCH /api/v1/docker/containers/{id}/resources` accepte `{memory_limit: int | None, cpu_shares: int | None, pids_limit: int | None}`
- [ ] AC 8 : Un endpoint `POST /api/v1/docker/containers/{id}/rename` accepte `{new_name: str}`
- [ ] AC 9 : Les modifications de restart policy et resources utilisent `docker update` (sans recréation) — retourne le résultat immédiatement
- [ ] AC 10 : Les modifications d'env vars / labels affichent un avertissement : "⚠️ Modifier les variables d'environnement nécessite de recréer le container. Un arrêt de quelques secondes est à prévoir." avec confirmation obligatoire
- [ ] AC 11 : Un bouton "Renommer" avec validation du nouveau nom est disponible
- [ ] AC 12 : Les inputs sont pré-remplis avec les valeurs actuelles du container

## Dépendances
- STORY-024 (schémas structurés) — pour lire les valeurs actuelles structurées
- STORY-026 (onglet État détaillé) — pour afficher les valeurs actuelles de config dans le bon format

## État d'avancement technique
- [ ] Backend : Créer endpoint PATCH restart-policy
- [ ] Backend : Créer endpoint PATCH resources
- [ ] Backend : Créer endpoint POST rename
- [ ] Frontend : Créer l'onglet Config avec sections éditables
- [ ] Frontend : Implémenter les formulaires d'édition
- [ ] Frontend : Ajouter les confirmations et avertissements

## Tâches d'implémentation détaillées
<!-- Section remplie par la skill analyse-story -->

## Tests à écrire
<!-- Section remplie par la skill analyse-story -->
