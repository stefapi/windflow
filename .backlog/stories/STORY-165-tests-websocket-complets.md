# STORY-165 : Tests WebSocket — couverture complète du module temps réel (handlers, managers, plugins, souscriptions, auth) (P2-5, partie tests — axes C9, C14)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-5 / P2-14 partie WebSocket (axes C9, C14, rapport §16) — ampleur **M**

## Description

En tant que développeur backend WindFlow, je veux une **suite de tests dédiée** couvrant l'ensemble du module WebSocket — connexions aux canaux, authentification, heartbeats/expiration, acknowledgment, re-souscription, managers de connexions, modules de broadcast internes (plugins) et pont bus→WS — afin de combler le **zéro test** actuel sur cette zone critique (plan §7.2 : les zones à zéro test doivent être couvertes au fil des vagues, pas en fin de projet) et de sécuriser les durcissements de STORY-164.

**Problème constaté** ([`backend_status.md`](../../docs/backend_status.md) §13.4) : **aucun test** sur le module websocket ; les 5 canaux, les managers ([`connection_managers.py:27`](../../backend/app/websocket/connection_managers.py:27)), les modules internes et le pont fonctionnent sans filet — rendant chaque durcissement (heartbeats, ack, reconnexion) risqué.

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Fixtures** : [`tests/conftest.py:42`](../../backend/tests/conftest.py) (client `httpx.AsyncClient` + `ASGITransport`, override `get_db`) — pour WebSocket, utiliser le transport WS de httpx/Starlette (`client.websocket_connect`) avec les mêmes overrides ;
- **Périmètre de tests** (critère P2-5 : « suite de tests WS : connexion, auth, heartbeat timeout, re-souscription ») : canal général (auth premier message, timeout 30 s, subscribe/unsubscribe, dispatch), canaux dédiés (deployment logs, terminal, container logs/stats — avec mocks des services Docker/terminal), nouveaux canaux de STORY-164 (ssh/journal/batch — mock des runners), managers (`ConnectionManager`, `UserConnectionManager` : abonnements par utilisateur, dispatch), broadcasting (fonctions `broadcast_*`, `broadcast_to_event_subscribers`), pont [`event_bridge.py:20`](../../backend/app/websocket/event_bridge.py:20) (mapping événement canonique → type transport), modules internes (`audit_logger`, `deployment_monitor`, `subscription`, `deployment_notifications` enregistré par STORY-163), protocole (ping/pong, expiration des connexions muettes, ack TTL, re-diffusion à la reconnexion) ;
- **Sécurité** (rules 35 + 40) : tests obligatoires — connexion sans token refusée (par canal), token invalide expiré, RBAC par action WS (viewer bloqué sur canal d'opération), isolation organisationnelle (accès à un déploiement d'une autre org refusé — comportement existant de [`deployment_logs.py:23-48`](../../backend/app/websocket/deployment_logs.py) à couvrir) ;
- Coordonnée avec **STORY-164** (durcissements) : cette story capture en tests les comportements livrés par 164 et le legacy ; si 164 n'est pas encore fusionnée, écrire d'abord les tests du comportement actuel puis les étendre ;
- Cible de couverture : **≥ 80 %** du module websocket (contribution à la cible par domaine du plan P2-14).

## Critères d'acceptation (AC)

- [ ] AC 1 : Suite de tests de **connexion et auth** : chaque canal existant + nouveaux canaux — sans token → refus (401/1008) ; token valide → connecté ; token invalide → fermeture ; timeout d'auth (30 s) simulé ; `disable_auth` en dev toujours fonctionnel.
- [ ] AC 2 : Suite de tests de **protocole** : ping/pong, heartbeat serveur, expiration d'une connexion muette (~2 intervalles), acknowledgment des messages critiques (ack, TTL ~30 s, re-diffusion à la reconnexion, exclusion streaming/logs), re-souscription (`subscribe`/`unsubscribe`, `deployment_logs`) — conformes aux cibles de STORY-164.
- [ ] AC 3 : Suite de tests des **managers, broadcasting et pont** : `ConnectionManager`/`UserConnectionManager` (abonnements multiples, dispatch par utilisateur), `broadcast_*` (déploiement, abonnés d'événements), `event_bridge` (mapping canonique → transport, tous types mappés), modules internes (effets de `audit_logger`, `deployment_monitor`, `subscription`, `deployment_notifications`).
- [ ] AC 4 : Tests de **sécurité WS** : RBAC par action (viewer refusé sur canal d'opération), isolation organisationnelle (déploiement d'une autre org → refus, superadmin excepté), aucune donnée sensible (tokens/secrets) dans les payloads diffusés ; tests de non-régression des 5 canaux existants.
- [ ] AC 5 : Couverture mesurée **≥ 80 %** sur `backend/app/websocket/` (`--cov` par domaine) ; CI verte ; build + lint + tests passent.

## Références spécification

- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §7 (auth par canal), §8 (protocole détaillé : enveloppe, heartbeats, reconnexion, acknowledgment — cibles), §9 (tests manuels wscat à transposer en tests automatisés), §2 (modules à couvrir) ;
- [`09-api.md`](../../docs/general_specs/09-api.md) — § WebSocket (canaux canoniques, format des messages, auth JWT) ;
- `.roo/rules/35-testing-quality-gates.md` — pyramide de tests, cas obligatoires par endpoint, tests de sécurité obligatoires ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-5 (« suite de tests WS ») + P2-14, §2.C C9/C14, §7.2 (couverture au fil des vagues) ;
- [`backend_status.md`](../../docs/backend_status.md) — §13.4 (websocket : aucun test), §8 (inventaire du module à couvrir).

## Dépendances

- **STORY-164** (canaux + durcissement) — les tests capturent ses comportements ; analyse conjointe recommandée (ordre : 164 puis 165, ou itérations croisées).
- Contribution à la cible P2-14 (couverture ≥ 80 % par domaine) — coordonnée avec STORY-173 pour le reste des zones zéro.

## Sous-stories

*(non prévue — story M)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
