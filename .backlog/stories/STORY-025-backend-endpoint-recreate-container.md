# STORY-025 : Backend — Endpoint de recréation de container

**Statut :** TODO
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir modifier des paramètres structurels d'un container (image, ports, volumes, variables d'environnement, labels, mode privilégié, capabilities) via une API backend qui gère automatiquement l'arrêt, la suppression et la recréation du container afin de ne pas avoir à le faire manuellement.

## Contexte technique

Docker ne supporte pas la modification à chaud de la plupart des paramètres de configuration d'un container (image, ports, volumes, env vars, labels, privileged, capabilities). La seule solution est de recréer le container avec la nouvelle configuration.

L'endpoint `POST /containers` existe déjà (`ContainerCreateRequest` dans `backend/app/schemas/docker.py` lignes 448-465). L'endpoint `/recreate` doit :
1. Inspecter le container existant (`GET /containers/{id}`) pour récupérer sa config complète
2. Merger la config existante avec les overrides de la requête (les champs `None` conservent la valeur actuelle)
3. Arrêter proprement le container (`stop_container(timeout=stop_timeout)`)
4. Supprimer le container (`remove_container(force=True)`)
5. Optionnellement puller la nouvelle image si `pull_image=True`
6. Recréer le container avec la config mergée
7. Démarrer le nouveau container
8. Retourner les détails complets du nouveau container

**Fichiers backend à modifier** :
- `backend/app/schemas/docker.py` — ajouter `ContainerRecreateRequest` et `ContainerRecreateResponse`
- `backend/app/api/v1/docker.py` — ajouter le route handler `POST /containers/{id}/recreate`
- `backend/app/services/docker_client_service.py` — vérifier/ajouter la méthode `pull_image()` si absente

**Schéma de requête** :
```python
class ContainerRecreateRequest(BaseModel):
    image: Optional[str] = None          # si None, conserve l'image actuelle
    pull_image: bool = False             # pull avant de recréer (si image fournie ou actuelle)
    env: Optional[list[str]] = None      # format ["KEY=VALUE", ...]
    labels: Optional[dict[str, str]] = None
    port_bindings: Optional[dict[str, Any]] = None
    mounts: Optional[list[dict[str, Any]]] = None
    privileged: Optional[bool] = None
    readonly_rootfs: Optional[bool] = None
    cap_add: Optional[list[str]] = None
    cap_drop: Optional[list[str]] = None
    stop_timeout: int = 10
```

**Schéma de réponse** :
```python
class ContainerRecreateResponse(BaseModel):
    success: bool
    message: str
    old_container_id: str
    new_container_id: str
    container: ContainerDetailResponse
    warnings: list[str] = []
```

**Contrainte critique** : si la suppression réussit mais la création échoue, logger l'incident (le container original est perdu — erreur non rattrapable) et retourner HTTP 500 avec `old_container_id` dans le message d'erreur.

**Rate limit** : 10 requêtes/min (opération coûteuse).

## Critères d'acceptation (AC)

- [ ] AC 1 : `POST /docker/containers/{container_id}/recreate` est disponible et documenté dans OpenAPI
- [ ] AC 2 : Les champs `None` dans la requête conservent la valeur actuelle du container (merge, pas remplacement total)
- [ ] AC 3 : Si `pull_image=True`, l'image est pullée avant la recréation
- [ ] AC 4 : L'image du container peut être modifiée (ex: `nginx:latest` → `nginx:1.26`)
- [ ] AC 5 : Le nouveau container est démarré automatiquement après recréation
- [ ] AC 6 : La réponse contient `old_container_id` et `new_container_id`
- [ ] AC 7 : Si le container source n'existe pas → HTTP 404
- [ ] AC 8 : Si la suppression réussit mais la création échoue → HTTP 500 avec détail explicite incluant `old_container_id`
- [ ] AC 9 : Les named volumes et bind mounts du container original sont préservés (recréés avec la même config)
- [ ] AC 10 : Tests unitaires couvrant les cas nominaux et d'erreur (≥ 80%)

## Dépendances

- Aucune dépendance sur d'autres stories de cette epic

## État d'avancement technique

- [ ] Ajouter `ContainerRecreateRequest` et `ContainerRecreateResponse` dans `backend/app/schemas/docker.py`
- [ ] Vérifier la présence de `pull_image()` dans `docker_client_service.py` (ajouter si absent)
- [ ] Implémenter le handler `recreate_container()` dans `backend/app/api/v1/docker.py`
- [ ] Écrire les tests unitaires dans `backend/tests/unit/test_docker/`

## Tâches d'implémentation détaillées

<!-- À remplir par analyse-story -->

## Tests à écrire

<!-- À remplir par analyse-story -->
