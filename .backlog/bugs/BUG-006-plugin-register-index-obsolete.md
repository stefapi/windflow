# BUG-006 : Index `_event_handlers` obsolète dans `WebSocketPluginManager.register` en duplicate — le plugin « remplacé » continue de recevoir les dispatchs

**Statut :** DONE _(corrigé le 2026-10-24 — phase `treat-story` ; passage REVIEW→DONE, tests validés)_
**Gravité :** Majeur
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)
**Analysé le :** 2026-10-24 (phase `analyse-story` — analyse statique, bug confirmé dans le code)

## Reproduction

1. Créer un [`WebSocketPluginManager`](../../backend/app/websocket/plugin.py) et enregistrer un plugin `first` de nom `"dup"` écoutant un événement donné (`listens_for`).
2. Enregistrer un second plugin `second` portant le **même nom** `"dup"` et écoutant le même événement → un warning « already registered, replacing... » est loggué, `_plugins["dup"] = second`.
3. Émettre un `dispatch` de l'événement écouté.
4. L'index [`_event_handlers`](../../backend/app/websocket/plugin.py:200) (construit dans `register`, l.188-208) contient encore `first` **en plus** de `second` : le remplacement n'effectue jamais de `discard` de l'ancienne instance → **`first` continue de recevoir les dispatchs** alors qu'il est censé avoir été remplacé.

## Comportement attendu

Après un `register` en duplicate, seul le plugin de remplacement (`second`) doit être indexé dans `_event_handlers` pour les événements de `listens_for` : l'ancienne instance est retirée de tous les index au moment du remplacement (discard de l'ancien plugin des index avant ré-indexation, ou `unregister` préalable).

## Comportement actuel

[`register`](../../backend/app/websocket/plugin.py:200) remplace `_plugins[name]` mais ajoute uniquement la nouvelle instance à `_event_handlers[event_type]` — l'ancienne instance y reste à vie. Concrètement : un plugin « remplacé » (ex. rechargé à chaud, ré-enregistrement au redémarrage d'un module) exécute `handle_event` **en double** avec son successeur — effets dupliqués (logs d'audit doublés, notifications envoyées deux fois, souscriptions comptées deux fois), et l'instance obsolète n'est jamais nettoyée par `cleanup_all` (qui itère `_plugins`).

## Test documentant le bug

- [`test_register_duplicate_replaces_event_index`](../../backend/tests/unit/test_websocket/test_plugin_system.py:176) — marqué `xfail(strict=True)` : assert `plugin_manager._event_handlers[EVT] == {second}` échoue aujourd'hui (`{first, second}`) ; une fois corrigé, le test XPASS et **échoue**, forçant le retrait du marquage.

## Contexte technique

### Cause racine (confirmée statiquement le 2026-10-24)

[`WebSocketPluginManager.register`](../../backend/app/websocket/plugin.py:188) remplace bien `_plugins[plugin.name]` ([l.200](../../backend/app/websocket/plugin.py:200)) mais la boucle de ré-indexation ([l.203-206](../../backend/app/websocket/plugin.py:203)) se contente d'`add(plugin)` dans `_event_handlers[event_type]` : **l'ancienne instance n'est jamais `discard`ée**. Contrairement à [`unregister`](../../backend/app/websocket/plugin.py:232) qui applique le bon pattern (discard + suppression de la clé d'index vide, [l.244-250](../../backend/app/websocket/plugin.py:244)), le chemin « duplicate » de `register` ne nettoie rien.

Conséquences en cascade :

1. [`dispatch`](../../backend/app/websocket/plugin.py:323) itère `_event_handlers.get(event)` qui contient `{first, second}` → `first.handle_event` exécuté **en double** à chaque événement écouté ;
2. [`cleanup_all`](../../backend/app/websocket/plugin.py:384) itère `_plugins.values()` → `first.cleanup()` n'est **jamais appelé** (fuite de ressources de l'instance orpheline) ;
3. Le singleton [`plugin_manager`](../../backend/app/websocket/plugin.py:403) vit toute la durée du process → l'instance orpheline persiste jusqu'au redémarrage.

### Bug jumeau (même correctif) : `register_message_handler`

[`register_message_handler`](../../backend/app/websocket/plugin.py:210) présente exactement le même défaut sur `_message_type_handlers` ([l.217-228](../../backend/app/websocket/plugin.py:217)) : le handler remplacé reste indexé. [`handle_client_message`](../../backend/app/websocket/plugin.py:360) itère le set **non ordonné** et retourne la première réponse non nulle ([l.367-371](../../backend/app/websocket/plugin.py:367)) → comportement **non déterministe** entre ancien et nouveau handler (l'ancien peut répondre avant le nouveau). Ce volet est inclus dans le périmètre du correctif : même cause racine, même pattern de fix, même fichier.

### Vecteurs de déclenchement réels

| Vecteur | Localisation | Impact |
|---|---|---|
| Enregistrement par défaut (à l'import du module) | [`general.py` l.38-43](../../backend/app/websocket/general.py:38) | Aujourd'hui unique par process — le doublon n'apparaît que si un second site enregistre un plugin de même nom |
| Dispatch par contexte utilisateur | [`UserConnectionManager.dispatch_to_plugins` l.469-487](../../backend/app/websocket/connection_managers.py:469) | **Multiplicateur** : `plugin_manager.dispatch` est appelé par contexte utilisateur connecté → N utilisateurs connectés = exécutions dupliquées ×N |
| Plugins réels (futur) | STORY-169/170 (réinstallation/upgrade d'un plugin) | Vecteur majeur à venir : ré-enregistrement d'un plugin de même nom après upgrade = cas nominal — le fix est un pré-requis de fait |

### Effets dupliqués concrets (plugins par défaut)

Avec les 3 plugins par défaut ([`plugins/__init__.py` l.18-25](../../backend/app/websocket/plugins/__init__.py:18)) :

- `AuditLoggerPlugin` → **lignes d'audit dupliquées** (altère la valeur probante du trail d'audit STORY-125) ;
- `DeploymentMonitorPlugin` → logs status/progress doublés ;
- `DeploymentNotificationsPlugin` → notifications envoyées deux fois à l'initiateur ;
- `SubscriptionHandler` (bug jumeau) → réponse de souscription non déterministe.

### Correctif attendu (minimal, pattern existant)

Dans `register`, avant `self._plugins[plugin.name] = plugin` : si une instance existante est présente, appliquer le pattern de `unregister` ([l.244-250](../../backend/app/websocket/plugin.py:244)) — discard de l'ancienne instance de chaque `existing.listens_for` dans `_event_handlers`, avec suppression des clés devenues vides (cohérence avec `unregister`). Ré-indexer ensuite la nouvelle instance (code existant inchangé). Correctif symétrique dans `register_message_handler` sur `_message_type_handlers`.

### Volet sécurité (checklist `.roo/rules/40-security.md`)

- Aucun endpoint HTTP ni schéma d'authentification/validation modifié → tests 401/403/422 **non applicables** (aucune surface API touchée).
- **Intégrité de l'audit** : la duplication de `AuditLoggerPlugin` double les lignes d'audit (perte de valeur probante) — le fix rétablit l'unicité d'exécution.
- **Déterminisme** : pour les messages client, l'ancien handler pouvait répondre avant le nouveau (set non ordonné) → souscriptions potentiellement servies par une instance obsolète ; le fix élimine l'ambiguïté.
- Aucune donnée sensible loggée ni exposée par la correction (manipulation d'index internes uniquement) ; RBAC non touché.

### Fichiers de référence

- Code : [`backend/app/websocket/plugin.py`](../../backend/app/websocket/plugin.py) — **seul fichier de production à modifier** (`register` l.188-208 + `register_message_handler` l.210-230) ;
- Tests : [`backend/tests/unit/test_websocket/test_plugin_system.py`](../../backend/tests/unit/test_websocket/test_plugin_system.py) — helpers `FakePlugin` (l.52) / `FakeHandler` (l.90) / fixture `context` (l.123) ; suite isolée (jamais le singleton, docstring l.6-7) conforme à `.roo/rules/35-testing-quality-gates.md`.

### Invariants à préserver

- Le warning « already registered, replacing... » est conservé (asserté par `test_register_duplicate_warns_and_replaces` l.164 et `test_register_message_handler_duplicate_warns` l.208) ;
- `unregister` (l.232-253) inchangé comportementalement — ses tests (l.220-258) doivent rester verts ;
- Les signatures publiques de `register`/`register_message_handler` ne changent pas ;
- `dispatch`/`handle_client_message`/`cleanup_all` non modifiés (la correction est en amont, dans l'indexation).

## Dépendances

- **Aucune story pré-requise** — correction autonome (STORY-165 qui a consigné le bug est DONE ; BUG-005 corrigeait un autre manager, dans un autre fichier).
- Indépendant de BUG-007 (`connection_managers.py`), BUG-008 (`api/v1/websockets.py`), BUG-009 (frontend) — fichiers disjoints, aucun conflit de merge attendu.
- **STORY-169/170** (plugins réels — installation/extension) : le fix est un **pré-requis de fait** pour la réinstallation/upgrade propre d'un plugin (ré-enregistrement de même nom) ; à traiter avant ou pendant ces stories.
- Aucun service externe requis pour la correction ni les tests (mocks purs, managers isolés).

## Tâches d'implémentation détaillées

1. **`backend/app/websocket/plugin.py`** — dans `register` (l.188-208) : après le warning de duplicate, **avant** `self._plugins[plugin.name] = plugin` (l.200), récupérer `existing = self._plugins.get(plugin.name)` et, si non `None`, retirer l'ancienne instance des index en appliquant le pattern de `unregister` (l.244-250) : pour chaque `event_type in existing.listens_for`, `handlers.discard(existing)` puis suppression de la clé si le set est vide. Objectif : `_event_handlers` ne référence que le plugin remplaçant.
2. **`backend/app/websocket/plugin.py`** — correctif symétrique dans `register_message_handler` (l.210-230) : discard de l'ancien handler de `_message_type_handlers` (avec suppression des clés vides) avant remplacement dans `_message_handlers`. Objectif : éliminer le bug jumeau côté messages client.
3. **`backend/tests/unit/test_websocket/test_plugin_system.py`** — retirer le marquage `@pytest.mark.xfail(strict=True)` (l.176-186) de `test_register_duplicate_replaces_event_index` en conservant le corps du test (l.187-197). Objectif : le test devient l'assertion de la correction.
4. **`backend/tests/unit/test_websocket/test_plugin_system.py`** — ajouter les tests de non-régression dans `TestRegisterUnregister` (détail au § Tests à écrire) : dispatch n'exécute que le remplaçant, `cleanup_all` ne nettoie que le remplaçant, événements écoutés par l'ancien seul → clé d'index purgée, index messages remplacé + routage `handle_client_message` au remplaçant uniquement. Objectif : verrouiller le comportement corrigé sur les **deux** index.
5. **Validation ciblée** — `poetry run pytest backend/tests/unit/test_websocket/test_plugin_system.py -v` : 0 xfail restant sur ce fichier, tous verts. Objectif : preuve de la correction.
6. **Validation élargie + qualité** — `poetry run pytest backend/tests/unit/test_websocket/ -v` (attendu : **406 passed + 1 xfailed** — l'xfail restant = BUG-008 ; BUG-006 quitte la liste) puis `black --check` + `isort --check` + `flake8` sur les 2 fichiers modifiés. Objectif : non-régression du module temps réel et conformité lint.

## Tests à écrire

Tous dans [`backend/tests/unit/test_websocket/test_plugin_system.py`](../../backend/tests/unit/test_websocket/test_plugin_system.py), classe `TestRegisterUnregister` (l.140), en réutilisant `FakePlugin` / `FakeHandler` et la fixture `context` — manager **isolé** (`WebSocketPluginManager()`), jamais le singleton (docstring l.6-7) :

1. **`test_register_duplicate_replaces_event_index`** (l.187, existant) — retirer le xfail ; assertions conservées : `_event_handlers[AUTH_LOGOUT] == {second}`. *Non-régression directe.*
2. **`test_register_duplicate_dispatches_only_replacement`** (nouveau) — `first`/`second` même nom, même événement ; `await manager.initialize_all(context)` (pré-requis : `dispatch` exige le contexte, l.317) puis `await manager.dispatch(EVT, {...}, context)` → `second.handled_events == [(EVT, data)]` et `first.handled_events == []`. *Le plugin remplacé ne reçoit plus les dispatchs.*
3. **`test_register_duplicate_cleanup_all_only_replacement`** (nouveau) — après remplacement, `await manager.cleanup_all(context)` → `second.cleaned_up is True`, `first.cleaned_up is False`. *L'instance orpheline n'est plus référencée nulle part.*
4. **`test_register_duplicate_partial_listen_purges_stale_events`** (nouveau) — `first` écoute `[A, B]`, `second` (même nom) écoute `[A]` uniquement → après remplacement : `_event_handlers[A] == {second}` et `B not in _event_handlers` (clé purgée, pattern `unregister`). *Discard complet + suppression des clés vides.*
5. **`test_register_message_handler_duplicate_replaces_type_index`** (nouveau) — deux `FakeHandler` de même nom gérant `"x"` : `_message_type_handlers["x"] == {second}` et `await manager.handle_client_message({"type": "x", ...}, context)` → `second.handled_messages` reçoit le message, `first.handled_messages == []`. *Bug jumeau corrigé + routage déterministe.*

Sécurité (`.roo/rules/40-security.md`) : pas d'endpoint nouveau/modifié → tests 401/403/422 non applicables ; le volet intégrité de l'audit est couvert par le test n°2 (unicité d'exécution des plugins, donc d'`AuditLoggerPlugin`).

Non-régression élargie (existants, à rejouer sans modification) : `test_plugins_default.py` (effets des plugins par défaut), `test_ws_general_loop.py`, `test_broadcasting.py`, `test_connection_managers.py`.

Commandes de validation (cf. Makefile / `.roo/rules/35-testing-quality-gates.md`) :

- `poetry run pytest backend/tests/unit/test_websocket/test_plugin_system.py -v`
- `poetry run pytest backend/tests/unit/test_websocket/ -v`
- `make backend-lint` (ou black/isort/flake8 ciblés sur les 2 fichiers)

## État d'avancement technique

- [x] 1. `plugin.py` — `register` : discard de l'ancienne instance de `_event_handlers` (pattern `unregister`) avant remplacement
- [x] 2. `plugin.py` — `register_message_handler` : correctif symétrique sur `_message_type_handlers`
- [x] 3. `test_plugin_system.py` — retrait du xfail `strict=True` de `test_register_duplicate_replaces_event_index`
- [x] 4. `test_plugin_system.py` — 4 tests de non-régression (dispatch, cleanup_all, écoutes partielles, index messages)
- [x] 5. Validation ciblée : `poetry run pytest backend/tests/unit/test_websocket/test_plugin_system.py -v` (0 xfail)
- [x] 6. Validation élargie + lint : `poetry run pytest backend/tests/unit/test_websocket/ -v` (410 passed + 1 xfailed) + black/isort/flake8

## Résolution

**Corrigé le 2026-10-24** (phase `treat-story`).

### Cause racine

[`register`](../../backend/app/websocket/plugin.py) remplaçait `_plugins[name]` mais la boucle de ré-indexation se contentait d'un `add(plugin)` dans `_event_handlers[event_type]` : l'ancienne instance n'était jamais `discard`ée et restait indexée à vie → dispatchs doublés (`first.handle_event` exécuté avec son successeur), `cleanup()` de l'orpheline jamais appelé (fuite jusqu'au redémarrage du process, le singleton vivant toute la durée de vie). Bug jumeau dans `register_message_handler` sur `_message_type_handlers` : routage client non déterministe (set non ordonné, l'ancien handler pouvait répondre avant le nouveau).

### Correctif appliqué

Pattern de [`unregister()`](../../backend/app/websocket/plugin.py) appliqué **avant** remplacement dans les deux méthodes (discard de l'ancienne instance de chaque index + `del` des clés devenues vides) :

1. **`register`** : `existing = self._plugins.get(plugin.name)` ; si non `None` (warning conservé), pour chaque `event_type in existing.listens_for` → `handlers.discard(existing)` + suppression de la clé si le set est vide, puis remplacement et ré-indexation de la nouvelle instance (code existant inchangé).
2. **`register_message_handler`** : correctif symétrique sur `_message_type_handlers` (discard de l'ancien handler par `handles_message_types`, purge des clés vides).

Signatures publiques inchangées ; `dispatch`/`handle_client_message`/`cleanup_all`/`unregister` non modifiés ; warnings « already registered, replacing... » conservés.

### Fichiers modifiés/créés

- [`backend/app/websocket/plugin.py`](../../backend/app/websocket/plugin.py) — `register` + `register_message_handler` (seul fichier de production modifié)
- [`backend/tests/unit/test_websocket/test_plugin_system.py`](../../backend/tests/unit/test_websocket/test_plugin_system.py) — retrait xfail + 4 nouveaux tests

### Tests ajoutés

Dans `TestRegisterUnregister` :

1. `test_register_duplicate_replaces_event_index` — xfail retiré, assertions conservées (index = remplaçant seul) ;
2. `test_register_duplicate_dispatches_only_replacement` — dispatch n'exécute que le remplaçant (`first.handled_events == []`) ;
3. `test_register_duplicate_cleanup_all_only_replacement` — `cleanup_all` ne nettoie que le remplaçant ;
4. `test_register_duplicate_partial_listen_purges_stale_events` — écoutes partielles `[A, B]`→`[A]` : clé `B` purgée de l'index ;
5. `test_register_message_handler_duplicate_replaces_type_index` — index messages remplacé + routage `handle_client_message` déterministe vers le remplaçant.

### Validation

| Commande | Résultat |
|---|---|
| `poetry run pytest backend/tests/unit/test_websocket/test_plugin_system.py -v` | **44 passed, 0 failed, 0 xfail** (40 existants + 4 nouveaux ; l'ex-xfail BUG-006 est passé) — `plugin.py` 100 % couverture |
| `poetry run pytest backend/tests/unit/test_websocket/` | **410 passed + 1 xfailed** (xfail restant = BUG-008 seul) |
| `black` + `isort` + `flake8` sur les 2 fichiers modifiés | OK après reformatage black du fichier de tests (aucun changement sémantique, re-vérifié : 44 passed) |

Aucune commande non exécutée — toutes les commandes du § Tâches ont été lancées.

### Divergences / difficultés

- **Aucune divergence** : les 6 tâches ont été exécutées telles que spécifiées. Le décompte attendu « 406 passed » de l'analyse correspondait à l'état avant ajout des 4 nouveaux tests (405 + ex-xfail = 406) ; avec les 4 tests de non-régression le total monte mécaniquement à **410** — l'xfail restant est bien BUG-008 seul, conforme à l'objectif « BUG-006 quitte la liste ».
- Note triviale : `black` a reformaté le fichier de tests (retour à la ligne sur une signature) — corrigé automatiquement avant le check final.
