# BUG-007 : Clé vide résiduelle dans `ConnectionManager.broadcast_to_deployment` — purge sans nettoyage de l'entrée

**Statut :** NEW
**Gravité :** Mineur
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)

## Reproduction

1. Connecter un ou plusieurs clients au canal `deployment_logs` d'un déploiement `dep-1` (via [`ConnectionManager.connect`](../../backend/app/websocket/connection_managers.py:120)).
2. Fermer toutes les sockets sans déconnexion propre (le handler `disconnect` n'est pas exécuté, ex. crash client / coupure réseau).
3. Déclencher un [`broadcast_to_deployment("dep-1", …)`](../../backend/app/websocket/connection_managers.py:155) : l'envoi échoue sur chaque socket morte → purge ([l.181-184](../../backend/app/websocket/connection_managers.py:181)) `discard` les sockets du set `active_connections["dep-1"]` **sans supprimer la clé** devenue vide.
4. État final : `active_connections == {"dep-1": set()}` — l'entrée `dep-1` persiste indéfiniment.

## Comportement attendu

Cohérence avec [`disconnect`](../../backend/app/websocket/connection_managers.py:137) : quand un set de connexions devient vide après purge, la clé `deployment_id` doit être retirée du dict (`del self.active_connections[deployment_id]`). Même harmonisation attendue que celle déjà appliquée à `remove_connection` (clé `user_id` purgée) et `unsubscribe_from_event` (clé purgée).

## Comportement actuel

[`broadcast_to_deployment`](../../backend/app/websocket/connection_managers.py:184) laisse une **clé vide résiduelle** `{"dep-id": set()}` dans `active_connections` — fuite mémoire mineure (une entrée par déploiement dont les clients ont tous disparu impoliment) **sans impact fonctionnel immédiat** : les broadcasts suivants sur la clé trouvent un set vide (no-op, comptage 0/0). Le désagrément principal est l'incohérence d'état : `deployment_id in active_connections` retourne `True` alors qu'aucun client n'est connecté, ce qui peut fausser tout futur usage de ce prédicat (métriques, conditions de re-diffusion ack).

## Test documentant le bug

- Comportement consigné avec **note de divergence** dans [`test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py:275) (docstring l.273-286) : le test actuel assert `active_connections.get("dep-1") == set()` — c'est-à-dire qu'il **verrouille le comportement bogué** ; à la correction, retourner l'assertion à `assert "dep-1" not in connection_manager.active_connections` et mettre à jour la note.

## Résolution

*(à compléter à la résolution — piste suggérée : après le `discard` des connexions mortes, `if not self.active_connections[deployment_id]: del self.active_connections[deployment_id]`, sous le même lock)*
