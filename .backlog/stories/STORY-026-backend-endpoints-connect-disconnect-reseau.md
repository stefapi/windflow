# STORY-026 : Backend — Endpoints connect/disconnect réseau

**Statut :** DONE
**Epic Parent :** EPIC-009 — Refonte de la page ContainerDetail — Homogénéisation et édition complète

## Description

En tant qu'opérateur, je veux pouvoir connecter et déconnecter un container d'un réseau Docker à chaud (sans recréation ni redémarrage) afin de modifier la connectivité réseau d'un container en cours d'exécution.

## Contexte technique

Docker supporte nativement la connexion/déconnexion réseau à chaud via :
- `POST /v1.xx/networks/{id}/connect` (corps : `{"Container": "<id>", "EndpointConfig": {...}}`)
- `POST /v1.xx/networks/{id}/disconnect` (corps : `{"Container": "<id>", "Force": false}`)

Ces opérations ajoutent/retirent une interface réseau virtuelle dans le container **sans l'arrêter**. Elles peuvent échouer si :
- Le réseau est en mode `host` ou `none` (non supporté)
- Le container est arrêté (la déconnexion peut échouer silencieusement)
- Le réseau n'existe pas

### Couches impactées

| Couche | Fichier | Action |
|--------|---------|--------|
| Schemas | `backend/app/schemas/docker.py` | Ajouter 2 classes Request |
| Service | `backend/app/services/docker_client_service.py` | Ajouter 2 méthodes |
| Endpoint | `backend/app/api/v1/docker.py` | Ajouter 2 route handlers |
| Tests | `backend/tests/unit/test_docker/test_container_network_connect_disconnect.py` | Créer |

### Fichiers de référence (patterns existants)

| Besoin | Fichier de référence | Élément |
|--------|---------------------|---------|
| Schema Request simple | `backend/app/schemas/docker.py` l.794-801 | `ContainerRenameRequest` |
| Schema Response simple | `backend/app/schemas/docker.py` l.813-817 | `ContainerRenameResponse` |
| Service POST simple | `backend/app/services/docker_client_service.py` l.896-912 | `rename_container()` |
| Endpoint POST simple | `backend/app/api/v1/docker.py` l.838-883 | `rename_container` handler |
| Pattern tests endpoint | `backend/tests/unit/test_docker/test_container_recreate.py` l.1-150 | Fixtures + structure |
| Service `_request()` | `backend/app/services/docker_client_service.py` l.391-455 | Méthode générique |

### Exigences sécurité

- **Authentification** : Les endpoints Docker existants de type opération (recreate, rename, start/stop) n'utilisent PAS `get_current_active_user`. Par cohérence, ces endpoints suivent le même pattern. ⚠️ À noter : cette absence d'auth est une dette technique connue.
- **Rôles concernés** : Selon RBAC (`doc/general_specs/06-rbac-permissions.md`), connect/disconnect réseau est une action opérationnelle → rôle **Operator** minimum. Non applicable tant que l'auth n'est pas ajoutée.
- **Validation & injection** : `network_id` doit être une chaîne non-vide validée par Pydantic. `ipv4_address` doit être validée au format IP. `aliases` est une liste de chaînes. Aucun risque d'injection (Docker API gère la validation côté daemon).
- **Exposition de données sensibles** : Aucune. Les endpoints retournent HTTP 204 No Content.
- **Audit & traçabilité** : Logger l'opération (container_id, network_id, action) avec correlation_id. Pas de données sensibles dans les logs.

### Routes

- `POST /api/v1/docker/containers/{container_id}/networks/connect`
- `POST /api/v1/docker/containers/{container_id}/networks/disconnect`

### Schémas attendus

```python
class ContainerNetworkConnectRequest(BaseModel):
    network_id: str                       # ID ou nom du réseau — requis, non-vide
    aliases: Optional[list[str]] = None   # Alias réseau dans ce réseau
    ipv4_address: Optional[str] = None    # IP fixe optionnelle (format IPv4)

class ContainerNetworkDisconnectRequest(BaseModel):
    network_id: str                       # ID ou nom du réseau — requis, non-vide
    force: bool = False                   # Force la déconnexion même si container arrêté
```

**Rate limit** : 30 requêtes/min.

### Complexité : SIMPLE

- 3 fichiers à modifier + 1 fichier de test à créer
- 2 endpoints symétriques, straightforward (proxy vers Docker API)
- Patterns bien établis dans le codebase existant
- Aucune logique métier complexe

## Critères d'acceptation (AC)

- [x] AC 1 : `POST /docker/containers/{id}/networks/connect` connecte le container au réseau spécifié
- [x] AC 2 : `POST /docker/containers/{id}/networks/disconnect` déconnecte le container du réseau spécifié
- [x] AC 3 : Les deux endpoints retournent HTTP 204 (success, no content) en cas de succès
- [x] AC 4 : Si le container n'existe pas → HTTP 404
- [x] AC 5 : Si le réseau n'existe pas → HTTP 404
- [x] AC 6 : Les deux endpoints sont documentés dans OpenAPI
- [x] AC 7 : Tests unitaires couvrant les cas nominaux et d'erreur (≥ 80%)

## Dépendances

- Aucune dépendance sur d'autres stories de cette epic

## État d'avancement technique

- [x] Tâche 1 : Ajouter les schémas Pydantic `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest`
- [x] Tâche 2 : Ajouter les méthodes `connect_container_to_network()` et `disconnect_container_from_network()` dans le service
- [x] Tâche 3 : Implémenter les deux route handlers dans `docker.py`
- [x] Tâche 4 : Écrire les tests unitaires (nominaux + erreurs + sécurité)

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter les schémas Pydantic de requête

**Objectif :** Définir les schémas de validation pour les requêtes connect/disconnect réseau, en suivant le pattern de `ContainerRenameRequest`.

**Fichiers :**
- `backend/app/schemas/docker.py` — Modifier — Ajouter après la section `ContainerRenameResponse` (l.~817), dans la section `# Container Update & Rename` :
  - `ContainerNetworkConnectRequest(BaseModel)` avec champs :
    - `network_id: str = Field(..., min_length=1, description="ID ou nom du réseau")`
    - `aliases: Optional[list[str]] = Field(None, description="Alias réseau optionnels dans ce réseau")`
    - `ipv4_address: Optional[str] = Field(None, description="Adresse IPv4 fixe optionnelle")`
  - `ContainerNetworkDisconnectRequest(BaseModel)` avec champs :
    - `network_id: str = Field(..., min_length=1, description="ID ou nom du réseau")`
    - `force: bool = Field(False, description="Forcer la déconnexion même si le container est arrêté")`

**Exigences sécurité :** Validation Pydantic `min_length=1` sur `network_id` pour rejeter les chaînes vides.

**Dépend de :** Aucune

---

### Tâche 2 : Ajouter les méthodes service dans DockerClientService

**Objectif :** Ajouter deux méthodes qui appellent l'API Docker Engine pour connecter/déconnecter un container d'un réseau, en suivant le pattern de `rename_container()` (l.896-912).

**Fichiers :**
- `backend/app/services/docker_client_service.py` — Modifier — Ajouter dans la section `# Networks` (après `inspect_network`, l.~1342) :
  - `async def connect_container_to_network(self, network_id: str, container_id: str, aliases: Optional[list[str]] = None, ipv4_address: Optional[str] = None) -> None`
    - Construit le body Docker : `{"Container": container_id, "EndpointConfig": {...}}`
    - `EndpointConfig` inclut `Aliases` et `IPAMConfig` avec `IPv4Address` si fournis
    - Appelle `self._request("POST", f"/networks/{network_id}/connect", body=body)`
  - `async def disconnect_container_from_network(self, network_id: str, container_id: str, force: bool = False) -> None`
    - Construit le body Docker : `{"Container": container_id, "Force": force}`
    - Appelle `self._request("POST", f"/networks/{network_id}/disconnect", body=body)`

**Exigences sécurité :** Aucune exigence spécifique (les paramètres sont validés par Pydantic en amont).

**Dépend de :** Aucune

---

### Tâche 3 : Implémenter les deux route handlers

**Objectif :** Ajouter les deux endpoints POST dans le router Docker, en suivant le pattern de `rename_container` (l.838-883) : rate limiter, logging avec correlation_id, error handling `aiohttp.ClientResponseError` pour 404.

**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Ajouter après le handler `rename_container` (l.~883) :
  - Importer `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest` depuis `...schemas.docker` (ajouter aux imports existants l.19-52)
  - `POST /containers/{container_id}/networks/connect` :
    - `dependencies=[Depends(conditional_rate_limiter(30, 60))]`
    - `status_code=status.HTTP_204_NO_CONTENT`
    - `response_model=None` (pas de contenu retourné)
    - Handler : log + `get_docker_client()` + `client.connect_container_to_network(...)` + `client.close()` + `return Response(status_code=204)`
    - Error handling : `aiohttp.ClientResponseError` → 404 si container ou réseau non trouvé, 500 sinon
  - `POST /containers/{container_id}/networks/disconnect` :
    - Même structure, appelle `client.disconnect_container_from_network(...)`
    - Error handling identique

**Exigences sécurité :** Logging de l'opération avec `correlation_id`, `container_id` et `network_id`. Pas de données sensibles dans les logs.

**Dépend de :** Tâche 1, Tâche 2

---

### Tâche 4 : Écrire les tests unitaires

**Objectif :** Couvrir les cas nominaux, d'erreur et de validation pour les deux endpoints, en suivant le pattern de `test_container_recreate.py` (FastAPI app + httpx AsyncClient + mock `get_docker_client`).

**Fichiers :**
- `backend/tests/unit/test_docker/test_container_network_connect_disconnect.py` — Créer — Tests complets pour les deux endpoints

**Exigences sécurité :** Tests de validation (422 sur body invalide), tests d'erreur (404 container/network).

**Dépend de :** Tâche 3

## Tests à écrire

### Fichier : `backend/tests/unit/test_docker/test_container_network_connect_disconnect.py`

**Pattern** : FastAPI app + httpx AsyncClient + mock `get_docker_client` (cf. `test_container_recreate.py`)

#### Tests nominaux

| Test | Description | Statut attendu |
|------|-------------|----------------|
| `test_connect_network_success` | Connecte un container à un réseau avec `network_id` valide | 204 No Content |
| `test_connect_network_with_aliases` | Connecte avec aliases réseau | 204 No Content |
| `test_connect_network_with_ipv4` | Connecte avec IP fixe | 204 No Content |
| `test_connect_network_with_all_options` | Connecte avec aliases + IP fixe | 204 No Content |
| `test_disconnect_network_success` | Déconnecte un container d'un réseau | 204 No Content |
| `test_disconnect_network_with_force` | Déconnecte avec `force=True` | 204 No Content |

#### Tests d'erreur

| Test | Description | Statut attendu |
|------|-------------|----------------|
| `test_connect_network_container_not_found` | Container inexistant → Docker API 404 | 404 Not Found |
| `test_connect_network_network_not_found` | Réseau inexistant → Docker API 404 | 404 Not Found |
| `test_disconnect_network_container_not_found` | Container inexistant → Docker API 404 | 404 Not Found |
| `test_disconnect_network_network_not_found` | Réseau inexistant → Docker API 404 | 404 Not Found |
| `test_connect_network_docker_error` | Erreur Docker générique (500) | 500 Internal Server Error |
| `test_disconnect_network_docker_error` | Erreur Docker générique (500) | 500 Internal Server Error |

#### Tests de validation (sécurité)

| Test | Description | Statut attendu |
|------|-------------|----------------|
| `test_connect_network_empty_network_id` | `network_id` vide | 422 Unprocessable Entity |
| `test_connect_network_missing_network_id` | Body sans `network_id` | 422 Unprocessable Entity |
| `test_connect_network_invalid_body` | Body complètement invalide | 422 Unprocessable Entity |
| `test_disconnect_network_empty_network_id` | `network_id` vide | 422 Unprocessable Entity |
| `test_disconnect_network_missing_network_id` | Body sans `network_id` | 422 Unprocessable Entity |
| `test_disconnect_network_invalid_body` | Body complètement invalide | 422 Unprocessable Entity |

#### Tests du service (DockerClientService)

| Test | Description |
|------|-------------|
| `test_service_connect_calls_correct_endpoint` | Vérifie l'appel `POST /networks/{id}/connect` avec le bon body |
| `test_service_disconnect_calls_correct_endpoint` | Vérifie l'appel `POST /networks/{id}/disconnect` avec le bon body |
| `test_service_connect_with_aliases` | Vérifie que les aliases sont inclus dans `EndpointConfig` |
| `test_service_connect_with_ipv4` | Vérifie que l'IP est incluse dans `IPAMConfig` |
| `test_service_disconnect_with_force` | Vérifie que `Force` est passé dans le body |

### Commandes de validation

```bash
# Tests unitaires spécifiques
pytest backend/tests/unit/test_docker/test_container_network_connect_disconnect.py -v

# Couverture du module
pytest backend/tests/unit/test_docker/test_container_network_connect_disconnect.py --cov=app.api.v1.docker --cov=app.services.docker_client_service --cov=app.schemas.docker --cov-report=term-missing

# Vérification du seuil 80%
pytest backend/tests/unit/test_docker/test_container_network_connect_disconnect.py --cov-fail-under=80
```

## Notes d'implémentation

### Fichiers modifiés/créés

| Fichier | Action | Description |
|---------|--------|-------------|
| `backend/app/schemas/docker.py` | Modifié | Ajout de `ContainerNetworkConnectRequest` et `ContainerNetworkDisconnectRequest` après `ContainerRenameResponse` |
| `backend/app/services/docker_client_service.py` | Modifié | Ajout de `connect_container_to_network()` et `disconnect_container_from_network()` dans la section Networks |
| `backend/app/api/v1/docker.py` | Modifié | Ajout de 2 endpoints POST + import `Response` de FastAPI + import des 2 nouveaux schémas |
| `backend/tests/unit/test_docker/test_container_network_connect_disconnect.py` | Créé | 23 tests unitaires (6 nominaux, 6 erreurs, 6 validation, 5 service) |

### Décisions techniques

- **Schémas** : Suivi exactement le pattern `ContainerRenameRequest` avec `Field(...)` pour les champs requis et `Field(None)` pour les optionnels. `network_id` utilise `min_length=1` pour rejeter les chaînes vides.
- **Service** : Les méthodes construisent le body Docker API natif (`Container`, `EndpointConfig`, `IPAMConfig`, `Force`). `EndpointConfig` est un dict vide `{}` quand ni aliases ni ipv4_address ne sont fournis — cohérent avec l'API Docker.
- **Endpoints** : Retour `Response(status_code=204)` au lieu de `None` pour être explicite sur le HTTP 204 No Content. Rate limiter à 30 req/min comme spécifié. Logging structuré avec `correlation_id`, `container_id` et `network_id` dans `extra`.
- **Tests** : Pattern `FastAPI + httpx AsyncClient + mock get_docker_client` hérité de `test_container_recreate.py`. `ClientResponseError` instancié avec `MagicMock()` comme premier argument positional (pattern du codebase existant).

### Divergences

- **Ruff non installé** : L'outil `ruff` n'est pas disponible dans l'environnement. La vérification du lint a été remplacée par `py_compile` qui confirme que tous les fichiers sont syntaxiquement corrects. Les 297 tests existants passent sans régression.

### Tests ajoutés

- **23 tests** au total :
  - 4 tests nominaux connect (simple, aliases, ipv4, all options)
  - 2 tests nominaux disconnect (simple, force)
  - 3 tests erreur connect (container 404, network 404, docker 500)
  - 3 tests erreur disconnect (container 404, network 404, docker 500)
  - 3 tests validation connect (empty network_id, missing network_id, invalid body)
  - 3 tests validation disconnect (empty network_id, missing network_id, invalid body)
  - 5 tests service (connect endpoint, disconnect endpoint, aliases, ipv4, force)
- **Résultat** : 23/23 passed, 0 failed
- **Régression** : 297 tests dans `test_docker/` tous passés

