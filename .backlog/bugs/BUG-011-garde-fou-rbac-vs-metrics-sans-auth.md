# BUG-011 : Garde-fou RBAC vs `/api/v1/metrics` sans auth — arbitrer le contrat (résidu STORY-172)

**Statut :** DONE
**Gravité :** Majeur

> Constaté lors de la revue finale de conformité (STORY-254.3, 2026-11-07) ; signalé initialement par STORY-251/252, jamais arbitré.

## Reproduction
1. `cd backend && poetry run pytest tests/unit/test_api/test_rbac_exhaustivite.py -q`
2. Observer `TestEveryApiRouteIsProtected::test_every_api_route_is_protected` → **FAILED**

## Comportement attendu
Le garde-fou d'exhaustivité RBAC (`test_rbac_exhaustivite.py` — chaque route API doit être protégée) et l'endpoint `GET /api/v1/metrics` ([`backend/app/api/v1/metrics.py`](../../backend/app/api/v1/metrics.py) l.28) doivent être **contractuellement cohérents** : soit la route est explicitement exemptée dans le garde-fou (metrics sans auth = design documenté — scrape interne Docker, rules 45 : « sans auth, jamais enveloppé »), soit elle est protégée (contradiction avec rules 45 à lever alors).

## Comportement actuel
L'endpoint est servi **sans authentification** (design scrape STORY-172) tandis que le garde-fou historique attend un contrôle d'accès sur chaque route → échec permanent de la suite RBAC depuis STORY-172 (~1 mois), masquant potentiellement de futures régressions réelles sur ce garde-fou.

## Résolution

Corrigé le 2026-11-07 (cycle NEW → CONFIRMED → IN_PROGRESS → REVIEW → DONE parcouru lors de la session de correction).

### Arbitrage retenu

**Exemption explicite et documentée dans le garde-fou** (option 1 du contrat) : `metrics` sans auth est un design documenté par la rules 45 (`.roo/rules/45-observability.md` — « `GET /api/v1/metrics` **sans auth** (scrape interne Docker), format texte Prometheus, jamais enveloppé ») et par la docstring du module [`metrics.py`](../../backend/app/api/v1/metrics.py) (exemptions spec 09, pattern `system`, scrape réseau interne Docker uniquement, aucun router Traefik n'expose le chemin). La rules 45 étant une source de vérité de niveau supérieur au test, c'est le garde-fou qui devait être aligné — pas l'endpoint.

### Correctif appliqué

- [`backend/tests/unit/test_api/test_rbac_exhaustivite.py`](../../backend/tests/unit/test_api/test_rbac_exhaustivite.py) : ajout de `"/api/v1/metrics"` à `PUBLIC_PATHS` avec commentaire renvoyant à la rules 45, à STORY-172 et au présent bug (entrée motivée, revue obligatoire pour tout ajout ultérieur).

### Vérification

- `poetry run pytest tests/unit/test_api/test_rbac_exhaustivite.py -q` → **6 passed** (suite RBAC verte, sans xfail) ;
- `test_public_whitelist_minimal` confirme que chaque entrée blanchie est une route réelle (pas de fantôme) ;
- Aucun autre test n'utilisait d'xfail sur ce point (écran grep : 0 xfail résiduel dans la suite RBAC).

### Note

Le tableau de conformité du rapport STORY-254.4 (`docs/backend_conformity_report.md`) mentionnait ce bug comme « 4 bugs ouverts BUG-011→014 » — ce constat historique reste exact à sa date d'écriture ; les 4 bugs ont été corrigés ce 2026-11-07.
