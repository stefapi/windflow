# STORY-252 : Corrections consolidées des spécifications — arbitrages F1-F6 appliqués aux specs (P3-4)

**Statut :** DONE
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-4 (arbitrages F1, F2, F5, F3, F4, F6 + retombée nomenclature P2-2) — ampleur **M**

> ⚠️ **Numérotation** : cette story porte le numéro STORY-252 conformément au découpage final de la phase 5 (les éditions antérieures des epics EPIC-012/EPIC-013 et de STORY-130 la citaient comme « STORY-253 » — référence corrigée lors de l'audit de cohérence).

## Description

En tant que responsable technique WindFlow, je veux appliquer aux spécifications générales les arbitrages validés du plan de remédiation (Argon2 remplace bcrypt — F2 ; JWT 15 min — F5 ; incorporation des surfaces HORS SPEC — F3 ; suppression des références Celery — F1 ; bus asyncio/Redis Pub/Sub — F6 ; annotation de phasage du modèle directeur — F4), afin que **les specs reflètent le code livré** et qu'il ne subsiste plus d'écart « annoncé vs réel » côté documentation contractuelle.

**Problème constaté** : plusieurs specs divergent du code, soit parce que le code est meilleur (JWT 15 min réel vs 30 min spec), soit parce que le plan a arbitré (Celery abandonné, Argon2 adopté, surfaces API existantes à incorporer). Les corrections ont été **volontairement différées** jusqu'ici (répartition du plan : STORY-130.1/130.2, STORY-162, STORY-166, STORY-173 livrent le code et renvoient les corrections consolidées de specs à la vague P3).

## Contexte technique

### Constats d'exploration (état réel du code et des specs au 2026-10-31)

**Code — source de vérité pour chaque arbitrage :**

- **F2 (Argon2id effectif)** : [`backend/app/services/user_service.py`](../../backend/app/services/user_service.py) l.27 — `pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")` : Argon2id en écriture, double lecture bcrypt legacy avec re-hash automatique au login (`verify_and_update_user`, STORY-130.1) ; `refresh_token_service.py`/`api_key_service.py` hashent en **Argon2 déterministe** ; **résidu constaté** : [`backend/app/helper/security.py`](../../backend/app/helper/security.py) (bcrypt brut, grep 0 consommateur dans `app/` + `tests/` — code mort à signaler, cf. D4).
- **F5 (JWT 15 min réel)** : [`backend/app/config.py`](../../backend/app/config.py) l.36 — `jwt_access_token_expire_minutes: int = 15` ; les réponses réelles (`auth.py` l.375/534/865) calculent `settings × 60` = **900 s**. **Écart interne code** : les exemples docstring codés durs `expires_in: 1800/3600` ([`auth.py`](../../backend/app/api/v1/auth.py) l.150/450/731, [`schemas/user.py`](../../backend/app/schemas/user.py) l.259/318/370) rendent l'OpenAPI mensonger — à **signaler** (AC 5), pas corriger ici.
- **F1 (Celery purgé)** : garde-fou [`backend/tests/unit/test_no_celery_residue.py`](../../backend/tests/unit/test_no_celery_residue.py) (module `app.celery_app` absent, dépendance absente de `pyproject.toml`) ; runtime réel **asyncio unique** = boucles lifespan ([`main.py`](../../backend/app/main.py)) + scheduler engine (STORY-160.2) + `DeploymentOrchestrator` + [`background_tasks.py`](../../backend/app/tasks/background_tasks.py).
- **F6 (bus livré)** : [`backend/app/core/events.py`](../../backend/app/core/events.py) — interface `Bus` unique, `InMemoryEventBus` par défaut + `RedisPubSubEventBus` optionnel (canal unique `windflow:events`, activé quand `cache_url` configuré) ; `LEGACY_EVENT_ALIASES` (l.183) = table de correspondance ancien→nouveau (`deployment.completed`→`deployment.succeeded`, `target.*`→`host.*`) ; **Redis Streams assumé hors périmètre** (docstring l.16-18).
- **F3 (surfaces réelles inventoriées)** — montages dans [`api/v1/__init__.py`](../../backend/app/api/v1/__init__.py) l.34-67 : `compute.py` **7 routes** (`/stats`, `/global`, `/browse`, `/volumes`, `/volumes/{name}`, `/volumes/{name}/browse`, `/prune` — STORY-173) ; `discovery.py` **2 routes** (`/{item_type}/{item_id}/adoption-data`, `/adopt`) ; `stats.py` **2** (`/stats/dashboard`, `/stats/stacks/{id}`) ; `import_export.py` **2** (`/stacks/{id}/export`, `/stacks/import`) ; `admin/stacks_management.py` **13 routes** (validate, import, sync/status, sync/auto, `{id}/export`, `export/bulk`, `{id}/toggle-visibility`, `{id}/duplicate`, `DELETE {id}`, `stats/overview`, `{id}/usage`, `health`, `search` — le plan §F3 annonçait 15, écart tracé) ; `plugin_registry.py` **2** sous `/registry` (`/plugins`, `/plugins/{name}`) ; alias [`targets_legacy.py`](../../backend/app/api/v1/targets_legacy.py) (préfixe `/targets`, `deprecated=True` + Sunset, STORY-166.2/166.6) ; `/docker` **35 endpoints** (garde-fou STORY-173) ; `GET /api/v1/metrics` sans auth (STORY-172).
- **F4 (étape 2 livrée)** : migrations Alembic `1661`/`1662` (Host + `origin` + `environments` + `Stack.git_url`) ; étape 3 (`Apps`/`Machines`/`Clusters`) absente du code — le contrat `WorkloadAdapter` est posé (STORY-174.1, [`services/workloads/`](../../backend/app/services/workloads/)).
- **STORY-251 (DONE 2026-10-31)** : CircuitBreaker **câblé** — garde partagé [`workloads/_circuit_guard.py`](../../backend/app/services/workloads/_circuit_guard.py), settings `circuit_breaker_*` ([`config.py`](../../backend/app/config.py)), séries `windflow_circuit_breaker_*` ([`core/metrics.py`](../../backend/app/core/metrics.py)) → la spec 04 § Résilience devient **conforme sans retouche** : ne pas y toucher au-delà de la suppression Celery ; si la section chiffre des seuils, les aligner sur les défauts settings (failure_threshold 5, timeout 60 s, half_open 30 s).

**Specs — écarts exacts relevés (grep du 2026-10-31) :**

- [`07`](../../docs/general_specs/07-authentification.md) : bcrypt ×4 (l.16, 33, 46, 76) ; JWT « 30 min » ×3 (l.35, 63, 212) ; exemples `expires_in: 1800` ×2 (l.111, 126).
- [`15`](../../docs/general_specs/15-securite.md) : bcrypt ×3 (l.20, 68, 141 — l.141 porte aussi « JWT HS256 de 30 min »).
- [`19-glossaire`](../../docs/general_specs/19-glossaire.md) : « Access token … 30 min » l.116 — retombée F5 **non listée** au tableau contractuel (à corriger pour AC 2/AC 4).
- [`04`](../../docs/general_specs/04-architecture.md) : Celery ×9 (diagramme l.46, mode léger l.162/169, standard l.177/183-184, arborescence `tasks/` l.235-238, perf l.342) ; § Bus l.287-291 déjà « Redis Pub/Sub ou asyncio » mais **sans** interface canonique ni renvoi nomenclature/aliases STORY-162.
- [`05`](../../docs/general_specs/05-stack-technologique.md) : Celery l.25-26 (table Task queue), l.89-91 (modes), l.104-107 (section dédiée), l.257-258 (récap dépendances), l.290-292 (image `windflow/worker`).
- [`06`](../../docs/general_specs/06-modele-de-donnees.md) : aucune annotation de phasage (Vue d'ensemble l.7 + § Migration l.526+ décrivent la cible complète sans dire ce qui est livré) ; « hash bcrypt de la clé » l.823 (`api_keys`) — retombée F2 non listée au tableau.
- [`09`](../../docs/general_specs/09-api.md) : § Volumes l.439-446 porte **déjà** le renvoi [`COMPUTE-DOCKER-MAPPING.md`](../../docs/technical_specs/COMPUTE-DOCKER-MAPPING.md) avec la mention « consolidation rédactionnelle… coordonnée avec STORY-252 » — la tâche 6 honore cette promesse ; surfaces HORS SPEC absentes ; § Hosts (l.239+) sans double nommage.
- [`16`](../../docs/general_specs/16-deploiement.md) : `windflow-worker` l.72-75 (compose léger + `CELERY_CONCURRENCY`) et l.119-121 (compose standard).
- **Celery résiduel hors tableau contractuel** : `02` l.303, `03` l.284, `17` l.24/66/81/113 — cf. divergence n°1 (balayage complémentaire pour tenir AC 2).

**Patterns documentaires à imiter :**

- Bloc note « Implémentation & rapprochement » de `09` § Volumes (l.439-446) : renvoi vers `technical_specs/` + mention explicite de convergence et de la story porteuse ;
- [`COMPUTE-DOCKER-MAPPING.md`](../../docs/technical_specs/COMPUTE-DOCKER-MAPPING.md) : table statut par paire, décisions argumentées, différés Roadmap tracés ;
- Format standard des chapitres : en-tête Statut/Public/Lié à ; exemples préfixés **« Exemple illustratif »** (jamais contractuels — H1) ; renvois « Voir aussi » systématiques.

### Décisions d'analyse (252)

- **D1 — Périmètre contractuel vs balayage exhaustif** : le tableau contractuel fixe 7 specs (04/05/06/07/09/15/16) ; l'analyse **ajoute** un balayage cohérence sur `02`/`03`/`17`/`19` (mentions Celery + glossaire « 30 min ») parce qu'AC 2 exige « plus d'écart annoncé vs réel sur les points traités » — laisser ces mentions contesterait la relecture croisée specs ↔ `backend_status.md`. Balayage strictement limité aux mentions Celery/JWT/Argon2 (aucune réécriture).
- **D2 — Statut de spec CIBLE préservé** : `09`/`06` décrivent la cible produit (`/apps`, `/machines`, `/clusters`…). L'incorporation F3 **n'efface pas la cible** : les surfaces livrées sont incorporées avec annotation de convergence F4 (« surface livrée, converge vers … lors du phasage ») — même méthode que le renvoi l.439-446.
- **D3 — Nom des variables d'env** : vérifier à l'édition le nom réel (field [`config.py`](../../backend/app/config.py) `jwt_access_token_expire_minutes` ; la spec cite `ACCESS_TOKEN_EXPIRE_MINUTES`) — si aucun alias n'existe côté code, documenter le **nom réel** (principe « les specs reflètent le code livré »).
- **D4 — Aucune retouche code** : les écarts code découverts (`helper/security.py` bcrypt résiduel ; docstrings `expires_in: 1800/3600` ; plan « 15 endpoints stacks-management » vs 13 réels) sont **signalés** (AC 5 : bug ou story), jamais corrigés en silence ici.
- **D5 — Gate utilisateur §7.4** : F3/F4/F5/F6 restent à valider **avant édition** (AC 3) — traité en tête de la tâche 1 ; tout refus → divergence tracée dans les notes d'implémentation, spec non éditée pour cet arbitrage.

**Hypothèses & risques** — **H1** le préfixe « Exemple illustratif » des exemples de specs évite tout contrat figé sur `expires_in` (correction peu risquée) ; **H2** la spec 17 a déjà été partiellement alignée par STORY-160 (registre d'actions) — le balayage ne doit remplacer que « worker Celery » par le runtime réel, sans régénérer du contenu scheduler ; **R1** risque de dérive de périmètre (plan §7.5) : toute amélioration rédactionnelle hors arbitrages F1-F6 est refusée ; **R2** la relecture croisée AC 2 se fait contre le **code** si STORY-253 (`backend_status.md`) n'est pas encore livrée — tracer la méthode dans les notes.

**Divergences par rapport au tableau contractuel :**
1. **Balayage 02/03/17/19 ajouté** (D1 — tient AC 2) ;
2. **Enrichissement 09** : incorporation de `GET /api/v1/metrics` (STORY-172, sans auth) et mentions transverses `/schedules` (spec 17), `/ssh-keys` (STORY-131.2), dépréciation `/auth/me` (STORY-250.2) — surfaces HORS SPEC vivantes non listées au tableau, recommandées pour cohérence AC 2/AC 4 ;
3. **06 l.823** « hash bcrypt » corrigé en Argon2 — retombée F2 non listée au tableau.

Modifications consolidées attendues, **chacune citée avec son chapitre** :

| Spéc | Chapitre concerné | Correction | Arbitrage |
|------|-------------------|------------|-----------|
| [`07-authentification.md`](../../docs/general_specs/07-authentification.md) | § Authentification par mot de passe | Remplacer « bcrypt (cost 12) » par **Argon2id** (passlib + argon2-cffi, upgrade au login) | F2 |
| [`07-authentification.md`](../../docs/general_specs/07-authentification.md) | § Access token (JWT) + § Configuration (`ACCESS_TOKEN_EXPIRE_MINUTES=30`) + § Exemples (`expires_in: 1800`) | Durée access token **30 min → 15 min** (le code est plus sûr) | F5 |
| [`09-api.md`](../../docs/general_specs/09-api.md) | § API Mode Infra — vue Compute + § Endpoints transverses + nouvelles sections | **Incorporation des surfaces HORS SPEC** : `/compute/*` (dont `browse`/`prune` de STORY-173), `/discovery/*`, `/stats/*`, import/export stacks, `admin/stacks-management`, `plugin_registry` — avec enveloppes/pagination conformes aux stories P1 | F3 |
| [`09-api.md`](../../docs/general_specs/09-api.md) | § API par famille › Hosts | Documenter le **double nommage `/targets` → `/hosts`** avec période d'alias de compatibilité (livré par STORY-166) | F3/F4 |
| [`04-architecture.md`](../../docs/general_specs/04-architecture.md) | § Architecture globale / § Architecture du core (runtime de tâches) | Supprimer les références **Celery** ; documenter le runtime **asyncio** unique (lifespan + scheduler engine) — si STORY-130.2 est faite | F1 |
| [`04-architecture.md`](../../docs/general_specs/04-architecture.md) | § Communication et temps réel › Bus d'événements internes | Préciser : interface `Bus` canonique, implémentation **in-memory (asyncio) par défaut + Redis Pub/Sub optionnel** (pas de Redis Streams à ce stade) | F6 |
| [`05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) | § Traitement asynchrone — Celery | Remplacer la section Celery par le traitement asynchrone **asyncio** ; mettre à jour § Récapitulatif des dépendances (retrait Celery, ajout argon2-cffi) | F1/F2 |
| [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) | § Vue d'ensemble + § Migration de `targets` vers `hosts` | Annoter le **déploiement phasé** du modèle directeur : étapes 1-2 livrées (tables support, `Host` + `origin`), étape 3 (`Apps`/`Machines`/`Clusters`) reportée Roadmap Phase 2 | F4 |
| [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) | § Profils d'installation / § Installation mode standard | Retirer toute référence au **worker Celery** (service compose, build) si STORY-130.2 est faite ; vérifier la cohérence d'`alembic upgrade head` (STORY-120) | F1 |
| [`15-securite.md`](../../docs/general_specs/15-securite.md) | § synthèse auth (si bcrypt cité) | Aligner la mention du hash sur Argon2id (cohérence avec 07) | F2 |

Éléments existants à réutiliser / contraintes :
- Les chapitres exacts (lignes) seront fixés par `analyse-story` après relecture des specs ; le tableau ci-dessus fixe le **périmètre contractualisé** ;
- ⚠️ **Validation utilisateur préalable obligatoire** (plan §7.4) : F1 et F2 sont déjà validés (acquiescement documenté lors de la création des epics P1 — cf. STORY-130) ; **F3, F4, F5, F6 restent à confirmer par l'utilisateur avant édition des specs** — si un arbitrage est refusé, ne pas l'appliquer et tracer la divergence (l'arbitrage appartient à l'utilisateur) ;
- Cohérence croisée : les exemples OpenAPI intégrés aux specs (durées de token, endpoints) doivent correspondre au code livré ;
- La nomenclature des événements (retombée de P2-2/STORY-162 : table de correspondance ancien→nouveau) est reflétée dans les specs concernées (04 § bus, 11 § liste canonique) si STORY-162 l'a documentée côté code.

## Critères d'acceptation (AC)

- [x] AC 1 : Chaque modification de spec est **traçable** : spec ↔ chapitre ↔ arbitrage (F1/F2/F3/F4/F5/F6) ↔ story livreuse (STORY-130.1/130.2/160/162/166/173…) — tableau de correspondance fourni dans les notes d'implémentation.
- [x] AC 2 : Relecture croisée specs ↔ [`backend_status.md`](../../docs/backend_status.md) (actualisé par STORY-253) : **plus d'écart « annoncé vs réel »** sur les points traités (JWT 15 min, Argon2, absence de Celery, surfaces incorporées, phasage modèle, bus d'événements).
- [x] AC 3 : La validation utilisateur des arbitrages §7.4 (F3/F4/F5/F6) est **acquise et documentée** avant édition ; tout arbitrage refusé est tracé en divergence sans édition de spec.
- [x] AC 4 : Les documents internes restent cohérents : liens et renvois entre specs valides (00-index, « Voir aussi »), exemples de requêtes/réponses alignés sur le code (ex. `expires_in: 900`).
- [x] AC 5 : Revue documentaire terminée (relecture croisée) ; aucun impact code attendu — si un écart code est découvert pendant la revue, il est signalé (bug ou story) et non corrigé en silence.

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §3 (arbitrages F1-F6 détaillés), §4 P3-4, §7.4 (arbitrages nécessitant validation utilisateur), §8.1 (P3 couvre F1/F2/F5 docs) ;
- [`07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Authentification par mot de passe, § Access token (JWT), § Configuration, § Exemples de requêtes et réponses ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Conventions générales, § API Mode Infra — vue Compute, § API par famille › Hosts, § Endpoints transverses ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Architecture globale, § Architecture du core, § Communication et temps réel › Bus d'événements internes ;
- [`05-stack-technologique.md`](../../docs/general_specs/05-stack-technologique.md) — § Traitement asynchrone — Celery, § Récapitulatif des dépendances ;
- [`06-modele-de-donnees.md`](../../docs/general_specs/06-modele-de-donnees.md) — § Vue d'ensemble, § Migration de `targets` vers `hosts`, § Profils canoniques ;
- [`16-deploiement.md`](../../docs/general_specs/16-deploiement.md) — § Profils d'installation, § Installation mode standard, § Configuration initiale ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — synthèse auth (cohérence Argon2) ;
- `.roo/rules/40-security.md` — bibliothèques d'auth (passlib + argon2-cffi) : les rules imposent déjà Argon2, la spec 07 s'aligne.

## Dépendances

- ⚠️ **Validation utilisateur des arbitrages §7.4** (F3, F4, F5, F6 — F1/F2 déjà acquis lors de la création de STORY-130).
- **Vagues P0-P2 terminées** — les specs reflètent le code livré : STORY-130.1 (F2 effectif) + STORY-130.2 (F1 effectif), STORY-160 (runtime scheduler asyncio), STORY-162 (bus + nomenclature), STORY-166 (modèle Host — F4 étape 2), STORY-173 (compute — F3).
- Étroitement coordonnée avec **STORY-253** (mise à jour documentaire : `backend_status.md` et la revue croisée specs ↔ status doivent être cohérents).

### Compléments d'analyse (2026-10-31)

- **Prérequis livrés (vérifiés au kanban)** : STORY-130.1 (Argon2id + upgrade au login — F2 effectif), STORY-130.2 (purge Celery + garde-fou `test_no_celery_residue.py` — F1 effectif), STORY-160.1→160.3 + 161 (scheduler asyncio + API `/schedules`), STORY-162 (bus F6 + `LEGACY_EVENT_ALIASES`), STORY-166.1→166.6 (Host, `origin`, alias `/targets` déprécié — F4 étape 2), STORY-173 (`/compute` `browse`/`prune` + `COMPUTE-DOCKER-MAPPING.md` — F3), STORY-250.1/250.2 (purge code mort + dépréciation `/auth/me`).
- **STORY-251 (DONE — impact direct, story aval citée par ses notes d'implémentation)** : CircuitBreaker câblé via le garde partagé [`backend/app/services/workloads/_circuit_guard.py`](../../backend/app/services/workloads/_circuit_guard.py), settings `circuit_breaker_*` dans [`backend/app/config.py`](../../backend/app/config.py), séries `windflow_circuit_breaker_*` dans [`backend/app/core/metrics.py`](../../backend/app/core/metrics.py) → la spec 04 § Résilience devient conforme **sans retouche de cette story** (ne pas y toucher au-delà de la suppression Celery) ; si la section chiffre des seuils, aligner sur les défauts settings (5 / 60 s / 30 s).
- **Services externes** : **aucun** requis (story documentaire) ; Redis optionnel — documenter le bus F6 sans l'exiger (mode léger intact).
- **Base de données** : **aucune migration, aucune table** — aucun impact Alembic ; les migrations `1661`/`1662` existantes servent de référence rédactionnelle pour l'annotation F4.
- **Configuration** : lecture seule de [`backend/app/config.py`](../../backend/app/config.py) (`jwt_access_token_expire_minutes=15`, `refresh_token_expire_days=7`, `circuit_breaker_*`) pour aligner les valeurs documentées ; `env.example` non modifié (aucune nouvelle variable).
- **Coordination aval** : STORY-253 (`backend_status.md` + rules `.roo` + CHANGELOG) doit rester cohérente — 252 (specs) et 253 (status) se référencent mutuellement ; STORY-254 auditera le résultat (tableau de conformité final).
- **Dépendance processus (gate)** : validation utilisateur §7.4 (F3/F4/F5/F6) **avant toute édition** (AC 3) — F1/F2 déjà acquis lors de la création de STORY-130.

## État d'avancement technique

- [x] T1. Gate validation utilisateur §7.4 (F3/F4/F5/F6) + corrections spec 07 (F2 Argon2id + F5 JWT 15 min)
- [x] T2. Spec 15 — cohérence Argon2id / JWT 15 min
- [x] T3. Spec 04 — suppression Celery (F1) + bus d'événements canonique (F6)
- [x] T4. Spec 05 — traitement asynchrone asyncio + récap dépendances (F1/F2)
- [x] T5. Spec 06 — annotation phasage modèle directeur (F4) + hash Argon2 l.823
- [x] T6. Spec 09 — incorporation surfaces HORS SPEC (F3) + double nommage `/targets`→`/hosts`
- [x] T7. Spec 16 — retrait worker Celery des profils compose (F1)
- [x] T8. Balayage cohérence 02/03/17/19 (divergence n°1 — Celery + glossaire 30 min)
- [x] T9. Écrans de contrôle grep + tableau de traçabilité AC 1 + signalements écarts code (AC 5)

## Tâches d'implémentation détaillées

> Story **documentaire** : les « fichiers » ci-dessous sont des specs Markdown — **aucun code applicatif, aucun test automatisé nouveau** ; la validation passe par les écrans de contrôle de la section « Tests à écrire ». Chaque édition cite son arbitrage (F1-F6) et sa story livreuse (traçabilité AC 1).

### Tâche 1 : Gate §7.4 + spec 07 — Argon2id (F2) et JWT 15 min (F5)
**Objectif :** Faire valider les arbitrages restants, puis aligner le chapitre auth sur le code livré.
**Fichiers :**
- `docs/general_specs/07-authentification.md` — **Modifier** : l.16 « Hashage bcrypt » → « Hashage Argon2id » ; l.33 (diagramme) « Vérifier bcrypt » → « Vérifier Argon2id » + « JWT 30 min » → « JWT 15 min » ; l.46 « bcrypt (cost factor 12) » → **Argon2id** (passlib + argon2-cffi, paramètres par défaut passlib, double lecture bcrypt legacy et re-hash automatique au login — STORY-130.1) ; l.63 « **30 minutes** » → « **15 minutes** » + nom réel de la variable (D3 : vérifier l'alias env de `jwt_access_token_expire_minutes`) ; l.76 « hash bcrypt de la clé » → « hash Argon2id déterministe » (STORY-124.2) ; l.111 et l.126 exemples `expires_in: 1800` → **900** ; l.212 `ACCESS_TOKEN_EXPIRE_MINUTES=30` → 15 (+ nom réel, D3).
**Points clés :** garder le ton contractuel et le préfixe « Exemple illustratif » ; si la validation §7.4 refuse F5, ne pas éditer les durées et tracer la divergence (D5).
**Dépend de :** validation utilisateur §7.4 (gate AC 3).

### Tâche 2 : Spec 15 — cohérence Argon2id / JWT 15 min (F2/F5)
**Objectif :** Aligner la synthèse sécurité du chapitre 15 sur le chapitre 07 corrigé.
**Fichiers :**
- `docs/general_specs/15-securite.md` — **Modifier** : l.20 « Hashage bcrypt des mots de passe » → « Hashage Argon2id des mots de passe » ; l.68 « hashés avec bcrypt » → « hashés avec Argon2id » (`api_keys.key_hash`, `refresh_tokens.token_hash`) ; l.141 « bcrypt (cost 12), JWT HS256 de 30 min » → « Argon2id, JWT HS256 de 15 min ».
**Points clés :** aucune autre retouche du chapitre (R1) ; cohérence littérale avec 07 (mêmes termes).
**Dépend de :** Tâche 1.

### Tâche 3 : Spec 04 — suppression Celery (F1) + bus canonique (F6)
**Objectif :** Documenter le runtime asyncio unique et le bus d'événements livré par STORY-162.
**Fichiers :**
- `docs/general_specs/04-architecture.md` — **Modifier** : l.46 diagramme — retirer « Celery Worker tâches async », refléter le runtime asyncio (boucles lifespan + scheduler engine) ; l.157-185 (modes léger/standard) — schémas sans bloc worker, Redis documenté « cache + bus Pub/Sub » (plus « broker Celery ») ; l.235-238 arborescence — `tasks/` décrit les tâches asyncio (`background_tasks.py`), pas Celery ; l.342 « exécutées par Celery worker(s) » → tâches async du process API, planifiées par le scheduler engine (contrepartie F1 : single-process assumé, single-worker supporté) ; l.287-291 § Bus d'événements internes — préciser : **interface `Bus` canonique**, `InMemoryEventBus` (asyncio) par défaut + `RedisPubSubEventBus` optionnel (canal unique `windflow:events`, activé quand `cache_url` est configuré), **Redis Streams hors périmètre**, nomenclature spec 11 + table de correspondance ancien→nouveau (`LEGACY_EVENT_ALIASES`, STORY-162).
**Points clés :** **ne pas toucher § Résilience et fiabilité** au-delà de la suppression Celery — le circuit breaker annoncé est désormais réel (STORY-251) ; si des seuils y sont cités, aligner sur les défauts settings (5 échecs / 60 s / 30 s half-open).
**Dépend de :** Tâche 1 (F1 déjà validé, F6 confirmé par le gate).

### Tâche 4 : Spec 05 — traitement asynchrone asyncio + dépendances (F1/F2)
**Objectif :** Retirer Celery du chapitre stack et refléter les dépendances réelles.
**Fichiers :**
- `docs/general_specs/05-stack-technologique.md` — **Modifier** : l.25-26 table — ligne « Task queue | Celery » → runtime asyncio (scheduler engine + tâches lifespan) ; l.89-91 modes — Redis sans mention « broker Celery », supprimer « Celery utilise le filesystem comme broker » ; l.104-107 section « Traitement asynchrone — Celery » → « Traitement asynchrone — asyncio » (déploiements en tâches async du process API, planification par le scheduler engine, F1) ; l.257-258 récap dépendances — retirer `celery`, vérifier/ajouter `argon2-cffi` ; l.290-292 table conteneurs — retirer la ligne « Celery Worker / windflow/worker ».
**Points clés :** cohérence littérale avec 04 (Tâche 3) — mêmes formulations runtime ; récap dépendances = miroir de `pyproject.toml`.
**Dépend de :** Tâche 3.

### Tâche 5 : Spec 06 — annotation phasage du modèle directeur (F4) + Argon2 (F2)
**Objectif :** Annoter ce qui est livré (étapes 1-2) vs reporté (étape 3) sans effacer la cible.
**Fichiers :**
- `docs/general_specs/06-modele-de-donnees.md` — **Modifier** : § Vue d'ensemble (l.7) — ajouter un paragraphe « **Déploiement phasé** » : étapes 1-2 **livrées** (tables support + `Host`/`origin`/`environments`/`Stack.git_url`, migrations `1661`/`1662`), étape 3 (`apps`/`machines`/`clusters`, triple XOR, verbes universels) **reportée Roadmap Phase 2** (contrat posé par `WorkloadAdapter`, STORY-174.1) ; § Entités workloads (l.257+) et § Entité Cluster (l.374+) — annotation courte « cible non livrée (phasage F4) » sur les sections concernées (D2 : pas de suppression) ; § Migration `targets`→`hosts` (l.526) — statuer « migration livrée (Alembic 1661/1662) » ; l.823 commentaire SQL « hash bcrypt de la clé » → « hash Argon2id de la clé » (divergence n°3).
**Points clés :** annotations courtes et systématiques (même formulation partout) ; le diagramme ER et les schémas cibles restent (spec cible).
**Dépend de :** Tâche 1.

### Tâche 6 : Spec 09 — incorporation des surfaces HORS SPEC (F3) + double nommage (F3/F4)
**Objectif :** Incorporer les contrats réels livrés dans le chapitre API, avec annotation de convergence D2.
**Fichiers :**
- `docs/general_specs/09-api.md` — **Modifier** :
  - § Structure des endpoints (l.22-50) : ajouter à l'arborescence les surfaces réelles (`registry/`, `discovery/`, `stats/`, `docker/`, `metrics`, `schedules/`, `ssh-keys/`) ;
  - § API Mode Infra — vue Compute : nouvelle sous-section « Surfaces livrées (transitoires) » — `/compute/stats`, `/compute/global`, `/compute/browse` (paginé filtrable, STORY-173), `/compute/volumes`, `/compute/volumes/{name}`, `/compute/volumes/{name}/browse`, `POST /compute/prune` (superadmin + confirmation + dry-run + audit) + renvoi [`COMPUTE-DOCKER-MAPPING.md`](../../docs/technical_specs/COMPUTE-DOCKER-MAPPING.md) pour la surface `/docker` (35 endpoints, décision : aucune suppression, convergence par dépréciation modèle 166) — honore la promesse rédactionnelle l.439-446 ;
  - § API par famille › Hosts : documenter le **double nommage `/targets` → `/hosts`** — alias déprécié (`deprecated: true` OpenAPI, header `Sunset`), période de compatibilité, retrait planifié (STORY-166.2/166.6, renvoi F3) ;
  - § Endpoints transverses : nouvelles sections — `/discovery` (2 routes adoption-data/adopt), `/stats` (dashboard, stacks/{id}), import/export stacks (2 routes), `/admin/stacks-management` (**13 routes réelles** : validate, import, sync/status, sync/auto, {id}/export, export/bulk, toggle-visibility, duplicate, delete, stats/overview, {id}/usage, health, search), `/registry/plugins` (2 routes) — toutes documentées **avec enveloppes/pagination conformes STORY-126/128** (exemples `{data, pagination}`) ;
  - compléments (divergence n°2) : mention `GET /api/v1/metrics` sans auth (exemption sondes, STORY-172), renvoi `/schedules` vers spec 17, `/ssh-keys` (STORY-131.2), note dépréciation `/auth/me` (STORY-250.2).
**Points clés :** chaque section incorporée porte son annotation de convergence F4 (« converge vers `/apps`/`/hosts` lors du phasage ») ; exemples au format « Exemple illustratif » ; aucune promesse de suppression d'endpoint Docker.
**Dépend de :** Tâche 1 (F3 validé).

### Tâche 7 : Spec 16 — retrait du worker Celery des profils (F1)
**Objectif :** Aligner les exemples de déploiement sur les compose réels post-purge.
**Fichiers :**
- `docs/general_specs/16-deploiement.md` — **Modifier** : l.72-75 compose léger — retirer le service `windflow-worker` et `CELERY_CONCURRENCY` ; l.119-121 compose standard — idem ; vérifier la cohérence de `alembic upgrade head` (STORY-120 : migrations au démarrage, plus de `create_all`) ; vérifier que les profils listent uniquement les images réelles (`api`, `frontend` — `Dockerfile.worker` supprimé par STORY-130.2).
**Points clés :** miroir des `docker-compose*.yml` réels du dépôt ; aucune évolution de contenu déploiement au-delà de F1 (R1).
**Dépend de :** Tâches 3-4 (cohérence 04/05).

### Tâche 8 : Balayage cohérence 02/03/17/19 (divergence n°1)
**Objectif :** Éliminer les dernières mentions « annoncé vs réel » Celery/JWT hors specs contractuelles (tient AC 2).
**Fichiers :**
- `docs/general_specs/02-familles-workloads.md` — **Modifier** l.303 : « exécutées par les workers Celery » → « exécutées par le scheduler core (asyncio) » ;
- `docs/general_specs/03-modele-compute.md` — **Modifier** l.284 : « scheduler core + Celery » → « scheduler core » ;
- `docs/general_specs/17-automatisation-workflows.md` — **Modifier** l.24/66/81/113 : « worker Celery »/« file Celery » → moteur asyncio du scheduler (boucle lifespan, verrous anti-chevauchement, STORY-160.2) — **H2** : remplacer uniquement les mentions Celery, ne pas régénérer le contenu scheduler déjà aligné ;
- `docs/general_specs/19-glossaire.md` — **Modifier** l.116 : « JWT de courte durée (30 min) » → « (15 min) ».
**Points clés :** diff minimal — une phrase par site, pas de réécriture.
**Dépend de :** Tâches 3-5.

### Tâche 9 : Écrans de contrôle + traçabilité (AC 1/2/4/5)
**Objectif :** Prouver la conformité finale de l'édition documentaire.
**Fichiers :**
- `.backlog/stories/STORY-252-corrections-consolidees-specifications.md` (notes d'implémentation) — **Modifier** : tableau de correspondance **spec ↔ chapitre/ligne ↔ arbitrage (F1-F6) ↔ story livreuse** (AC 1) + divergences effectives (arbitrages refusés éventuels) ;
- vérifications (sans édition) : greps de la section « Tests à écrire », relecture croisée specs ↔ code sur les 6 points (JWT 15 min, Argon2, absence de Celery, surfaces incorporées, phasage modèle, bus d'événements) — contre `backend_status.md` si STORY-253 est livrée, sinon contre le code (R2), liens `00-index`/« Voir aussi » valides (AC 4) ;
- **signalements écarts code (AC 5 — jamais corrigés ici)** : [`helper/security.py`](../../backend/app/helper/security.py) bcrypt résiduel 0 consommateur (candidat bug/purge) ; docstrings `expires_in: 1800/3600` ([`auth.py`](../../backend/app/api/v1/auth.py) l.150/450/731, [`schemas/user.py`](../../backend/app/schemas/user.py) l.259/318/370 — OpenAPI mensonger) ; plan §F3 « 15 endpoints » vs 13 réels (`admin/stacks_management.py`).
**Dépend de :** Tâches 1-8.

## Tests à écrire

> **Checklist sécurité (rules 40 § 8) — dérogation documentée** : story **documentaire** — aucun endpoint, aucun code, aucune donnée manipulée : les cas 401/403/422/404 sont **non applicables** (même posture que les stories tests-only). Exigences appliquées par analogie : les exemples de specs ne contiennent **jamais de secrets réels** (clés d'exemple factices) ; l'éventuelle URL Redis documentée ne porte **jamais de credentials** (cf. masquage `_safe_redis_url` de [`core/events.py`](../../backend/app/core/events.py)) ; les valeurs de configuration documentées reflètent les défauts réels de [`config.py`](../../backend/app/config.py).
>
> **Couverture ≥ 80 % (rules 35) — non applicable** : aucun module de code modifié ; la « validation » = écrans de contrôle documentaires ci-dessous + non-régression code.

### Écrans de contrôle documentaires (validation treat-story)

| # | Commande | Résultat attendu |
|---|----------|------------------|
| E1 | `grep -rni "celery" docs/general_specs/` | **0 hit** (hors mention historique expressément tracée en note, ex. « alias historique ») |
| E2 | `grep -rniE "bcrypt\|cost factor\|cost 12" docs/general_specs/` | **0 hit** sur 04/05/06/07/15/16/19 |
| E3 | `grep -rniE "30 min\|30 minutes\|expires_in: 1800" docs/general_specs/07-authentification.md docs/general_specs/15-securite.md docs/general_specs/19-glossaire.md` | **0 hit** (cible : 15 min / 900) |
| E4 | relecture manuelle des liens relatifs (`00-index`, « Voir aussi », renvois inter-chapitres et vers `technical_specs/`) | **tous valides** (AC 4) |
| E5 | tableau de traçabilité dans les notes d'implémentation | chaque ligne : spec ↔ chapitre/ligne ↔ arbitrage ↔ story livreuse (AC 1) |
| E6 | relecture croisée des 6 points (JWT 15 min, Argon2, Celery, surfaces, phasage, bus) specs ↔ code (ou `backend_status.md` si STORY-253 livrée) | **0 écart annoncé vs réel** (AC 2) |

### Non-régression code (aucun code modifié — garde-fous)

- `make backend-test-unit` — inchangé vert (attendu : unique échec préexistant `/api/v1/metrics`, résidu STORY-172 documenté R3 STORY-251 — jamais régressé) ;
- `poetry run pytest backend/tests/unit/test_no_celery_residue.py -v` — reste vert (preuve F1 côté code, non touché) ;
- `make lint && make typecheck` — non impactés (aucun fichier code modifié).

### Tests automatisés nouveaux

- **Aucun** — la story ne crée aucun endpoint ni module ; toute découverte d'écart **code** pendant la revue est signalée (Tâche 9, AC 5) et porteuse d'un bug ou d'une story dédiée, jamais corrigée ici.

## Notes d'implémentation (2026-10-31)

### Gate §7.4 (AC 3)

**Gate acquise par l'utilisateur le 2026-10-31** : arbitrages tranchés en faveur de **l'alignement des specs sur le code réel (source de vérité)** pour F3 (surfaces API réelles), F4 (étapes 1-2 livrées), F5 (JWT 15 min), F6 (bus livré). F1/F2 étaient déjà acquis (création STORY-130). Aucun arbitrage refusé → aucune divergence de gate.

### Fichiers specs modifiés (11)

`docs/general_specs/` : `02-familles-workloads.md`, `03-modele-compute.md`, `04-architecture.md`, `05-stack-technologique.md`, `06-modele-de-donnees.md`, `07-authentification.md`, `09-api.md`, `15-securite.md`, `16-deploiement.md`, `17-automatisation-workflows.md`, `19-glossaire.md` — aucun fichier de code applicatif touché (`git status docs/` : uniquement ces 11 fichiers).

### Tableau de traçabilité (AC 1)

| Spec | Chapitre / site | Arbitrage | Story livreuse |
|---|---|---|---|
| 07 | § Core vs plugin (« Hashage Argon2id ») ; § Flow login (diagramme Argon2id + JWT 15 min) ; § Auth par mot de passe (Argon2id + double lecture bcrypt + re-hash au login) ; § Access token (15 min, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`/`jwt_access_token_expire_minutes`) ; § Clés API (hash Argon2id déterministe) ; § Exemples (`expires_in: 900` ×2) ; § Configuration (`JWT_SECRET_KEY`, `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=15`) | F2, F5 | STORY-130.1, STORY-124.2, STORY-123.1 |
| 15 | § Core vs plugin ; § Ce qui est chiffré (`api_keys.key_hash`/`refresh_tokens.token_hash` Argon2id) ; § Synthèse auth (Argon2id, JWT 15 min) ; § Docker socket (process unique, retrait `windflow-worker` du texte et du compose) | F2, F5, F1 | STORY-130.1, STORY-130.2 |
| 04 | § Pas un système distribué (process unique) ; § Diagramme global (runtime asyncio) ; § Modes léger/standard + plugins (schémas sans worker, Redis « cache + bus Pub/Sub ») ; § Arborescence `tasks/` (asyncio, `background_tasks.py`) ; § Bus d'événements (interface `Bus`, `InMemoryEventBus` défaut + `RedisPubSubEventBus` optionnel canal `windflow:events`, Redis Streams hors périmètre, `LEGACY_EVENT_ALIASES` STORY-162) ; § Performance (tâches async du process API) | F1, F6 | STORY-130.2, STORY-160.2, STORY-162 |
| 05 | § Table core/plugins (cache/bus + traitement asynchrone asyncio) ; § Cache (Redis cache + bus Pub/Sub, fallback mémoire) ; § « Traitement asynchrone — asyncio » (ex-section Celery) ; § Récap dépendances (retrait `celery`, ajout `passlib` + `argon2-cffi`) ; § Services Docker (retrait ligne Celery Worker/`windflow/worker`) | F1, F2 | STORY-130.2, STORY-130.1 |
| 06 | § Vue d'ensemble (bloc « Déploiement phasé » : étapes 1-2 livrées migrations 1661/1662, étape 3 reportée Roadmap Phase 2, contrat `WorkloadAdapter`) ; § Entités workloads (annotation phasage hosts livrée / apps+machines cibles) ; § Entité Cluster (cible non livrée) ; § Migration `targets`→`hosts` (livrée 1661/1662) ; § Migration `host_kubernetes`→`clusters` (cible non livrée) ; § `api_keys.key_hash` (commentaire « hash Argon2id ») | F4, F2 | STORY-166.1→166.6, STORY-174.1, STORY-124.2 |
| 09 | § Structure des endpoints (arborescence complétée : `docker/`, `stacks/`, `deployments/`, `schedules/`, `stats/`, `discovery/`, `registry/`, `ssh-keys/`, `admin/stacks-management/`, `metrics`) ; § Hosts (double nommage `/targets` alias déprécié, `Deprecation`+`Sunset: 2027-01-01`, OpenAPI `deprecated: true`, retrait 2027-01-01) ; § Vue Compute (« Surfaces livrées (transitoires) » : 7 routes dont `browse`/`prune` + renvoi COMPUTE-DOCKER-MAPPING pour `/docker` 35 endpoints — promesse l.439-446 honorée) ; § Transverses : dépréciation `/auth/me` (Sunset 2027-05-31), `/discovery` (2 routes), `/stats` (2), import/export stacks (2), `/admin/stacks-management` (**13 routes réelles**), `/registry/plugins` (2), `/ssh-keys`, `/schedules` (renvoi 17), `GET /metrics` sans auth non enveloppé ; § Sécurité (exemption `/api/v1/metrics`) | F3, F4 | STORY-173, STORY-166.2/166.6, STORY-160.1, STORY-131.2, STORY-250.2, STORY-172, STORY-126/128 (enveloppes) |
| 16 | § Mode léger (compose sans `windflow-worker`/`CELERY_*`, empreinte ~2 containers) ; § Mode standard (compose sans worker ni `CELERY_BROKER_URL`) ; `alembic upgrade head` vérifié cohérent (STORY-120) | F1 | STORY-130.2, STORY-120 |
| 02 | § Backups — planifications exécutées par le moteur asyncio du scheduler core | F1 | STORY-130.2, STORY-160.2 |
| 03 | § Mises à jour d'images — « scheduler core » sans Celery | F1 | STORY-130.2 |
| 17 | § Scheduler core (moteur asyncio au lifespan) ; § Planification cron ; § Diagramme trigger (nœud « Moteur asyncio ») ; § Maintenance planifiée | F1 | STORY-160.2, STORY-130.2 |
| 19 | § Glossaire Access token (15 min) | F5 | STORY-130.1 |

### Écrans de contrôle (section Tests à écrire)

- **E1** Celery sur `docs/general_specs/` : **0 hit** ✅
- **E2** bcrypt/cost sur 04/05/06/07/15/16/19 : **1 hit en 07 l.46 uniquement** — mention **historique volontaire** (« les anciens hashes bcrypt restent acceptés en lecture (double lecture legacy) »), fidèle au code `schemes=["argon2", "bcrypt"]` et expressément couverte par l'exception « mention historique tracée » ✅
- **E3** « 30 min / 30 minutes / expires_in: 1800 » sur 07/15/19 : **0 hit** ✅
- **E4** liens relatifs : 561 liens vérifiés par script sur `docs/general_specs/` — **tous les liens posés/modifiés par cette story sont valides** ; 6 liens cassés **préexistants** vers `../user-guide` (00-index ×3, 03 ×2, 10 ×1) hors périmètre (R1), signalés ci-dessous ✅
- **E5** tableau de traçabilité : section ci-dessus (chaque ligne spec ↔ chapitre ↔ arbitrage ↔ story) ✅
- **E6** relecture croisée 6 points — **contre le code** (R2 : STORY-253/`backend_status.md` non livrée au 2026-10-31) : JWT 15 min (`config.py` l.36 = 15, exemples 900) ; Argon2 (`user_service.py` l.27) ; Celery absent (garde-fou 3 passed + E1) ; surfaces (13 routes stacks-management vérifiées dans `admin/stacks_management.py`, 7 compute, 2 discovery, 2 stats, 2 import/export, 2 registry, alias `/targets`, `/metrics`) ; phasage (migrations `1661`/`1662` présentes, aucune table `apps`/`machines`/`clusters` dans `models/` → annotations exactes) ; bus (`core/events.py` : `Bus` l.280, `InMemoryEventBus` l.316, `RedisPubSubEventBus` l.452, `EVENTS_CHANNEL = "windflow:events"` l.438, `LEGACY_EVENT_ALIASES` l.183) — **0 écart annoncé vs réel** ✅

### Non-régression code

- `poetry run pytest tests/unit/test_no_celery_residue.py -v` : **3 passed** ✅
- `poetry run pytest tests/unit -q` : **3254 passed, 1 failed** — l'unique échec est `test_rbac_exhaustivite::test_every_api_route_is_protected` sur `/api/v1/metrics`, **préexistant prouvé** (résidu STORY-172 documenté R3 STORY-251, aucun code modifié par cette story) ✅
- lint/typecheck : non impactés (aucun fichier code modifié).

### Signalements d'écarts code (AC 5 — jamais corrigés ici)

1. [`backend/app/helper/security.py`](../../backend/app/helper/security.py) : résidu bcrypt brut, **0 consommateur** (`app/` + `tests/`) — candidat purge (même veine que STORY-250.1) ;
2. Docstrings/exemples OpenAPI mensongers `expires_in: 1800/3600` vs 900 s réel : [`auth.py`](../../backend/app/api/v1/auth.py) l.150/450/731 et [`schemas/user.py`](../../backend/app/schemas/user.py) l.259/318/370 ;
3. Plan §F3 annonçait « 15 endpoints » `admin/stacks-management` vs **13 réels** — écart tracé, la spec 09 documente 13 ;
4. [`env.example`](../../env.example) l.84 : `ACCESS_TOKEN_EXPIRE_MINUTES=60` — nom sans alias côté code (champ réel `jwt_access_token_expire_minutes` → `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`) **et** valeur ≠ défaut réel (15) ; `SECRET_KEY` l.35 vs `JWT_SECRET_KEY` (seul nom consommé) — candidat nettoyage (hors périmètre, `env.example` explicitement non modifié par cette story) ;
5. Liens cassés préexistants `../user-guide` (00-index, 03, 10) — hors périmètre, à traiter par une story doc dédiée ou STORY-253.

### Divergences par rapport à l'analyse

Aucune divergence d'exécution. Trois ajouts assumés, tous pré-autorisés par l'analyse : (a) résidu F1 `windflow-worker` purgé en spec 15 § Docker socket (texte + compose, cohérence E1/E6 — la spec 15 n'était pas listée pour F1 au tableau contractuel mais l'analyse exige « plus d'écart annoncé vs réel ») ; (b) mention transverse `/api/v1/metrics` ajoutée à § Sécurité de la spec 09 (liste des endpoints sans auth, cohérence AC 4/E6) ; (c) D3 : nom réel `JWT_ACCESS_TOKEN_EXPIRE_MINUTES`/`JWT_SECRET_KEY` documenté (aucun alias `ACCESS_TOKEN_EXPIRE_MINUTES`/`SECRET_KEY` consommé côté code pour le JWT — `SECRET_KEY` ne subsiste qu'en spec 15 comme concept de clé maîtresse de chiffrement, fidèle au `SecretManager`).

### Difficultés rencontrées

Mineures : l'outil d'édition a nécessité un contournement script pour `kanban.md` (erreur technique de l'outil, sans impact contenu) ; le hunk `expires_in` l.111 collé au bloc json (indentation 4 espaces) — résolu par bloc dédié.
