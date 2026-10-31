# WorkloadAdapter — socle adapters (STORY-174.1)

> Contrat spec 02 § [Interface WorkloadAdapter](../../../../docs/general_specs/02-familles-workloads.md) —
> arbitration F7 du plan de remédiation : **interface + adapters Docker
> maintenant**, adapters K8s/Helm/Swarm/VM à la Roadmap.

## Contrat

| Méthode | Type | Description |
|---|---|---|
| `family()` | `WorkloadFamily` | `APP` \| `MACHINE` \| `HOST` \| `CLUSTER` |
| `profile()` | `str` | Profil canonique (`docker_container`, `docker_compose`…) |
| `profile_label()` | `str` | Libellé Mode Infra |
| `get_metrics()` | `WorkloadMetrics` | CPU/RAM/Réseau unifiés |
| `health()` | `HealthStatus` | healthy/unhealthy/starting/unknown |
| `contextual_actions(context)` | `list[ContextualAction]` | Action bar + menu (catalogues spec 02) |
| `child_actions(child_kind, child_id)` | `list[ContextualAction]` | Actions d'un composant enfant |
| `get_native_config()` | `NativeConfig` | Config moteur (compose/json/xml/yaml) |
| `get_technical_components()` | `list[TechnicalComponent]` | Mode Infra |

`AppAdapter` ajoute : `get_open_url()`, `list_services_or_pods()`, verbes
`start/stop/restart/update/backup/configure/stream_logs/open_console`.

**Sémantique d'erreur** : toute erreur métier remonte en
`WindFlowException` — jamais d'exception Docker/aiohttp brute.

## Adapters (enveloppement — zéro duplication)

| Adapter | Profil | Enveloppe (couche d'exécution inchangée) |
|---|---|---|
| `DockerContainerAdapter` | `docker_container` | `DockerService` (substitution/validation/deploy), `DockerExecutor` (cycle de vie), `DockerClientService` (inspection) |
| `ComposeStackAdapter` | `docker_compose` | `DockerComposeService`, `ComposeExecutor` |

Factory : `get_app_adapter(profile, **kwargs)` — profil inconnu →
`ValueError` explicite (jamais de fallback silencieux).

## Chemin de déploiement (AC 2)

`deploy_stack_async` ([background_tasks.py](../tasks/background_tasks.py))
route par la factory depuis STORY-174.1 : branche Docker →
`DockerContainerAdapter.deploy()`, branche compose →
`ComposeStackAdapter.deploy()`. Les **gates pre-deploy (STORY-170.2) et
les jalons WS (STORY-163) restent portés par background_tasks**, à la
même position (gates après résolution d'images / génération compose,
avant toute création de container — spec 11).

## Point d'extension

`DockerContainerAdapter.update()` délègue au recreate du client Engine —
rebranché sur le **recreate sécurisé** (capture avant pull, renommage
`-old`, rollback, secrets `***`) par la **STORY-174.2**.

## Stubs explicites

`backup`/`configure`/`open_console` lèvent `ActionNotImplementedError`
(renvoi F8 initiative backup / surfaces existantes) — terminaison
franche, jamais de succès silencieux.

> Annotation de la spec 02 : coordonnée avec P3-4/STORY-252 si non fusionnée.
