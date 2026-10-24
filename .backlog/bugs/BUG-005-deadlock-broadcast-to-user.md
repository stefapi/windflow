# BUG-005 : Deadlock dans `UserConnectionManager.broadcast_to_user` — purge des connexions mortes sous le lock non-réentrant

**Statut :** DONE _(via REVIEW — validation complète le 2026-10-24 : 47/47 puis 405 passed + 2 xfailed hors périmètre, lint OK)_
**Gravité :** Bloquant
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)
**Analysé le :** 2026-10-24 (phase `analyse-story` — analyse statique, bug confirmé dans le code)

## Reproduction

1. Connecter un utilisateur via le canal général avec **plusieurs** connexions (onglets multiples), dont au moins une **morte** (socket fermée côté client, `send_json` lève).
2. Déclencher un [`broadcast_to_user`](../../backend/app/websocket/connection_managers.py:308) vers cet utilisateur (ex. notification ciblée, message critique avec ack).
3. L'envoi échoue sur la socket morte → `_broadcast_to_connections` la retourne dans `disconnected` → la purge ([l.333-337](../../backend/app/websocket/connection_managers.py:333)) appelle [`remove_connection`](../../backend/app/websocket/connection_managers.py:235) **sous** `async with self._lock`.
4. `remove_connection` ré-acquiert `self._lock` ([l.243](../../backend/app/websocket/connection_managers.py:243)) — un `asyncio.Lock` est **non-réentrant** → la coroutine attend indéfiniment sa propre libération → **deadlock**.

## Comportement attendu

La purge des connexions mortes doit compléter normalement : `remove_connection` est appelée **hors** du lock, et la socket morte est retirée des connexions de l'utilisateur (pattern déjà correct dans [`broadcast_to_event_subscribers`](../../backend/app/websocket/connection_managers.py:339), qui collecte les `disconnected_users` sous le lock puis les purge après libération).

## Comportement actuel

Dès qu'un envoi échoue pour une connexion utilisateur, [`broadcast_to_user`](../../backend/app/websocket/connection_managers.py:334) gèle : l'attente du lock déjà détenu bloque la coroutine, et comme le lock n'est jamais libéré, **toute la chaîne en attente de `self._lock` se fige** (gel de la boucle d'événements pour les chemins qui passent par ce verrou : `add_connection`, `remove_connection`, souscriptions, autres broadcasts user). Un seul client déconnecté impoliment peut donc paralyser le temps réel utilisateur.

## Test documentant le bug

- [`test_broadcast_purges_dead_connections`](../../backend/tests/unit/test_websocket/test_connection_managers.py:438) — marqué `xfail(strict=True)` avec `asyncio.wait_for(timeout=1.0)` : le deadlock actuel lève `TimeoutError` (→ xfail) ; une fois corrigé, le test XPASS et **échoue**, forçant le retrait du marquage.
- Note de divergence dans l'en-tête du fichier de test (l.23-31).

## Analyse technique

### Cause racine

[`UserConnectionManager.broadcast_to_user`](../../backend/app/websocket/connection_managers.py:308) purge les connexions mortes **sous** `self._lock` en appelant `remove_connection`, qui ré-acquiert ce même verrou :

- Purge fautive : [connection_managers.py l.333-337](../../backend/app/websocket/connection_managers.py:333) — `async with self._lock:` puis `await self.remove_connection(user_id, ws)` dans la boucle ;
- Ré-acquisition : [`remove_connection` l.243](../../backend/app/websocket/connection_managers.py:243) — `async with self._lock:` ;
- `asyncio.Lock` ([l.210](../../backend/app/websocket/connection_managers.py:210)) est **non-réentrant** : la tâche courante attend la libération d'un verrou qu'elle détient elle-même → attente infinie, le verrou n'est jamais libéré.

### Mécanisme détaillé

1. Les envois sont effectués **hors lock** (correct — pas de contention pendant l'I/O réseau) via `_broadcast_to_connections` ([l.324-326](../../backend/app/websocket/connection_managers.py:324)) : chaque socket dont `send_json` lève est ajoutée à `disconnected` sans propager l'exception.
2. Si `disconnected` est non vide, la purge entre dans `async with self._lock` (l.335) puis appelle `remove_connection` (l.337) **dans le même bloc et la même tâche**.
3. `remove_connection` bloque sur `self._lock.acquire()` (l.243). Personne ne peut libérer le verrou — son propriétaire est la tâche bloquée elle-même → **deadlock permanent de la tâche**.
4. La boucle d'événements continue de tourner (le `await` rend la main), mais `user_manager._lock` n'est jamais relâché : **toute opération passant par ce verrou se bloque en cascade** — `add_connection` (l.226), `remove_connection` (l.243), `subscribe_to_event` (l.268), `unsubscribe_from_event` (l.284), `subscribe_to_deployment_logs` (l.303), `broadcast_to_user` (l.335), `broadcast_to_event_subscribers` (l.354), `broadcast_deployment_log_to_subscribers` (l.429), `dispatch_to_plugins` (l.469).

### Chemins d'appel affectés (vecteurs de déclenchement réels)

| Appelant | Localisation | Déclencheur typique |
|---|---|---|
| Wrapper public [`broadcasting.broadcast_to_user`](../../backend/app/websocket/broadcasting.py:247) | [broadcasting.py l.264-268](../../backend/app/websocket/broadcasting.py:264) (ack registry STORY-164.1 puis délégation) | Toute notification ciblée / message critique avec ack |
| Plugin `deployment_notifications` | [plugins/deployment_notifications.py l.102-104, l.142-144, l.182-184](../../backend/app/websocket/plugins/deployment_notifications.py:102) | `DEPLOYMENT_STATUS_CHANGED`, `DEPLOYMENT_COMPLETE`, `DEPLOYMENT_PROGRESS` vers l'initiateur |
| Injection `PluginContext` | [general.py l.117](../../backend/app/websocket/general.py:117) | Contexte du canal général `/ws/general` |

Concrètement : un utilisateur avec ≥ 2 onglets, dont un tué brutalement (onglet fermé, réseau coupé — pas de close frame), paralyse le temps réel utilisateur au **premier événement de déploiement le concernant**. Le heartbeat/expiration (STORY-164.1) ne prévient pas le cas : la socket morte est encore présente dans `user_connections` tant que le serveur ne l'a pas détectée, et l'échec du `send_json` **est** souvent cette première détection.

### Correctif attendu (minimal, pattern existant)

Dans `broadcast_to_user`, supprimer le bloc `async with self._lock:` autour de la purge et appeler directement `remove_connection` hors verrou — le cas est encore plus simple que `broadcast_to_event_subscribers` car le `user_id` est déjà connu (pas d'identification préalable sous lock nécessaire) :

```python
# Nettoyer les connexions mortes — HORS lock (remove_connection acquiert _lock)
for ws in disconnected:
    await self.remove_connection(user_id, ws)
```

Ne **pas** remplacer par un simple `discard` sous lock (pattern de [`broadcast_to_deployment` l.181-184](../../backend/app/websocket/connection_managers.py:181), qui est un autre manager) : `remove_connection` fait plus qu'un discard — elle purge en cascade `user_subscriptions` et `user_plugin_contexts` quand la dernière connexion disparaît ([l.247-255](../../backend/app/websocket/connection_managers.py:247)). Réutiliser `remove_connection` hors lock garantit cette cohérence.

### Volet sécurité (checklist `.roo/rules/40-security.md`)

- Aucun endpoint HTTP ni schéma d'authentification/validation touché → tests 401/403/422 **non applicables** (aucune surface API modifiée).
- **Disponibilité / déni de service** : le deadlock est un vecteur DoS trivial côté canal général — un client malveillant connecte ≥ 2 sockets, en tue une (RST), et paralyse le temps réel de son utilisateur (et tout chemin passant par `user_manager._lock`). La correction élimine le vecteur ; le test de non-régression « lock libéré après purge » (voir Tests à écrire) en est la contre-mesure vérifiable.
- Aucune donnée sensible loggée ni exposée par la correction (purge de références de sockets uniquement).

## Contexte technique

### Patterns de référence à respecter (dans le même fichier)

- [`broadcast_to_event_subscribers` l.398-408](../../backend/app/websocket/connection_managers.py:398) — collecte des `disconnected_users` **sous** lock (l.401-405), purge **hors** lock (l.407-408) : pattern canonique à imiter ;
- [`broadcast_deployment_log_to_subscribers` l.446-459](../../backend/app/websocket/connection_managers.py:446) — même pattern (identification sous lock l.449-456, purge hors lock l.458-459).

### Fichiers de référence

- Code : [`backend/app/websocket/connection_managers.py`](../../backend/app/websocket/connection_managers.py) (seul fichier de production à modifier — la fix est locale à `UserConnectionManager.broadcast_to_user`) ;
- Tests : [`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py) — helpers `_make_websocket(*, fail=...)` (l.59-60), classes `TestUserConnectionManagerBroadcastToUser` (l.413) ; pattern de mock sans serveur conforme à `.roo/rules/35-testing-quality-gates.md` ;
- Non-régression de bout en bout existante : [`test_ws_general_loop.py` l.350+](../../backend/tests/unit/test_websocket/test_ws_general_loop.py:350) (chemin plugin → `broadcast_to_user` → ack registry) — à rejouer, rien à modifier.

### Invariants à préserver

- Contrat de `remove_connection` inchangé (discard + purge cascade abonnements/contextes plugins) — d'autres chemins l'appellent ;
- Les envois restent hors lock (pas de régression de contention pendant l'I/O) ;
- `BroadcastManager._broadcast_to_connections` et `_log_broadcast` non modifiés.

## Dépendances

- **Aucune story pré-requise** — correction autonome (STORY-165 qui a consigné le bug est DONE).
- Indépendant de BUG-006 (plugin manager), BUG-008 (double accept), BUG-009 (frontend) ; **attention** : BUG-007 touche `ConnectionManager.broadcast_to_deployment` dans le **même fichier** — coordonner les merges si traitement simultané (conflit trivial possible sur `connection_managers.py`).
- Aucun service externe requis pour la correction ni les tests (mocks purs).

## Tâches d'implémentation détaillées

- [x] 1. **`backend/app/websocket/connection_managers.py`** — dans `UserConnectionManager.broadcast_to_user` (l.333-337) : supprimer le bloc `async with self._lock:` englobant la purge et appeler `await self.remove_connection(user_id, ws)` directement pour chaque socket de `disconnected`, hors verrou (pattern de `broadcast_to_event_subscribers` l.407-408). Objectif : éliminer la ré-acquisition du lock non-réentrant.
- [x] 2. **`backend/tests/unit/test_websocket/test_connection_managers.py`** — retirer le marquage `@pytest.mark.xfail(strict=True)` (l.438-447) de `test_broadcast_purges_dead_connections` ; **conserver** `asyncio.wait_for(timeout=1.0)` (ceinture de sécurité anti-blocage de la suite). Objectif : le test devient l'assertion de la correction.
- [x] 3. **`backend/tests/unit/test_websocket/test_connection_managers.py`** — mettre à jour la note de divergence de l'en-tête (l.23-31) : remplacer « Bug de production détecté (NON corrigé…) » par « corrigé via BUG-005 ». Objectif : cohérence documentation ↔ code.
- [x] 4. **`backend/tests/unit/test_websocket/test_connection_managers.py`** — ajouter les tests de non-régression (classe `TestUserConnectionManagerBroadcastToUser`) : verrou libéré après purge, purge multiple, cascade `remove_connection` (détail au § Tests à écrire). Objectif : verrouiller le comportement corrigé.
- [x] 5. **Validation ciblée** — `poetry run pytest backend/tests/unit/test_websocket/test_connection_managers.py -v` (0 xfail restant sur ce fichier, 100 % verts). Objectif : preuve de la correction.
- [x] 6. **Validation élargie** — `poetry run pytest backend/tests/unit/test_websocket/ -v` puis vérifier l'absence de régression (notamment `test_ws_general_loop.py`, `test_ws_ack.py`, `test_broadcasting.py`, `test_plugins_default.py` qui couvrent les chemins appelants). Objectif : non-régression du module temps réel.

## Tests à écrire

Tous dans [`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py), classe `TestUserConnectionManagerBroadcastToUser` (l.413), en réutilisant le helper `_make_websocket(*, fail=...)` :

1. **`test_broadcast_purges_dead_connections`** (l.438, existant) — retirer le xfail ; assertions conservées : `user_connections["user-1"] == {alive}` et `alive.send_json` attendu une fois. *Non-régression directe du deadlock.*
2. **`test_broadcast_user_lock_released_after_dead_purge`** (nouveau) — après un `broadcast_to_user` avec socket morte, les opérations concurrentes du manager complètent : `add_connection` puis `remove_connection` sous `asyncio.wait_for(timeout=1.0)` retournent. *Contre-mesure DoS : le verrou est réellement libéré.*
3. **`test_broadcast_user_purges_all_dead_connections_and_keeps_alive`** (nouveau) — 2 sockets mortes + 1 vivante : les deux mortes purgées, la vivante reçoit le message une seule fois. *Robustesse de la boucle de purge.*
4. **`test_broadcast_user_last_dead_connection_cleans_subscriptions_and_plugin_context`** (nouveau) — unique connexion morte + abonnement actif + `PluginContext` enregistré : après broadcast, `user_connections`/`user_subscriptions`/`user_plugin_contexts` ne contiennent plus l'utilisateur. *Garantit que la purge passe bien par `remove_connection` (cascade complète) et non un simple discard.*

Sécurité (`.roo/rules/40-security.md`) : pas d'endpoint nouveau/modifié → tests 401/403/422 non applicables ; le volet disponibilité/DoS est couvert par le test n°2.

Non-régression élargie (existants, à rejouer sans modification) : `test_ws_general_loop.py` (chemin complet plugin → broadcast → ack), `test_ws_ack.py`, `test_broadcasting.py`, `test_plugins_default.py`.

## Résolution

**Corrigé le 2026-10-24** (cycle IN_PROGRESS → REVIEW → DONE, tous les tests passants).

### Cause racine (rappel)

[`UserConnectionManager.broadcast_to_user`](../../backend/app/websocket/connection_managers.py:308) purgeait les connexions mortes **sous** `self._lock` en appelant `remove_connection`, qui ré-acquiert ce même verrou (`asyncio.Lock` non-réentrant) → deadlock permanent de la tâche et gel en cascade de tous les chemins passant par `user_manager._lock` (ajouts, retraits, souscriptions, broadcasts).

### Correction appliquée

- **[`backend/app/websocket/connection_managers.py`](../../backend/app/websocket/connection_managers.py)** — dans `broadcast_to_user` : suppression du bloc `async with self._lock:` englobant la purge ; `await self.remove_connection(user_id, ws)` est désormais appelé directement pour chaque socket de `disconnected`, **hors verrou** (pattern canonique de `broadcast_to_event_subscribers`). `remove_connection` est bien réutilisée (et non un simple `discard`) afin de conserver la purge en cascade `user_subscriptions` / `user_plugin_contexts` quand la dernière connexion disparaît. Commentaire ajouté pour verrouiller l'invariant.

### Tests ajoutés / modifiés

**[`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py)** — classe `TestUserConnectionManagerBroadcastToUser` :

1. `test_broadcast_purges_dead_connections` — xfail `strict=True` retiré, `asyncio.wait_for(timeout=1.0)` conservé (ceinture de sécurité anti-blocage de la suite) ;
2. `test_broadcast_user_lock_released_after_dead_purge` *(nouveau)* — contre-mesure DoS : après purge d'une socket morte, `add_connection` puis `remove_connection` complètent sous timeout → le verrou est réellement libéré ;
3. `test_broadcast_user_purges_all_dead_connections_and_keeps_alive` *(nouveau)* — 2 sockets mortes purgées, la vivante reçoit le message exactement une fois ;
4. `test_broadcast_user_last_dead_connection_cleans_subscriptions_and_plugin_context` *(nouveau)* — la dernière connexion morte emporte `user_connections` + `user_subscriptions` + `user_plugin_contexts` (preuve que la purge passe par `remove_connection` et sa cascade, pas un `discard`).

Note de divergence de l'en-tête du fichier de tests mise à jour (« corrigé via BUG-005 »).

### Validation

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_websocket/test_connection_managers.py -v` | **47 passed** (0 xfail restant sur le fichier), `connection_managers.py` couverture **100 %** |
| `poetry run pytest backend/tests/unit/test_websocket/ -v` | **405 passed, 2 xfailed** (xfail restants = BUG-006 et BUG-008, hors périmètre) — non-régression du module temps réel confirmée (y compris `test_ws_general_loop.py`, `test_ws_ack.py`, `test_broadcasting.py`, `test_plugins_default.py`) |
| `black --check` + `isort --check` + `flake8` sur les 2 fichiers modifiés | conformes (aucune modification requise) |

Référence avant correction : 401 passed + 3 xfailed (clôture STORY-165) → après : **405 passed + 2 xfailed** (+4 tests verts, −1 xfail).

### Divergences par rapport à l'analyse

Aucune — correctif appliqué exactement comme spécifié (sortie du lock, réutilisation de `remove_connection`, 4 tests conformes au § Tests à écrire).
