# STORY-164 : Canaux WebSocket manquants + durcissement du protocole — `/ws/ssh`, `/ws/journal`, `/ws/batch`, heartbeats avec expiration, ack et reconnexion unifiée (P2-5, partie durcissement — axes C3, C4)

**Statut :** TODO
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend)
**Item plan :** P2-5 (axes C3, C4, rapports §8) — ampleur **L**

## Description

En tant qu'utilisateur WindFlow, je veux que les canaux WebSocket canoniques manquants (`/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}`) soient ajoutés aux 5 canaux existants et que le protocole soit durci — authentification obligatoire généralisée (dépend STORY-100), heartbeats avec expiration des connexions muettes, acknowledgment des messages critiques et politique de reconnexion unifiée avec jitter — afin que le temps réel couvre les usages spécifiés (SSH Host, journal système, opérations groupées) et ne laisse plus de connexions zombies.

**Problème constaté** ([WEBSOCKET-REAL-TIME.md §3.2, §8](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md)) : 4 canaux canoniques non montés (`console` VNC, `ssh`, `journal`, `batch`) ; le nommage réel `/api/v1/ws/...` diverge de `/ws/...` ; le serveur **n'expire pas** une connexion silencieuse (aucun contrôle des `pong`, `receive_text()` attend indéfiniment) ; l'acknowledgment est non implémenté ; la reconnexion n'est pas unifiée (backoff 1/2/4 s × 3 sur le canal général vs 5 × 2 s fixes sur les canaux dédiés, sans jitter ni resynchronisation d'état).

## Contexte technique

*(à remplir par analyse-story)*

Éléments existants à réutiliser / contraintes :
- **Auth** : STORY-100 (P0-1) rend le refus sans token obligatoire sur les 5 canaux — les nouveaux canaux naissent avec ; convergence du mécanisme (JWT query param généralisé, cible ch. 09) vs premier-message (canal général/terminal) à trancher à l'analyse ;
- **Canal `/ws/ssh/{host}`** : s'appuie sur STORY-131 (SSH keys + empreintes anti-MITM — la mission et l'epic corrigée citent bien **STORY-131**, pas 128) et les runners [`commands.py:167`](../../backend/app/services/commands.py:167) / [`socket_clients.py`](../../backend/app/services/socket_clients.py) ; le canal `/ws/terminal` reste réservé aux containers (consoles Machines = `/ws/console`) ;
- **Canal `/ws/journal/{host}`** : journal système du Host (`journalctl` via SSH — verbe Host spec 02) ; ≠ logs d'App (`/ws/logs`) ;
- **Canal `/ws/batch/{batch_id}`** : progression des opérations groupées (batch update, check-updates — messages `start`/`progress`/`complete`/`error`, enveloppe `type`/`data` spec 09) ; alimenté par l'orchestration batch (à câbler côté émission) ;
- **Console VNC explicitement reportée** aux phases Roadmap VMs (machines — plan §6 « Console VNC / canaux WS liés aux machines ») : **ne pas implémenter** `/ws/console/{machine_id}`, le noter dans la doc ;
- **Heartbeats** : expiration serveur si aucun `pong` sous ~2 intervalles (cible §8.2) ; le heartbeat 30 s existant est conservé comme base ;
- **Ack** (cible §8.4) : champ `id` UUID sur les messages critiques, ack client `{"type":"ack","data":{"id":…}}`, rétention par connexion TTL ~30 s avec re-diffusion à la reconnexion, dégradation en logs/métriques au-delà ; **pas d'ack** pour streaming de logs, heartbeats, toasts éphémères ;
- **Reconnexion unifiée** : un seul algorithme tous canaux, backoff avec **jitter** (anti-tempête), re-souscription automatique, resynchronisation d'état après reconnexion (refaire un `GET` de la ressource suivie), pas de retry sur fermetures d'auth (1008/1003) ;
- **Client type documenté** (critère de done) : documenter le comportement attendu du client (auth, ping/pong, ack, reconnexion) — côté spec technique WEBSOCKET-REAL-TIME et README du module ;
- Zones : [`websocket/`](../../backend/app/websocket) (handlers, [`connection_managers.py:27`](../../backend/app/websocket/connection_managers.py:27), [`broadcasting.py`](../../backend/app/websocket/broadcasting.py)), router [`api/v1/websockets.py:27`](../../backend/app/api/v1/websockets.py:27) ; frontend [`services/websocket.ts`](../../frontend/src/services/websocket.ts) + composables à synchroniser ;
- Garde-fou §2.G : WebSocket modulaire — étendre sans casser l'architecture plugins interne ni les 5 canaux existants.

## Critères d'acceptation (AC)

- [ ] AC 1 : Les 3 canaux `/ws/ssh/{host}`, `/ws/journal/{host}`, `/ws/batch/{batch_id}` sont montés avec auth obligatoire — tests : connexion **sans token → refusée (401/fermeture 1008)** sur chacun ; avec token valide → connecté ; un viewer ne peut pas ouvrir un canal d'opération (RBAC par action WS, spec 15) ; `/ws/console` VNC explicitement absent et documenté comme reporté (Roadmap VMs).
- [ ] AC 2 : `/ws/ssh/{host}` ouvre une session SSH interactive vers le Host (via STORY-131 : clé référencée + empreinte vérifiée — divergeance d'empreinte = blocage), `/ws/journal/{host}` streame le journal système, `/ws/batch/{batch_id}` diffuse `start`/`progress`/`complete` d'une opération groupée simulée — chacun testé avec un abonné authentifié (mock des runners SSH/journal côté tests unitaires).
- [ ] AC 3 : **Heartbeats avec expiration** : une connexion qui ne répond pas (aucun `pong` sous ~2 intervalles) est fermée côté serveur — test avec mock client muet ; les heartbeats streaming/logs restent exclus de l'ack ; **acknowledgment** implémenté pour les messages critiques : le client accuse réception, un message non acquitté au-delà du TTL (~30 s) est re-diffusé à la reconnexion et la dégradation est journalisée/mesurée.
- [ ] AC 4 : **Reconnexion unifiée avec jitter** : une seule politique documentée et implémentée côté client type (backoff + jitter, re-souscription, resynchronisation d'état par GET, jamais de retry sur 1008/1003) — testée sur au moins un canal dédié et le canal général ; le client type (comportement attendu) est documenté.
- [ ] AC 5 : Non-régression : les 5 canaux existants (général, deployment logs, terminal, container logs/stats) fonctionnent toujours ; `disable_auth` en dev préservé ; couverture ≥ 80 % sur les modules touchés (les tests dédiés sont renforcés par STORY-165) ; build + lint + tests passent.

## Références spécification

- [`09-api.md`](../../docs/general_specs/09-api.md) — **§ WebSocket** (référence unique des 8 canaux canoniques, JWT en query parameter, format des messages, `/ws/batch` progression des opérations groupées) ;
- [WEBSOCKET-REAL-TIME.md](../../docs/technical_specs/WEBSOCKET-REAL-TIME.md) — §3 (canaux, état implémenté vs cible, écart d'authentification), §7 (auth par canal), §8.2 (heartbeat + expiration cible ~2 intervalles), §8.3 (reconnexion : politique unifiée, jitter, resynchronisation), §8.4 (acknowledgment cible complet), §10.3 (écarts) ;
- [`02-familles-workloads.md`](../../docs/general_specs/02-familles-workloads.md) — § Famille Hosts (verbes SSH, journalctl — usages des canaux `/ws/ssh` et `/ws/journal`) ;
- [`15-securite.md`](../../docs/general_specs/15-securite.md) — § Authentification et RBAC (permissions vérifiées sur chaque action WebSocket), § Hosts distants SSH (clés réutilisables, empreintes, anti-tempête) ;
- [`04-architecture.md`](../../docs/general_specs/04-architecture.md) — § WebSocket (usages temps réel), § Performance (connexions simultanées cibles) ;
- [`backend_remediation_plan.md`](../../docs/backend_remediation_plan.md) — §4 P2-5, §2.C C3/C4, §6 (VNC hors périmètre), §5 chaîne n°2 (P1-9 → P2-5) ;
- [`backend_status.md`](../../docs/backend_status.md) — §3.17, §8 (module WebSocket), §13.4 (zéro test WS).

## Dépendances

- **STORY-100** (auth WS obligatoire — EPIC-011) et **STORY-131** (SSH keys + empreintes — EPIC-012).
- **STORY-165** (tests WebSocket) couvre la suite de tests dédiée — analyse conjointe recommandée.
- Interagit avec **STORY-162/163** (bridge/nomenclature transport) ; les opérations groupées alimentant `/ws/batch` suivront la surface élargie (STORY-173).

## Sous-stories

*(section réservée — story L : `analyse-story` pourra découper par famille de canaux ou par mécanique protocole ; plage réservée STORY-175-199)*

## État d'avancement technique

*(à remplir par analyse-story)*

## Tâches d'implémentation détaillées

*(à remplir par analyse-story)*

## Tests à écrire

*(à remplir par analyse-story)*
