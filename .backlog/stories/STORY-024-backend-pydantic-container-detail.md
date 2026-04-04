# STORY-024 : Backend — Schémas Pydantic structurés pour ContainerDetail

**Statut :** TODO
**Epic Parent :** EPIC-009 — Container Detail — Complétude des informations et UX

## Description
En tant que développeur backend, je veux structurer les schémas Pydantic de ContainerDetailResponse avec des sous-modèles typés (au lieu de `dict[str, Any]`) afin que le frontend reçoive des données pré-formatées, fiables et documentées dans l'OpenAPI.

## Contexte technique
Actuellement, `ContainerDetailResponse` dans `backend/app/schemas/docker.py` expose `state`, `config`, `host_config` et `network_settings` comme des `dict[str, Any]`. Le frontend doit parser manuellement ces dicts (ex: `container.state?.Status`, `container.host_config?.RestartPolicy?.Name`), ce qui est fragile et ne bénéficie pas de la validation Pydantic ni de la documentation OpenAPI auto-générée.

La route `GET /api/v1/docker/containers/{container_id}` dans `backend/app/api/v1/docker.py` appelle le service Docker qui retourne le résultat brut de `docker_client.inspect_container()`.

## Critères d'acceptation (AC)
- [ ] AC 1 : Un sous-modèle `ContainerStateInfo` expose : status, running, paused, restarting, oom_killed, dead, exit_code, error, started_at, finished_at, health (status, failing_streak, log)
- [ ] AC 2 : Un sous-modèle `ContainerConfigInfo` expose : hostname, domainname, user, attach_stdin, attach_stdout, attach_stderr, tty, open_stdin, stdin_once, env (liste), cmd (liste), entrypoint (liste), image, working_dir, labels (dict), stop_signal, stop_timeout
- [ ] AC 3 : Un sous-modèle `ContainerHostConfigInfo` expose : binds, container_id_file, log_config (type + config), network_mode, port_bindings, restart_policy (name + maximum_retry_count), auto_remove, volume_driver, volumes_from, cap_add, cap_drop, cap_drop, cgroupns_mode, dns, dns_options, dns_search, extra_hosts, group_add, ipc_mode, cgroup, links, oom_score_adj, pid_mode, privileged, publish_all_ports, readonly_rootfs, security_opt, storage_opt, tmpfs, uts_mode, userns_mode, shm_size, sysctls, runtime, console_size, isolation, resources (memory, memory_reservation, memory_swap, memory_swappiness, cpu_shares, cpu_period, cpu_quota, cpus, cpuset_cpus, cpuset_mems, devices, ulimits, pids_limit), mount_label
- [ ] AC 4 : Un sous-modèle `ContainerNetworkSettingsInfo` expose les networks avec ip, gateway, mac_address, network_id, endpoint_id, ipv6_gateway, global_ipv6_address, global_ipv6_prefix_len, ip_prefix_len, driver
- [ ] AC 5 : `ContainerDetailResponse` utilise ces sous-modèles au lieu de `dict[str, Any]`
- [ ] AC 6 : La route `/api/v1/docker/containers/{container_id}` mappe correctement les données brutes Docker vers les nouveaux schémas
- [ ] AC 7 : L'OpenAPI auto-généré documente tous les champs des sous-modèles
- [ ] AC 8 : Les champs optionnels ont des valeurs par défaut None (pas d'erreur si Docker ne retourne pas le champ)

## Dépendances
- Aucune

## État d'avancement technique
- [ ] Créer les sous-modèles Pydantic dans docker.py
- [ ] Mettre à jour ContainerDetailResponse
- [ ] Mettre à jour le mapping dans la route API
- [ ] Vérifier l'OpenAPI généré

## Tâches d'implémentation détaillées
<!-- Section remplie par la skill analyse-story -->

## Tests à écrire
<!-- Section remplie par la skill analyse-story -->
