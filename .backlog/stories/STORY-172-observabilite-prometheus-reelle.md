# STORY-172 : Observabilité Prometheus réelle — instrumentation `/metrics` (latence, erreurs, déploiements ok/ko, tâches scheduler), câblage de `websocket/metrics.py` et dashboards alimentés (P2-9 — axes B4, E5)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-9 (axes B4, E5, rapports §15) — ampleur **M**

## Description

En tant qu'opérateur WindFlow, je veux que `prometheus_enabled=True` corresponde à une **instrumentation réelle** : endpoint `/metrics` exposant sans auth au minimum la **latence des endpoints**, le **taux d'erreur**, les compteurs business **déploiements ok/ko** et les **tâches scheduler** (exécutions par statut) ; que le module défini-mais-jamais-importé [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) soit câblé (ou supprimé si sa fonction est couverte autrement) ; et que les dashboards Grafana provisionnés affichent des données réelles sur un run de démo, afin de remplacer le « Prometheus mensonger » par une observabilité effective.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §11, §14.1, [WEBSOCKET-REAL-TIME.md §10.3](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : `prometheus_enabled=True` dans [`config.py:41`](../../backend/app/config.py) mais **aucune instrumentation** Prometheus dans le code (B4) ; [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) est défini mais **jamais importé** par aucun module (E5 : « ressusciter via B4 sinon purger ») ; les dashboards provisionnés ([`infrastructure/docker/grafana/dashboards/`](../../infrastructure/docker/grafana/dashboards/)) n'ont pas de métriques réelles en face.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Instrumentation HTTP** : réutiliser le **middleware Timing** existant ([`main.py:254`](../../backend/app/main.py) — mesure déjà `X-Process-Time` et log des requêtes lentes) comme point de collecte des histogrammes de latence + compteurs de requêtes/erreurs par endpoint/code — le middleware Correlation ID et Logging ne sont pas modifiés en profondeur (garde-fou §2.G : ne pas régresser les middlewares sécurité) ;
- **Métriques business** : déploiements ok/ko — brancher sur les changements de statut ([`deployment_service.py:23`](../../backend/app/services/deployment_service.py) / événements bus STORY-162) ; tâches scheduler — exécutions par statut (`success`/`failed`/`skipped`) depuis STORY-160/161 ; le module [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) contient déjà des définitions de métriques temps réel (connexions, messages) à **câbler** : décision E5 explicite — importer/consommer, ou supprimer si doublon (le choix doit être documenté dans la story) ;
- **Endpoint `/metrics`** : format Prometheus, **sans auth** (scrapé par Prometheus), conditionné par `prometheus_enabled` (désactivé → endpoint absent ou vide) ; la config Prometheus ([`infrastructure/docker/prometheus.yml`](../../infrastructure/docker/prometheus.yml)) scrape déjà la cible attendue — vérifier/port ;
- **Dashboards** : les deux dashboards provisionnés (`windflow-deployments.json`, `windflow-system-overview.json`) doivent référencer les métriques réellement exposées — corriger les requêtes si besoin (pas de nouvelles métriques fantômes) ;
- **Rules 45** : métriques obligatoires = latence endpoints, taux d'erreur par service, métriques business (déploiements ok/ko) ; alertes définies dans `prometheus-alerts.yml` (existant — vérifier cohérence) ;
- Dépendance à ajouter si nécessaire : bibliothèque client Prometheus (ex. `prometheus-client`) — justification claire requise (rules 05 : pas de dépendance sans justification) ; format JSON des logs inchangé ;
- ⚠️ **Constat STORY-165 (2026-10-24, à traiter impérativement ici)** : `prometheus_client` est importé **en top-level** dans [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) ([`from prometheus_client import Counter, Gauge, Histogram`](../../backend/app/websocket/metrics.py:14)) mais **n'est PAS déclarée dans `pyproject.toml`** (seul un override mypy la mentionne, [`pyproject.toml:118`](../../pyproject.toml)) → tout import du module crasherait en production/CI (`ModuleNotFoundError`). Les tests STORY-165 ([`test_ws_metrics_helpers.py`](../../backend/tests/unit/test_websocket/test_ws_metrics_helpers.py:32)) l'ont géré via `pytest.importorskip` + installation pip locale. **Cette story doit ajouter la dépendance Poetry `prometheus_client` (avec version justifiée)** — c'est un prérequis au câblage AC 3 (décision E5) ;
- Corrélation : le correlation ID existe déjà — pas d'OpenTelemetry (prévu mais non implémenté, hors périmètre).

## Critères d'acceptation (AC)

- [ ] AC 1 : `/metrics` (sans auth) expose au minimum : **latence des endpoints** (histogramme par route), **taux d'erreur** (compteur par code/route), **déploiements ok/ko** (compteurs business), **tâches scheduler** (exécutions par statut) — test : requêtes + un déploiement de test + une exécution de tâche → les séries attendues sont présentes dans la réponse `/metrics` (format Prometheus valide).
- [ ] AC 2 : Le flag `prometheus_enabled` gouverne réellement : désactivé → pas d'instrumentation ni d'endpoint `/metrics` (ou réponse vide 404 selon choix documenté) ; activé → tout est exposé — les deux états testés.
- [ ] AC 3 : **Décision E5 appliquée et documentée** sur [`websocket/metrics.py`](../../backend/app/websocket/metrics.py) : soit câblé (importé/consommé — ses métriques temps réel apparaissent dans `/metrics` quand des connexions WS actives existent), soit supprimé au profit de définitions équivalentes centralisées — plus aucun module « défini mais jamais importé » ; la dégradation d'ack (STORY-164) y est mesurable si câblé.
- [ ] AC 4 : **Dashboards alimentés** : sur un run de démo (API + trafic + 1 déploiement + 1 tâche), les deux dashboards Grafana provisionnés affichent des données — vérification documentée (captures ou requêtes Prometheus vérifiées) ; les requêtes de dashboards corrigées vers les vraies séries ; `prometheus-alerts.yml` cohérent avec les métriques exposées.
- [ ] AC 5 : Non-régression : middlewares sécurité/timing/correlation non cassés ; overhead d'instrumentation négligeable (pas de sérialisation bloquante par requête) ; couverture ≥ 80 % sur les modules d'instrumentation testables ; build + lint + tests passent.

## Références spécification

- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Résilience et fiabilité (health checks), § Performance (benchmarks cibles), § Bus d'événements (sources business) ;
- `.roo/rules/45-observability.md` — **métriques obligatoires** (latence endpoints, taux d'erreur par service, métriques business déploiements ok/ko), outils cibles Prometheus + Grafana, dashboards provisionnés, alertes ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Sécurité réseau (ports exposés — `/metrics` interne au scrape, pas exposé Internet), § Principes (pas de données sensibles dans les métriques/labels) ;
- [ARCHITECTURE-MODULAIRE.md](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) — brique `monitoring` (Prometheus + Grafana, activation `make enable-monitoring`, volumes, provisioning) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §2.2 (`metrics.py` défini mais non intégré), §8.4 (dégradation ack mesurée par `metrics.py`), §10.3 ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-9, §2.B B4 (« Prometheus mensonger »), §2.E E5 ;
- [`backend_status.md`](../../docs/backend_status.md) — §11 (`prometheus_enabled=True` sans instrumentation), §14.1, §2.3 (middlewares — point de collecte).

## Dépendances

- **Aucune dépendance marquée par le plan** (P2-9 « dépend de : — »).
- Les métriques scheduler (STORY-160/161) et déploiements (événements STORY-162) ne sont complètes que si ces stories sont fusionnées — sinon instrumenter ce qui existe et étendre (le tracer dans l'analyse) ; interagit avec STORY-164 (métriques WS/ack).

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
