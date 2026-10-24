# BUG-007 : Clé vide résiduelle dans `ConnectionManager.broadcast_to_deployment` — purge sans nettoyage de l'entrée

**Statut :** DONE
**Gravité :** Mineur
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)
**Analysé le :** 2026-10-24 (phase `analyse-story` — analyse statique, cause racine vérifiée dans le code)

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
- Contrairement à BUG-005/006, ce test n'est **pas** marqué `xfail` : il assert directement l'état bogué et reste vert — la correction doit **inverser** son assertion (et idéalement le renommer), pas retirer un marquage.

## Cause racine

**Confirmée statiquement le 2026-10-24.** La purge des connexions mortes dans [`ConnectionManager.broadcast_to_deployment`](../../backend/app/websocket/connection_managers.py:155) ([l.180-184](../../backend/app/websocket/connection_managers.py:180)) se contente d'un `discard` par socket morte sous le lock :

```python
# Nettoyer les connexions mortes
if disconnected:
    async with self._lock:
        for ws in disconnected:
            self.active_connections[deployment_id].discard(ws)
```

…alors que [`disconnect`](../../backend/app/websocket/connection_managers.py:145) (l.145-151) applique le pattern complet sous le même lock — `discard` **puis** suppression de la clé devenue vide :

```python
async with self._lock:
    if deployment_id in self.active_connections:
        self.active_connections[deployment_id].discard(websocket)
        # Nettoyer si plus aucune connexion
        if not self.active_connections[deployment_id]:
            del self.active_connections[deployment_id]
```

Le chemin « purge post-broadcast » a simplement été écrit sans la seconde moitié du pattern (suppression de la clé vide) : incohérence entre les deux sites de mutation du même dict `active_connections` dans la même classe.

### Défaut adjacent découvert à l'analyse : `KeyError` latent (race condition)

L'accès [`self.active_connections[deployment_id]`](../../backend/app/websocket/connection_managers.py:184) dans la purge est **non gardé**. Scénario de course :

1. `broadcast_to_deployment("dep-1", …)` lit `connections` ([l.167](../../backend/app/websocket/connection_managers.py:167)) puis effectue les envois **hors lock** (I/O réseau, durée non bornée — [`BroadcastManager._broadcast_to_connections`](../../backend/app/websocket/connection_managers.py:36)) ;
2. pendant cet envoi, le `finally` du handler ([`deployment_logs.py` l.156+](../../backend/app/websocket/deployment_logs.py:156) ou [`batch.py` l.156](../../backend/app/websocket/batch.py:156)) exécute `disconnect(websocket, "dep-1")` pour la dernière socket vivante restante → `discard` + `del` de la clé ;
3. au retour de la purge sous lock (l.182-184), la clé `dep-1` n'existe plus → **`KeyError`** dans `broadcast_to_deployment`.

Ce défaut est **du même bloc de code** et du même correctif (garde d'accès) : il est inclus dans le périmètre de la correction, sans en changer la nature (la garde `.get()` résout les deux aspects d'un coup).

### Chemins d'appel affectés (vecteurs de déclenchement réels)

| Appelant | Localisation | Canal / déclencheur |
|---|---|---|
| Singleton [`manager`](../../backend/app/websocket/connection_managers.py:497) | [`_broadcast_deployment_event`](../../backend/app/websocket/broadcasting.py:108) (broadcasting.py l.77-109) | `/ws/deployments/{id}/logs` — tous les événements de déploiement (`broadcast_deployment_log`, statut, progression, complétion, erreur) |
| Instance [`batch_manager`](../../backend/app/websocket/batch.py:50) (même classe `ConnectionManager`) | [`broadcast_batch_event`](../../backend/app/websocket/batch.py:87) (batch.py l.57-93) | `/ws/batch/{batch_id}` — phases `start`/`progress`/`complete`/`error` (canal émetteur-ready STORY-164.2 ; future consommatrice : STORY-173 check-updates) |

**Conséquence** : le bug ne touche pas seulement `deployment_logs` — toute instance de `ConnectionManager` est affectée, dont `batch_manager`. Le correctif dans la classe corrige les **deux canaux** simultanément ; les tests de non-régression sur `batch.py` (`test_ws_batch.py`) doivent être rejoués.

### Impact précis

- **Fuite mémoire** : une entrée dict (`deployment_id` → `set()`) par déploiement/batch dont tous les clients ont disparu sans `disconnect` propre. Les clés étant des UUID, croissance non bornée en théorie sur un process longue durée (mineur en pratique).
- **Incohérence d'état** : `deployment_id in manager.active_connections` retourne `True` à tort. Aujourd'hui les 3 seuls usages du prédicat ([`connect` l.131](../../backend/app/websocket/connection_managers.py:131), [`disconnect` l.146](../../backend/app/websocket/connection_managers.py:146), [`broadcast_to_deployment` l.163](../../backend/app/websocket/connection_managers.py:163)) tolèrent le set vide (no-op/recréation) — aucun casse fonctionnelle ; mais tout futur usage « y a-t-il des clients connectés ? » (métriques STORY-172, conditions de re-diffusion ack) hériterait du mensonge.
- **`KeyError` latent** (volet adjacent) : déclenchable par la race disconnect-concurrent pendant un broadcast — rare mais réel (le `finally` des handlers déconnecte précisément quand la socket meurt, même fenêtre que la purge).

## Contexte technique

### Patterns de référence à respecter (dans le même fichier)

- [`disconnect` l.145-151](../../backend/app/websocket/connection_managers.py:145) — pattern canonique de ce bug : `discard` + `if not …: del …` **sous le même lock** ;
- [`remove_connection`](../../backend/app/websocket/connection_managers.py:243) (BUG-005 déjà corrigé) — purge cascade `user_subscriptions`/`user_plugin_contexts` avec suppression des clés vides ;
- [`unsubscribe_from_event`](../../backend/app/websocket/connection_managers.py:284) — même hygiène de suppression de clé vide ;
- [`unregister` de WebSocketPluginManager](../../backend/app/websocket/plugin.py:244) (BUG-006 déjà corrigé) — discard + `del` des clés d'index vides : l'hygiène « pas de clé vide résiduelle » est la règle du module.

### Correctif attendu (minimal)

Dans [`broadcast_to_deployment`](../../backend/app/websocket/connection_managers.py:180), remplacer la purge par l'équivalent garanti de `disconnect` — discard des sockets mortes + suppression de la clé vide, avec garde contre la clé absente (race) :

```python
# Nettoyer les connexions mortes — même hygiène que disconnect :
# purge des sockets + suppression de la clé devenue vide (BUG-007).
# Garde .get() : la clé peut avoir été supprimée par un disconnect
# concurrent pendant l'envoi (la purge ne doit jamais lever KeyError).
if disconnected:
    async with self._lock:
        connections = self.active_connections.get(deployment_id)
        if connections is not None:
            connections.difference_update(disconnected)
            if not connections:
                del self.active_connections[deployment_id]
```

`difference_update` remplace avantageusement la boucle `for ws in disconnected: …discard(ws)` (une seule mutation du set), mais la boucle avec discard + garde `if not …: del` est également acceptable si plus proche du style existant — les deux valident les mêmes tests.

### Fichiers de référence

- Code : [`backend/app/websocket/connection_managers.py`](../../backend/app/websocket/connection_managers.py) — **seul fichier de production à modifier** (purge de `broadcast_to_deployment` l.180-184 ; la classe `ConnectionManager` sert les deux canaux `manager` et `batch_manager`) ;
- Tests : [`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py) — helper `_make_websocket(*, fail=...)` ([l.59-60](../../backend/tests/unit/test_websocket/test_connection_managers.py:59)), classe `TestConnectionManagerBroadcast` ([l.233](../../backend/tests/unit/test_websocket/test_connection_managers.py:233)) ; pattern de mock sans serveur conforme à `.roo/rules/35-testing-quality-gates.md` ;
- Non-régression élargie (à rejouer sans modification) : [`test_broadcasting.py`](../../backend/tests/unit/test_websocket/test_broadcasting.py) (chemins appelants mockés `manager.broadcast_to_deployment`), tests du canal batch ([`test_ws_batch.py`](../../backend/tests/unit/test_websocket/test_ws_batch.py)), [`test_ws_deployment_logs_e2e.py`](../../backend/tests/unit/test_websocket/test_ws_deployment_logs_e2e.py).

### Invariants à préserver

- Le early-return « No active connections » ([l.163-165](../../backend/app/websocket/connection_managers.py:163)) reste le premier chemin (no-op sur déploiement inconnu, log debug) ;
- Les envois restent hors lock (pas de régression de contention pendant l'I/O — pattern conservé) ;
- `BroadcastManager._broadcast_to_connections` et `_log_broadcast` non modifiés ;
- `connect`/`disconnect` inchangés comportementalement (recréation de clé au reconnect après purge doit fonctionner) ;
- Signature de `broadcast_to_deployment` inchangée.

### Volet sécurité (checklist `.roo/rules/40-security.md`)

- Aucun endpoint HTTP ni schéma d'authentification/validation touché → tests 401/403/422 **non applicables** (aucune surface API modifiée ; l'auth du canal `/ws/deployments/{id}/logs` reste portée par `get_current_user_ws` + `verify_deployment_access`, non modifiées).
- **Disponibilité / ressources** : la clé vide résiduelle est une micro-fuite non bornée en théorie (un dict entry par `deployment_id`/`batch_id` orphelin) ; le `KeyError` latent (race) peut interrompre une chaîne de broadcast (événement perdu pour les sockets encore vivantes du même déploiement). La correction élimine les deux vecteurs.
- Aucune donnée sensible loggée ni exposée par la correction (manipulation de références de sockets uniquement).

## Dépendances

- **Aucune story pré-requise** — correction autonome (STORY-165 qui a consigné le bug est DONE).
- BUG-005 (DONE) touchait le même fichier mais une autre classe (`UserConnectionManager`) — déjà fusionné, aucun conflit restant.
- Indépendant de BUG-008 (`api/v1/websockets.py` double accept) et BUG-009 (frontend) — fichiers disjoints.
- **Bénéfice collatéral** : le canal `/ws/batch/{batch_id}` (`batch_manager`, même classe) est corrigé d'office — pertinent pour STORY-173 (check-updates, future émettrice `broadcast_batch_event`).
- Aucun service externe requis pour la correction ni les tests (mocks purs).

## Tâches d'implémentation détaillées

1. **`backend/app/websocket/connection_managers.py`** — dans `ConnectionManager.broadcast_to_deployment` (l.180-184) : remplacer la purge par le pattern complet sous lock — récupérer `connections = self.active_connections.get(deployment_id)`, si non `None` : purger les sockets mortes (`difference_update(disconnected)` ou boucle de `discard`), puis `if not connections: del self.active_connections[deployment_id]`. Ajouter un commentaire référençant l'hygiène de `disconnect` et la garde race (cf. correctif attendu ci-dessus). Objectif : plus jamais de clé vide résiduelle ni de `KeyError` sur clé purgée concurrente.
2. **`backend/tests/unit/test_websocket/test_connection_managers.py`** — inverser le test documentaire `test_broadcast_dead_last_connection_leaves_empty_key` (l.271-287) : renommer en `test_broadcast_dead_last_connection_removes_empty_key`, remplacer l'assertion par `assert "dep-1" not in connection_manager.active_connections`, réécrire la docstring (comportement corrigé via BUG-007 — la note de divergence disparaît). Objectif : le test verrouille désormais l'état correct.
3. **`backend/tests/unit/test_websocket/test_connection_managers.py`** — mettre à jour l'en-tête du fichier (l.13-14 : « purge des connexions mortes après échec d'envoi » → mentionner « purge + suppression de la clé vide (BUG-007) »). Objectif : cohérence documentation ↔ code.
4. **`backend/tests/unit/test_websocket/test_connection_managers.py`** — ajouter les tests de non-régression dans `TestConnectionManagerBroadcast` (détail au § Tests à écrire) : broadcast suivant sur clé purgée → no-op debug, re-connect après purge → clé recréée et message délivré, tolérance à la clé supprimée pendant l'envoi (race). Objectif : verrouiller le comportement corrigé sur tous les chemins.
5. **Validation ciblée** — `poetry run pytest backend/tests/unit/test_websocket/test_connection_managers.py -v` : tous verts, aucun xfail sur ce fichier. Objectif : preuve de la correction.
6. **Validation élargie + qualité** — `poetry run pytest backend/tests/unit/test_websocket/ -v` (attendu : **413 passed + 1 xfailed** — l'xfail restant = BUG-008 seul ; 410 actuels + 3 nouveaux tests, l'existant inversé reste vert) puis `black --check` + `isort --check` + `flake8` sur les 2 fichiers modifiés. Objectif : non-régression du module temps réel (notamment `test_broadcasting.py`, `test_ws_batch.py`, `test_ws_deployment_logs.py`) et conformité lint.

## Tests à écrire

Tous dans [`backend/tests/unit/test_websocket/test_connection_managers.py`](../../backend/tests/unit/test_websocket/test_connection_managers.py), classe `TestConnectionManagerBroadcast` ([l.233](../../backend/tests/unit/test_websocket/test_connection_managers.py:233)), en réutilisant le helper `_make_websocket(*, fail=...)` :

1. **`test_broadcast_dead_last_connection_removes_empty_key`** (ex-`test_broadcast_dead_last_connection_leaves_empty_key` l.271, inversé/renommé) — une socket morte unique connectée à `dep-1`, broadcast → `assert "dep-1" not in connection_manager.active_connections`. *Non-régression directe du bug.*
2. **`test_broadcast_after_full_purge_is_noop_debug`** (nouveau) — après purge complète (état n°1), un second `broadcast_to_deployment("dep-1", MESSAGE)` passe par le early-return : pas d'exception, log debug « No active connections for deployment dep-1 » (caplog, pattern de [`test_unknown_deployment_is_noop_debug`](../../backend/tests/unit/test_websocket/test_connection_managers.py:234)). *La clé purgée redevient un déploiement « inconnu » — cohérence du chemin l.163-165.*
3. **`test_reconnect_after_full_purge_recreates_key_and_delivers`** (nouveau) — après purge complète, `connect(alive, "dep-1")` puis broadcast → `active_connections["dep-1"] == {alive}` et `alive.send_json` attendu une fois avec le message. *La suppression de la clé ne casse pas le chemin de reconnexion (recréation l.131-132).*
4. **`test_broadcast_purge_tolerates_concurrent_key_removal`** (nouveau) — simuler la race : patcher `BroadcastManager._broadcast_to_connections` (via `patch.object`) avec un side-effect async qui supprime la clé `dep-1` du dict **pendant** l'« envoi » puis retourne `(0, {dead})` ; le `broadcast_to_deployment` ne lève pas de `KeyError` et l'état reste `{}`. *Couvre la garde `.get()` du défaut adjacent — sous `asyncio.wait_for(timeout=1.0)` par sécurité (pattern BUG-005).*

Sécurité (`.roo/rules/40-security.md`) : pas d'endpoint nouveau/modifié → tests 401/403/422 non applicables ; le volet disponibilité (fuite de clés + `KeyError` interrompant une chaîne de broadcast) est couvert par les tests n°1 et n°4.

Non-régression élargie (existants, à rejouer sans modification) : `test_broadcasting.py` (appels mockés via `manager.broadcast_to_deployment`), tests du canal batch (`test_ws_batch.py` — `batch_manager` même classe), `test_ws_deployment_logs_e2e.py`, `test_ws_general_loop.py`.

Commandes de validation (cf. Makefile / `.roo/rules/35-testing-quality-gates.md`) :

- `poetry run pytest backend/tests/unit/test_websocket/test_connection_managers.py -v`
- `poetry run pytest backend/tests/unit/test_websocket/ -v`
- `make backend-lint` (ou black/isort/flake8 ciblés sur les 2 fichiers)

## État d'avancement technique

- [x] 1. `connection_managers.py` — purge `broadcast_to_deployment` : discard + suppression clé vide + garde race (`.get()`)
- [x] 2. `test_connection_managers.py` — inverser/renommer le test documentaire (assertion clé absente)
- [x] 3. `test_connection_managers.py` — mise à jour de l'en-tête du fichier de tests
- [x] 4. `test_connection_managers.py` — 3 tests de non-régression (no-op après purge, reconnect, tolérance race)
- [x] 5. Validation ciblée : `poetry run pytest backend/tests/unit/test_websocket/test_connection_managers.py -v`
- [x] 6. Validation élargie + lint : `poetry run pytest backend/tests/unit/test_websocket/ -v` + black/isort/flake8

## Résolution

**Corrigé le 2026-10-24** (statut : CONFIRMED → IN_PROGRESS → DONE ; tests validés, aucune divergence par rapport à l'analyse).

### Cause racine

La purge post-broadcast dans `ConnectionManager.broadcast_to_deployment` se limitait à un `discard` par socket morte sous le lock, sans supprimer la clé `deployment_id` devenue vide — incohérence avec le pattern complet de `disconnect` (`discard` + `del` de la clé vide). L'accès non gardé `self.active_connections[deployment_id]` exposait en outre un `KeyError` latent si un `disconnect` concurrent supprimait la clé pendant l'envoi (I/O hors lock).

### Correctif appliqué

`backend/app/websocket/connection_managers.py` — purge de `broadcast_to_deployment` réécrite sous le même lock avec l'hygiène de `disconnect` : `connections = self.active_connections.get(deployment_id)` (garde race), `difference_update(disconnected)` (mutation unique du set), puis `del self.active_connections[deployment_id]` si le set est vide. Les invariants sont préservés : early-return no-op inchangé, envois hors lock, `connect`/`disconnect` inchangés, signature inchangée. Le correctif couvre les deux canaux servis par la classe (`manager` pour `/ws/deployments/{id}/logs` et `batch_manager` pour `/ws/batch/{batch_id}`).

### Tests

- Test documentaire inversé/renommé : `test_broadcast_dead_last_connection_leaves_empty_key` → `test_broadcast_dead_last_connection_removes_empty_key` (assertion `"dep-1" not in active_connections`, note de divergence levée) ;
- 3 tests de non-régression ajoutés dans `TestConnectionManagerBroadcast` : `test_broadcast_after_full_purge_is_noop_debug` (early-return après purge), `test_reconnect_after_full_purge_recreates_key_and_delivers` (recréation de clé + délivrance), `test_broadcast_purge_tolerates_concurrent_key_removal` (garde `.get()` — race simulée via `patch.object` de `BroadcastManager._broadcast_to_connections`, `wait_for(timeout=1.0)` pattern BUG-005) ;
- Validation ciblée : `poetry run pytest backend/tests/unit/test_websocket/test_connection_managers.py -v` → **50 passed, 0 failed, 0 xfail** ;
- Validation élargie : `poetry run pytest backend/tests/unit/test_websocket/ -v` → **413 passed + 1 xfailed** (xfail restant = BUG-008 seul, conforme à l'attendu) ;
- Lint ciblé (black --check, isort --check, flake8) sur les 2 fichiers modifiés : **OK** (0 diff, 0 erreur) ;
- Couverture : `connection_managers.py` maintenu à **100 %**.

### Fichiers modifiés

- `backend/app/websocket/connection_managers.py` — purge de `broadcast_to_deployment` (correctif)
- `backend/tests/unit/test_websocket/test_connection_managers.py` — test inversé/renommé + en-tête + 3 tests non-régression
- `.backlog/bugs/BUG-007-cle-vide-broadcast-to-deployment.md` — statut, avancement, résolution
- `.backlog/kanban.md` — déplacement BUG-007 vers DONE
- `.backlog/epics/EPIC-013-remediation-p2-conformite-fonctionnelle.md` — note de conception BUG-007 DONE
