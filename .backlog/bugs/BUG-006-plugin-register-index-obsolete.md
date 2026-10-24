# BUG-006 : Index `_event_handlers` obsolète dans `WebSocketPluginManager.register` en duplicate — le plugin « remplacé » continue de recevoir les dispatchs

**Statut :** NEW
**Gravité :** Majeur
**Epic Parent :** EPIC-013 — P2 : Conformité fonctionnelle (remédiation backend) — détecté lors de STORY-165 (tests WebSocket)

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

## Résolution

*(à compléter à la résolution — piste suggérée : avant `self._plugins[plugin.name] = plugin`, discarder l'ancienne instance de chaque `plugin.listens_for` dans `_event_handlers`, ou passer par `unregister` de l'ancien)*
