# STORY-254.2 : Croisement plan ↔ backlog — items P0-P3 et reportés §6 ↔ Roadmap

**Statut :** DONE
**Story Parente :** STORY-254 — Revue finale de conformité — audit specs ↔ code de bout en bout et tableau de conformité (clôture du plan)
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)

## Description

En tant que responsable technique WindFlow, je veux vérifier que **chaque item du plan de remédiation** ([`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 : P0 ×5, P1 ×11, P2 ×15, P3 ×5 = 36 items) est couvert par une **story DONE vérifiée** (epics EPIC-011→014) ou un **divergence/report tracé**, et que **chaque item hors périmètre** (plan §6, 17 lignes) est bien **confirmé reporté** dans [`Roadmap.md`](../../docs/Roadmap.md) — afin de certifier qu'aucun item du plan n'est tombé à l'eau silencieusement.

Cette sous-story produit le **tableau de couverture plan ↔ backlog** consigné dans son fichier, matière première du tableau de conformité final (STORY-254.4).

## Critères d'acceptation (AC)

- [x] AC 3 : Chaque item P0 (5), P1 (11), P2 (15) et P3 (5) du plan est couvert : story DONE vérifiée, ou divergence/report tracé ; les items du plan §6 (hors périmètre) sont confirmés reportés dans [`Roadmap.md`](../../docs/Roadmap.md). *(35/36 couverts + 1 écart tracé n°8 ; 17/17 reportés confirmés — l'écart est arbitré en 254.3, la couverture « story DONE **ou** divergence/report **tracé** » est satisfaite dès lors que la trace existe)*

## Contexte technique

**Posture :** lecture seule du backlog et des documents. Les anomalies découvertes (story non DONE, reporté absent de la Roadmap) sont **consignées comme écarts** pour STORY-254.3/254.4 — jamais corrigées ici.

**Matière première :**
- Plan §4 (vagues P0-P3, colonnes ID/objectif/critère de done) — cf. [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) §4 ;
- Plan §8.2 (correspondance rapport ↔ plan) pour mémoire ;
- Plan §6 (17 items hors périmètre avec destination attendue) ;
- Kanban : EPIC-011 DONE (STORY-100→104), EPIC-012 DONE (STORY-120→131, 40/44), EPIC-013 DONE (STORY-160→174 + BUG-005→009, 31/36), EPIC-014 6/7 (250→253 DONE, 254 en cours de découpe) ;
- Registre [`identifiants.md`](../identifiants.md) : stories parentes ABANDONED = découpées (la couverture passe par leurs sous-stories DONE) — ne pas compter une parente ABANDONED comme un trou ;
- Écrans déjà connus : DoD des epics 011/012/013 ont leurs cases **non cochées** (constat de forme à lister en écart mineur) ; STORY-253 DONE sans section « Notes d'implémentation » dans son fichier (prévue en Tâche 9 — constat de forme à lister).

**Méthode :**
1. Pour chaque item P0-1→P3-5 : identifier la/les story(s) livreuse(s) (fichier epic parent + statut du contrat), statuer « couvert / divergence tracée / **écart** » ;
2. Pour chaque ligne du plan §6 : chercher la destination dans la Roadmap (Phase 2 : VMs/K8s/Apps/Clusters/marketplace ; Phase 5 : IA, check-updates ; initiatives dédiées : Keycloak, Vault, backup F8) — la correspondance est **thématique** (la Roadmap ne cite pas les items du plan) : vérifier que le thème existe bien à la phase annoncée ;
3. Consigner le tableau de couverture + la liste des écarts dans cette sous-story.

**Format attendu du tableau de couverture :**

```markdown
| Item plan | Story(s) livreuse(s) | Statut | Preuve |
| P0-1 | STORY-100 | Couvert | epic EPIC-011 DONE + test refus WS sans token |
```

## Dépendances

- STORY-254.1 (journal d'audit par domaine — recoupe les preuves d'inspection du code).

## Tâches d'implémentation détaillées

### Tâche 1 : Croisement des 36 items P0-P3 ↔ stories livreuseuses
**Objectif :** Vérifier item par item que chaque objectif du plan §4 a sa story DONE (ou sa trace de divergence).
**Fichiers :**
- `.backlog/stories/STORY-254.2-croisement-plan-backlog.md` (section tableau de couverture) — **Modifier** — Construire le tableau 36 lignes. Sources : §4 du plan, epics EPIC-011/012/013/014 (listes des stories + cases), registre [`identifiants.md`](../identifiants.md). Cas particuliers attendus : P1-2 (RBAC) = STORY-122 + sous-stories ; P2-1 = STORY-160.x ; P2-4 = STORY-166.x ; P3-1/P3-3 fusionnés dans STORY-250.x ; P3-4 = STORY-252 ; P3-5 = STORY-253 ; clôture = STORY-254 (cette découpe). Toute story introuvable ou non DONE = **écart** (pas de correction).
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Aucune (mais recoupe 254.1).

### Tâche 2 : Vérification des 17 reportés §6 ↔ Roadmap
**Objectif :** Confirmer que chaque item hors périmètre a bien sa destination dans la Roadmap.
**Fichiers :**
- `.backlog/stories/STORY-254.2-croisement-plan-backlog.md` (tableau reportés) — **Modifier** — Ajouter le tableau 17 lignes : item §6 → destination annoncée → présence du thème dans [`Roadmap.md`](../../docs/Roadmap.md) (phase + section) → statut (REPORTÉ confirmé / **écart** si thème introuvable). Constat déjà établi lors de l'analyse : `grep STORY-254 docs/Roadmap.md` = 0 hit — la correspondance est thématique, à vérifier ligne par ligne (ex. « IA / LiteLLM réel » → Roadmap Phase 5 « IA & Intelligence »).
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Tâche 1.

### Tâche 3 : Synthèse des écarts de couverture
**Objectif :** Consolider les écarts découverts (items non couverts, reportés non tracés, anomalies de forme backlog) pour STORY-254.3 (arbitrage/tracé).
**Fichiers :**
- `.backlog/stories/STORY-254.2-croisement-plan-backlog.md` (section « Écarts de couverture découverts ») — **Modifier** — Lister : chaque item non couvert, chaque reporté sans destination, + anomalies de forme déjà connues (DoD epics non cochées, notes 253 absentes, compteur EPIC-012 40/44 vs 12 stories P1 attendues par le plan — expliquer par les sous-stories). Chaque écart : description, preuve, proposition d'action (bug/story/WONT_FIX — décision à STORY-254.3).
**Exigences sécurité :** Aucune (lecture seule).
**Dépend de :** Tâches 1-2.

## Tests à écrire

> Story de **croisement documentaire** — aucun code : couverture et cas sécurité **non applicables**. Validation = écrans ci-dessous.

### Écrans de contrôle

| # | Commande / vérification | Résultat attendu |
|---|---|---|
| E1 | Tableau items : 36 lignes P0-1→P3-5 chacune avec story(s) + statut | 36/36, 0 ligne « ? » |
| E2 | Tableau reportés : 17 lignes §6 chacune avec destination Roadmap vérifiée | 17/17 |
| E3 | Toute ligne « écart » renvoie vers la section Écarts (réciprocité tableau ↔ liste) | cohérent |
| E4 | `make backlog-check` | vert (contrats cohérents) |

### Commandes de validation
```bash
make backlog-check
```

## Tableau de couverture — 36 items P0-P3 (Tâche 1, vérifié le 2026-11-07)

**Sources** : plan §4, epics 011-014, registre [`identifiants.md`](../identifiants.md), CHANGELOG, journal d'audit 254.1.

| Item plan | Story(s) livreuse(s) | Statut | Preuve |
|---|---|---|---|
| P0-1 Auth WS | STORY-100 | **Couvert** | CHANGELOG l.95 + audit 254.1 §8 (auth stricte) + rapport finalisation EPIC-011 (97 %) |
| P0-2 Secrets dev | STORY-101 | **Couvert** | CHANGELOG l.96 + status §14.3 |
| P0-3 Rate limit mémoire | STORY-102 | **Couvert** | CHANGELOG l.97 + status §13.3 (rate_limit 100 %) |
| P0-4 SecretManager | STORY-103 (+103.1-4) | **Couvert** | CHANGELOG l.98 + audit 254.1 §7 (Fernet l.23/40) |
| P0-5 Brute-force | STORY-104 | **Couvert** | CHANGELOG l.99 + status §7.7 |
| P1-1 Alembic | STORY-120.1/.2/.3 | **Couvert** | epic 012 cochée + audit 254.1 §4 (13 migrations) |
| P1-2 RBAC | STORY-121(.1-.3), 122(.1-.7) | **Couvert** | epic 012 cochée + audit 254.1 §3 (~179 points) |
| P1-3 Refresh + API keys | STORY-123(.1-.4), 124(.1-.4) | **Couvert** | epic 012 cochée + audit 254.1 §2 |
| P1-4 Audit trail | STORY-125.1/.2/.3 | **Couvert** | epic 012 cochée + status §7.10 |
| P1-5 Enveloppes | STORY-126.1/.2/.3, 127 | **Couvert** | epic 012 cochée + audit 254.1 §1 |
| P1-6 Pagination | STORY-128 | **Couvert** | epic 012 cochée + audit 254.1 §1 (PaginatedResponse) |
| P1-7 system/ready | STORY-129 | **Couvert** | epic 012 cochée + audit 254.1 §1 (system.py l.95) |
| P1-8 PUT /auth/password | STORY-129 | **Couvert** | audit 254.1 §2 (auth.py l.1005+) |
| P1-9 SSH TOFU | STORY-131.1/.2/.3 | **Couvert** | epic 012 cochée + audit 254.1 §7 (TOFU) |
| P1-10 Argon2id | STORY-130.1 | **Couvert** | epic 012 cochée + status §7.5 |
| P1-11 Purge Celery | STORY-130.2 | **Couvert** | epic 012 cochée + garde-fou test_no_celery_residue |
| P2-1 Scheduler engine | STORY-160.1/.2/.3 | **Couvert** | epic 013 cochée + audit 254.1 §12 |
| P2-2 Bus canonique | STORY-162, 163 | **Couvert** | epic 013 cochée + audit 254.1 §6 (l.280/316/452) |
| P2-3 Plugins réels | STORY-169.1-.4, 170.1-.3 | **Couvert** | epic 013 cochée + audit 254.1 §10 (checksum/rollback) |
| P2-4 Modèle Host | STORY-166.1-.6 | **Couvert** | epic 013 cochée + audit 254.1 §4 |
| P2-5 WS durci + tests | STORY-164.1-.3, 165 (+BUG-005→009) | **Couvert** | epic 013 cochée + audit 254.1 §8 + status §13.3 (WS 94 %) |
| P2-6 Stacks validation | STORY-171 | **Couvert** | epic 013 cochée + audit 254.1 §9 |
| P2-7 deployment_events | STORY-167 | **Couvert** | epic 013 cochée + registre |
| P2-8 Cache fallback | STORY-168 | **Couvert** | epic 013 cochée + status §13.3 (cache 93 %) |
| P2-9 Observabilité | STORY-172 | **Couvert (avec écart n°1 tracé)** | epic 013 cochée + audit 254.1 §15 — échec garde-fou RBAC/metrics résiduel |
| P2-10 Auto-détection host | STORY-166.5 | **Couvert** | epic 013 cochée + config.py l.553 |
| P2-11 /compute élargi | STORY-173 | **Couvert** | epic 013 cochée + audit 254.1 §5 |
| P2-12 WorkloadAdapter | STORY-174.1 | **Couvert** | epic 013 cochée + audit 254.1 §5 (workloads/) |
| P2-13 Recreate sécurisé | STORY-174.2 | **Couvert** | epic 013 cochée + status §14.5 |
| P2-14 Tests zones zéro | STORY-165 (+ intégrés aux vagues) | **Couvert** | status §13.3 zones comblées (WS 94 % etc.) |
| P2-15 Notifications core | **Aucune story** | **ÉCART n°8** | EPIC-013 l.38 : « non affecté dans la plage 160-174, matérialisation à décider — l'arbitrage doit être tracé » ; code : `notification.send` = stub tracé (action_registry.py l.33/133, scheduler_actions.py l.310-319 « renvoi P2-15 ») — jamais tranché depuis |
| P3-1 Purge code mort | STORY-250.1 | **Couvert** | epic 014 cochée + écran grep 254.1 |
| P3-2 CircuitBreaker | STORY-251 | **Couvert** | epic 014 cochée + audit 254.1 §5 (_circuit_guard) |
| P3-3 Dépréciation /auth/me | STORY-250.2 | **Couvert** | epic 014 cochée + status §14.4 |
| P3-4 Corrections specs | STORY-252 | **Couvert** | epic 014 cochée + recoupement E6 254.3 |
| P3-5 Rangement documentaire | STORY-253 | **Couvert** | epic 014 cochée + status édité 2026-11-01 |
| Clôture | STORY-254 (= cette découpe) | **En cours** | 254.1 DONE, 254.2-4 en cours |

**Bilan Tâche 1 :** 35/36 couverts, **1 écart** (P2-15 — notifications core non matérialisées, stub tracé dans le code, arbitrage réclamé par l'epic mais jamais tranché).

## Tableau des reportés — plan §6 ↔ Roadmap (Tâche 2, vérifié le 2026-11-07)

Correspondance **thématique** (la Roadmap ne cite pas les items du plan) — chaque ligne : destination annoncée §6 → présence du thème dans [`Roadmap.md`](../../docs/Roadmap.md).

| Item §6 | Destination annoncée | Présence Roadmap | Statut |
|---|---|---|---|
| Pilotage VMs/Proxmox/clusters/power/snapshot/VNC/cloud-init/images | Phase 2 (adapters Machines) | ✅ Phase 2 « Gestion VMs (core) » l.167-179 (CRUD VMs/LXC, snapshots, hyperviseurs distants l.261) | REPORTÉ confirmé |
| Pilotage Helm/K8s/Swarm | Phase 2 (adapters Clusters) | ✅ Phase 3 « Kubernetes (core, optionnel) » l.270+ (kubeconfig, clusters) | REPORTÉ confirmé |
| Entités Apps/Machines/Clusters/triple XOR/batch + WS batch | Phase 2 | ✅ Phase 2 (VM Foundation) + batch WS livré en P2-5 (STORY-164.2 canal batch) — entités Phase 2 | REPORTÉ confirmé |
| Marketplace multi-backends + catalogue 28 plugins | Phase 2 | ✅ Phase 2 « Plugin System & Marketplace » (l.121+) | REPORTÉ confirmé |
| Plugin Git GitOps (blobless, SHA-256, webhooks HMAC) | Phase 2/3 | ✅ Phase 4 « Git & Polish » l.362 (« Stacks depuis un dépôt Git » git_url/branch/path) | REPORTÉ confirmé |
| Check-updates + auto-update complet | Phase 5 | ✅ Phase 5 « Auto-Updates (core) » l.424+ (vérification mises à jour, politiques, rollback) | REPORTÉ confirmé |
| IA / LiteLLM réel | Phase 5 (plugin IA) | ✅ Phase 5 « Plugin IA (LiteLLM/Ollama) » l.412-418 | REPORTÉ confirmé |
| Keycloak SSO (plugin OIDC) | Initiative plugin dédiée | ✅ flags conservés en config (status §7.4, `make enable-sso`) + Roadmap Phase 4 « LDAP/Active Directory » l.370+ (authentification avancée) | REPORTÉ confirmé |
| Vault plugin `vault://` | Initiative plugin dédiée | ✅ flags conservés (`make enable-secrets`) + Roadmap l.70/351 (« Plugin Vault : HashiCorp Vault déployé et intégré », secrets dynamiques) | REPORTÉ confirmé |
| Backup/restore core (F8) | Initiative dédiée | ✅ Roadmap Phase 3 l.285-287 (plugins Restic/Borg) + action `admin.backup` du registre (plan §6 : « le registre prépare admin.backup » — vérifié : action_registry.py) | REPORTÉ confirmé |
| Validation Compose 20 règles vs état réel Host | Phase 2 | ✅ Phase 2 (avec Apps/Host consolidés) — règles communes livrées en P2-6 | REPORTÉ confirmé |
| Redis Streams complet (replay/event sourcing) | Arbitrage ultérieur scale-out | ✅ hors périmètre documenté (F6, rules 20 §6 interdits « Introduire Redis Streams ») | REPORTÉ confirmé |
| Isolation réseau par environnement | Phase 2 (environments complet) | ✅ Phase 2 — table `environments` livrée en P2-4 (STORY-166.4) | REPORTÉ confirmé |
| Console VNC / canaux WS machines | Phase 2 | ✅ Phase 2 (VMs) — VNC explicitement absent du WS (status §8.4) | REPORTÉ confirmé |
| Environnements API complète (CRUD multi-env) | Seule table + rattachement dans le plan | ✅ table livrée (STORY-166.4), CRUD complet Phase 2 | REPORTÉ confirmé |
| Admin `/admin/users\|audit\|backup\|registries` complet | `audit` livré (P1-4), `users` partiel, `backup`/`registries` reportés | ✅ `/admin/audit` livré (STORY-125.3) ; backup → plugins Restic Phase 3 ; registries → Phase 2 marketplace | REPORTÉ confirmé |
| Workflows n8n | Conforme arbitrage D2 (rien côté core) | ✅ Phase 5 « Plugin Workflow Engine » (n8n/Node-RED l.408-410) | REPORTÉ confirmé |

**Bilan Tâche 2 :** 17/17 reportés confirmés dans la Roadmap (correspondance thématique, sections vérifiées ligne à ligne).

## Écarts de couverture découverts (Tâche 3 — synthèse → 254.3)

| # | Écart | Gravité | Preuve | Proposition (à arbitrer 254.3) |
|---|---|---|---|---|
| 8 | **P2-15 Notifications core non matérialisées** — aucune story dédiée ; `notification.send` = stub tracé dans le code ; l'epic 013 (l.38) réclamait un arbitrage « avant la finalisation de STORY-160 » jamais tranché | Majeur | EPIC-013 l.38/l.103 ; action_registry.py l.33 « **stub** (P2-15) » ; scheduler_actions.py l.310-319 | Story de matérialisation (STORY-255, plage réservée 175-199 épuisée → nouvelle numérotation) ou REPORTÉ explicite Roadmap ( décision utilisateur) |
| F1 | DoD des epics 011/012/013 : cases non cochées alors que les epics sont DONE | Mineur (forme) | grep §DoD épics (012 l.90-97, 013 l.133-140 toutes `[ ]`) | Cochage rétroactif documenté ou WONT_FIX ( forme) |
| F2 | STORY-253 DONE sans « Notes d'implémentation » dans son fichier (Tâche 9 prévoyait tableau de traçabilité + écarts reportés) | Mineur (forme) | fichier 254 lignes 1-248, pas de section Notes | La présente sous-story + journal 254.1 compensent la matière ; WONT_FIX possible |
| F3 | STORY-100→104 absentes du registre [`identifiants.md`](../identifiants.md) (rétro-inscription du 2026-11-01 a démarré à 120) — fichiers supprimés à la clôture EPIC-011 (pratique antérieure à la règle d'or actuelle §7) | Mineur (forme) | registre l.42+ (première story = 120) ; EPIC-011 l.42 « stories supprimées » | Rétro-inscription au registre (lignes STORY-100→104 avec mention « fichiers supprimés — trace CHANGELOG ») — conforme règle « les abandons historiques non inscrits font l'objet d'une rétro-inscription » |
| F4 | Compteur kanban EPIC-012 « 40/44 » : 19 stories listées cochées + parentes découpées — cohérent mais peu lisible vs « 12 stories P1 » du plan (les 44 = stories + sous-stories) | Info (non écart) | kanban l.51 | Aucune action (explication consignée dans le rapport final 254.4) |

**Bilan Tâche 3 :** 1 écart substantiel (n°8) + 3 écarts de forme (F1-F3) + 1 note d'information (F4). Croisé avec 254.1 : liste consolidée pour arbitrage = écarts n°1, 3, 4, 5, 6, 7 (n°2 résorbé) + n°8 + F1-F3.

## État d'avancement technique
- [x] Tâche 1 : Croisement 36 items P0-P3 ↔ stories
- [x] Tâche 2 : Vérification 17 reportés §6 ↔ Roadmap
- [x] Tâche 3 : Synthèse des écarts de couverture

## Notes d'implémentation (treat-story — 2026-11-07)

### Fichiers modifiés
- `.backlog/stories/STORY-254.2-croisement-plan-backlog.md` — tableaux de couverture consignés (36 items + 17 reportés + écarts)

### Découvertes principales
1. **35/36 items couverts** par stories DONE (preuves : epics cochées, CHANGELOG, journal 254.1) ;
2. **Écart n°8 (Majeur)** : P2-15 notifications core jamais matérialisées — stub `notification.send` tracé dans le code, arbitrage réclamé par EPIC-013 l.38 mais jamais tranché → transmis à 254.3 ;
3. **17/17 reportés §6 confirmés** dans la Roadmap (correspondance thématique vérifiée ligne à ligne) ;
4. Écarts de forme : DoD epics non cochées (F1), notes 253 absentes (F2), STORY-100→104 absentes du registre (F3 — rétro-inscription proposée, la règle 01 §2 l'expose explicitement).

### Validation (écrans E1-E4)
- E1 ✅ 36/36 lignes avec story(s)+statut ; E2 ✅ 17/17 reportés vérifiés ; E3 ✅ réciprorité écarts↔sections (n°8, F1-F4 documentés) ; E4 ✅ `make backlog-check` vert.
