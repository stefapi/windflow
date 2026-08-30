# STORY-162 : Bus d'événements canonique — interface unique, nomenclature des ~18 événements, in-memory par défaut + Redis Pub/Sub optionnel (P2-2, partie bus — arbitrage F6)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-2 (axes B7, C5, F6, rapports §6/§8) — ampleur **L**

## Description

En tant que développeur backend WindFlow, je veux un **bus d'événements canonique** exposant une interface unique et la nomenclature exacte des ~18 événements de la spec 11 (`deployment.succeeded` — jamais `completed` —, `host.*` — jamais `target.*` —, `container.*`, `stack.deployed`…), avec l'implémentation in-memory par défaut (mode léger RPi) et une implémentation Redis Pub/Sub activée quand `cache_url` est configuré, afin que plugins, scheduler et pont WebSocket consomment un contrat stable conforme aux specs au lieu d'un enum divergent et de stubs Redis morts.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §9.2-9.4, [WEBSOCKET-REAL-TIME.md §10.2](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : l'enum `EventType` de [`events.py`](../../backend/app/core/events.py:115) suit le format mais **pas la liste** canonique (`deployment.completed` au lieu de `succeeded`, `target.*` au lieu de `host.*`, domaines `container.*`/`machine.*` manquants, domaines extra-canoniques `organization.*`/`user.*`/`system.*`) ; les stubs Redis Streams (lignes 144, 227, 255, 298, 321, 376) sont des coquilles TODO ; l'arbitrage F6 tranche : interface canonique + 2 implémentations, Streams complets (replay/event sourcing) hors périmètre.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Arbitrage F6 (tranché)** : extraire une interface `Bus` canonique ; garder l'EventBus in-memory comme implémentation par défaut (le pont WebSocket [`event_bridge.py`](../../backend/app/websocket/event_bridge.py:20) est un consommateur réel — ne pas casser) ; ajouter l'implémentation **Redis Pub/Sub** activée quand `cache_url` est configuré ; les stubs Redis Streams commentés sont **remplacés** par cette implémentation Pub/Sub ;
- **Nomenclature** : liste canonique des 18 événements (spec 11 § Liste canonique) : `container.created|started|stopped|removed`, `stack.deployed|updated|removed`, `machine.created|started|stopped`, `deployment.started|succeeded|failed`, `host.added|removed|offline`, `plugin.installed|removed` ; « les événements `host.*` remplacent les anciens `target.*` (alias historique) ; `deployment.succeeded` est la forme canonique » ;
- **Migration des émetteurs** : corriger `deployment.completed` → `deployment.succeeded`, `target.*` → `host.*` ; le pont ne mappe aujourd'hui que 5 types déploiement — l'étendre ; **période d'émission double** prévue pour le frontend (risque §7.3 : la nomenclature touche bridge WS et plugins) ;
- **Table de correspondance ancien→nouveau documentée** (critère de done du plan) — à livrer dans la doc technique de l'epic ;
- Zones : [`core/events.py`](../../backend/app/core/events.py:115) (+ stubs lignes 144-376 remplacés), [`websocket/event_bridge.py`](../../backend/app/websocket/event_bridge.py:20), [`services/deployment_events.py`](../../backend/app/services/deployment_events.py:22) ;
- Les domaines extra-canoniques existants (`organization.*`, `user.*`, `system.*`) restent émis mais sont clairement séparés de la liste canonique (pas de silence métier) ;
- `DEPLOYMENT_PROGRESS` (transport WS) : « émis ou retiré » — la décision d'émission est portée par **STORY-163** (consommateurs/plugins) ; cette story aligne le contrat transport sans le dupliquer ;
- Garde-fou §2.G : WebSocket modulaire — étendre le pont sans casser l'architecture plugins interne.

## Critères d'acceptation (AC)

- [ ] AC 1 : Une interface `Bus` canonique (publish/subscribe, typée sur la nomenclature) est extraite ; les ~18 événements spec 11 sont définis en un **unique** référentiel ; sans Redis configuré, le comportement in-memory est intact (tests de non-régression du pont WebSocket : les abonnés `deployment.*` reçoivent bien les événements).
- [ ] AC 2 : Avec Redis configuré (`cache_url`), un événement publié est **visible sur le canal Pub/Sub** (test d'intégration avec Redis réel) ; sans Redis, aucune tentative de connexion, aucun warning répété ; les stubs Redis Streams (lignes 144-376) sont supprimés et remplacés par l'implémentation Pub/Sub — Streams/replay restent hors périmètre (noté).
- [ ] AC 3 : **Chaque événement canonique est émis par son émetteur réel** — tests : `deployment.succeeded` émis au statut `success` (plus jamais `deployment.completed`), `host.added`/`host.removed` émis à la création/suppression d'une cible (plus jamais `target.*`), `container.started`/`stopped`, `stack.deployed`, `plugin.installed`/`removed` vérifiés sur un échantillon représentatif ; la **table de correspondance ancien→nouveau est documentée** et une période d'émission double (ancien nom + canonique) est active pour le frontend, bornée dans le temps.
- [ ] AC 4 : Le pont `event_bridge.py` mappe l'ensemble des événements canoniques vers les types transport pertinents (extension du mapping déploiement-seul actuel) ; la fragilité connue (`emit()` avec un `WebSocketEventType` réencapsulé en `system.error`) n'est plus dépendue et est corrigée ou supprimée.
- [ ] AC 5 : Tests de sécurité/non-régression : consommateurs existants (bridge WS, modules `deployment_monitor`, `subscription`) non cassés ; couverture ≥ 80 % sur les modules touchés ; build + lint + tests passent.

## Références spécification

- [`11-plugins.md`](../../docs/general_specs/11-plugins.md) — § Système d'événements / **Liste canonique des 18 événements** (référence unique du nommage, alias interdits), § Bus d'événements (Redis Pub/Sub en mode standard, `asyncio.Queue` en mode léger, interface identique pour les plugins) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § Bus d'événements internes (nomenclature `domaine.action_passé`, modes léger/standard) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (événements système `/ws/events` au nommage canonique) ;
- [`17-automatisation-workflows.md`](../../docs/general_specs/17-automatisation-workflows.md) — § Triggers (scheduler notifié par le bus, liste canonique) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §4 (deux couches d'événements, pont, articulation), §10.2 (bus semi-canonique : écarts `deployment.completed`/`target.*`, domaines manquants/extra) ;
- [ARCHITECTURE-MODULAIRE.md](../../docs/technical_specs/ARCHITECTURE-MODULAIRE.md) — briques optionnelles (brique `cache` Redis) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-2, §2.B B7, §2.C C5, §3 F6, §7.3 (période d'émission double) ;
- [`backend_status.md`](../../docs/backend_status.md) — §9.2-9.4, §8.3.

## Dépendances

- **Aucune dépendance dure P1** (le plan marque P2-2 « dépend de : — ») ; néanmoins les enveloppes API (STORY-126) ne concernent pas le bus — indépendant.
- **STORY-163** (consommateurs plugins) s'appuie sur cette story ; le trigger événement du scheduler (**STORY-160**) consomme la nomenclature ; **STORY-167** (deployment_events) s'aligne sur elle ; notifications P2-15 en dépend.

## Sous-stories

*(non prévue — story L ; découpe possible par l'analyse si la migration des émetteurs s'avère trop invasive)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
