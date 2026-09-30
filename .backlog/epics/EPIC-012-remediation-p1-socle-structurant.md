# EPIC-012 : P1 — Socle structurant (remédiation backend)

**Statut :** IN_PROGRESS
**Priorité :** Haute

## Vision

Poser le socle technique structurant sans lequel aucune extension du backend n'est possible : migrations Alembic, RBAC 4 rôles, refresh tokens révocables et clés API, audit trail, enveloppes API et hiérarchie d'exceptions, pagination généralisée, endpoint de readiness, SSH keys avec empreintes, arbitrage Argon2, et purge du double runtime Celery fantôme. Cette vague P1 du plan de remédiation ([`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4) conditionne toutes les vagues suivantes.

Spécifications de référence : [`07-authentification.md`](../../docs/general_specs/07-authentification.md), [`08-rbac-permissions.md`](../../docs/general_specs/08-rbac-permissions.md), [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md), [`09-api.md`](../../docs/general_specs/09-api.md), [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md).

## Description

Chaque item P1 du plan de remédiation devient une story (certains items XL/L sont découpés en 2 stories — modèle puis application — pour isoler les migrations et faciliter l'analyse) :

| Story | Item plan | Objectif | Ampleur |
|-------|-----------|----------|---------|
| STORY-120 | P1-1 (A1) | Alembic : init, baseline du schéma existant (10 modèles), `upgrade head` au démarrage/install à la place de `create_all` nu | M |
| STORY-121 | P1-2 partie modèle (A2) | RBAC — **modèle** : table `user_organizations.role` (viewer/operator/admin, Super_Admin sur `User.is_superadmin`), migration des données (FK org direct → association, mapping non cassant) | M |
| STORY-122 | P1-2 application (A2, B15) | RBAC — **application** : `require_role(...)` + hiérarchie + cache TTL 300 s + protections d'escalade (dernier superadmin, non-promotion) sur les ~110 endpoints | XL |
| STORY-123 | P1-3 partie refresh (A4, B6) | Refresh tokens révocables : table `refresh_tokens` (opaque hashé), rotation, logout invalide, révocation globale par user | M |
| STORY-124 | P1-3 partie clés API (A5) | Clés API `wf_ak_` : table `api_keys` (hash bcrypt), génération/révocation, header `X-API-Key` coexistant avec JWT (RBAC s'applique) | M |
| STORY-125 | P1-4 (A3) | Audit trail : table `audit_logs` (qui/quoi/quand/cible/correlation_id), émission sur actions critiques, `GET /admin/audit` paginé filtrable, rétention configurable | M |
| STORY-126 | P1-5 partie enveloppes (A10) | Enveloppes API `{data,message}` / `{data,pagination}` / `{error:{code,message}}` sur tous les routers — ⚠️ breaking change, clients frontend/CLI synchronisés dans le même lot, à merger tôt | L |
| STORY-127 | P1-5 partie exceptions (A11) | Hiérarchie d'exceptions `WindFlowException` → NotFound/Conflict/Validation/PermissionDenied/Authentication… ; remplacement des `HTTPException` brutes ; handler global → enveloppe erreur | M |
| STORY-128 | P1-6 (C1) | Pagination généralisée `?page&per_page` : stacks, organizations, schedules, plugins, plugin_registry, targets… + harmonisation `pagination{}` | M |
| STORY-129 | P1-7 + P1-8 (A12, A13) | `GET /system/ready` sans auth (migrations + DB + dépendances optionnelles, 503 si non-prêt) + formalisation `/system/health` ; `PUT /auth/password` (ancien requis, hash mis à jour, refresh révoqués) | S |
| STORY-130 | P1-10 + P1-11 (F2, F1, E10) | Migration hash Argon2id via upgrade au login (spec 07 corrigée consolidément en STORY-252/P3-4) + purge Celery : `celery_app.py`, `Dockerfile.worker`, cibles Makefile — arbitrages F1/F2 validés | S+S |
| STORY-131 | P1-9 (A7) | SSH réutilisables + empreintes hôtes + anti-MITM (TOFU + écran de confirmation) ; credentials cibles passent par `ssh_keys` chiffrées (via STORY-103) | L |

**Dépendances internes** (plan §4-§5, cf. sections Dépendances de chaque story) :
- STORY-121, STORY-123, STORY-124, STORY-125, STORY-131 dépendent de STORY-120 (Alembic avant toute migration de modèle).
- STORY-122 dépend de STORY-121 (modèle des rôles) ; STORY-124 et STORY-125 s'appuient sur STORY-122 pour la protection des endpoints.
- STORY-123 dépend de STORY-120 ; STORY-129 dépend de STORY-120 (check migrations) + STORY-123 (révocation des refresh).
- STORY-128 dépend de STORY-126 (format `pagination{}`) ; STORY-127 est coordonnée avec STORY-126 (handler global → enveloppe erreur).
- STORY-131 dépend de STORY-120 + STORY-103 (EPIC-011, SecretManager avant ssh_keys).
- STORY-126 doit être mergée tôt pour éviter les conflits (breaking change consommateur : synchroniser frontend/CLI dans le même lot).
- Chaîne critique : Alembic (STORY-120) → RBAC (STORY-121+122) → modèle Hosts (P2) et `/compute` élargi (P2).

**Critères de done (reprends fidèlement le plan)** :
- P1-1 : base existante → `alembic stamp baseline` puis démarrage sans diff ; base vierge → création complète par migrations uniquement ; CI exécute les migrations.
- P1-2 : matrice rôle×endpoint représentative (viewer 403 sur DELETE `/docker/containers/{id}`, operator 200…) ; dernier superadmin non-démotable ; cache TTL vérifié. Mapping non cassant : superuser→Super_Admin, autres→Operator.
- P1-3 : refresh révoqué → 401 ; logout → refresh suivant refusé ; clé `wf_ak_...` authentifie ; révocation immédiate ; hash bcrypt en base (jamais la clé).
- P1-4 : DELETE stack → ligne d'audit avec user, org, action, cible, correlation_id ; rétention configurable appliquée.
- P1-5 : tous les endpoints au format enveloppe (test de contrat sur échantillon par router) ; 409 sur conflit (ex. slug org dupliqué) ; OpenAPI exemples mis à jour.
- P1-6 : chaque liste expose `pagination{page,per_page,total}` ; bornes per_page (max 100) ; defaults documentés OpenAPI.
- P1-7 : `/ready` vérifie migrations appliquées + DB + dépendances optionnelles ; sans auth ; 503 si non-prêt.
- P1-8 : 200 avec ancien mdp correct, 400 si faux, refresh tokens révoqués après changement.
- P1-9 : fingerprint inconnu → déploiement bloqué + événement de confirmation ; clé réutilisée sur N cibles ; flux `commands.py` inchangé côté appelants.
- P1-10 : login d'un utilisateur bcrypt → hash re-haché Argon2id en base après login ; aucun reset requis ; spec 07 corrigée (consolidée en STORY-252).
- P1-11 : plus aucune référence Celery dans code/CI/docs ; `make docker-build-worker` retiré ; specs et rules mises à jour (specs 04/05 consolidées en STORY-252).

**Garde-fous** (plan §2.G) : module Docker (aucune suppression d'endpoint — RBAC et enveloppes par-dessus), OpenAPI multi-interfaces maintenu à jour lors du changement de contrat, login username/email + register non régressé.

## Liste des Stories liées

- [x] STORY-120 : Alembic — baseline du schéma existant et `upgrade head` au démarrage à la place de `create_all` (P1-1)
- [x] STORY-121 : Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)
- [x] STORY-122 : Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application) — via STORY-122.1 → 122.7
- [x] STORY-123 : Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)
- [x] STORY-124 : Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)
- [x] STORY-125.1 : Socle audit trail — modèle, migration, config, schemas et service (P1-4 — STORY-125 découpée)
- [x] STORY-125.2 : Émission d'audit sur les actions critiques (P1-4 — STORY-125 découpée)
- [x] STORY-125.3 : Endpoint admin `GET /admin/audit`, purge lifespan et rétention (P1-4 — STORY-125 découpée)
- [x] STORY-126.1 : Socle enveloppes API — schémas spec 09, middleware/handlers derrière `api_envelope_enabled=False` (P1-5 — STORY-126 découpée)
- [x] STORY-126.2 : Activation des enveloppes — défaut `True`, adaptation suite backend, tests de contrat par router (P1-5 — STORY-126 découpée)
- [x] STORY-126.3 : Synchronisation des clients — frontend unwrap `data`, CLI, CHANGELOG versionné (P1-5 — STORY-126 découpée)
- [x] STORY-127 : Hiérarchie d'exceptions — compléter `core/exceptions.py` et remplacer les `HTTPException` brutes (P1-5, partie exceptions)
- [ ] STORY-128 : Pagination généralisée — `?page&per_page` sur toutes les listes non paginées (P1-6)
- [ ] STORY-129 : Endpoints santé & mot de passe — `GET /system/ready` sans auth et `PUT /auth/password` (P1-7 + P1-8)
- [ ] STORY-130 : Purge Celery + arbitrage Argon2 — suppression du double runtime fantôme et migration Argon2id (P1-10 + P1-11)
- [ ] STORY-131 : SSH réutilisables + empreintes hôtes + anti-MITM TOFU (P1-9)

## Notes de conception

- **Plage de numéros réservée** : STORY-120 à STORY-159 (seules 120-131 sont affectées ; 132-159 disponibles pour sous-découpes, ex. STORY-122 XL sur ~110 endpoints et STORY-126/131 L).
- Source principale : [`docs/backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 « Vague P1 », axes A1-A5, A7, A10-A13, B6/B15, C1, E10/F1/F2.
- Règle de dépendance du plan : **Alembic avant toute migration de modèle ; RBAC avant ouverture de nouveaux endpoints ; SecretManager (STORY-103, EPIC-011) avant ssh_keys**.
- Arbitrages validés par l'utilisateur avant exécution (plan §7.4) : F1 (abandon Celery → STORY-130), F2 (Argon2 → STORY-130), P1-5 enveloppes (breaking change → STORY-126, coordination frontend/CLI requise).
- STORY-122 (application RBAC) est l'item le plus invasif : découpage impératif par router avec la matrice de rôles spec 08 comme critère d'acceptation (risque §7.3).
- La cible de couverture 95 % sur chemins critiques (auth/déploiement/RBAC — rules 35) devient réaliste après STORY-122.
- ✅ **Référence croisée vérifiée (audit phase 5)** : STORY-164 (WS durci) cite bien **STORY-131** (ssh_keys) — la correction annoncée ci-contre dans les éditions précédentes a été appliquée dans [`.backlog/epics/EPIC-013-remediation-p2-conformite-fonctionnelle.md`](EPIC-013-remediation-p2-conformite-fonctionnelle.md) (notes de conception) et dans STORY-164.
- Les corrections consolidées de specs (04/05 pour Celery, 07 pour Argon2, F5 JWT) sont portées par STORY-252 (P3-4, EPIC-014) conformément à la répartition du plan ; STORY-130 documente l'upgrade path et renvoie à STORY-252.

## Critères de succès (Definition of Done)

- [ ] Les 12 stories P1 sont DONE avec leurs critères de done vérifiables validés (tests passants).
- [ ] Plus aucun `create_all` nu : le schéma est géré exclusivement par migrations Alembic (baseline + CI).
- [ ] Les ~110 endpoints existants sont protégés par `require_role(...)` selon la matrice spec 08.
- [ ] Logout et révocation effectifs (refresh tokens + clés API).
- [ ] Actions critiques tracées dans `audit_logs` avec correlation_id.
- [ ] Contrat API stable : enveloppes, pagination, 409, OpenAPI à jour — base prête pour les vagues P2/P3.
- [ ] Compatibilité des installations existantes préservée (mapping RBAC non cassant, baseline Alembic).
- [ ] Couverture de tests ≥ 80 % sur les modules touchés, viser 95 % sur auth/RBAC.
