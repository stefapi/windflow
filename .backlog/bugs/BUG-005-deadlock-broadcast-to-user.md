# BUG-005 : Deadlock dans `UserConnectionManager.broadcast_to_user` — purge des connexions mortes sous le lock non-réentrant

**Statut :** NEW
**Gravité :** Bloquant
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)

## Reproduction

1. Connecter un utilisateur via le canal général avec **plusieurs** connexions (onglets multiples), dont au moins une **morte** (socket fermée côté client, `send_json` lève).
2. Déclencher un [`broadcast_to_user`](../../backend/app/websocket/connection_managers.py:310) vers cet utilisateur (ex. notification ciblée, message critique avec ack).
3. L'envoi échoue sur la socket morte → `_broadcast_to_connections` la retourne dans `disconnected` → la purge ([l.333-337](../../backend/app/websocket/connection_managers.py:333)) appelle [`remove_connection`](../../backend/app/websocket/connection_managers.py:235) **sous** `async with self._lock`.
4. `remove_connection` ré-acquiert `self._lock` — un `asyncio.Lock` est **non-réentrant** → la coroutine attend indéfiniment sa propre libération → **deadlock**.

## Comportement attendu

La purge des connexions mortes doit compléter normalement : `remove_connection` est appelée **hors** du lock, et la socket morte est retirée des connexions de l'utilisateur (pattern déjà correct dans [`broadcast_to_event_subscribers`](../../backend/app/websocket/connection_managers.py:339), qui collecte les `disconnected_users` sous le lock puis les purge après libération).

## Comportement actuel

Dès qu'un envoi échoue pour une connexion utilisateur, [`broadcast_to_user`](../../backend/app/websocket/connection_managers.py:334) gèle : l'attente du lock déjà détenu bloque la coroutine, et comme le lock n'est jamais libéré, **toute la chaîne en attente de `self._lock` se fige** (gel de la boucle d'événements pour les chemins qui passent par ce verrou : `add_connection`, `remove_connection`, souscriptions, autres broadcasts user). Un seul client déconnecté impoliment peut donc paralyser le temps réel utilisateur.

## Test documentant le bug

- [`test_broadcast_purges_dead_connections`](../../backend/tests/unit/test_websocket/test_connection_managers.py:438) — marqué `xfail(strict=True)` avec `asyncio.wait_for(timeout=1.0)` : le deadlock actuel lève `TimeoutError` (→ xfail) ; une fois corrigé, le test XPASS et **échoue**, forçant le retrait du marquage.
- Note de divergence dans l'en-tête du fichier de test (l.27-29).

## Résolution

*(à compléter à la résolution — piste suggérée : sortir l'appel à `remove_connection` du bloc `async with self._lock`, en s'inspirant du pattern de `broadcast_to_event_subscribers`)*
