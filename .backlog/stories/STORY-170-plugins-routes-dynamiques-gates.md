# STORY-170 : Plugins — routes API dynamiques `/api/v1/plugins/{name}/…` et gates pre-deploy (approve/deny, timeout, Trivy) (P2-3, partie extension — axes B5, C6)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-3 partie extension (axes B5, C6, rapports §10/§7) — ampleur **L**

## Description

En tant que développeur de plugins WindFlow, je veux que les extension/hybrid plugins montent **dynamiquement leurs routes API** sous `/api/v1/plugins/{name}/…` (préfixées, protégées par l'auth JWT et le RBAC du core, documentées OpenAPI, désenregistrées à la désinstallation) et que les **gates pre-deploy** — hooks synchrones de décision `approve`/`deny` exécutés après résolution d'images et avant création des containers, avec timeout (défaut 300 s) et plugin Trivy comme implémentation de référence — soient câblées dans le pipeline de déploiement, afin que l'extension du core promise par la spec 11 soit réelle.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §5, §14.1) : aucune route dynamique de plugin n'existe — le chargement d'extensions (api_module) de la spec 11 n'est pas implémenté ; les gates pre-deploy (`deploy_hooks.pre_deploy`) sont absentes du pipeline de déploiement.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Routes dynamiques spec 11 § Extension de l'API** : `plugin_router("{name}")` préfixé `/api/v1/plugins/{name}/` ; enregistrées au chargement du plugin (étape INSTALL de STORY-169), automatiquement : préfixées, **protégées JWT + RBAC core** (permissions endpoints plugin : lecture Viewer, écriture Operator, config Admin — spec 08), **documentées dans OpenAPI** (visibles `/docs`, tag dédié), **désenregistrées à la désinstallation** ; échec de chargement → rollback (désenregistrement des routes partiellement chargées, STORY-169 AC 3) ;
- **Gates pre-deploy spec 11 § Hooks de déploiement** : exécution **après résolution d'image, avant création des containers** — le plugin connaît les images exactes (nom, tag, digest) ; contrat d'entrée (`deployment_id`, `target`, `images[]`, `trigger` `manual|scheduled|webhook|batch`) et sortie (`approve()` / `deny(reason)`) ; **comportements par défaut** : aucun plugin n'implémente la gate → déploiement suit son cours (le core ne bloque jamais par défaut) ; **timeout** (défaut 300 s, configurable) → refus prudent `GATE_TIMEOUT` (« on ne déploie pas ce qu'on n'a pas pu évaluer ») sauf `on_timeout: approve` déclaré ; un refus = échec de déploiement classique : événement `deployment.failed` (code `GATE_DENIED`, plugin, raison), progression WebSocket et **lignes `deployment_events`** (STORY-167) ;
- **La gate s'applique à tous les chemins de déploiement** : stack deploy, recreate/Mettre à jour, batch-update, synchro Git future — brancher au niveau du pipeline commun ([`background_tasks.py:24`](../../backend/app/tasks/background_tasks.py:24) / [`docker_service.py:20`](../../backend/app/services/docker_service.py:20)) ;
- **Plugin Trivy de référence** : matrice de critères de blocage (`never` défaut / `any` / `critical_high` / `critical` / `more_than_current`), flux protégé par **tag temporaire** `<tag>-windflow-pending` (image candidate tirée puis scannée, image refusée supprimée, tag original restauré à l'approbation), image du scanner **épinglée par version** (jamais `:latest`), cache dans un volume `windflow-plugin-trivy-*` protégé du prune — implémenter au moins la gate + un mode `never` fonctionnel ; le scan complet (report vulnérabilités) peut rester simplifié à ce stade (le plugin complet relève du catalogue) ;
- **Distinction hooks vs gates** : `@on_event` (STORY-163) = asynchrone non bloquant ; gate = décision bloquante synchrone — ne pas mélanger ;
- Zones : pipeline de déploiement, nouveau support `plugin_api`/`plugin_gates`, [`plugin_manager_service.py:27`](../../backend/app/services/plugin_manager_service.py:27) (chargement extensions), OpenAPI multi-interfaces (garde-fou : maintenu à jour).

## Critères d'acceptation (AC)

- [ ] AC 1 : Un plugin extension (démonstrateur) déclarant `extensions.api_module` voit ses routes montées sous `/api/v1/plugins/{name}/…` — test : appel authentifié → 200 ; **sans token → 401** ; rôle insuffisant → 403 (RBAC core appliqué) ; la route apparaît dans `/openapi.json` avec son tag ; à la désinstallation, la route disparaît (404) et de l'OpenAPI.
- [ ] AC 2 : Les gates pre-deploy s'exécutent **après résolution d'images, avant création des containers** — test : une gate `deny(reason)` fait annuler le déploiement **avant toute création de container** (aucun conteneur créé), avec événement `deployment.failed` portant code `GATE_DENIED` + plugin + raison, progression WS et lignes `deployment_events` typées (STORY-167).
- [ ] AC 3 : **Comportements par défaut** : aucune gate enregistrée → déploiement suit son cours (non-régression) ; gate qui timeout (défaut 300 s, test avec timeout court simulé) → refus prudent `GATE_TIMEOUT` ; `on_timeout: approve` déclaré → déploiement autorisé au timeout ; plusieurs gates → approbation de toutes requise (premier `deny` l'emporte).
- [ ] AC 4 : Le **plugin Trivy** (gate de référence) fonctionne au moins en mode `never` (jamais bloquant) et en mode bloquant simulé — la matrice de critères est exposée dans sa config ; le flux tag temporaire et l'image épinglée sont implémentés ou documentés comme simplifiés à ce stade (écart noté pour le plugin catalogue complet) ; le cache scanner vit dans un volume protégé du prune (convention `windflow-plugin-*`).
- [ ] AC 5 : Tests de sécurité : routes dynamiques soumises au RBAC (401/403/422 sur échantillon), secrets du plugin jamais exposés ; non-régression des déploiements sans plugin ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Extension de l'API (`plugin_router`, préfixe, auth/RBAC/OpenAPI/désenregistrement), § **Hooks de déploiement (gates)** (moment d'exécution, contrat entrée/sortie, comportements par défaut, déclaration manifest `deploy_hooks.pre_deploy`), § Plugin Trivy (exemple, matrice de critères, flux tag temporaire, image épinglée), § Extension plugin / Hybrid plugin (types) ;
- [`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md) — § Permissions sur les endpoints plugin (lecture Viewer, écriture Operator, config Admin) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Routes dynamiques des plugins (exemples Traefik/PostgreSQL/IA/Restic), § Prune des images/volumes (liste protégée `windflow-plugin-*`) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Sémantique de mise à jour / recreate (la gate s'applique au chemin de recréation) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité des plugins (isolation, permissions), § Plugin Trivy (blocage optionnel via gate) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-3 (« routes dynamiques d'extension `/api/v1/plugins/{name}/…` documentées OpenAPI »), §2.B B5, §2.C C6 ;
- [`backend_status.md`](../../docs/backend_status.md) — §5 (plugin_* services), §3.14, §4.4 (pipeline `background_tasks`).

## Dépendances

- **STORY-169** (installation réelle — le chargement des extensions fait partie du même pipeline) ; analyse conjointe recommandée.
- S'appuie sur **STORY-122** (RBAC appliqué aux routes dynamiques), **STORY-167** (lignes `deployment_events` des refus), **STORY-163** (chargement `hooks_module` — même mécanique d'import), **STORY-162** (événement `deployment.failed`), **STORY-125** (audit des actions plugin si fusionné).

## Sous-stories

*(section réservée — story L : découpe possible routes dynamiques / gates ; plage réservée STORY-175-199)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
