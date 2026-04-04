# EPIC-009 : Container Detail — Complétude des informations et UX

**Statut :** TODO
**Priorité :** Haute

## Vision

La page de détail d'un container (`ContainerDetail.vue`) est aujourd'hui incomplète : de nombreuses informations disponibles dans l'API Docker inspect ne sont pas exploitées, le header ne donne pas un résumé visuel suffisant, des actions critiques manquent (Start, Delete, Pause), et la structure des onglets ne correspond pas aux maquettes UI définies dans `doc/general_specs/11-UI-mockups.md`.

Cette epic vise à rendre la page Container Detail aussi complète et utilisable que celles de Portainer, Proxmox ou Incus/LXD — les outils de référence identifiés dans les mockups.

## Description

### Problèmes constatés

#### 1. Schéma backend trop brut
`ContainerDetailResponse` retourne des `dict[str, Any]` non structurés pour `state`, `config`, `host_config` et `network_settings`. Le frontend doit parser manuellement ces dicts bruts, ce qui est fragile et incomplet.

#### 2. Header incomplet
Le header affiche uniquement le nom et le statut (`running`/`exited`). Il manque : Target (machine cible), uptime/durée, résumé ressources (CPU/RAM), domaine/URL, et les actions Start/Delete/Pause.

#### 3. Informations container manquantes
De nombreuses informations critiques ne sont pas affichées :
- **État détaillé** : ExitCode, OOMKilled, StartedAt, FinishedAt, Health (status + failingStreak + log), Dead, Paused, Error
- **Configuration** : User, WorkingDir, Entrypoint (distinct de Command), TTY, StdinOpen, Labels (tous), StopSignal, StopTimeout
- **Limites ressources** : RestartPolicy (type + max retry), Memory limit, MemorySwap, CPU shares/period/quota, CpusetCpus, PidsLimit, Privileged, CapAdd/CapDrop, SecurityOpt, Ulimits, ReadonlyRootfs, AutoRemove
- **Log config** : driver + options (max-size, max-file)
- **Taille** : SizeRw, SizeRootFs
- **Image** : Image ID / Digest complet

#### 4. Structure des onglets ≠ maquette
La maquette (Écran 3 de `11-UI-mockups.md`) prévoit : `Aperçu | Services | Logs | Terminal | Volumes | Domaine | Config`
Actuellement : `Infos | Logs | Terminal | Stats | Processus`

Il manque :
- Un onglet **Aperçu** synthétique (services + ressources + volumes en cards)
- Un onglet **Services** (containers de la même stack)
- Un onglet **Config** (édition env vars, labels, restart policy)
- La vue **Network I/O** et **Disk I/O** dans les métriques
- Le bouton **Ouvrir** (lien URL) et **Backup**

#### 5. Actions manquantes
Start (container arrêté), Delete, Pause/Unpause, Rename, Duplicate.

### Approche

L'epic est découpée en 6 stories couvrant du backend au frontend, par ordre de dépendance :

1. **Schéma backend structuré** — Remplacer les `dict[str, Any]` par des schémas Pydantic typés
2. **Header enrichi** — Target, Uptime, Résumé ressources, Actions manquantes
3. **Onglet État & Configuration détaillés** — Toutes les infos manquantes (exit code, health, restart policy, limits, labels...)
4. **Onglet Aperçu synthétique** — Vue condensée conforme à la maquette
5. **Onglet Config éditable** — Édition env vars, labels, restart policy
6. **I/O Réseau et Disque** — Métriques Network I/O et Disk I/O

## Liste des Stories liées

- [ ] STORY-024 : Backend — Schémas Pydantic structurés pour ContainerDetail (state, config, host_config, network_settings)
- [ ] STORY-025 : Frontend — Header enrichi du Container Detail (Target, Uptime, Résumé ressources, Actions Start/Delete/Pause)
- [ ] STORY-026 : Frontend — Onglet État & Configuration détaillés (ExitCode, Health, RestartPolicy, ResourceLimits, Labels)
- [ ] STORY-027 : Frontend — Onglet Aperçu synthétique conforme maquette UI
- [ ] STORY-028 : Backend + Frontend — Onglet Config éditable (env vars, labels, restart policy)
- [ ] STORY-029 : Backend + Frontend — Métriques Network I/O et Disk I/O dans Stats

## Critères de succès (Definition of Done)

- [ ] Toutes les informations Docker inspect pertinentes sont affichées dans le détail du container
- [ ] Le header donne un résumé visuel complet (Target, Uptime, CPU, RAM, actions)
- [ ] Les actions Start, Stop, Restart, Delete, Pause sont toutes disponibles selon le contexte
- [ ] La structure des onglets correspond à la maquette UI (Aperçu, Infos, Logs, Terminal, Stats, Config)
- [ ] Les schémas backend sont typés (pas de `dict[str, Any]` pour les sous-objets)
- [ ] Les health checks sont visibles (status, failingStreak, derniers résultats)
- [ ] Les limites de ressources sont affichées (Memory, CPU, RestartPolicy, Privileged)
- [ ] Les erreurs d'état sont visibles (ExitCode, OOMKilled, Error)
- [ ] Tests backend ≥ 80% de couverture sur les nouveaux schémas
- [ ] Pas de régression sur les fonctionnalités existantes

## Notes de conception

### Architecture
- Le schéma `ContainerDetailResponse` doit être décomposé en sous-modèles Pydantic : `ContainerStateInfo`, `ContainerConfigInfo`, `ContainerHostConfigInfo`, `ContainerNetworkSettingsInfo`
- Le frontend doit mapper ces nouveaux types dans `frontend/src/types/api.ts`
- Les computed de parsing manuel dans `ContainerDetail.vue` seront simplifiés grâce aux données pré-structurées

### Références
- Maquette UI : `doc/general_specs/11-UI-mockups.md` — Écran 3 (Détail App/Container)
- Schéma actuel : `backend/app/schemas/docker.py` — `ContainerDetailResponse`
- API route : `backend/app/api/v1/docker.py` — `get_container()`
- Vue frontend : `frontend/src/views/ContainerDetail.vue`
- Types frontend : `frontend/src/types/api.ts` — `ContainerDetail`

### Risques
- Le Docker API inspect retourne énormément de données — il faut filtrer et ne remonter que ce qui est utile
- Certains champs peuvent varier selon la version de Docker — tester avec Docker 24+ et 25+
- L'édition de config (STORY-028) nécessite de nouvelles routes API (PATCH) — complexité moyenne
