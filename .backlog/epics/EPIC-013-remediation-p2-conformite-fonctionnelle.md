# EPIC-013 : P2 — Conformité fonctionnelle (remédiation backend)

**Statut :** IN_PROGRESS
**Priorité :** Moyenne

## Vision

Rendre le backend réellement conforme aux spécifications fonctionnelles sur les axes qui structurent le produit : moteur de planification d'actions (scheduler asyncio), bus d'événements canonique et ses consommateurs plugins, plugins réels (download/checksum/compose/rollback, routes dynamiques et gates), modèle `Target`→`Host` avec axe `origin`, WebSocket durci (canaux, heartbeats, ack, reconnexion) et testé, validation stacks unifiée, `deployment_events` persistés, cache avec fallback mémoire, observabilité Prometheus réelle, surface `/compute` étendue (`browse`/`prune`) et socle `WorkloadAdapter` avec recreate sécurisé. Cette vague P2 du plan de remédiation ([`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4) transforme les coquilles existantes en fonctionnalités vérifiables.

Spécifications de référence : [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md), [`11-plugins.md`](../../docs/general_specs/11-plugins.md), [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md), [`03-modele-compute.md`](../../docs/general_specs/03-modele-compute.md), [`04-architecture.md`](../../docs/general_specs/04-architecture.md), [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md), [`09-api.md`](../../docs/general_specs/09-api.md), [`15-securite.md`](../../docs/general_specs/15-securite.md), [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) + [`docs/technical_specs/WEBSOCKET-REAL-TIME.md`](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md), [`STACK-DEFINITIONS.md`](../../docs/technical_specs/STACK-DEFINITIONS.md), [`VIRTUALIZATION-SYSTEMS.md`](../../docs/technical_specs/VIRTUALIZATION-SYSTEMS.md), [`ARCHITECTURE-MODULAIRE.md`](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md).

## Description

Chaque item P2 du plan de remédiation est couvert par une story de la plage STORY-160→174 — certains items XL/L étant découpés en 2 stories (moteur/persistance, bus/consommateurs, installation/extension, durcissement/tests) et certains items M étant regroupés là où ils partagent la même zone de code :

| Story | Items plan | Objectif | Ampleur |
|-------|-----------|----------|---------|
| STORY-160 | P2-1 moteur (A8) | Moteur d'exécution du scheduler : boucle asyncio (croniter), registre d'actions (`stack.backup`, `compute.docker.prune`, `host.scan`, `admin.backup`, `notification.send`), triggers cron **et** événement, verrous anti-chevauchement, relecture défensive, récupération des orphelins, fuseaux IANA | XL |
| STORY-161 | P2-1 traçabilité (A8) | Table `scheduled_task_executions` : historique des exécutions (statut, déclencheur, durée, erreur, journaux), endpoints de consultation paginés, purge/rétention | M |
| STORY-162 | P2-2 bus (B7, C5, F6) | Bus d'événements canonique : interface unique, nomenclature des ~18 événements (`deployment.completed`→`succeeded`, `target.*`→`host.*`), in-memory par défaut + Redis Pub/Sub optionnel | L |
| STORY-163 | P2-2 consommateurs (B7, C6) | Consommateurs plugins du bus : hooks `@on_event` sur les 18 événements canoniques, enregistrement de `deployment_notifications`, émission de `DEPLOYMENT_PROGRESS` | M |
| STORY-164 | P2-5 durcissement (C3, C4) | Canaux WS manquants (`/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}` — VNC reporté Roadmap VMs) + heartbeats avec expiration, acknowledgment, reconnexion unifiée avec jitter | L |
| STORY-165 | P2-5/P2-14 tests WS (C9, C14) | Tests WebSocket : couverture complète du module (handlers, managers, plugins, souscriptions, auth) — comble le zéro de test | M |
| STORY-166 | P2-4 **+ P2-10** (F4 étape 2, A14, C13, D2, C8) | Migration `Target`→`Host` (modèle/API toutes couches, profils 3 valeurs, alias `/targets` déprécié), axe `origin` managed/adopted/external, `environments` activés, `Stack.git_url`, **auto-détection du host local (P2-10, désactivable)** | XL |
| STORY-167 | P2-7 (A15) | `deployment_events` : table dédiée remplaçant la colonne texte `Deployment.logs` (migration des données), events typés horodatés, endpoint paginé, rétention | M |
| STORY-168 | P2-8 (C7, E4) | Cache avec fallback mémoire : interface unique get/set/delete + TTL (Redis si configuré sinon mémoire), consommée par rate limiter/plugin registry/RBAC, supprime les dégradations silencieuses | M |
| STORY-169 | P2-3 installation (B5, C12) | Plugins — installation réelle : téléchargement (URL registre), vérification checksum SHA-256 obligatoire, extraction, `docker compose up` du service, rollback complet sur échec, `plugin_configs` chiffré si `encrypted` | XL |
| STORY-170 | P2-3 extension (B5, C6) | Plugins — routes API dynamiques `/api/v1/plugins/{name}/…` (RBAC + OpenAPI + désenregistrement) et gates pre-deploy (approve/deny, timeout 300 s, Trivy de référence) | L |
| STORY-171 | P2-6 (B8, B9) | Unification validation stacks : fusionner `stack_loader_service` (allégé) et la validation admin en un moteur unique (même moteur en seed et en import admin ; corriger postgresql.yaml « invalide ») + bornes `min/max`→`minimum`/`maximum` | M |
| STORY-172 | P2-9 (B4, E5) | Prometheus réel : instrumentation `/metrics` (latence, erreurs, déploiements ok/ko, tâches scheduler), câbler `websocket/metrics.py` ou le supprimer, dashboards Grafana alimentés par de vraies métriques | M |
| STORY-173 | P2-11 + P2-14 partie compute (D1, F3, C9) | `/compute` élargi : `browse` (inventaire détaillé paginé filtrable, dont volumes), `prune` protégé (superadmin + confirmation + dry-run + audit, liste `windflow-plugin-*` épargnée), rapprochement surface `/compute` ↔ `/docker` (incorporation F3) | M |
| STORY-174 | P2-12 **+ P2-13** (D3, F7, C10) | Socle `WorkloadAdapter` + `DockerWorkloadAdapter`/Compose encapsulant les services existants (sans réécrire, sans adapters K8s/VM) + **recreate sécurisé (P2-13 : rebase par valeur, rollback sur échec, secrets masqués `***`)** | L |

**Traçabilité des items P2 sans story dédiée** (aucun détail perdu) :
- **P2-10 (auto-détection du host local, C8)** → intégré à **STORY-166** (le plan le conditionnait à P2-4 « entité Host » — fusion naturelle).
- **P2-13 (recreate sécurisé, C10)** → intégré à **STORY-174** (même zone de code : le recreate est la traduction Docker du verbe Mettre à jour porté par l'adapter).
- **P2-14 (tests des zones zéro, C9/C14)** → réparti : websocket via **STORY-165**, schedules via **STORY-161**, compute via **STORY-173** ; le solde (organizations, users API, discovery/adoption complément, import_export, stats) reste couvert **au fil des vagues** conformément au risque §7.2 — à vérifier dans chaque story touchant ces zones (cible ≥ 80 % par domaine sur les modules touchés).
- **P2-15 (notifications core in-app + webhook, A9)** → **non affecté dans la plage 160-174** (15 stories strictes) ; les stories dépendantes référencent « story notifications P2-15 » (STORY-160 pour `notification.send`, STORY-161 pour l'alerte 3 échecs). Matérialisation à décider lors de l'analyse : numéro libre de la plage réservée **STORY-175-199** ou vague suivante — l'arbitrage doit être tracé avant la finalisation de STORY-160.

**Dépendances internes** (plan §4-§5 + sections Dépendances de chaque story) :
- **STORY-160** et **STORY-161** dépendent de **STORY-120** (Alembic, EPIC-012) — analyse conjointe recommandée.
- **STORY-162** : aucune dépendance dure P1 ; **STORY-163** dépend de STORY-162.
- **STORY-164** (découpée → **STORY-164.1/.2/.3**) dépend de **STORY-100** (WS auth, EPIC-011) + **STORY-131** (ssh_keys — ⚠️ correction : la version précédente de cette epic citait « STORY-128 (ssh_keys) », erroné — STORY-128 est la pagination, les ssh_keys sont la STORY-131) ; 164.2 dépend en outre de 164.1 (helper d'expiration — recommandé), 164.3 a une dépendance documentaire avec 164.1 ; **STORY-165** dépend des sous-stories 164.1→164.3.
- **STORY-166** dépend de **STORY-120 + STORY-121 + STORY-122** (chaîne critique Alembic → RBAC → nouveaux chemins `/hosts`) ; s'appuie sur STORY-103 (credentials chiffrés) et STORY-131 (`hosts.ssh_key_id`).
- **STORY-167** dépend de **STORY-120** ; liée à STORY-162 (nomenclature).
- **STORY-168** dépend de **STORY-121/STORY-122** (cache RBAC TTL 300 s) ; harmonisation avec STORY-102 (rate limit mémoire).
- **STORY-169** dépend de **STORY-103** (SecretManager — dépendance explicite du plan) ; idéalement après **STORY-125** (audit branché, risque §7.3) ; **STORY-170** dépend de STORY-169.
- **STORY-171**, **STORY-172**, **STORY-174** : aucune dépendance marquée par le plan (STORY-174 recommande STORY-103 ; prépare P3-2 CircuitBreaker).
- **STORY-173** dépend de **STORY-121/122 + STORY-126/128** (RBAC + enveloppes/pagination avant élargissement — ⚠️ correction : la version précédente citait « STORY-124/125 » pour enveloppes/pagination, erroné — ce sont STORY-126 et STORY-128) ; idéalement après STORY-166.
- Chaînes critiques du plan §5 : Alembic(120) → RBAC(121/122) → Host(166) et `/compute` élargi (173) ; SecretManager(103) → SSH(131) → plugins réels (169) et canal WS ssh (164) ; scheduler(160) → purge croniter (P3-1, EPIC-014) ; enveloppes(126) → pagination(128) → surfaces élargies.

**Critères de done (reprend fidèlement le plan)** :
- P2-1 (STORY-160/161) : cron déclenché à l'heure (time travel/monkeypatch), verrou (2 déclenchements simultanés → 1 exécution), exécutions persistées et listables, redémarrage mi-exécution → récupération ; rétention appliquée, orphelins marqués `failed`.
- P2-2 (STORY-162/163) : table de correspondance ancien→nouveau documentée ; chaque événement spec émis par son émetteur réel ; avec Redis configuré, événement visible sur canal Pub/Sub ; sans Redis, in-memory intact ; `DEPLOYMENT_PROGRESS` émis, `deployment_notifications` enregistré.
- P2-3 (STORY-169/170) : install avec checksum invalide → rejet ; échec de hook → rollback complet (DB + filesystem + conteneur) ; config chiffrée en base ; routes dynamiques documentées OpenAPI ; gates approve/deny/timeout avec Trivy de référence.
- P2-4 + P2-10 (STORY-166) : migration de données sans perte (test sur fixture réaliste) ; double nommage actif avec header de dépréciation ; adoption marque `origin=adopted` ; stacks rattachables à un environnement ; premier démarrage → host local détecté, désactivable par setting.
- P2-5 (STORY-164.1→164.3/165) : suite de tests WS (connexion, auth, heartbeat timeout, re-souscription) ; client type documenté ; VNC explicitement absent (machines = Roadmap).
- P2-6 (STORY-171) : `postgresql.yaml` passe la validation API admin ET le seed avec les mêmes règles ; `minimum/maximum` servis au formulaire.
- P2-7 (STORY-167) : un déploiement de test produit une séquence d'events requêtable paginée ; rétention appliquée.
- P2-8 (STORY-168) : sans Redis, cache mémoire fonctionne et warning émis ; avec Redis, clés visibles ; TTL respecté.
- P2-9 (STORY-172) : `/metrics` expose au minimum latence endpoints, taux d'erreur, déploiements ok/ko ; dashboards provisionnés affichent des données sur un run de démo.
- P2-11 (STORY-173) : `browse` paginé filtrable ; `prune` (images/volumes/conteneurs stoppés) protégé RBAC + audit + dry-run.
- P2-12 + P2-13 (STORY-174) : le chemin de déploiement existant passe par l'adapter (test de non-régression complet) ; interface documentée spec 02 ; recreate avec secret env → aperçu masqué ; échec de recreate → retour à l'état antérieur.

**Garde-fous** (plan §2.G) : scan de cibles (~20 parseurs, profils d'accès) branché sur Host sans casser les payloads ; module Docker (aucune suppression d'endpoint) ; WebSocket modulaire étendu sans casser l'architecture plugins ; stack definitions + Jinja2 (ne toucher qu'aux bornes B9) ; recovery orchestrateur conservé ; registre plugins = base saine pour les plugins réels ; middlewares sécurité non régressés.

## Liste des Stories liées

- [x] STORY-160.1 : Modèle ScheduledTask spec 17, registre d'actions et API `/schedules` v2 (P2-1, partie définition — STORY-160 découpée)
- [x] STORY-160.2 : Moteur runtime asyncio — boucle lifespan, verrous, timeout, orphelins, fuseaux IANA, contrat `ExecutionStore` (P2-1, partie moteur — STORY-160 découpée)
- [x] STORY-160.3 : Actions core réelles et triggers événement (P2-1, partie exécution — STORY-160 découpée)
- [x] STORY-161 : Table `scheduled_task_executions` — historique des exécutions, endpoints de consultation, rétention (P2-1, partie traçabilité)
- [x] STORY-162 : Bus d'événements canonique — interface unique, nomenclature spec, in-memory + Redis Pub/Sub optionnel (P2-2, partie bus — F6)
- [x] STORY-163 : Consommateurs plugins du bus — hooks `@on_event`, `deployment_notifications` enregistré, `DEPLOYMENT_PROGRESS` émis (P2-2, partie consommateurs)
- [x] STORY-164.1 : Mécaniques de protocole serveur — heartbeats avec expiration des connexions muettes + acknowledgment des messages critiques (P2-5, partie protocole — STORY-164 découpée)
- [x] STORY-164.2 : Canaux WebSocket manquants — `/ws/ssh/{host}` TOFU STRICT, `/ws/journal/{host}`, `/ws/batch/{batch_id}` émetteur-ready, VNC reporté documenté (P2-5, partie canaux — STORY-164 découpée)
- [x] STORY-164.3 : Reconnexion unifiée avec jitter + resynchronisation d'état + client type documenté (P2-5, partie client — STORY-164 découpée)
- [x] STORY-165 : Tests WebSocket — couverture complète du module temps réel (P2-5/P2-14, partie tests)
- [ ] STORY-166 : Migration `Target`→`Host` + axe `origin` + `environments` + `Stack.git_url` + auto-détection du host local (P2-4 + P2-10 — F4 étape 2)
- [ ] STORY-167 : `deployment_events` structurés — table dédiée, migration des données, endpoint paginé, rétention (P2-7)
- [ ] STORY-168 : Cache avec fallback mémoire — interface unique + TTL, Redis sinon mémoire locale (P2-8)
- [ ] STORY-169 : Plugins — installation réelle — download, checksum SHA-256, extraction, compose up, rollback (P2-3, partie installation)
- [ ] STORY-170 : Plugins — routes API dynamiques + gates pre-deploy (approve/deny, timeout, Trivy) (P2-3, partie extension)
- [ ] STORY-171 : Unification de la validation des stacks + bornes numériques `min/max` (P2-6)
- [ ] STORY-172 : Observabilité Prometheus réelle — `/metrics`, métriques business, dashboards alimentés (P2-9)
- [ ] STORY-173 : `/compute` élargi — `browse` paginé et `prune` protégé, rapprochement `/compute`↔`/docker` (P2-11 — F3)
- [ ] STORY-174 : Socle `WorkloadAdapter` + adapter Docker + recreate sécurisé (P2-12 + P2-13 — F7)

## Notes de conception

- **Plage de numéros réservée** : STORY-160 à STORY-199 (seules 160-174 sont affectées ; 175-199 disponibles pour sous-découpes — ex. STORY-166/169 XL et STORY-162/164/170/174 L — et pour la matérialisation éventuelle de P2-15, cf. traçabilité ci-dessus).
- ✂️ **STORY-160 découpée (2026-10-21)** : `split-story` proactif post-analyse (complexité XL — 4 domaines peu couplés) → **STORY-160.1** (modèle spec 17 + registre d'actions + API `/schedules` v2), **STORY-160.2** (moteur runtime asyncio), **STORY-160.3** (actions core + triggers événement), suffixes `.1/.2/.3` pattern STORY-131 ; la mère est `ABANDONED` ([STORY-160](../stories/STORY-160-moteur-scheduler-asyncio.md)) et le critère de done « P2-1 (STORY-160/161) » se vérifie désormais sur 160.1→160.3 + 161.
- ✂️ **STORY-164 découpée (2026-10-23)** : `split-story` proactif post-analyse (complexité L — ~10 tâches hétérogènes sur 3 périmètres indépendants) → **STORY-164.1** (protocole serveur : expiration heartbeat ~2 intervalles + ack TTL/re-diffusion), **STORY-164.2** (canaux `/ws/ssh`/`journal`/`batch` + VNC reporté documenté), **STORY-164.3** (reconnexion unifiée jitter + client type documenté), suffixes `.1/.2/.3` pattern STORY-160/131 ; la mère est `ABANDONED` ([STORY-164](../stories/STORY-164-canaux-websocket-manquants-durcissement.md)) et le critère de done « P2-5 » se vérifie désormais sur 164.1→164.3 + 165 ; inter-dépendances : 164.2 → 164.1 (helper expiration, recommandé), 164.3 → 164.1 (documentaire).
- ✅ **STORY-165 DONE (2026-10-24)** — statut dérivé vérifié à la clôture : 9 stories restent ouvertes (STORY-166, 167, 168, 169, 170, 171, 172, 173, 174 — toutes TODO) → l'epic reste **IN_PROGRESS** conformément à la règle de statut dérivé ; les 5 bugs détectés par la story (BUG-005→009) sont en BACKLOG.
- Source principale : [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 « Vague P2 », axes A8, A9, A14, A15, A16/F3, B4, B5, B7, B8, B9, C3-C11, C13, C14, D1-D5, F4 (étape 2), F6, F7.
- Arbitrages concernés : **F4** (modèle directeur phasé — étape 2 ici ; `Apps`/`Machines`/`Clusters` = Roadmap Phase 2, noté dans STORY-166), **F6** (bus — interface + 2 implémentations, STORY-162), **F3** (incorporation HORS SPEC, STORY-166/173), **F1** (purge Celery déjà traitée en STORY-130.2 — le scheduler assume asyncio, STORY-160), **F7** (WorkloadAdapter, STORY-174).
- Hors périmètre explicitement rappelé dans les stories : console VNC et canal `batch` lié aux Machines (Roadmap VMs — `/ws/batch` livré car lié aux opérations groupées Apps), check-updates et graph complet (Roadmap Phase 5), GitOps (plugin Git), Redis Streams replay, adapters K8s/VM, étape 3 du modèle directeur.
- Risque §7.2 : les zones à zéro test doivent être couvertes **au fil des vagues** (STORY-165 coordonnée avec 164, STORY-161 avec 160, STORY-173 pour compute), pas en fin de projet.
- Risque §7.3 : STORY-169 (plugins réels) introduit de la surface d'attaque — checksum obligatoire, sandboxing documenté, audit branché avant (STORY-125) ; STORY-162 (nomenclature) touche les consommateurs — période d'émission double pour le frontend.
- Corrections de cohérence appliquées à cette édition (signalées phase 3/4) : dépendance WS durci « STORY-128 (ssh_keys) » → **STORY-131** ; dépendances compute « STORY-124/125 (enveloppes/pagination) » → **STORY-126/128** ; « audit branché (STORY-123) » → **STORY-125**.
- Les corrections consolidées de specs (nomenclature événements, annotation phasage modèle 06, incorporation F3 dans 09…) sont portées par STORY-252 (P3-4, EPIC-014) conformément à la répartition du plan.

## Critères de succès (Definition of Done)

- [ ] Les 15 stories P2 sont DONE avec leurs critères de done vérifiables validés (tests passants).
- [ ] Le scheduler exécute réellement les tâches planifiées (cron + événement) avec verrous, fuseaux IANA et reprise après redémarrage ; exécutions persistées et purgeables.
- [ ] La nomenclature d'événements spec est respectée par tous les émetteurs, avec table de correspondance documentée et consommateurs plugins actifs.
- [ ] L'installation d'un plugin effectue download + checksum + hooks + compose avec rollback vérifié ; routes dynamiques OpenAPI et gates pre-deploy opérationnelles.
- [ ] Le modèle `Host` + axe `origin` est en place avec migration de données sans perte, double nommage API déprécié, environments activés et host local auto-détecté.
- [ ] Le module WebSocket est testé (suite WS dédiée) et durci (heartbeat expiration, ack, reconnexion unifiée) avec les canaux ssh/journal/batch.
- [ ] L'observabilité est réelle : `/metrics` instrumenté, dashboards Grafana alimentés.
- [ ] Le chemin de déploiement existant passe par `DockerWorkloadAdapter` sans régression, avec recreate sécurisé (rebase, rollback, secrets masqués).
- [ ] Couverture ≥ 80 % par domaine sur les modules touchés (zones anciennement zéro comprises).
