# EPIC-015 : Compute — Clusters Kubernetes & Apps cluster-scoped

**Statut :** TODO
**Priorité :** Moyenne — item « Kubernetes (core, optionnel) » de la Phase 3 Roadmap, volontairement différé après la remédiation backend (EPIC-011→014) conformément à l'arbitrage F4 ([docs/backend_remediation_plan.md](../../docs/backend_remediation_plan.md) §3/§6) : créer les entités sans adapters de pilotage produirait des coquilles vides non testables. Priorité remontée à Haute le moment venu si un utilisateur cible k8s se manifeste.
**Phase Roadmap :** Phase 3 — Q3 2026 (item optionnel, séquencé après remédiation)
**Version cible :** 1.2

## Vision

Lever le dernier grand écart spec ↔ code du modèle directeur Compute : les **Clusters** Kubernetes (k8s, k3s, microk8s) et les **Apps cluster-scoped** (`helm_release`, `k8s_manifest`). Aujourd'hui, le backend ne fait que **détecter** les outils Kubernetes via `_detect_kubernetes()` dans [`target_scanner_service.py`](../../backend/app/services/target_scanner_service.py) — aucun pilotage (kubeconfig, pods, nœuds, releases Helm) n'existe.

Cette epic livre le segment Kubernetes du modèle directeur des specs [02-familles-workloads.md](../../docs/general_specs/02-familles-workloads.md) et [03-modele-compute.md](../../docs/general_specs/03-modele-compute.md) :

1. **Entité Cluster** de premier rang (type `kubernetes`, connexion par kubeconfig **chiffré en base**), constituée de membres (Hosts/Machines, rôles `control-plane`/`worker`, `k8s_metadata` labels/taints) et hébergeant des Apps.
2. **Apps cluster-scoped** : profils `helm_release` / `k8s_manifest` hébergées par le Cluster (`apps.cluster_id`), avec le triple XOR `host_id`/`machine_id`/`cluster_id` sur `AppCreateRequest` ([09-api.md](../../docs/general_specs/09-api.md) l.143).
3. **Adapters** `KubernetesClusterAdapter`, `HelmReleaseAdapter`, `K8sManifestAdapter` sur l'interface `WorkloadAdapter` posée par STORY-174 — cibles documentées [VIRTUALIZATION-SYSTEMS.md](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md) §3.13/§3.14/§6.
4. **Pilotage complet** : santé (quorum, nœuds notReady), scan (résolution nœuds par nom/IP → `cluster_members`), events k8s, actions de maintenance (drain/uncordon/reboot), déploiement manifests YAML et gestion de releases Helm (install/upgrade/rollback).

À la fin de cette epic, la chaîne complète `Host → Machine (nœud) → Cluster → App` du modèle directeur est représentable et pilotable, et les endpoints `/clusters` documentés dans la spec API existent réellement.

### Valeur Business
- Débloque le critère de succès Phase 3 « Kubernetes basique fonctionnel » ([Roadmap.md](../../docs/Roadmap.md))
- Élimine le principal écart résiduel entre le modèle directeur spec et le code (families `Apps`/`Clusters` partiellement inexistantes)
- Ouvre WindFlow aux utilisateurs homelab/PME déjà équipés d'un cluster k3s/microk8s — sans les forcer à replier leur cluster en machines individuelles
- Clôture l'arbitrage F4 : les entités `Clusters` arrivent **avec** leurs adapters, jamais en coquilles vides

### Utilisateurs cibles
- **Self-hoster k8s** : un cluster k3s/microk8s sur RPi/NUC, veut le piloter depuis le même dashboard que ses containers Docker
- **Développeur DevOps** : déploie des Helm charts / manifests YAML et veut update + rollback intégrés
- **Admin infrastructure** : santé du cluster (quorum, notReady), events, drain de nœud avant maintenance

## Contenu de l'Epic

### Modèle de données & migrations
- [ ] Entité **Cluster** : `type` (`kubernetes`|`proxmox`|`docker_swarm` — seul `kubernetes` implémenté ici), `environment_id`, `connection_config` (kubeconfig) chiffré en base via SecretManager, `origin` (`managed`/`adopted`/`external`), `status`, métriques agrégées
- [ ] Table **`cluster_members`** : `cluster_id`, XOR `host_id`/`machine_id`, `role` (`control-plane`|`worker`|`member`), `k8s_metadata` (JSON labels/taints), `joined_at` ; unicité « un Host/Machine membre d'au plus un Cluster »
- [ ] Extension **App** pour les profils cluster-scoped : `profile` = `helm_release`|`k8s_manifest`, colonne `cluster_id`, contrainte triple XOR `host_id`/`machine_id`/`cluster_id`
- [ ] Migrations Alembic + fixtures de test réalistes (cluster 1 control-plane + 2 workers)

### API `/clusters` (API-first — [09-api.md](../../docs/general_specs/09-api.md) §Cluster)
- [ ] `GET/POST /api/v1/clusters` + `GET/PUT/DELETE /{id}` — CRUD, enveloppes `APIResponse`/`PaginatedResponse` (STORY-126), pagination (STORY-128)
- [ ] `GET/POST /clusters/{id}/members`, `DELETE /clusters/{id}/members/{member_id}` — rattachement manuel, détachement sans suppression de l'entité Host/Machine
- [ ] `GET /clusters/{id}/health` — quorum, membres down/notReady, versions
- [ ] `POST /clusters/{id}/scan` — scan cluster-scoped : résolution nœuds par nom/IP → création de lignes `cluster_members`, nœuds non reconnus listés en lecture seule
- [ ] `GET /clusters/{id}/apps` — Apps hébergées (helm_release, k8s_manifest)
- [ ] `GET /clusters/{id}/events` — events k8s (flux WebSocket)
- [ ] `POST /clusters/{id}/actions/{action_id}` — ContextualActions : drain, uncordon, reboot membre (section Avancé, spec 02)
- [ ] Montage du router `clusters` dans [`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) (aujourd'hui absent)

### Apps cluster-scoped — router `/apps`
- [ ] Profils `helm_release` / `k8s_manifest` sur `AppCreateRequest` avec **triple XOR** validé (exactement un de `host_id`/`machine_id`/`cluster_id`)
- [ ] `GET/POST /api/v1/apps` + `GET/PUT /{id}/config` + `DELETE /{id}` + `POST /{id}/start|stop|restart|update|backup|restore` — verbes universels traduits par les adapters (spec 02 « Mapping par profil App »)
- [ ] Montage du router `apps` dans [`backend/app/api/v1/__init__.py`](../../backend/app/api/v1/__init__.py)

### Adapters (interface `WorkloadAdapter` — STORY-174)
- [ ] **`KubernetesClusterAdapter`** (`ClusterAdapter`) : connexion kubeconfig, `list_members()` (rôle, santé), `get_health()` (quorum, versions, notReady), `scan()` (nœuds → `cluster_members`), `list_apps_hosted()`, events, `contextual_actions()` (drain/uncordon/reboot), Mode Infra (`get_native_config()`, `get_technical_components()`)
- [ ] **`HelmReleaseAdapter`** (`AppAdapter`) : install/upgrade/rollback/history (`helm list` pour discovered → `external`)
- [ ] **`K8sManifestAdapter`** (`AppAdapter`) : apply/re-apply/scale de manifests YAML, lecture de l'état observé
- [ ] Détection de l'origine (spec 03 §matrice) : namespace dédié `windflow` / annotation Helm `windflow.io/managed=true` → `managed`, sinon `external` (observation + adoption)

### Pilotage temps réel & WebSocket
- [ ] Terminal dans pods (`GET /apps/{id}/console` → exec k8s)
- [ ] Logs pods (`GET /apps/{id}/logs` → flux WebSocket)
- [ ] Events cluster (`/clusters/{id}/events`) réutilisant le pattern du module WebSocket existant

### Frontend — vue Compute
- [ ] `/compute/clusters` : liste Clusters (statut, type, membres, santé agrégée)
- [ ] `/compute/graph` : arêtes same-namespace entre Apps d'un même cluster
- [ ] Exposition des pods k8s dans `/compute/containers` (onglet Containers : Docker + k8s — **zone d'imprécision spec à clarifier en analyse**, spec 03 §Vue Compute)
- [ ] Onglets Cluster Mode Infra : `K8s : Namespaces & Events`, `Scan & Diagnostics` (spec 02 §onglets Clusters)

### Transversal
- [ ] RBAC sur tous les endpoints `/clusters` et `/apps` (admin/operator pour actions de maintenance, viewer lecture seule — `require_role` STORY-122)
- [ ] Audit trail sur actions critiques (drain, suppression cluster, déploiement Helm — STORY-125)
- [ ] Kubeconfig et credentials cluster **chiffrés au repos** (SecretManager STORY-103), jamais loggés ni exposés dans les réponses API
- [ ] Rate limiting sur les endpoints de scan (opérations coûteuses)

## Liste des Stories liées
*À créer ultérieurement*

Stories suggérées (numéros libres, à confirmer à la création) :

- [ ] STORY-260 : Modèle `Cluster` + `cluster_members` — entités, migrations Alembic, fixtures, contraintes XOR et unicité d'appartenance
- [ ] STORY-261 : Router `/api/v1/clusters` — CRUD + members + health + scan + apps + events + actions, montage dans `api/v1/__init__.py`
- [ ] STORY-262 : `KubernetesClusterAdapter` — connexion kubeconfig chiffrée, santé, scan/résolution des membres, events, contextual actions (drain/uncordon/reboot)
- [ ] STORY-263 : Extension App cluster-scoped — profils `helm_release`/`k8s_manifest`, triple XOR sur AppCreateRequest, router `/apps` + montage
- [ ] STORY-264 : `HelmReleaseAdapter` — install/upgrade/rollback/history + détection d'origine (`helm list`, annotation `windflow.io/managed`)
- [ ] STORY-265 : `K8sManifestAdapter` — apply/re-apply/scale + état observé + détection d'origine (namespace `windflow`)
- [ ] STORY-266 : WebSocket temps réel k8s — terminal pods, logs pods, events cluster
- [ ] STORY-267 : Frontend vue Compute — `/compute/clusters`, `/compute/graph` (arêtes same-namespace), pods dans `/compute/containers`, onglets Mode Infra

## Notes de conception

- **Fidélité aux specs** : le périmètre est défini par [02-familles-workloads.md](../../docs/general_specs/02-familles-workloads.md) (entité Cluster, famille Clusters, mapping verbes), [03-modele-compute.md](../../docs/general_specs/03-modele-compute.md) (matrice profil × origine, détection runtime, vue Compute) et [09-api.md](../../docs/general_specs/09-api.md) (surface REST `/clusters`, triple XOR l.143) ; la Roadmap ne fait que le phaser.
- **Origine de l'epic (traçabilité)** : écarts spec → code identifiés par les audits précédents et **reportés via l'arbitrage F4** ([docs/backend_remediation_plan.md](../../docs/backend_remediation_plan.md) §3 F4 + §6 « hors périmètre → Roadmap Phase 2 ») : « Entités Apps/Machines/Clusters, triple XOR, verbes universels — les entités arrivent avec leurs adapters » ; « Piloting Helm/K8s/Swarm → adapters Clusters ».
- **Absorption d'intentions EPIC-003** : les STORY-351→354 (connexion kubeconfig, manifests/Helm, dashboard cluster, terminal pods) référencées dans [EPIC-003](EPIC-003-security-gitops-multitarget.md) §« Kubernetes basique (Phase 3 — optionnel) » mais **jamais créées** sont absorbées par la présente epic — la section EPIC-003 porte une note de renvoi croisé.
- **Périmètre volontairement restreint à `kubernetes`** : les types `proxmox` et `docker_swarm` de l'entité Cluster restent hors périmètre (enum préparé, adapters non implémentés) — ils feront l'objet d'extensions ultérieures ; l'interface `ClusterAdapter` est posée pour les accueillir.
- **Client k8s** : privilégier une lib Python officielle (`kubernetes` async) ou subprocess `kubectl`/`helm` — arbitrage à trancher en analyse de STORY-262/264 (ARM-first : le binaire helm/kubectl multi-arch existe déjà comme prérequis de détection).
- **Détection existante conservée** : `_detect_kubernetes()` (kubeadm/k3s/microk8s, VIRTUALIZATION-SYSTEMS §3.13) reste la brique de scan SSH des nœuds ; le scan **cluster-scoped** (API du cluster) est complémentaire, pas redondant.
- **Sécurité** : kubeconfig = credential sensible → chiffrement au repos (SecretManager STORY-103), RBAC strict, audit des actions de maintenance, masquage dans toutes les réponses et logs (checklist sécurité règles 40).
- **API-first** : endpoints REST complets et documentés (OpenAPI/Scalar) avant toute consommation UI ; enveloppes et pagination conformes aux standards STORY-126/128.
- **Zone d'imprécision spec** : l'exposition des pods k8s dans `/compute/containers` (spec 03 §onglet Containers « Docker + k8s ») devra être clarifiée pendant l'analyse (granularité pod vs container, filtres) — signalée en divergence potentielle.

## Critères de succès (Definition of Done)
- [ ] Un cluster k3s réel peut être ajouté via `POST /api/v1/clusters` (kubeconfig) et ses membres résolus par `POST /{id}/scan`
- [ ] `GET /clusters/{id}/health` retourne quorum, membres notReady et versions
- [ ] Une App `helm_release` peut être déployée, mise à jour (upgrade) et rollbackée sur le cluster ; une App `k8s_manifest` appliquée et re-scalée
- [ ] Le triple XOR `host_id`/`machine_id`/`cluster_id` est validé (422 si 0 ou 2+ cibles — tests unitaires)
- [ ] Terminal et logs dans les pods accessibles via WebSocket
- [ ] Vue Compute : clusters visibles, graphe avec arêtes same-namespace, pods exposés
- [ ] Kubeconfig chiffré en base, absent des réponses API et des logs (test de non-exposition)
- [ ] RBAC effectif : viewer en lecture seule, operator/admin pour drain/déploiements
- [ ] OpenAPI à jour (Scalar/Swagger/ReDoc) pour `/clusters` et `/apps`
- [ ] Couverture tests ≥ 80 % sur le nouveau code (cibles critiques : adaptateurs, XOR, chiffrement)
- [ ] Tous les éléments du contenu implémentés

## Risques
| Risque | Impact | Mitigation |
|--------|--------|------------|
| Complexité k8s (versions, RBAC du cluster cible, contextes kubeconfig) | Élevé | Périmètre « basique » : un seul contexte, opérations idempotentes ; tests contre cluster k3s de CI (kind/k3d) |
| Dépendance à un client k8s Python mature en async | Moyen | Arbitrage lib officielle vs subprocess kubectl en analyse (STORY-262) ; l'exécution CLI est déjà le pattern Helm retenu (VIRTUALIZATION-SYSTEMS §3.14) |
| Coquilles vides si les adapters glissent (périmètre F4 réédité) | Élevé | Découpage stories entité+adapter liées (260/262, 263/264/265) ; aucun endpoint exposé sans adapter fonctionnel derrière |
| Zone d'imprécision spec (`/compute/containers` pods) | Moyen | Clarification en analyse de STORY-267 avec divergence signalée à l'utilisateur avant implémentation |
| Kubeconfig fuite (secret le plus sensible du dépôt) | Élevé | SecretManager (STORY-103), tests de non-exposition systématiques, RBAC admin, audit |
| Collision numérotation stories avec réservations EPIC-003 (plage 300+) | Faible | Plage 260+ réservée à l'epic ; vérification `list_files` à la création |
| Charge des scans cluster (rate limiting, timeouts) | Moyen | Rate limiting sur `/scan`, timeouts configurables, opérations async avec retry/backoff |

## Dépendances
- **STORY-166** (EPIC-013) : migration `Target`→`Host` + axe `origin` — prérequis du modèle (les membres de cluster sont des Hosts/Machines)
- **STORY-173** (EPIC-013) : `/compute` browse paginé — la vue Compute s'y raccroche
- **STORY-174** (EPIC-013) : interface `WorkloadAdapter` + adapter Docker + recreate sécurisé — le contrat sur lequel s'appuient `KubernetesClusterAdapter`/`HelmReleaseAdapter`/`K8sManifestAdapter`
- **EPIC-011** (P0 sécurité) : SecretManager (STORY-103) pour le chiffrement du kubeconfig, RBAC (STORY-122)
- **EPIC-012** (P1 socle) : enveloppes APIResponse/PaginatedResponse (STORY-126), pagination (STORY-128), audit trail (STORY-125), Alembic (STORY-120)
- **EPIC-014** (P3 finitions) : STORY-252 (arbitrages F1-F6 appliqués aux specs, dont l'annotation « déploiement phasé » de la spec 06) et STORY-254 (revue conformité finale) — clôture du plan de remédiation qui précède cette epic
- **EPIC-003** : intentions Kubernetes (STORY-351→354, jamais créées) absorbées ici — renvoi croisé posé dans le fichier EPIC-003

## Séquençage recommandé

```
STORY-260 (modèle Cluster+members) ──► STORY-261 (router /clusters) ──► STORY-267 (frontend Compute)
        │                                       │
        │                                       ▼
        │                            STORY-262 (KubernetesClusterAdapter : santé/scan/events/actions)
        │                                       │
        └──► STORY-263 (App cluster-scoped + triple XOR + router /apps)
                        │
                        ├──► STORY-264 (HelmReleaseAdapter)
                        └──► STORY-265 (K8sManifestAdapter)
                                        │
                                        ▼
                              STORY-266 (WebSocket pods/logs/events)
```
