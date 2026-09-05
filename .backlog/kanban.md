# KANBAN BOARD

## 📋 BACKLOG

### EPIC-011 : P0 — Sécurité bloquante (remédiation backend)
- [ ] STORY-104 : Protection brute-force du login — compteur par username, blocage temporaire (P0-5)

### EPIC-012 : P1 — Socle structurant (remédiation backend)
- [ ] STORY-120 : Alembic — baseline du schéma existant et `upgrade head` au démarrage à la place de `create_all` (P1-1)
- [ ] STORY-121 : Modèle `user_organizations` — association utilisateur ↔ organisation avec rôle (P1-2, partie modèle)
- [ ] STORY-122 : Dépendances RBAC `require_role(...)` — hiérarchie, cache TTL 300 s et protections d'escalade sur les ~110 endpoints (P1-2, application)
- [ ] STORY-123 : Refresh tokens révocables — table, rotation et logout invalidant (P1-3, partie refresh)
- [ ] STORY-124 : Clés API `wf_ak_` — table `api_keys`, auth `X-API-Key` coexistant avec JWT (P1-3, partie clés API)
- [ ] STORY-125 : Audit trail — table `audit_logs`, émission sur actions critiques, `GET /admin/audit`, rétention (P1-4)
- [ ] STORY-126 : Enveloppes de réponse API — `APIResponse` / `PaginatedResponse` / erreur `{error:{code,message}}` (P1-5)
- [ ] STORY-127 : Hiérarchie d'exceptions — compléter `core/exceptions.py` et remplacer les `HTTPException` brutes (P1-5, partie exceptions)
- [ ] STORY-128 : Pagination généralisée — `?page&per_page` sur toutes les listes non paginées (P1-6)
- [ ] STORY-129 : Endpoints santé & mot de passe — `GET /system/ready` sans auth et `PUT /auth/password` (P1-7 + P1-8)
- [ ] STORY-130 : Purge Celery + arbitrage Argon2 — suppression du double runtime fantôme et migration Argon2id (P1-10 + P1-11)
- [ ] STORY-131 : SSH réutilisables + empreintes hôtes + anti-MITM TOFU (P1-9)

### EPIC-013 : P2 — Conformité fonctionnelle (remédiation backend)
- [ ] STORY-160 : Moteur d'exécution du scheduler — boucle asyncio, registre d'actions, triggers cron/événement, verrous, fuseaux IANA (P2-1, partie moteur)
- [ ] STORY-161 : Table `scheduled_task_executions` — historique des exécutions, endpoints de consultation, rétention (P2-1, partie traçabilité)
- [ ] STORY-162 : Bus d'événements canonique — interface unique, nomenclature spec, in-memory + Redis Pub/Sub optionnel (P2-2, partie bus — F6)
- [ ] STORY-163 : Consommateurs plugins du bus — hooks `@on_event`, `deployment_notifications` enregistré, `DEPLOYMENT_PROGRESS` émis (P2-2, partie consommateurs)
- [ ] STORY-164 : Canaux WebSocket manquants + durcissement — `/ws/ssh`, `/ws/journal`, `/ws/batch`, heartbeats, ack, reconnexion (P2-5, partie durcissement)
- [ ] STORY-165 : Tests WebSocket — couverture complète du module temps réel (P2-5/P2-14, partie tests)
- [ ] STORY-166 : Migration `Target`→`Host` + axe `origin` + `environments` + `Stack.git_url` + auto-détection du host local (P2-4 + P2-10 — F4 étape 2)
- [ ] STORY-167 : `deployment_events` structurés — table dédiée, migration des données, endpoint paginé, rétention (P2-7)
- [ ] STORY-168 : Cache avec fallback mémoire — interface unique + TTL, Redis sinon mémoire locale (P2-8)
- [ ] STORY-169 : Plugins — installation réelle — download, checksum SHA-256, extraction, compose up, rollback (P2-3, partie installation)
- [ ] STORY-170 : Plugins — routes API dynamiques + gates pre-deploy (approve/deny, timeout, Trivy) (P2-3, partie extension)
- [ ] STORY-171 : Unification de la validation des stacks + bornes numériques `min/max` (P2-6)
- [ ] STORY-172 : Observabilité Prometheus réelle — `/metrics`, métriques business, dashboards alimentés (P2-9)
- [ ] STORY-173 : `/compute` élargi — `browse` paginé et `prune` protégé, rapprochement `/compute`↔`/docker` (P2-11 — F3)
- [ ] STORY-174 : Socle `WorkloadAdapter` + adapter Docker + recreate sécurisé (P2-12 + P2-13 — F7)

### EPIC-014 : P3 — Finitions & purge (remédiation backend)
- [ ] STORY-250 : Purge du code mort et résidus + dépréciation `/auth/me` — permissions legacy, croniter conditionnel, abstractions, stub workflows, litellm orphelin, print debug, HealthCheck (P3-1 + P3-3)
- [ ] STORY-251 : CircuitBreaker — câbler sur les appels externes ou supprimer le module (P3-2)
- [ ] STORY-252 : Corrections consolidées des spécifications — arbitrages F1-F6 appliqués aux specs (P3-4)
- [ ] STORY-253 : Mise à jour documentaire post-remédiation — `backend_status.md`, rules `.roo`, CHANGELOG (P3-5)
- [ ] STORY-254 : Revue finale de conformité — audit specs ↔ code et tableau de conformité final (clôture du plan)

### EPIC-015 : Compute — Clusters Kubernetes & Apps cluster-scoped

## 🏗️ IN PROGRESS

_(vide)_

## 🚫 BLOCKED

_(vide)_

## 🚧 REVIEW

_(vide)_

## ✅ DONE

- [x] STORY-103 : SecretManager AES/Fernet — chiffrement au repos des credentials cibles et env vars de stacks (P0-4)
- [x] STORY-103.1 : SecretManager Fernet — socle config, dépendance et classe core (P0-4a)
- [x] STORY-103.2 : Chiffrement de Target.credentials + migration double lecture (P0-4b)
- [x] STORY-103.3 : Env vars stacks — chiffrement au repos et masquage API (P0-4c)
- [x] STORY-103.4 : Validation finale — 0 credential lisible, non-régression, couverture (P0-4d)
- [x] STORY-100 : Auth WebSocket obligatoire — refus des connexions sans token valide sur les 5 canaux (P0-1)
- [x] STORY-101 : Garde-fou de démarrage — refus des secrets dev par défaut en production (P0-2)
- [x] STORY-102 : Rate limiting effectif sans Redis — fallback mémoire + warning (P0-3)

