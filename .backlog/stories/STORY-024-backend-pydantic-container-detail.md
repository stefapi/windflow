# STORY-024 : Backend — Schémas Pydantic structurés pour ContainerDetail

**Statut :** DONE
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant que développeur backend, je veux structurer les schémas Pydantic de ContainerDetailResponse avec des sous-modèles typés (au lieu de `dict[str, Any]`) afin que le frontend reçoive des données pré-formatées, fiables et documentées dans l'OpenAPI.

## Critères d'acceptation (AC)
- [x] AC 1 : Un sous-modèle `ContainerStateInfo` expose : status, running, paused, restarting, oom_killed, dead, exit_code, error, started_at, finished_at, health (status, failing_streak, log)
- [x] AC 2 : Un sous-modèle `ContainerConfigInfo` expose : hostname, domainname, user, attach_stdin, attach_stdout, attach_stderr, tty, open_stdin, stdin_once, env (liste), cmd (liste), entrypoint (liste), image, working_dir, labels (dict), stop_signal, stop_timeout
- [x] AC 3 : Un sous-modèle `ContainerHostConfigInfo` expose : binds, container_id_file, log_config (type + config), network_mode, port_bindings, restart_policy (name + maximum_retry_count), auto_remove, volume_driver, volumes_from, cap_add, cap_drop, cgroupns_mode, dns, dns_options, dns_search, extra_hosts, group_add, ipc_mode, cgroup, links, oom_score_adj, pid_mode, privileged, publish_all_ports, readonly_rootfs, security_opt, storage_opt, tmpfs, uts_mode, userns_mode, shm_size, sysctls, runtime, console_size, isolation, resources, mount_label
- [x] AC 4 : Un sous-modèle `ContainerNetworkSettingsInfo` expose les networks avec ip, gateway, mac_address, network_id, endpoint_id, ipv6_gateway, global_ipv6_address, global_ipv6_prefix_len, ip_prefix_len, driver
- [x] AC 5 : `ContainerDetailResponse` utilise ces sous-modèles au lieu de `dict[str, Any]`
- [x] AC 6 : La route `/api/v1/docker/containers/{container_id}` mappe correctement les données brutes Docker vers les nouveaux schémas
- [x] AC 7 : L'OpenAPI auto-généré documente tous les champs des sous-modèles
- [x] AC 8 : Les champs optionnels ont des valeurs par défaut None (pas d'erreur si Docker ne retourne pas le champ)

## État d'avancement technique
- [x] Créer les sous-modèles Pydantic dans docker.py
- [x] Mettre à jour ContainerDetailResponse
- [x] Mettre à jour le mapping dans la route API
- [x] Écrire les tests unitaires (61/61 passants)
- [x] Vérifier l'OpenAPI généré

## Notes d'implémentation

### Fichiers modifiés/créés
- `backend/app/schemas/docker.py` — Ajout de 11 sous-modèles Pydantic typés (`ContainerHealthLogEntry`, `ContainerHealthInfo`, `ContainerStateInfo`, `ContainerConfigInfo`, `ContainerLogConfigInfo`, `ContainerRestartPolicyInfo`, `ContainerResourcesInfo`, `ContainerHostConfigInfo`, `ContainerNetworkEndpointInfo`, `ContainerNetworkSettingsInfo`) + mise à jour de `ContainerDetailResponse` pour les utiliser
- `backend/app/api/v1/docker.py` — Mise à jour des routes `get_container` et `create_container` pour utiliser les factories `from_docker_dict()` au lieu de passer les dicts bruts
- `backend/tests/unit/test_docker/test_docker_schemas.py` — Ajout de 11 classes de test couvrant tous les sous-modèles (de `TestContainerHealthLogEntry` à `TestContainerNetworkSettingsInfo`) + mise à jour de `TestContainerDetailResponse`

### Décisions techniques
- Chaque sous-modèle possède une factory `from_docker_dict(cls, data)` qui mappe les clés PascalCase de l'API Docker vers les champs snake_case Pydantic — pattern cohérent avec les modèles existants (`PortBinding`, `MountPoint`)
- La dataclass `ContainerDetail` dans `docker_client_service.py` n'a **pas** été modifiée — le mapping se fait uniquement dans la couche API (route)
- Le champ `cpus` de `ContainerResourcesInfo` mappe `NanoCpus` (API Docker) vers un int — cohérent avec le comportement Docker
- Les champs `mounts` reste en `list[dict[str, Any]]` car déjà couvert par le modèle `MountPoint` existant

### Tests
- **Exécuté :** oui (`poetry run pytest tests/unit/test_docker/test_docker_schemas.py -v`)
- **Résultat :** 61 passed en 1.68s — couverture docker.py schemas à 100%
