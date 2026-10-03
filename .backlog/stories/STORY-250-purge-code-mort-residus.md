# STORY-250 : Purge du code mort et résidus + dépréciation `/auth/me` (P3-1 + P3-3)

**Statut :** TODO
**Epic Parent :** EPIC-014 — P3 : Finitions & purge (remédiation backend)
**Item plan :** P3-1 (axes E1, E3, E4, E6, E7, E8, E2 partiel) + P3-3 (axe E9) — ampleur **M** (fusion de deux items S du plan)

## Description

En tant que développeur WindFlow, je veux purger le code mort et les résidus identifiés par le plan de remédiation (permissions legacy, contrats non consommés, stub trompeur, service orphelin, print de debug) et résoudre la duplication `/users/me` vs `/auth/me` en dépréciant proprement `/auth/me`, afin que le code livré ne contienne plus **aucun symbole orphelin** et que le contrat API ne présente plus deux entrées pour une même ressource.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §6.1, §12, §17) : plusieurs modules existants ne sont importés nulle part et entretiennent un écart « annoncé vs réel » — [`helper/permissions.py`](../../backend/app/helper/permissions.py:64) (policies/groups/cron legacy), [`core/abstractions.py`](../../backend/app/core/abstractions.py:13) (ABC non consommées), le stub [`workflows.py`](../../backend/app/api/v1/workflows.py:17) qui retourne toujours `[]`, le service simulé orphelin [`litellm_service.py`](../../backend/app/services/litellm_service.py:24), le print de debug [`main.py:12`](../../backend/app/main.py:12), et la duplication d'endpoints `/users/me` ([`users.py:171`](../../backend/app/api/v1/users.py:171)) vs `/auth/me` ([`auth.py:756`](../../backend/app/api/v1/auth.py:756)).

## Contexte technique

*(à remplir par analyse-story)*

Décisions « purger OU ressusciter » déjà tranchées par le plan §2.E — **à reprendre et argumenter item par item dans les notes d'implémentation** :

| Item | Zone de code | Décision du plan | Justification |
|------|--------------|------------------|---------------|
| E1 | [`helper/permissions.py:64`](../../backend/app/helper/permissions.py:64) | **Purger** | Le RBAC cible (endpoint-based `require_role(...)`, STORY-121/122) est livré en P1 — ne pas ressusciter un modèle legacy divergent |
| E3 | [`helper/croniter.py`](../../backend/app/helper/croniter.py) | **Conditionnel** : conservé si STORY-160 l'a consommé (moteur scheduler), sinon purger | « Seul consommateur crédible = scheduler » — dépendance croisée à documenter explicitement |
| E4 | [`core/abstractions.py:13`](../../backend/app/core/abstractions.py:13) | `CacheManager` conservé si STORY-168 l'a consommé ; `DatabaseManager` **purger** si non consommé | Éviter un contrat mort ; en supprimer la partie inutile |
| E6 | [`workflows.py:17`](../../backend/app/api/v1/workflows.py:17) | **Purger** | Arbitrage des specs : workflows = plugins n8n, pas du core ; le stub trompe le contrat API |
| E7 | [`litellm_service.py:24`](../../backend/app/services/litellm_service.py:24) | **Purger du core** | Spec 18 positionne l'IA en plugin (recréer en plugin IA Roadmap Phase 5) |
| E8 | print de debug [`main.py:12`](../../backend/app/main.py:12) | **Purger** | Trivial |
| E2 (partiel) | `HealthCheck` de [`resilience.py`](../../backend/app/core/resilience.py) | **Purger la classe** | Redondante avec [`target_service.check_all_health()`](../../backend/app/services/target_service.py:30) — le reste du module (`CircuitBreaker`) est traité par STORY-251 |
| E9 | duplication [`/users/me`](../../backend/app/api/v1/users.py:171) vs [`/auth/me`](../../backend/app/api/v1/auth.py:756) | **Déprécier `/auth/me`** | Convention REST (ressource utilisateur sous `/users`) ; éviter deux contrats pour une ressource |

Contraintes et gardes-fous :
- Ne toucher **aucun** des points forts §2.G du plan (module Docker, WebSocket modulaire, scan de cibles…) ;
- La purge de `croniter.py` n'est statuée **qu'une fois STORY-160 exécutée** (chaîne critique n°3 du plan §5 : scheduler → purge croniter) ;
- La dépréciation de `/auth/me` suit la RFC de dépréciation HTTP : header `Deprecation: true` + header `Sunset: <date de retrait planifiée>` (le plan P3-3 cite le header `Deprecation`, la mission précise `Sunset` — **les deux** sont posés), champ OpenAPI `deprecated: true` avec note de remplacement vers `/users/me`, et removal planifié documenté ;
- Vérifier qu'aucun consommateur interne (frontend, CLI) n'appelle encore `/auth/me` avant de planifier le retrait.

## Critères d'acceptation (AC)

- [ ] AC 1 : `grep`/import-check sur le dépôt → **aucun symbole orphelin** : les fichiers/membres supprimés (E1, E6, E7, E8, `HealthCheck`, `DatabaseManager` si non consommé) n'ont plus aucune référence (imports, tests, docs générées) ; OpenAPI ne référence plus `/workflows` ; CI et tests verts.
- [ ] AC 2 : Chaque décision purger/ressusciter est **argumentée par item** (tableau E1/E3/E4/E6/E7/E8/E2/E9) dans les notes d'implémentation — y compris le statut conditionnel de `croniter.py` selon ce que STORY-160 a livré (conservé comme dépendance du scheduler, ou supprimé).
- [ ] AC 3 : `/auth/me` répond toujours 200 (compatibilité) avec les headers `Deprecation: true` et `Sunset: <date>` + note OpenAPI `deprecated: true` indiquant le remplacement par `/users/me` et le retrait planifié ; `/users/me` est inchangé et demeure l'endpoint contractuel.
- [ ] AC 4 : Aucune régression des points forts §2.G ; les tests existants passent ; les tests référençant les éléments purgés sont nettoyés.
- [ ] AC 5 : Build + lint + tests passent (`make lint`, `make backend-test`).

## Références spécification

- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P3-1 et P3-3, §2.E (décisions E1-E9 item par item), §5 chaîne critique n°3 (scheduler → croniter), §8.1 (P3 couvre E1-E9) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.16 (stub `workflows.py`), §4.5 (résilience non câblée), §6.1 (RBAC : permissions legacy code mort, lignes ~508-509), §9 (abstractions non consommées), §12 (IA simulée orpheline), §17 (print debug `main.py:12`, duplication `/users/me` vs `/auth/me`) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § Endpoints transverses › Authentification — `/api/v1/auth/` (contrat impacté par la dépréciation, coordination avec STORY-252 pour la spec) ;
- [`07-authentification.md`](../../docs/general_specs/07-authentification.md) — § Endpoints auth (périmètre des endpoints `/auth/*`) ;
- `.roo/rules/01-Project-management.md` — règle d'or backlog (les fichiers purgés du code ne concernent pas le backlog).

## Dépendances

- **STORY-160** (EPIC-013) — le sort de `croniter.py` dépend de sa consommation par le moteur scheduler (chaîne critique du plan §5).
- **STORY-168** (EPIC-013) — le sort de `CacheManager`/`core/abstractions.py` dépend de sa consommation par le cache avec fallback mémoire (E4).
- **STORY-130.2** (EPIC-012) — purge Celery effective (l'écran de contrôle grep doit trouver un dépôt déjà nettoyé côté Celery).
- Les vagues P0-P2 doivent être terminées avant finalisation (cette epic clôt le cycle de remédiation).

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
