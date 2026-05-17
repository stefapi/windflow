# STORY-035 : Pagination des listes Docker

**Statut :** TODO
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Amélioration
**Priorité :** Moyenne

## Description
Ajouter la pagination (paramètres `skip` et `limit`) sur les endpoints de listage Docker : containers, images, volumes et réseaux.

## Contexte technique

### Comportement actuel
- Les endpoints de listage Docker retournent l'intégralité des résultats sans pagination
- Cela peut causer des problèmes de performance avec un grand nombre d'objets Docker

### Comportement attendu
- Les endpoints de listage acceptent des paramètres de pagination `skip` et `limit`
- Les réponses sont paginées correctement
- Des valeurs par défaut raisonnables sont appliquées

### Fichiers impactés
| Fichier | Modification |
|---------|-------------|
| `backend/app/api/v1/docker.py` | Ajout paramètres `skip`/`limit` sur 4 endpoints |
| `backend/tests/unit/test_docker/*` | Tests de pagination |

## Critères d'acceptation (AC)
- [ ] AC 1 : `GET /docker/containers` accepte les paramètres `skip` (défaut 0) et `limit` (défaut 50)
- [ ] AC 2 : `GET /docker/images` accepte les paramètres `skip` et `limit`
- [ ] AC 3 : `GET /docker/volumes` accepte les paramètres `skip` et `limit`
- [ ] AC 4 : `GET /docker/networks` accepte les paramètres `skip` et `limit`
- [ ] AC 5 : Les réponses sont paginées correctement
- [ ] AC 6 : Tests unitaires pour la pagination
- [ ] AC 7 : Build, lint et tests passent

## Tâches d'implémentation
- [ ] Ajouter les paramètres `skip: int = Query(0, ge=0)` et `limit: int = Query(50, ge=1, le=100)` aux 4 endpoints
- [ ] Appliquer la pagination dans la logique de chaque handler (slice de la liste résultat)
- [ ] Mettre à jour les tests existants et ajouter des tests de pagination
- [ ] Vérifier build et tests
