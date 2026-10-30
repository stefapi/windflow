# STORY-166.6 : Synchronisation frontend + CLI — bascule des consommateurs vers `/hosts` et purge des références `target` (P2-4, partie consommateurs — STORY-166 découpée)

**Statut :** DONE
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Story Parent (split) :** STORY-166 ([ABANDONED — découpe proactive post-analyse le 2026-10-24](STORY-166-migration-target-vers-host-origin.md))
**Item plan :** P2-4 (F4 étape 2 — volet consommateurs frontend/CLI) — ampleur **M**

> **Périmètre (découpe)** : cette sous-story reprend le **volet consommateurs** de STORY-166 — bascule du frontend vers l'API `/hosts` ([`services/api.ts`](../../frontend/src/services/api.ts) `targetsApi`→`hostsApi`, [`stores/targets.ts`](../../frontend/src/stores/targets.ts)→`hosts.ts`, types `types/api.ts`, vues `Targets.vue`→`Hosts.vue`, sidebar, widgets) et du CLI (tests envelope sur `/hosts`), **purge des références `target` résiduelles** (y compris les alias de transition backend posés en [STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md), si la période de transition l'autorise — coordination avec le plan F3) et alignement de la documentation (spec 09 déjà à jour côté backend par 166.2). Couvre la partie **frontend/CLI de l'AC 5 de la mère**. ℹ️ La bascule consomme l'alias déprécié sans casse : le frontend peut basculer avant ou après la purge des alias — **recommandé en dernier**, après 166.1→166.5.

## Description

En tant qu'utilisateur WindFlow, je veux que le frontend et le CLI consomment la surface canonique `/api/v1/hosts/*` (pages Hosts, store, types, navigation) et que toutes les références `target` résiduelles soient purgées — afin que l'interface et les clients soient alignés sur le modèle directeur et que le nommage legacy disparaisse des consommateurs.

**Problème constaté** : [`services/api.ts`](../../frontend/src/services/api.ts) (l.142) expose `targetsApi` (11 méthodes) ; le store, les vues et la navigation portent `/targets` ; le CLI consomme `/targets` dans ses tests envelope.

## Contexte technique

> Extrait de l'analyse STORY-166 (2026-10-24, `analyse-story`) — volet consommateurs, fondé sur le code réel du dépôt.

### État réel du code (exploration mère)

**Frontend**
- [`services/api.ts`](../../frontend/src/services/api.ts) : `targetsApi` (11 méthodes, l.142) → `hostsApi` (surface spec 09 exposée par [STORY-166.2](STORY-166.2-api-hosts-alias-targets-evenements.md)) ;
- [`stores/targets.ts`](../../frontend/src/stores/targets.ts) : store complet + health polling + pagination STORY-128 → `stores/hosts.ts` ;
- Types dans [`types/api.ts`](../../frontend/src/types/api.ts) (`Target*` → `Host*`) — centralisés, importer depuis là (convention) ;
- Vues/composants : `views/Targets.vue` → `Hosts.vue`, `DeploymentDetail.vue` (lien `/targets`), `Dashboard.vue`, [`useSidebarNav.ts`](../../frontend/src/composables/useSidebarNav.ts) (l.72, path `/targets`), `SidebarNav.vue`, `ResourceMetricsWidget.vue` ;
- Tests frontend existants à migrer en conséquence.

**CLI**
- Pas de commandes targets dédiées — seul [`cli/tests/test_client_envelope.py`](../../cli/tests/test_client_envelope.py) consomme `/targets` comme URL générique de test → passer à `/hosts`.

**Backend (purge)**
- Alias de transition posés par 166.1 (`models/target.py`, `enums/target.py` re-exports) et imports `target_*` résiduels — à purger **après** bascule des consommateurs ; ⚠️ coordination plan F3 : l'alias `/targets` (166.2) reste actif pour les intégrations externes tant que la transition le requiert — la purge des alias **internes** ne casse rien, la suppression du **router alias** est un arbitrage séparé (à tracer).

### Points d'attention

- Renommage de fichiers/vue = routes frontend (`/targets` → `/hosts` dans le router) — prévoir redirection ou accepter le changement d'URL (arbitrage en analyse) ;
- Non-régression : pagination STORY-128 (enveloppe `data`/`pagination`), health polling, tests existants adaptés ;
- `make frontend-typecheck` + `make frontend-lint` stricts (TS strict, `noPropertyAccessFromIndexSignature`).

### Checklist sécurité (règle 40)

- Aucun token/secret affiché dans les vues Hosts (identique à l'existant) ;
- Routes protégées : rediction `/login` si non authentifié (tests) ; actions admin masquées pour viewer.

## Critères d'acceptation (AC)

- [x] AC 1 *(reprend la partie frontend/CLI de l'AC 5 de la mère)* : Frontend et CLI synchronisés — `hostsApi`/store `hosts`/types `Host*`/vue `Hosts.vue`/navigation `/hosts` consomment la surface canonique (166.2), pagination et health polling non régressés ; tests frontend adaptés et passants ; CLI tests envelope sur `/hosts`.
- [x] AC 2 : **Purge des références `target` résiduelles** — plus aucune occurrence `target` côté frontend/CLI ; backend : alias internes 166.1 purgés (le router alias `/targets` déprécié reste actif tant que le plan F3 le requiert — décision tracée) ; `make typecheck` + `make lint` + tests verts.
- [x] AC 3 : Couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — § Famille Hosts (surface consommée) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §3 F3 (double nommage/transition), §4 P2-4.

## Dépendances

- **[STORY-166.2](STORY-166.2-api-hosts-alias-targets-evenements.md)** (dur) — surface `/hosts` disponible ; **[STORY-166.1](STORY-166.1-modele-host-enums-migration-alembic.md)** (purge alias) ; **[STORY-166.3](STORY-166.3-services-host-scanners-ws.md)** et **[STORY-166.5](STORY-166.5-auto-detection-host-local-seed.md)** recommandées avant (évite de purger puis ré toucher) ;
- **À traiter en dernier** de la série 166.x ; indépendante de [STORY-166.4](STORY-166.4-origin-environments-git-url.md).

## État d'avancement technique

*(à cocher pendant `treat-story` — une case par tâche détaillée ci-dessous)*

- [x] T1. Types `Host*` dans `types/api.ts`
- [x] T2. `hostsApi` dans `services/api.ts` (+ retrait `targetsApi`)
- [x] T3. Store `stores/hosts.ts` (ex-`targets.ts`)
- [x] T4. Vue `Hosts.vue` + `TargetWizard.vue`→`HostWizard.vue` + router (redirection `/targets`)
- [x] T5. Sidebar + vues consommatrices (`Dashboard`, `DeploymentDetail`, `Stacks`, `Deployments`, `Compute`, `ResourceMetricsWidget`)
- [x] T6. CLI `test_client_envelope.py` sur `/hosts`
- [x] T7. Purge alias backend 166.1/166.3 (internes) + décision tracée router alias `/targets`
- [x] T8. Tests frontend/CLI adaptés + non-régression TS stricte

## Tâches d'implémentation détaillées

### Tâche 1 : Types `Host*` centralisés
**Objectif :** Dans `types/api.ts` : renommer `Target`→`Host`, `TargetCreate`→`HostCreate`, `TargetUpdate`→`HostUpdate`, `TargetAccessProfile`→`HostAccessProfile` (l.73), `TargetCapability`→`HostCapability` (l.172, champ `host_id`), `TargetCapabilitiesResponse`→`HostCapabilitiesResponse` (l.181), `TargetHealthItem`→`HostHealthItem` (l.489), `TargetMetrics`→`HostMetrics`/`TargetGroup`→`HostGroup` (l.857-863, champ `host_id`) — champs alignés sur les schémas 166.2 (`profile`, `hardware_info`, `installed_engines`, `origin`, `last_scan_at`). Aucune redéfinition locale ailleurs (convention : importer depuis `types/api`).
**Fichiers :**
- `frontend/src/types/api.ts` — [Modifier] — renommages + nouveaux champs
**Dépend de :** STORY-166.2 (contrat API)

### Tâche 2 : `hostsApi` dans `services/api.ts`
**Objectif :** Remplacer `targetsApi` (l.142-162, 11 méthodes) par `hostsApi` sur les chemins `/hosts` : `list` (params `page`/`per_page`/`organization_id`), `get`, `create`, `update`, `delete`, `scan`, `getCapabilities`, `testReachability`, `testConnection`, `healthCheck` — mêmes signatures/types retournés (`Host`, enveloppe `data`/`pagination` STORY-128). Mettre à jour l'agrégat `api.targets`→`api.hosts` (l.383) et l'auto-import (`auto-imports.d.ts` se régénère — vérifier `targetsApi` absent après build).
**Fichiers :**
- `frontend/src/services/api.ts` — [Modifier] — `hostsApi` (l.141-162 + l.383)
**Dépend de :** Tâche 1

### Tâche 3 : Store `stores/hosts.ts`
**Objectif :** `git mv frontend/src/stores/targets.ts frontend/src/stores/hosts.ts` : `useTargetsStore`→`useHostsStore` (`defineStore('hosts')`), state `hosts`/`currentHost`, toutes les actions sur `hostsApi` — comportements conservés : pagination enveloppe (`response.data` post-unwrap, commentaire STORY-128 l.24), **health polling** (`startHealthPolling`/`stopHealthPolling`, interval + `_applyHealthResult` l.146-165), scan, erreurs via store. Export dans `stores/index.ts` (l.8) ; supprimer l'ancien export `useTargetsStore`.
**Fichiers :**
- `frontend/src/stores/hosts.ts` — [Créer] — ex-`targets.ts` renommé
- `frontend/src/stores/targets.ts` — [Supprimer]
- `frontend/src/stores/index.ts` — [Modifier] — export `useHostsStore`
**Dépend de :** Tâches 1, 2

### Tâche 4 : Vue `Hosts.vue` + wizard + router
**Objectif :** `git mv frontend/src/views/Targets.vue frontend/src/views/Hosts.vue` : `useHostsStore`, labels i18n « Targets »→« Hosts », colonnes profil/status (`profile` badge au lieu de `type`), hardware/engines affichables. `components/TargetWizard.vue`→`HostWizard.vue` (mêmes étapes connectivité/TOFU — store `hosts`). Router (`router/index.ts` l.46-48) : route `name: 'Hosts'`, `path: '/hosts'`, component `Hosts.vue` + **redirection** `{ path: '/targets', redirect: '/hosts' }` (arbitrage d'analyse : redirection conservée pendant la transition — bookmarks/utilisateurs ; retrait ultérieur tracé avec plan F3).
**Fichiers :**
- `frontend/src/views/Hosts.vue` — [Créer] — ex-`Targets.vue`
- `frontend/src/views/Targets.vue` — [Supprimer]
- `frontend/src/components/HostWizard.vue` — [Créer] — ex-`TargetWizard.vue`
- `frontend/src/components/TargetWizard.vue` — [Supprimer]
- `frontend/src/router/index.ts` — [Modifier] — route `/hosts` + redirection `/targets`
**Dépend de :** Tâche 3

### Tâche 5 : Sidebar + vues consommatrices
**Objectif :** `useSidebarNav.ts` (l.72) : `{ icon: ..., label: 'Hosts', path: '/hosts' }` ; `SidebarNav.vue` (l.200 `useTargetsStore`→`useHostsStore` — usage badges/état) ; `Dashboard.vue` (l.211/231), `Stacks.vue` (l.668/679), `Deployments.vue` (l.216/229), `Compute.vue` (l.335/355) : imports `useHostsStore` depuis `stores` ; `DeploymentDetail.vue` (l.116-120) : label « Target »→« Host », lien `to="/hosts"` ; `ResourceMetricsWidget.vue` : types `HostMetrics` si consommateur. Vérifier i18n (`locales/*.ts` clés `targets.*`→`hosts.*` si présentes).
**Fichiers :**
- `frontend/src/composables/useSidebarNav.ts` — [Modifier] — l.72
- `frontend/src/components/SidebarNav.vue` — [Modifier] — store + libellés
- `frontend/src/views/Dashboard.vue` — [Modifier] — import store
- `frontend/src/views/Stacks.vue` — [Modifier] — idem
- `frontend/src/views/Deployments.vue` — [Modifier] — idem
- `frontend/src/views/Compute.vue` — [Modifier] — idem
- `frontend/src/views/DeploymentDetail.vue` — [Modifier] — l.116-120
- `frontend/src/components/ResourceMetricsWidget.vue` — [Modifier] — types
- fichiers i18n le cas échéant — [Modifier]
**Dépend de :** Tâches 3, 4

### Tâche 6 : CLI — tests envelope sur `/hosts`
**Objectif :** `cli/tests/test_client_envelope.py` (l.194, l.246) : URLs `/targets`→`/hosts` (tests génériques d'envelope pagination — aucune commande CLI dédiée targets/hosts à renommer, vérifié). Vérifier absence d'autres occurrences `/targets` dans `cli/`.
**Fichiers :**
- `cli/tests/test_client_envelope.py` — [Modifier] — l.194, l.246
**Dépend de :** STORY-166.2 (endpoint `/hosts` joignable)

### Tâche 7 : Purge des alias backend internes + décision router alias
**Objectif :** Supprimer les alias de transition **internes** posés par 166.1/166.3 : `models/target.py` (remplacé par alias — supprimer le fichier, imports mis à jour vers `models/host`), `models/target_capability.py` (idem), `enums/target.py` : ⚠ **conserver `TargetType`** (loader stack definitions + `stacks.target_type` — divergence n°4, incorporation F3 reportée) mais purger les re-exports canoniques ; `services/target_service.py`/`target_scanner_service.py`/`target_scan_parsers.py`/`target_access_profile.py` (alias minces — supprimer, consommateurs déjà basculés par 166.2/166.3/166.5) ; `schemas/target.py` alias. Recenser les références résiduelles : `grep -r "target" backend/app --include="*.py"` et traiter (docstrings/variables internes renommables sans risque). **Décision tracée** : le **router alias `/targets`** (166.2) **reste actif** (plan F3 — intégrations externes) ; sa suppression future = arbitrage séparé (tracer dans Notes d'implémentation + backlog item à créer si pertinent).
**Fichiers :**
- `backend/app/models/target.py` — [Supprimer]
- `backend/app/models/target_capability.py` — [Supprimer]
- `backend/app/enums/target.py` — [Modifier] — purger re-exports, conserver `TargetType`
- `backend/app/services/target_service.py` (et 3 autres alias) — [Supprimer]
- `backend/app/schemas/target.py` — [Modifier/Supprimer] — selon résiduels (schemas scan/discovery migrés vers `schemas/host`)
- divers imports backend — [Modifier] — recensement exhaustif par grep
**Dépend de :** Tâches 1-6 (consommateurs basculés) + 166.1→166.5 livrées

### Tâche 8 : Tests frontend/CLI + validation TS stricte
**Objectif :** Adapter les tests existants (stores/views/composants consommateurs) et valider la chaîne stricte (`noUncheckedIndexedAccess`, `noPropertyAccessFromIndexSignature`).
**Fichiers :**
- `frontend/tests/unit/stores/targets.spec.ts` — [Modifier→Renommer] — `hosts.spec.ts`
- `frontend/tests/unit/views/*` (toute spec référençant Targets/store) — [Modifier] — renommages
- `frontend/tests/unit/components/*TargetWizard*` — [Modifier→Renommer] — `HostWizard.spec.ts`
- autres specs consommatrices (`Dashboard`, `SidebarNav`, `DeploymentDetail`…) — [Modifier] — grep `useTargetsStore|targetsApi|Target`
**Dépend de :** Tâches 1-6

## Tests à écrire

### Frontend

**`frontend/tests/unit/stores/hosts.spec.ts`** (ex-`targets.spec.ts`, adapté) :
- chargement : liste vide → `hosts = []`, `loading` toggle ; liste avec éléments (mock `hostsApi.list` → enveloppe `data`) ;
- **pagination enveloppe STORY-128** : `response.data` liste + meta propagée (non-régression AC 1) ;
- **health polling** : `startHealthPolling` appelle `hostsApi.healthCheck` à l'intervalle (fake timers), `_applyHealthResult` met à jour `hosts[i].status`, `stopHealthPolling` purge (non-régression) ;
- create/update/delete/scan/testReachability/testConnection happy paths + **erreurs API** (`mockRejectedValue` → `error` setté, pas de crash) ;
- 401 → pas de données en clair stockées (sécurité).

**`frontend/tests/unit/views/HostsView.spec.ts`** (adapté/créé) :
- rendu initial : spinner loading, état vide, état avec données (table hosts) ;
- **redirection `/login` si non authentifié** (route protégée — règle 40) ;
- **actions admin masquées pour viewer** (boutons create/delete/scan non affichés si `authStore.role === 'viewer'`) ;
- **aucune donnée sensible dans le DOM** : assertions `wrapper.text()` `not.toContain` sur tokens/passwords (règle 40) ;
- lien sidebar `/hosts` actif.

**`frontend/tests/unit/components/HostWizard.spec.ts`** (adapté) : étapes wizard, émission événements, store interactions — non-régression.

**`frontend/tests/unit/composables/useSidebarNav.spec.ts`** (si existant) : entrée `Hosts` → `path === '/hosts'`.

**Tests routeur** : navigation `/targets` → redirection `/hosts` (spawn router ou assertion config).

### CLI

**`cli/tests/test_client_envelope.py`** :
- envelope pagination sur `/hosts` (l.194 `get_paginated` — params `status=up` inchangés, URL `/hosts`) ;
- `get_all('/hosts')` itération pages (l.246) ;
- non-régression : aucun test restant sur `/targets` (grep).

### Backend (purge — non-régression)

- `make backend-lint` vert sans les alias supprimés (imports résiduels détectés par flake8/mypy) ;
- `make backend-test-all` vert (suite complète sans `target_*` internes) ;
- grep final : `grep -rn "from app.models.target import\|from .target_service\|from .target_scanner\|from .target_scan_parsers\|from .target_access_profile" backend/` → **0 résultat**.

### Commandes de validation
```bash
cd frontend && pnpm test -- tests/unit
cd frontend && pnpm typecheck && pnpm lint
make cli-test
make backend-test-all
make backend-lint
```

## Notes d'implémentation (2026-10-30, treat-story)

### Fichiers renommés (`git mv` — historique préservé)

- `frontend/src/stores/targets.ts` → `frontend/src/stores/hosts.ts` (`useHostsStore`, `defineStore('hosts')`, state `hosts`/`currentHost`, actions `fetchHosts`/`createHost`/`updateHost`/`deleteHost`/`scanHost`/`healthCheckHost` — **health polling conservé à l'identique**, `_applyHealthResult` consomme désormais `host_id` canonique, l'alias `target_id` n'est plus lu) ;
- `frontend/src/views/Targets.vue` → `frontend/src/views/Hosts.vue` (labels « Hôtes », colonne **Profil** badge `profile` + affichage `installed_engines`/`hardware_info` avec repli legacy `platform_info`, actions de gestion masquées si non-superuser) ;
- `frontend/src/components/TargetWizard.vue` → `frontend/src/components/HostWizard.vue` (props `editHost`, émission `saved [hostId]`, création `profile: 'host_baremetal'` — ex `type: 'physical'`, arbitrage 166.1) ;
- `frontend/tests/unit/views/Targets.spec.ts` → `Hosts.spec.ts` (réécrite : statuts/profils canoniques, sécurité, tests router redirection) ;
- `backend/tests/unit/test_models/test_target.py` → `test_host_credentials.py` (imports canoniques `models.host`).

### Fichiers créés

- `frontend/tests/unit/stores/hosts.spec.ts` — 8 tests : enveloppe STORY-128 (dépack `data` + meta `pagination`, fallback `{items}`), health polling (fake timers : check immédiat, interval, `stopHealthPolling` purge, échec silencieux), `_applyHealthResult` via `host_id`, scan, 401 sans donnée en clair.

### Fichiers modifiés (frontend)

- `frontend/src/types/api.ts` — types canoniques `HostProfile` (3 valeurs)/`HostStatus` (online/offline/unreachable/scanning), `Host`/`HostCreate`/`HostUpdate`/`HostAccessProfile`/`HostCapability`/`HostCapabilitiesResponse` alignés sur les schémas 166.2 (`profile`, `hardware_info`, `installed_engines`, `last_scan_at`, `origin`, `environment_id`, `ssh_key_id`) ; `HealthCheckResponse.host_id` ; `Deployment.host?` (l'objet imbriqué est un enrichissement client, le backend n'expose que `target_id: str` — contrat non migré F3) ; **conservés** : `TargetGroup`/`TargetMetrics`/`TargetHealthItem`/compteurs `*targets*` du dashboard (contrats backend compute/dashboard non migrés — l'API émet encore ces clés) ;
- `frontend/src/services/api.ts` — `hostsApi` (10 méthodes sur `/hosts` : list/get/create/update/delete/scan/getCapabilities/testReachability/testConnection/healthCheck), agrégat `api.hosts`, `targetsApi` retiré ;
- `frontend/src/router/index.ts` — route `Hosts` (`/hosts`) + **redirection** `{ path: 'targets', redirect: { name: 'Hosts' } }` (arbitrage d'analyse : bookmarks préservés, retrait tracé plan F3) ;
- `frontend/src/composables/useSidebarNav.ts` — entrée `Hosts` → `/hosts` ;
- Vues consommatrices : `SidebarNav.vue` (`useHostsStore`, `activeHostName`/`hostIndicator`/`openHostSelector` → `/hosts`), `Dashboard.vue`, `Stacks.vue`, `Deployments.vue`, `Compute.vue`, `DeploymentDetail.vue` (label Host + lien `/hosts`), `DeploymentHistory.vue`, `ResourceMetricsWidget.vue` (« No host selected » + lien `/hosts`), `RecentDeploymentsWidget.vue` (`deployment.host`), `BaseWizard.vue` (commentaire) ;
- `frontend/src/stores/index.ts` — export `useHostsStore` ;
- `auto-imports.d.ts`/`components.d.ts` — régénérés/alignés (`hostsApi`, `HostWizard`, plus de `targetsApi`/`TargetWizard`).

### Fichiers modifiés (CLI)

- `cli/tests/test_client_envelope.py` — URLs de test `/targets` → `/hosts` (l.194/l.246) ; aucune autre occurrence `/targets` dans `cli/` (vérifié) ; **aucune commande CLI dédiée à renommer** (confirmé par l'analyse — le flag `--target` de `deploy.py` mappe `target_type` des stack definitions, hors périmètre loader/`TargetType`).

### Purge backend (Tâche 7)

**Alias supprimés** (`git rm`) : `app/models/target.py`, `app/models/target_capability.py`, `app/services/target_service.py`, `app/services/target_scanner_service.py`, `app/services/target_scan_parsers.py`, `app/services/target_access_profile.py`, `app/schemas/target.py` (7 fichiers d'alias purs posés par 166.1/166.2/166.3).

**Conservés (décisions tracées)** :
- `app/enums/target.py` — divergence n°4 : `TargetType` requis par le loader stack definitions + `TargetStatus`/enums d'accès legacy (round-trips migrations) ;
- `app/api/v1/targets_legacy.py` + `DeprecationHeadersMiddleware` — **router alias `/targets` actif (plan F3)** pour les intégrations externes ; sa suppression future = arbitrage séparé (ci-dessous) ;
- `app/schemas/target_scan.py` et `app/schemas/target_capability.py` — modules **vivants** (pas des alias de `schemas/target.py`) : consommés par `hosts/scanning.py`, `hosts/capabilities.py`, `host_scanner_service.py`, `socket_clients.py` ; leur renommage éventuel relève d'un arbitrage contrats scanner séparé (le `TargetCapabilityResponse` expose encore `target_id` — contrat figé) ;
- garde-fou `EXPECTED_ROUTE_COUNTS["targets_legacy"]` intact (RBAC exhaustivité).

**Imports internes basculés vers les canoniques** : `host_service.py` (`HostCreateRequest`/`HostUpdate`), `host_scanner_service.py` + `host_access_profile.py` (`HostAccessProfile` depuis `schemas.host`), `api/v1/stats.py` (`models.host.Host`, variables locales `hosts` — **compteurs de sortie `total_targets`/`target_health`/`targets_detail` inchangés**, contrat dashboard figé), `models/__init__.py` + `schemas/__init__.py` (exports alias retirés), `alembic/versions/2026_10_16_1311_ssh_keys_and_fingerprints.py` (helpers chiffrement depuis `models.host` — **découverte runtime** : la migration importait `app.models.target` à l'exécution, ce qui cassait la fixture `_migrated_schema_template` et 907 tests), `pyproject.toml` (override mypy `app.services.target_service` retiré — module supprimé).

**Tests backend adaptés** (28 fichiers) : imports/usages `Target`→`Host`, enums depuis `app.enums.target`, `HostCreateRequest`/`HostUpdate` dans `test_host_service.py`, `test_models/test_host.py` (classe `TestTransitionAliases` retirée — les alias n'existent plus, remplacée par `TestCanonicalTablenames`), golden test d'équivalence alias retiré (l'alias `target_scan_parsers` est supprimé — le garde-fou §2.G `test_payload_keys_contain_no_target_token` reste), `conftest.py` (enums + annotation fixture `test_target` → `Host` — **nom de fixture conservé**, consommateurs nombreux).

### Décisions techniques

1. **Masquage admin sur `isSuperuser`** : la story demandait `authStore.role === 'viewer'` masqué, mais le store auth **n'expose pas de rôle** (seulement `isSuperuser` — les rôles RBAC viewer/operator/admin vivent dans `user_organizations` côté backend, non exposés à `/auth/me`). Actions de gestion (create/scan/edit/delete) masquées si `!isSuperuser` ; l'API reste la source de vérité RBAC (require_admin renvoie 403) — divergence documentée.
2. **Redirection `/targets`→`/hosts`** appliquée comme arbitré en analyse (bookmarks) ; retrait tracé avec le plan F3 (item à créer lors de l'arbitrage de suppression du router alias).
3. **Contrats backend non migrés sciemment consommés en l'état** : compute (`TargetGroup`/`target_id`), dashboard (`total_targets`/`targets_detail`), deployment (`target_id: str`), capabilities (`target_id` dans `HostCapability` TS) — la story vise la bascule frontend vers `/hosts` (166.2), pas la migration des contrats compute/dashboard/deployment (plan F3 ultérieur). Types TS alignés sur les clés réellement émises.
4. **`HostCapability.target_id`** (TS) : le `TargetCapabilityResponse` backend expose `target_id` (synonym model) — le type reflète le contrat réel avec commentaire de bascule future.
5. **Router alias `/targets` + `Sunset: 2027-01-01`** conservés tels quels — la suppression du router alias et le retrait de la redirection frontend seront arbitrés **ensemble** à la fin du plan F3 (backlog item à créer si pertinent — tracé ici).

### Divergences par rapport à l'analyse

- **Découverte 1** : `HostWizard` — la story mentionnait « mêmes étapes connectivité/TOFU » ; le wizard existant n'a pas d'étape TOFU (l'empreinte est capturée par `test-connection` via `ConnectionTestResponse.host_fingerprint`, acceptation via fingerprints API STORY-131.2) — comportement conservé à l'identique, renommage seul.
- **Découverte 2** : la migration `1311` importait `app.models.target` à l'exécution (non recensé par l'analyse — visible seulement au runtime des tests de migrations) — bascule vers `models.host` effectuée.
- **Découverte 3** : `RecentDeploymentsWidget.vue` et `DeploymentHistory.vue` consommaient `deployment.target` (non listés dans la tâche 5) — basculés vers `deployment.host`.
- `pnpm typecheck` s'appelle `pnpm type-check` dans ce projet (Makefile cible `frontend-typecheck` OK).

### Validation

| Vérification | Commande | Résultat |
|---|---|---|
| Tests frontend | `cd frontend && pnpm test -- tests/unit` | **1025 passed** (63 fichiers, dont nouveaux `hosts.spec.ts` store 8 tests + `Hosts.spec.ts` vue+router 6 tests) |
| Typecheck TS strict | `cd frontend && pnpm type-check` | **0 erreur** |
| Lint frontend | `cd frontend && pnpm lint` | **0 erreur** (142 warnings préexistants, fichiers non touchés) |
| Build frontend | `cd frontend && pnpm build` | ✅ |
| Tests CLI | `make cli-test` | **17 passed** |
| Non-régression backend | `make backend-test-unit` | **2607 passed, 0 failed** (dont contrat alias `/targets` figé 19 tests `test_hosts_alias_contract.py` + RBAC exhaustivité) |
| Tests backend ciblés purgés | pytest ciblés | **108 passed** |
| Lint périmètre backend purgé | isort + black + flake8 (15 fichiers) | **0 erreur** |
| mypy périmètre | 6 fichiers production touchés | **0 nouvelle erreur** (2 préexistantes documentées : `host_scanner_service.py:375` ≡ HEAD, `stats.py` psutil stubs) |
| Import app | `python -c "from app.main import app"` | ✅ |

### Grep final de non-régression (résultat documenté — AC 2)

```
grep -rn "from app.models.target import\|from .target_service\|from .target_scanner\|from .target_scan_parsers\|from .target_access_profile" backend/
→ 0 résultat

grep -rn "targetsApi\|useTargetsStore\|TargetWizard\|stores/targets" frontend/src/
→ 0 résultat

grep -rn "/targets" cli/ --include="*.py"
→ 0 résultat

Alias supprimés confirmés absents : models/target.py, models/target_capability.py,
services/target_{service,scanner_service,scan_parsers,access_profile}.py, schemas/target.py
Fichiers conservés attendus présents : enums/target.py, schemas/target_scan.py,
schemas/target_capability.py, api/v1/targets_legacy.py (+ redirection router /targets→/hosts)
```

Résiduels `target` **légitimes** (contrats backend non migrés F3 + divergence n°4) : `TargetGroup`/`TargetMetrics` (compute), compteurs `*targets*` dashboard, `Deployment.target_id`, `TargetCapabilityResponse.target_id`, `TargetType`/`TargetStatus` (enums legacy), `HostResponse.type`/`scan_date`/`platform_info` (echo contrat `/targets` figé), garde-fou `EXPECTED_ROUTE_COUNTS["targets_legacy"]`.
