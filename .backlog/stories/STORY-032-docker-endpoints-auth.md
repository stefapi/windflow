# STORY-032 : Sécurité — Authentification sur les endpoints Docker

**Statut :** DONE
**Epic Parent :** EPIC-008 — Couverture Frontend des APIs Backend
**Type :** Correction sécurité
**Priorité :** Haute (sécurité)

## Description
Ajouter l'authentification (`Depends(get_current_active_user)`) sur les 30 endpoints Docker qui en sont dépourvus dans `backend/app/api/v1/docker.py`. Actuellement, seuls 5 endpoints sur 35 ont une authentification.

## Contexte technique

### Comportement actuel
- La majorité des endpoints Docker dans `backend/app/api/v1/docker.py` ne vérifient pas l'authentification
- Seuls 5 endpoints sur 35 utilisent `Depends(get_current_active_user)`
- Cela représente une faille de sécurité majeure : tout utilisateur non authentifié pourrait interagir avec Docker

### Comportement attendu
- Tous les endpoints Docker exigent une authentification via `Depends(get_current_active_user)`
- Les tests existants sont mis à jour pour mock l'authentification
- Les endpoints continuent de fonctionner correctement avec l'authentification

### Couches impactées
- **Backend uniquement** — aucun impact frontend, CLI ou infrastructure

### Fichiers de référence (patterns)
- **Pattern d'auth sur endpoint** : [`promote_container()`](backend/app/api/v1/docker.py:1006), [`get_container_shells()`](backend/app/api/v1/docker.py:1185), [`get_system_info()`](backend/app/api/v1/docker.py:1984) — ces 3 endpoints utilisent déjà `current_user: User = Depends(get_current_active_user)`
- **Pattern de mock auth dans tests** : [`test_container_shells.py`](backend/tests/unit/test_docker/test_container_shells.py) — `app.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()`
- **Pattern de test 401** : [`test_system_info.py`](backend/tests/unit/test_docker/test_system_info.py:97) — override auth pour lever `HTTPException(401)`
- **Dépendance d'authentification** : [`get_current_active_user`](backend/app/auth/dependencies.py:74) — vérifie token JWT + utilisateur actif
- **Conventions de test** : [`.clinerules/35-testing-quality-gates.md`](.clinerules/35-testing-quality-gates.md) — cas de test obligatoires par verbe HTTP
- **Checklist sécurité** : [`.clinerules/40-security.md`](.clinerules/40-security.md) — tests 401/403/422 obligatoires

### Inventaire des endpoints

#### Endpoints DÉJÀ authentifiés (5 — aucune modification)
| # | Fonction | Route | Ligne |
|---|----------|-------|-------|
| 1 | `promote_container` | POST `/containers/{id}/promote` | 1006 |
| 2 | `get_container_shells` | GET `/containers/{id}/shells` | 1185 |
| 3 | `get_system_info` | GET `/system/info` | 1984 |
| 4 | `get_version` | GET `/system/version` | 2029 |
| 5 | `ping` | GET `/system/ping` | 2067 |

#### Endpoints SANS auth à sécuriser (30)
| # | Fonction | Route | Ligne | Section |
|---|----------|-------|-------|---------|
| 1 | `list_containers` | GET `/containers` | 77 | Containers |
| 2 | `get_container` | GET `/containers/{id}` | 134 | Containers |
| 3 | `create_container` | POST `/containers` | 192 | Containers |
| 4 | `batch_start_containers` | POST `/containers/batch/start` | 271 | Containers |
| 5 | `batch_stop_containers` | POST `/containers/batch/stop` | 330 | Containers |
| 6 | `start_container` | POST `/containers/{id}/start` | 389 | Containers |
| 7 | `stop_container` | POST `/containers/{id}/stop` | 434 | Containers |
| 8 | `restart_container` | POST `/containers/{id}/restart` | 480 | Containers |
| 9 | `pause_container` | POST `/containers/{id}/pause` | 522 | Containers |
| 10 | `unpause_container` | POST `/containers/{id}/unpause` | 563 | Containers |
| 11 | `remove_container` | DELETE `/containers/{id}` | 604 | Containers |
| 12 | `recreate_container` | POST `/containers/{id}/recreate` | 652 | Containers |
| 13 | `update_restart_policy` | PATCH `/containers/{id}/restart-policy` | 743 | Containers |
| 14 | `update_resources` | PATCH `/containers/{id}/resources` | 794 | Containers |
| 15 | `rename_container` | POST `/containers/{id}/rename` | 849 | Containers |
| 16 | `connect_container_to_network` | POST `/containers/{id}/networks/connect` | 898 | Containers |
| 17 | `disconnect_container_from_network` | POST `/containers/{id}/networks/disconnect` | 953 | Containers |
| 18 | `get_container_stats` | GET `/containers/{id}/stats` | 1242 | Containers |
| 19 | `get_container_processes` | GET `/containers/{id}/top` | 1293 | Containers |
| 20 | `get_container_logs` | GET `/containers/{id}/logs` | 1393 | Containers |
| 21 | `list_images` | GET `/images` | 1458 | Images |
| 22 | `get_image` | GET `/images/{id}` | 1515 | Images |
| 23 | `pull_image` | POST `/images/pull` | 1588 | Images |
| 24 | `remove_image` | DELETE `/images/{id}` | 1636 | Images |
| 25 | `load_image` | POST `/images/load` | 1680 | Images |
| 26 | `save_image` | GET `/images/{id}/save` | 1732 | Images |
| 27 | `list_volumes` | GET `/volumes` | 1796 | Volumes |
| 28 | `create_volume` | POST `/volumes` | 1835 | Volumes |
| 29 | `remove_volume` | DELETE `/volumes/{name}` | 1889 | Volumes |
| 30 | `list_networks` | GET `/networks` | 1937 | Networks |

### Exigences sécurité
- **Authentification** : `get_current_active_user` obligatoire sur chaque endpoint — cf. [`.clinerules/40-security.md`](.clinerules/40-security.md)
- **Rôles** : Tout utilisateur actif authentifié (pas de RBAC spécifique, cohérent avec les 5 endpoints déjà authentifiés qui n'utilisent pas `require_role`)
- **Isolation des ressources** : Non applicable — les ressources Docker sont partagées au niveau du daemon, pas par utilisateur
- **Logging** : Ajouter `user_id` dans les logs existants quand `current_user` est disponible (optionnel, cohérent avec `promote_container` qui le fait déjà)
- **Audit** : Hors scope de cette story (se concentrer sur l'auth)

## Critères d'acceptation (AC)
- [x] AC 1 : Tous les endpoints de `docker.py` ont `current_user: User = Depends(get_current_active_user)` dans leurs paramètres
- [x] AC 2 : Les tests existants sont mis à jour pour mock l'authentification
- [x] AC 3 : Les endpoints continuent de fonctionner correctement avec l'authentification
- [x] AC 4 : Build, lint et tests passent sans erreur

## Tâches d'implémentation détaillées

### Tâche 1 : Ajouter l'authentification sur les 20 endpoints Containers
**Objectif :** Ajouter `current_user: User = Depends(get_current_active_user)` à chaque handler de la section Containers qui n'en dispose pas encore.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Ajouter le paramètre `current_user: User = Depends(get_current_active_user)` aux 20 fonctions handler de la section Containers (lignes 77 à 1443). Les imports `get_current_active_user` et `User` sont déjà présents en en-tête du fichier (lignes 15-18).
**Exigences sécurité :** `Depends(get_current_active_user)` — authentification JWT obligatoire. Pattern identique à [`promote_container()`](backend/app/api/v1/docker.py:1006).
**Dépend de :** Aucune

**Liste exhaustive des fonctions à modifier :**
1. `list_containers` (l.77) — ajouter `current_user: User = Depends(get_current_active_user),`
2. `get_container` (l.134) — ajouter `current_user: User = Depends(get_current_active_user),`
3. `create_container` (l.192) — ajouter `current_user: User = Depends(get_current_active_user),`
4. `batch_start_containers` (l.271) — ajouter `current_user: User = Depends(get_current_active_user),`
5. `batch_stop_containers` (l.330) — ajouter `current_user: User = Depends(get_current_active_user),`
6. `start_container` (l.389) — ajouter `current_user: User = Depends(get_current_active_user),`
7. `stop_container` (l.434) — ajouter `current_user: User = Depends(get_current_active_user),`
8. `restart_container` (l.480) — ajouter `current_user: User = Depends(get_current_active_user),`
9. `pause_container` (l.522) — ajouter `current_user: User = Depends(get_current_active_user),`
10. `unpause_container` (l.563) — ajouter `current_user: User = Depends(get_current_active_user),`
11. `remove_container` (l.604) — ajouter `current_user: User = Depends(get_current_active_user),`
12. `recreate_container` (l.652) — ajouter `current_user: User = Depends(get_current_active_user),`
13. `update_restart_policy` (l.743) — ajouter `current_user: User = Depends(get_current_active_user),`
14. `update_resources` (l.794) — ajouter `current_user: User = Depends(get_current_active_user),`
15. `rename_container` (l.849) — ajouter `current_user: User = Depends(get_current_active_user),`
16. `connect_container_to_network` (l.898) — ajouter `current_user: User = Depends(get_current_active_user),`
17. `disconnect_container_from_network` (l.953) — ajouter `current_user: User = Depends(get_current_active_user),`
18. `get_container_stats` (l.1242) — ajouter `current_user: User = Depends(get_current_active_user),`
19. `get_container_processes` (l.1293) — ajouter `current_user: User = Depends(get_current_active_user),`
20. `get_container_logs` (l.1393) — ajouter `current_user: User = Depends(get_current_active_user),`

### Tâche 2 : Ajouter l'authentification sur les 6 endpoints Images
**Objectif :** Ajouter `current_user: User = Depends(get_current_active_user)` à chaque handler de la section Images.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Ajouter le paramètre aux 6 fonctions handler de la section Images (lignes 1450 à 1780).
**Exigences sécurité :** `Depends(get_current_active_user)` — authentification JWT obligatoire.
**Dépend de :** Aucune

**Liste exhaustive des fonctions à modifier :**
1. `list_images` (l.1458) — ajouter `current_user: User = Depends(get_current_active_user),`
2. `get_image` (l.1515) — ajouter `current_user: User = Depends(get_current_active_user),`
3. `pull_image` (l.1588) — ajouter `current_user: User = Depends(get_current_active_user),`
4. `remove_image` (l.1636) — ajouter `current_user: User = Depends(get_current_active_user),`
5. `load_image` (l.1680) — ajouter `current_user: User = Depends(get_current_active_user),`
6. `save_image` (l.1732) — ajouter `current_user: User = Depends(get_current_active_user),`

### Tâche 3 : Ajouter l'authentification sur les 4 endpoints Volumes + Networks
**Objectif :** Ajouter `current_user: User = Depends(get_current_active_user)` aux handlers des sections Volumes et Networks.
**Fichiers :**
- `backend/app/api/v1/docker.py` — Modifier — Ajouter le paramètre aux 4 fonctions handler (lignes 1788 à 1968).
**Exigences sécurité :** `Depends(get_current_active_user)` — authentification JWT obligatoire.
**Dépend de :** Aucune

**Liste exhaustive des fonctions à modifier :**
1. `list_volumes` (l.1796) — ajouter `current_user: User = Depends(get_current_active_user),`
2. `create_volume` (l.1835) — ajouter `current_user: User = Depends(get_current_active_user),`
3. `remove_volume` (l.1889) — ajouter `current_user: User = Depends(get_current_active_user),`
4. `list_networks` (l.1937) — ajouter `current_user: User = Depends(get_current_active_user),`

### Tâche 4 : Mettre à jour les tests existants pour mock l'authentification
**Objectif :** Chaque fichier de test d'endpoint Docker qui ne mock pas actuellement l'authentification doit ajouter un override de `get_current_active_user` dans sa fixture `app`, suivant le pattern de [`test_container_shells.py`](backend/tests/unit/test_docker/test_container_shells.py:83) et [`test_system_info.py`](backend/tests/unit/test_docker/test_system_info.py:61).
**Fichiers :**
- `backend/tests/unit/test_docker/test_container_create.py` — Modifier — Ajouter `app.dependency_overrides[get_current_active_user]` dans la fixture `app` + import de `get_current_active_user` depuis `app.auth.dependencies` + helper `_make_mock_user()`
- `backend/tests/unit/test_docker/test_container_recreate.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_container_network_connect_disconnect.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_container_processes.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_container_stats.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_docker_api_pause.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_docker_config_update.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_images_inspect.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_images_list_in_use.py` — Modifier — Même pattern
- `backend/tests/unit/test_docker/test_images_import_export.py` — Modifier — Même pattern
**Exigences sécurité :** Mock de `get_current_active_user` requis pour que les tests existants passent avec l'auth activée.
**Dépend de :** Tâche 1, Tâche 2, Tâche 3

**Pattern à appliquer dans chaque fichier de test :**
```python
# Ajouter l'import
from app.auth.dependencies import get_current_active_user

# Helper existant ou à ajouter
def _make_mock_user():
    mock_user = MagicMock()
    mock_user.id = "test-user-id"
    mock_user.email = "test@example.com"
    mock_user.is_active = True
    return mock_user

# Dans la fixture app, ajouter l'override
@pytest.fixture
def app():
    application = FastAPI()
    application.include_router(router, prefix="/api/v1/docker")
    application.dependency_overrides[get_current_active_user] = lambda: _make_mock_user()
    return application
```

### Tâche 5 : Ajouter les tests de sécurité 401 sur les endpoints Docker
**Objectif :** Créer un fichier de test dédié vérifiant que chaque endpoint Docker retourne 401 sans token JWT, conformément à [`.clinerules/40-security.md`](.clinerules/40-security.md).
**Fichiers :**
- `backend/tests/unit/test_docker/test_docker_auth_security.py` — Créer — Tests 401 pour chaque endpoint Docker sans token
**Exigences sécurité :** Tests 401 obligatoires selon [`.clinerules/40-security.md`](.clinerules/40-security.md) — Checklist des tests de sécurité.
**Dépend de :** Tâche 1, Tâche 2, Tâche 3

**Tests à inclure :**
- 1 test par endpoint vérifiant le retour 401 sans authentification (mode production avec `disable_auth=False`)
- Pattern : `patch.object(settings, "disable_auth", False)` + requête sans header `Authorization` → assert 401
- Les endpoints avec body POST/PUT/PATCH peuvent utiliser un body minimal valide

### Tâche 6 : Validation — build, lint, tests
**Objectif :** Vérifier que l'ensemble du projet passe sans erreur après les modifications.
**Fichiers :**
- Aucun fichier à modifier — exécution uniquement
**Exigences sécurité :** Aucune exigence spécifique
**Dépend de :** Tâche 4, Tâche 5

**Commandes de validation :**
```bash
# Lint backend
make lint

# Type checking
make typecheck

# Tests unitaires backend (tous les tests Docker)
make test-backend

# Vérifier que les tests Docker passent spécifiquement
cd backend && python -m pytest tests/unit/test_docker/ -v
```

## Tests à écrire

### Tests unitaires backend — Sécurité (fichier nouveau)

| Test | Endpoint | Attendu |
|------|----------|---------|
| `test_list_containers_returns_401_without_token` | GET `/containers` | 401 |
| `test_get_container_returns_401_without_token` | GET `/containers/{id}` | 401 |
| `test_create_container_returns_401_without_token` | POST `/containers` | 401 |
| `test_batch_start_returns_401_without_token` | POST `/containers/batch/start` | 401 |
| `test_batch_stop_returns_401_without_token` | POST `/containers/batch/stop` | 401 |
| `test_start_container_returns_401_without_token` | POST `/containers/{id}/start` | 401 |
| `test_stop_container_returns_401_without_token` | POST `/containers/{id}/stop` | 401 |
| `test_restart_container_returns_401_without_token` | POST `/containers/{id}/restart` | 401 |
| `test_pause_container_returns_401_without_token` | POST `/containers/{id}/pause` | 401 |
| `test_unpause_container_returns_401_without_token` | POST `/containers/{id}/unpause` | 401 |
| `test_remove_container_returns_401_without_token` | DELETE `/containers/{id}` | 401 |
| `test_recreate_container_returns_401_without_token` | POST `/containers/{id}/recreate` | 401 |
| `test_update_restart_policy_returns_401_without_token` | PATCH `/containers/{id}/restart-policy` | 401 |
| `test_update_resources_returns_401_without_token` | PATCH `/containers/{id}/resources` | 401 |
| `test_rename_container_returns_401_without_token` | POST `/containers/{id}/rename` | 401 |
| `test_connect_network_returns_401_without_token` | POST `/containers/{id}/networks/connect` | 401 |
| `test_disconnect_network_returns_401_without_token` | POST `/containers/{id}/networks/disconnect` | 401 |
| `test_get_container_stats_returns_401_without_token` | GET `/containers/{id}/stats` | 401 |
| `test_get_container_processes_returns_401_without_token` | GET `/containers/{id}/top` | 401 |
| `test_get_container_logs_returns_401_without_token` | GET `/containers/{id}/logs` | 401 |
| `test_list_images_returns_401_without_token` | GET `/images` | 401 |
| `test_get_image_returns_401_without_token` | GET `/images/{id}` | 401 |
| `test_pull_image_returns_401_without_token` | POST `/images/pull` | 401 |
| `test_remove_image_returns_401_without_token` | DELETE `/images/{id}` | 401 |
| `test_load_image_returns_401_without_token` | POST `/images/load` | 401 |
| `test_save_image_returns_401_without_token` | GET `/images/{id}/save` | 401 |
| `test_list_volumes_returns_401_without_token` | GET `/volumes` | 401 |
| `test_create_volume_returns_401_without_token` | POST `/volumes` | 401 |
| `test_remove_volume_returns_401_without_token` | DELETE `/volumes/{name}` | 401 |
| `test_list_networks_returns_401_without_token` | GET `/networks` | 401 |

### Tests existants à mettre à jour (mock auth)

| Fichier | Modification |
|---------|-------------|
| `backend/tests/unit/test_docker/test_container_create.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_container_recreate.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_container_network_connect_disconnect.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_container_processes.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_container_stats.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_docker_api_pause.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_docker_config_update.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_images_inspect.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_images_list_in_use.py` | Ajouter override `get_current_active_user` dans fixture `app` |
| `backend/tests/unit/test_docker/test_images_import_export.py` | Ajouter override `get_current_active_user` dans fixture `app` |

### Commandes de validation
```bash
# Tests unitaires Docker
cd backend && python -m pytest tests/unit/test_docker/ -v

# Lint + typecheck
make lint && make typecheck

# Tous les tests backend
make test-backend
```

## État d'avancement technique
- [x] Tâche 1 : Authentification ajoutée sur les 20 endpoints Containers
- [x] Tâche 2 : Authentification ajoutée sur les 6 endpoints Images
- [x] Tâche 3 : Authentification ajoutée sur les 4 endpoints Volumes + Networks
- [x] Tâche 4 : Tests existants mis à jour avec mock d'authentification (10 fichiers)
- [x] Tâche 5 : Tests de sécurité 401 créés (fichier nouveau `test_docker_auth_security.py`)
- [x] Tâche 6 : Build, lint et tests passent sans erreur

## Notes d'implémentation

### Fichiers modifiés dans cette session
- `backend/app/api/v1/docker.py` — Ajout de `current_user: User = Depends(get_current_active_user)` sur les 30 endpoints non authentifiés. Le paramètre est placé en dernière position de la signature pour respecter la règle Python (params sans défaut avant params avec défaut).
- `backend/tests/unit/test_docker/test_container_create.py` — Correction du commentaire obsolète (l'endpoint a maintenant l'auth), mise à jour du test 401 pour utiliser le pattern `_raise_401()` au lieu du pattern `settings.disable_auth` qui attendait un 500, ajout des imports `HTTPException` et `status`.

### Fichiers déjà implémentés (session précédente)
- `backend/tests/unit/test_docker/test_docker_auth_security.py` — 30 tests 401 créés (20 containers + 6 images + 3 volumes + 1 network)
- 10 fichiers de tests existants mis à jour avec le mock d'authentification (`dependency_overrides[get_current_active_user]`)

### Décisions techniques
- Le paramètre `current_user` est placé en **dernière position** dans chaque signature de fonction, après tous les autres paramètres. Cela évite les erreurs Python "parameter without a default follows parameter with a default" car `Depends(get_current_active_user)` a une valeur par défaut.
- Les 5 endpoints déjà authentifiés (`promote_container`, `get_container_shells`, `get_system_info`, `get_version`, `ping`) n'ont pas été modifiés.

### Validation
- 343 tests passent (0 échec) — `pytest backend/tests/unit/test_docker/ -v`
- Aucune erreur de syntaxe dans `docker.py`
- 36 occurrences de `get_current_active_user` (1 import + 35 endpoints)
