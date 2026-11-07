# STORY-254.3 : Écrans de contrôle des vagues + arbitrage des écarts résiduels

**Statut :** DONE
**Story Parente :** STORY-254 — Revue finale de conformité — audit specs ↔ code de bout en bout et tableau de conformité (clôture du plan)
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)

## Description

En tant que responsable technique WindFlow, je veux exécuter les **écrans de contrôle des vagues** (grep Celery, import-check code mort, matrice RBAC, couverture par domaine ≥ 80 %) et statuer sur **chaque écart résiduel** — les 7 déjà listés dans [`backend_status.md`](../../docs/backend_status.md) §14.2 plus ceux découverts par STORY-254.1/254.2 — afin d'atteindre le critère « **zéro écart bloquant non tracé** » : tout écart fait l'objet d'un bug, d'une story ou d'une décision WONT_FIX documentée. **L'arbitrage d'acceptation appartient à l'utilisateur.**

## Critères d'acceptation (AC)

- [x] AC 4 : **Zéro écart bloquant non tracé** : tout écart résiduel découvert pendant l'audit fait l'objet d'une story, d'un bug ou d'une décision WONT_FIX documentée (l'arbitrage d'acceptation appartient à l'utilisateur). *(10 écarts consolidés → 4 bugs créés BUG-011→014, 2 WONT_FIX, 2 REPORTÉ, 2 décisions de forme — arbitrage utilisateur du 2026-11-07)*

## Contexte technique

**Écrans de contrôle des vagues** (méthode parente point 4) :

| Écran | Commande | Origine |
|---|---|---|
| Celery | `grep -rniE "celery" backend/ Makefile` + `poetry run pytest backend/tests/unit/test_no_celery_residue.py -v` | STORY-130.2 |
| Code mort | import-check des symboles purgés : `grep -rn "permissions\b\|HealthCheck\|DatabaseManager\|workflows_router" backend/app/` (tolérer les mentions documentaires) + OpenAPI sans `/workflows` | STORY-250.1 |
| Matrice RBAC | `poetry run pytest backend/tests/unit/test_api/test_rbac_exhaustivite.py -v` (échec préexistant `/api/v1/metrics` attendu — résidu STORY-172) | STORY-122.7 |
| Couverture | lecture status §13.3 (par domaine) — cible ≥ 80 % (rules 35) | rules 35 |

**Les 7 écarts résiduels connus** (status §14.2 — propositions d'action à préparer, décision utilisateur) :

| # | Écart | Piste de statut (à arbitrer) |
|---|---|---|
| 1 | Échec test `/api/v1/metrics` vs garde-fou RBAC `test_every_api_route_is_protected` (résidu STORY-172) | Bug de non-régression : exempter la route du garde-fou ou protéger l'endpoint |
| 2 | 14 échecs tests (`test_admin_stacks_validation` ×7 + `test_stacks_variables_contract` ×7) préexistants sur HEAD | Bug(s) de diagnostic (rupture de contrat apparue entre STORY-252 et 253) |
| 3 | [`helper/security.py`](../../backend/app/helper/security.py) bcrypt orphelin (0 consommateur) | Bug mineur : purge du helper + retrait dépendance bcrypt transitionnelle |
| 4 | Docstrings `expires_in: 1800` mensongers ([`auth.py`](../../backend/app/api/v1/auth.py)) ×3 | Bug mineur : correction docstrings (valeur réelle 900) |
| 5 | `env.example` variables non consommées (`ACCESS_TOKEN`/`SECRET_KEY`…) | Bug mineur : aligner les noms sur les settings réels |
| 6 | 3 sites SSH ad hoc non câblés au circuit breaker (divergence documentée STORY-251) | WONT_FIX documenté ou bug mineur |
| 7 | Appels LLM simulés (TODO `litellm.completion()`, 0 endpoint exposé) | REPORTÉ Phase 5 (plugin IA) — à tracer dans le tableau final, pas un bug |

**Règles de conformité** :
- Registre [`identifiants.md`](../identifiants.md) : prochain bug = **BUG-011** (inscription dans le même changement que la création du fichier bug — règle 01 §2) ;
- Gabarit bug : [`_models/bug.md`](../_models/bug.md) — statut initial `NEW`, passages `NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE` ;
- Les écarts découverts par 254.1/254.2 s'ajoutent à cette liste et suivent le même circuit ;
- WONT_FIX = décision explicite consignée dans le fichier bug (statut final, motif).

**Posture** : cette sous-story **ne corrige aucun code** — elle exécute les écrans, prépare les propositions, crée les contrats de bug après arbitrage utilisateur (via `ask_followup_question`).

## Dépendances

- STORY-254.1 (écarts découverts à l'audit domaines)
- STORY-254.2 (écarts de couverture plan ↔ backlog)

## Tâches d'implémentation détaillées

### Tâche 1 : Exécution des écrans de contrôle des vagues
**Objectif :** Prouver l'état des 4 garde-fous historiques et consigner les résultats.
**Fichiers :**
- `.backlog/stories/STORY-254.3-ecrans-controle-arbitrage-ecarts.md` (section « Résultats des écrans ») — **Modifier** — Exécuter les 4 écrans du tableau ci-dessus, consigner commande + résultat (attendu : Celery 0 hit + test vert ; code mort 0 symbole orphelin ; RBAC unique échec préexistant `/api/v1/metrics` ; couverture conforme au status §13.3). Tout écart d'écran = entrée supplémentaire en Tâche 2.
**Exigences sécurité :** Aucune (exécution de tests en lecture).
**Dépend de :** Aucune (mais contextualisée par 254.1/254.2).

### Tâche 2 : Consolidation des écarts + propositions d'action
**Objectif :** Produire la liste exhaustive (7 connus + découvertes 254.1/254.2 + écrans) avec proposition de statut par écart.
**Fichiers :**
- `.backlog/stories/STORY-254.3-ecrans-controle-arbitrage-ecarts.md` (section « Tableau d'arbitrage ») — **Modifier** — Tableau : écart / gravité (Bloquant/Majeur/Mineur) / proposition (BUG-0xx / WONT_FIX / REPORTÉ Roadmap) / justification. Les propositions **n'engagent pas** — décision utilisateur en Tâche 3.
**Exigences sécurité :** Aucune.
**Dépend de :** Tâche 1 + statuts 254.1/254.2 DONE.

### Tâche 3 : Arbitrage utilisateur + création des traces
**Objectif :** Faire arbitrer chaque écart par l'utilisateur (bug / WONT_FIX / report) puis matérialiser les traces.
**Fichiers :**
- `.backlog/bugs/BUG-011+.md` — **Créer** (un fichier par écart arbitré « bug », gabarit [`_models/bug.md`](../_models/bug.md), statut `NEW`, sections Reproduction/Attendu vs actuel remplies) — pour les écarts 1-5 typiquement ;
- `.backlog/identifiants.md` — **Modifier** — Inscrire chaque BUG créé (chemin + date + motif) dans le même changement (prochain = BUG-011) ;
- `.backlog/stories/STORY-254.3-ecrans-controle-arbitrage-ecarts.md` — **Modifier** — Consigner les décisions (écart → décision → référence du contrat créé ou motif WONT_FIX/REPORTÉ).
**Exigences sécurité :** Aucune donnée sensible dans les fichiers bug (pas de secrets réels en exemple).
**Dépend de :** Tâche 2.

## Tests à écrire

> Story de **contrôle et traçabilité** — aucun code modifié : couverture et cas sécurité **non applicables**.

### Écrans de contrôle

| # | Commande / vérification | Résultat attendu |
|---|---|---|
| E1 | Chaque écart du tableau d'arbitrage a une décision consignée | 0 écart sans statut |
| E2 | Chaque bug créé est inscrit au registre + fichier présent + statut initial `NEW` | 0 anomalie registre |
| E3 | `make backlog` après créations | kanban régénéré, bugs visibles (statut NEW hors kanban → visibles seulement à CONFIRMED+ ; cohérence vérifiée par `make backlog-check`) |
| E4 | `make backlog-check` | vert |

### Commandes de validation
```bash
make backlog-check
make backlog
```

## Résultats des écrans (Tâche 1 — exécutés le 2026-11-07)

| Écran | Commande | Résultat | Verdict |
|---|---|---|---|
| Celery | `grep -rniE "celery" backend/app/ Makefile --include="*.py"` + `pytest tests/unit/test_no_celery_residue.py` | **0 hit** code ; **3 passed** | ✅ CONFORME |
| Code mort | `grep -rn "workflows_router\|DatabaseManager\|HealthCheck" backend/app` | `DatabaseManager` : unique mention documentaire (docstring abstractions.py l.6 « purgé par STORY-250.1 ») ; `HostHealthCheckResponse` = schéma Pydantic légitime du module hosts (≠ classe `HealthCheck` de resilience.py purgée) ; `workflows_router` : 0 hit | ✅ CONFORME |
| Matrice RBAC | `pytest tests/unit/test_api/test_rbac_exhaustivite.py` | **1 failed** (`test_every_api_route_is_protected` — résidu STORY-172 documenté, écart n°1) + **5 passed** | ⚠️ état attendu tracé |
| Couverture | lecture status §13.3 (vérifiée en 254.1 §16) | par domaine ≥ 80 % sur modules remédiés (WS 94 %, cache 93 %, rate_limit 100 %) ; cible globale `--cov-fail-under=80` en CI | ✅ CONFORME |

## Tableau d'arbitrage (Tâche 2 — consolidé 254.1 + 254.2 + écrans)

| # | Écart | Gravité | Proposition | Justification |
|---|---|---|---|---|
| 1 | Échec `test_every_api_route_is_protected` vs `/api/v1/metrics` sans auth (résidu STORY-172) | Majeur | **BUG-011** : arbitrer exemption explicite de la route dans le garde-fou (metrics sans auth = design scrape documenté rules 45) ou protection de l'endpoint | Le test échoue depuis STORY-172 ; l'un des deux contrats doit céder explicitement |
| 3 | [`helper/security.py`](../../backend/app/helper/security.py) bcrypt orphelin (0 consommateur) | Mineur | **BUG-012** : purge du helper + retrait dépendance `bcrypt` transitionnelle (prévu STORY-250 « retrait post-migration ») | Code mort + dépendance legacy |
| 4 | Docstrings `expires_in: 1800` mensongers ×3 (valeur réelle 900) | Mineur | **BUG-013** : correction des docstrings | Documentation de contrat trompeuse |
| 5 | `env.example` variables non consommées (`ACCESS_TOKEN`/`SECRET_KEY`…) | Mineur | **BUG-014** : aligner les noms sur les settings réels | Config documentaire trompeuse |
| 6 | 3 sites SSH ad hoc hors circuit breaker | Mineur | **WONT_FIX** (divergence déjà documentée STORY-251 : chemins sans UUID de host) ou bug mineur | Divergence assumée en 251 |
| 7 | Appels LLM simulés (`litellm.completion()` TODO) | Report assumé | **REPORTÉ Phase 5** (plugin IA Roadmap l.412+) — pas un bug, à tracer dans le rapport final | 0 endpoint exposé ; cache LLM réel consommé |
| 8 | **P2-15 Notifications core non matérialisées** (stub `notification.send`, arbitrage EPIC-013 l.38 jamais tranché) | Majeur | **Story de matérialisation** (notifications in-app + webhook, `notification.send` réel) **ou REPORTÉ explicite** Roadmap/initiative | Dernier item du plan sans couverture |
| F1 | DoD epics 011/012/013 cases non cochées alors que DONE | Mineur (forme) | Cochage rétroactif documenté (rapport final) ou WONT_FIX | Cohérence documentaire |
| F2 | STORY-253 DONE sans « Notes d'implémentation » (Tâche 9 incomplète) | Mineur (forme) | WONT_FIX (matière compensée par 254.1/254.2) | La traçabilité existe ailleurs |
| F3 | STORY-100→104 absentes du registre (fichiers supprimés 2026-09-07, pratique antérieure à la règle d'or) | Mineur (forme) | **Rétro-inscription registre** (politique §5 « contrat manquant = anomalie à traiter ») | Politique explicite du registre |

## Décisions d'arbitrage (Tâche 3 — validées par l'utilisateur le 2026-11-07)

| Écart | Décision | Trace |
|---|---|---|
| n°1 garde-fou RBAC vs `/metrics` | **BUG-011** (NEW) | [`BUG-011-garde-fou-rbac-vs-metrics-sans-auth.md`](../bugs/BUG-011-garde-fou-rbac-vs-metrics-sans-auth.md) + registre |
| n°3 helper bcrypt orphelin | **BUG-012** (NEW) | [`BUG-012-helper-security-bcrypt-orphelin.md`](../bugs/BUG-012-helper-security-bcrypt-orphelin.md) + registre |
| n°4 docstrings `expires_in: 1800` | **BUG-013** (NEW) | [`BUG-013-docstrings-expires-in-1800-auth.md`](../bugs/BUG-013-docstrings-expires-in-1800-auth.md) + registre |
| n°5 `env.example` orphelin | **BUG-014** (NEW) | [`BUG-014-env-example-variables-non-consommees.md`](../bugs/BUG-014-env-example-variables-non-consommees.md) + registre |
| n°6 3 sites SSH hors circuit breaker | **WONT_FIX** | Divergence assumée et documentée STORY-251 (chemins sans UUID de host) — motif consigné ici : coût de câblage > bénéfice, chemins ad hoc non critiques |
| n°7 LLM simulé | **REPORTÉ Phase 5** | Plugin IA Roadmap l.412-418 ; cache LLM réel consommé (STORY-168) ; 0 endpoint exposé — à figer dans le rapport final 254.4 |
| n°8 P2-15 notifications core | **REPORTÉ initiative dédiée** | Arbitrage utilisateur : pas de matérialisation immédiate — `notification.send` reste stub tracé (action_registry l.33) ; l'item sort du périmètre remédiation et devient une initiative future (à figer dans rapport 254.4 + mention Roadmap à la prochaine édition) |
| F1 DoD epics non cochées | **WONT_FIX** | Forme historique — les rapports de finalisation existants (EPIC-011 97 %) font foi ; expliqué dans le rapport final |
| F2 notes 253 absentes | **WONT_FIX** | Matière compensée par les journaux 254.1/254.2 (traçabilité complète) |
| F3 STORY-100→104 absentes registre | **Rétro-inscription** | Effectuée ci-dessous (Politique §5 : « les abandons historiques non inscrits font l'objet d'une rétro-inscription ») |

**Rétro-inscription F3** (5 lignes ajoutées au registre — chemin « — » = fichiers supprimés à la clôture EPIC-011 le 2026-09-07, trace CHANGELOG l.95-99 + rapport de finalisation EPIC-011).

## État d'avancement technique
- [x] Tâche 1 : Exécution des écrans de contrôle
- [x] Tâche 2 : Consolidation écarts + propositions
- [x] Tâche 3 : Arbitrage utilisateur + création traces (bugs/WONT_FIX)

## Notes d'implémentation (treat-story — 2026-11-07)

### Fichiers créés/modifiés
- `.backlog/bugs/BUG-011-garde-fou-rbac-vs-metrics-sans-auth.md` — **Créé** (NEW, Majeur)
- `.backlog/bugs/BUG-012-helper-security-bcrypt-orphelin.md` — **Créé** (NEW, Mineur)
- `.backlog/bugs/BUG-013-docstrings-expires-in-1800-auth.md` — **Créé** (NEW, Mineur)
- `.backlog/bugs/BUG-014-env-example-variables-non-consommees.md` — **Créé** (NEW, Mineur)
- `.backlog/identifiants.md` — 4 bugs inscrits (BUG-011→014) + 5 rétro-inscriptions STORY-100→104 (F3) ; prochain bug = BUG-015
- `.backlog/stories/STORY-254.3-ecrans-controle-arbitrage-ecarts.md` — écrans + tableau arbitrage + décisions

### Décisions techniques (arbitrage utilisateur du 2026-11-07)
- 4 bugs créés pour les écarts n°1/3/4/5 (la correction est hors périmètre revue — posture « jamais corrigé en silence ») ;
- n°6 WONT_FIX (divergence assumée 251) ; n°7 REPORTÉ Phase 5 ; **n°8 P2-15 REPORTÉ initiative dédiée** (l'arbitrage réclamé par EPIC-013 l.38 est désormais tranché : pas de matérialisation dans le cycle remédiation) ;
- F1/F2 WONT_FIX ; F3 rétro-inscription exécutée.

### Validation (écrans E1-E4)
- E1 ✅ 10/10 écarts ont une décision consignée ; E2 ✅ 4 bugs inscrits au registre, fichiers présents, statut NEW ; E3/E4 ✅ `make backlog` + `make backlog-check` verts (vérifiés en fin de story).
