"""Tests unitaires des gestionnaires de connexions WebSocket (STORY-165 — Tâche 1, AC 3).

Couvre ``app/websocket/connection_managers.py`` (53 % → ≥ 85 %) :

- ``BroadcastManager._broadcast_to_connections`` : envoi à N sockets
  (sent_count), socket morte comptée ``disconnected`` sans jamais propager
  l'exception (les autres reçoivent quand même) ;
- ``BroadcastManager._log_broadcast`` : branches info (types importants
  ``DEPLOYMENT_STATUS_CHANGED`` / ``DEPLOYMENT_COMPLETE`` /
  ``AUTH_LOGIN_SUCCESS``) vs debug, cas 0 envoyé / N potentiels ;
- ``ConnectionManager`` : ``connect`` (accept + enregistrement par
  deployment_id, double connexion même id), ``disconnect`` (retrait +
  nettoyage de la clé vide), ``broadcast_to_deployment`` (inconnu → no-op
  debug ; envoi N/M ; purge des connexions mortes après échec d'envoi
  + suppression de la clé vide — BUG-007) ;
- ``UserConnectionManager`` : ``add_connection`` (stockage PluginContext du
  premier user), ``remove_connection`` (dernière connexion → purge
  abonnements + contextes), ``subscribe_to_event`` /
  ``unsubscribe_from_event`` (nettoyage de la clé vide),
  ``subscribe_to_deployment_logs``, ``broadcast_to_user``,
  ``broadcast_to_event_subscribers``,
  ``broadcast_deployment_log_to_subscribers``, ``dispatch_to_plugins``.

✅ Bug de production détecté (décision 7 de la story) puis **corrigé via
BUG-005** : ``UserConnectionManager.broadcast_to_user`` purgeait les
connexions mortes en appelant ``remove_connection`` **sous** ``self._lock``
alors que ``remove_connection`` ré-acquiert ce lock non-réentrant →
deadlock dès qu'un envoi échoue. La purge appelle désormais
``remove_connection`` **hors** du lock (pattern de
``broadcast_to_event_subscribers``, connection_managers.py:333-337).
Les tests de purge conservent un timeout court (``asyncio.wait_for``) :
ceinture de sécurité anti-blocage de la suite si une régression du
deadlock était réintroduite.

✅ Bug de production détecté (décision 7 de la story) puis **corrigé via
BUG-007** : ``ConnectionManager.broadcast_to_deployment`` purgeait les
sockets mortes sans supprimer la clé ``deployment_id`` devenue vide —
il restait ``{"dep-id": set()}`` (fuite de clé résiduelle + ``KeyError``
latent si un ``disconnect`` concurrent supprimait la clé pendant l'envoi).
La purge applique désormais l'hygiène de ``disconnect`` :
``difference_update`` puis ``del`` de la clé vide, avec une garde
``.get()`` contre la suppression concurrente de la clé.
"""

from __future__ import annotations

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.websocket.connection_managers import (
    BroadcastManager,
    ConnectionManager,
    UserConnectionManager,
    manager,
    user_manager,
)

MESSAGE = {"type": "DEPLOYMENT_STATUS_CHANGED", "data": {"deploymentId": "dep-1"}}
LOGGER = "app.websocket.connection_managers"


# ===========================================================================
# Helpers — sockets mockées (pattern STORY-164.x, mockés sans serveur)
# ===========================================================================


def _make_websocket(*, fail: bool = False) -> AsyncMock:
    """WebSocket mockée : ``accept``/``send_json`` async ; ``send_json`` lève si ``fail``."""
    websocket = AsyncMock()
    if fail:
        websocket.send_json = AsyncMock(side_effect=RuntimeError("connection closed"))
    return websocket


@pytest.fixture(autouse=True)
def _clean_global_managers():
    """Purge des singletons globaux autour de chaque test (isolation — pattern _clean_batch_manager)."""
    manager.active_connections.clear()
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()
    yield
    manager.active_connections.clear()
    user_manager.user_connections.clear()
    user_manager.user_subscriptions.clear()
    user_manager.deployment_subscribers.clear()
    user_manager.user_plugin_contexts.clear()


# ===========================================================================
# BroadcastManager._broadcast_to_connections
# ===========================================================================


class TestBroadcastToConnections:
    async def test_sends_to_all_sockets_and_counts(self):
        sockets = {_make_websocket() for _ in range(3)}

        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            sockets, MESSAGE, "test context"
        )

        assert sent_count == 3
        assert disconnected == set()
        for websocket in sockets:
            websocket.send_json.assert_awaited_once_with(MESSAGE)

    async def test_dead_socket_counted_disconnected_never_raised(self):
        alive = _make_websocket()
        dead = _make_websocket(fail=True)

        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            {alive, dead}, MESSAGE, "test context"
        )

        # L'exception n'est jamais propagée : la socket morte est comptée,
        # les sockets vivantes reçoivent quand même.
        assert sent_count == 1
        assert disconnected == {dead}
        alive.send_json.assert_awaited_once_with(MESSAGE)
        dead.send_json.assert_awaited_once_with(MESSAGE)

    async def test_empty_set_is_noop(self):
        sent_count, disconnected = await BroadcastManager._broadcast_to_connections(
            set(), MESSAGE, "empty"
        )
        assert sent_count == 0
        assert disconnected == set()


# ===========================================================================
# BroadcastManager._log_broadcast
# ===========================================================================


class TestLogBroadcast:
    def test_important_type_logs_info(self, caplog):
        for message_type in (
            "DEPLOYMENT_STATUS_CHANGED",
            "DEPLOYMENT_COMPLETE",
            "AUTH_LOGIN_SUCCESS",
        ):
            with caplog.at_level(logging.INFO, logger=LOGGER):
                BroadcastManager._log_broadcast(
                    {"type": message_type},
                    sent_count=2,
                    total_count=3,
                    context="deployment: dep-1",
                )
        assert any(r.levelno == logging.INFO for r in caplog.records)
        info_records = [r for r in caplog.records if r.levelno == logging.INFO]
        assert len(info_records) == 3

    def test_ordinary_type_logs_debug_not_info(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            BroadcastManager._log_broadcast(
                {"type": "DEPLOYMENT_LOGS_UPDATE"},
                sent_count=1,
                total_count=2,
                context="user: u1",
            )
        matching = [r for r in caplog.records if "DEPLOYMENT_LOGS_UPDATE" in r.message]
        assert matching
        assert all(r.levelno == logging.DEBUG for r in matching)

    def test_zero_sent_with_potential_targets_logs_debug(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            BroadcastManager._log_broadcast(
                MESSAGE, sent_count=0, total_count=2, context="deployment: dep-1"
            )
        assert any(
            "No active connections despite 2 potential target(s)" in r.message
            for r in caplog.records
        )

    def test_zero_sent_zero_potential_logs_nothing(self, caplog):
        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            BroadcastManager._log_broadcast(
                MESSAGE, sent_count=0, total_count=0, context="x"
            )
        assert not [r for r in caplog.records if "broadcast" in r.message.lower()]


# ===========================================================================
# ConnectionManager — connect / disconnect
# ===========================================================================


class TestConnectionManagerConnectDisconnect:
    async def test_connect_accepts_and_registers_by_deployment(self):
        connection_manager = ConnectionManager()
        websocket = _make_websocket()

        await connection_manager.connect(websocket, "dep-1")

        websocket.accept.assert_awaited_once()
        assert connection_manager.active_connections["dep-1"] == {websocket}

    async def test_connect_default_accepts(self):
        """Contrat rétrocompatible du défaut : sans paramètre, ``connect``
        accepte la connexion exactement une fois (pattern ``batch.py``).
        """
        connection_manager = ConnectionManager()
        websocket = _make_websocket()

        await connection_manager.connect(websocket, "dep-1")

        websocket.accept.assert_awaited_once()
        assert connection_manager.active_connections["dep-1"] == {websocket}

    async def test_connect_with_accept_false_registers_without_accept(self):
        """BUG-008 : ``accept_connection=False`` enregistre la connexion
        **sans** accepter — chemin ``deployment_logs`` (l'endpoint a déjà
        accepté ; un second accept ferait échouer la connexion).
        """
        connection_manager = ConnectionManager()
        websocket = _make_websocket()

        await connection_manager.connect(websocket, "dep-1", accept_connection=False)

        websocket.accept.assert_not_awaited()
        assert connection_manager.active_connections["dep-1"] == {websocket}

    async def test_connect_same_deployment_twice_registers_both(self):
        connection_manager = ConnectionManager()
        first, second = _make_websocket(), _make_websocket()

        await connection_manager.connect(first, "dep-1")
        await connection_manager.connect(second, "dep-1")

        assert connection_manager.active_connections["dep-1"] == {first, second}

    async def test_disconnect_removes_and_cleans_empty_key(self):
        connection_manager = ConnectionManager()
        websocket = _make_websocket()
        await connection_manager.connect(websocket, "dep-1")

        await connection_manager.disconnect(websocket, "dep-1")

        assert "dep-1" not in connection_manager.active_connections

    async def test_disconnect_keeps_deployment_with_remaining_connections(self):
        connection_manager = ConnectionManager()
        first, second = _make_websocket(), _make_websocket()
        await connection_manager.connect(first, "dep-1")
        await connection_manager.connect(second, "dep-1")

        await connection_manager.disconnect(first, "dep-1")

        assert connection_manager.active_connections["dep-1"] == {second}

    async def test_disconnect_unknown_deployment_is_noop(self):
        connection_manager = ConnectionManager()
        # Aucune exception attendue pour un deployment_id inconnu.
        await connection_manager.disconnect(_make_websocket(), "unknown")
        assert connection_manager.active_connections == {}


# ===========================================================================
# ConnectionManager — broadcast_to_deployment
# ===========================================================================


class TestConnectionManagerBroadcast:
    async def test_unknown_deployment_is_noop_debug(self, caplog):
        connection_manager = ConnectionManager()

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await connection_manager.broadcast_to_deployment("unknown", MESSAGE)

        assert any(
            "No active connections for deployment unknown" in r.message
            for r in caplog.records
        )

    async def test_broadcast_reaches_all_deployment_connections(self):
        connection_manager = ConnectionManager()
        first, second = _make_websocket(), _make_websocket()
        other = _make_websocket()
        await connection_manager.connect(first, "dep-1")
        await connection_manager.connect(second, "dep-1")
        await connection_manager.connect(other, "dep-2")

        await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)

        first.send_json.assert_awaited_once_with(MESSAGE)
        second.send_json.assert_awaited_once_with(MESSAGE)
        other.send_json.assert_not_awaited()

    async def test_broadcast_purges_dead_connections(self):
        connection_manager = ConnectionManager()
        dead, alive = _make_websocket(fail=True), _make_websocket()
        await connection_manager.connect(dead, "dep-1")
        await connection_manager.connect(alive, "dep-1")

        await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)

        # La socket morte est purgée, la vivante reste (et a bien reçu).
        assert connection_manager.active_connections["dep-1"] == {alive}
        alive.send_json.assert_awaited_once_with(MESSAGE)

    async def test_broadcast_dead_last_connection_removes_empty_key(self):
        """BUG-007 : la purge post-broadcast supprime la clé devenue vide.

        Même hygiène que ``disconnect`` : purge de la socket morte puis
        ``del`` de la clé quand le set est vide — plus de clé résiduelle
        ``{"dep-1": set()}`` (l'ancienne note de divergence est levée).
        """
        connection_manager = ConnectionManager()
        dead = _make_websocket(fail=True)
        await connection_manager.connect(dead, "dep-1")

        await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)

        assert "dep-1" not in connection_manager.active_connections

    async def test_broadcast_after_full_purge_is_noop_debug(self, caplog):
        """Après purge complète, un second broadcast passe par le early-return
        (la clé purgée redevient un déploiement « inconnu » — chemin l.163)."""
        connection_manager = ConnectionManager()
        dead = _make_websocket(fail=True)
        await connection_manager.connect(dead, "dep-1")
        await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)

        assert any(
            "No active connections for deployment dep-1" in r.message
            for r in caplog.records
        )

    async def test_reconnect_after_full_purge_recreates_key_and_delivers(self):
        """La suppression de la clé ne casse pas la reconnexion : ``connect``
        recrée l'entrée et le message est délivré à la nouvelle socket."""
        connection_manager = ConnectionManager()
        dead = _make_websocket(fail=True)
        await connection_manager.connect(dead, "dep-1")
        await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)
        assert "dep-1" not in connection_manager.active_connections

        alive = _make_websocket()
        await connection_manager.connect(alive, "dep-1")
        await connection_manager.broadcast_to_deployment("dep-1", MESSAGE)

        assert connection_manager.active_connections["dep-1"] == {alive}
        alive.send_json.assert_awaited_once_with(MESSAGE)

    async def test_broadcast_purge_tolerates_concurrent_key_removal(self):
        """BUG-007 (volet race) : un ``disconnect`` concurrent qui supprime la
        clé pendant l'envoi ne fait pas lever ``KeyError`` à la purge (garde
        ``.get()``). Timeout court (pattern BUG-005) : ceinture de sécurité
        anti-blocage de la suite."""
        connection_manager = ConnectionManager()
        dead = _make_websocket(fail=True)
        await connection_manager.connect(dead, "dep-1")

        async def concurrent_disconnect_during_send(*args, **kwargs):
            # Simule le ``finally`` d'un handler qui déconnecte la dernière
            # socket pendant l'« envoi » : la clé dep-1 disparaît du dict.
            connection_manager.active_connections.pop("dep-1", None)
            return 0, {dead}

        with patch.object(
            BroadcastManager,
            "_broadcast_to_connections",
            new=concurrent_disconnect_during_send,
        ):
            await asyncio.wait_for(
                connection_manager.broadcast_to_deployment("dep-1", MESSAGE),
                timeout=1.0,
            )

        assert connection_manager.active_connections == {}


# ===========================================================================
# UserConnectionManager — add / remove / subscribe
# ===========================================================================


class TestUserConnectionManagerLifecycle:
    async def test_add_connection_registers(self):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()

        await user_manager_local.add_connection("user-1", websocket)

        assert user_manager_local.user_connections["user-1"] == {websocket}

    async def test_add_connection_stores_first_plugin_context_only(self):
        user_manager_local = UserConnectionManager()
        first_context, second_context = MagicMock(), MagicMock()
        first_ws, second_ws = _make_websocket(), _make_websocket()

        await user_manager_local.add_connection(
            "user-1", first_ws, context=first_context
        )
        await user_manager_local.add_connection(
            "user-1", second_ws, context=second_context
        )

        # Le premier contexte fourni gagne (pas d'écrasement).
        assert user_manager_local.user_plugin_contexts["user-1"] is first_context

    async def test_add_connection_without_context_stores_nothing(self):
        user_manager_local = UserConnectionManager()
        await user_manager_local.add_connection("user-1", _make_websocket())
        assert user_manager_local.user_plugin_contexts == {}

    async def test_remove_connection_last_purges_subscriptions_and_context(self):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.add_connection(
            "user-1", websocket, context=MagicMock()
        )
        await user_manager_local.subscribe_to_event("user-1", "EVT", websocket)
        await user_manager_local.subscribe_to_deployment_logs(
            "user-1", "dep-1", websocket
        )

        await user_manager_local.remove_connection("user-1", websocket)

        assert "user-1" not in user_manager_local.user_connections
        assert "user-1" not in user_manager_local.user_subscriptions
        assert "user-1" not in user_manager_local.user_plugin_contexts
        # Comportement actuel : deployment_subscribers (indexé par deployment)
        # n'est PAS purgé — l'abonnement survit à la déconnexion.
        assert "dep-1" in user_manager_local.deployment_subscribers

    async def test_remove_connection_keeps_user_with_remaining_connections(self):
        user_manager_local = UserConnectionManager()
        first, second = _make_websocket(), _make_websocket()
        context = MagicMock()
        await user_manager_local.add_connection("user-1", first, context=context)
        await user_manager_local.add_connection("user-1", second)
        await user_manager_local.subscribe_to_event("user-1", "EVT", first)

        await user_manager_local.remove_connection("user-1", first)

        assert user_manager_local.user_connections["user-1"] == {second}
        # Abonnements et contexte conservés tant qu'il reste une connexion.
        assert "user-1" in user_manager_local.user_subscriptions
        assert user_manager_local.user_plugin_contexts["user-1"] is context

    async def test_remove_connection_unknown_user_is_noop(self):
        user_manager_local = UserConnectionManager()
        await user_manager_local.remove_connection("ghost", _make_websocket())
        assert user_manager_local.user_connections == {}

    async def test_subscribe_to_event_creates_entry(self):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()

        await user_manager_local.subscribe_to_event("user-1", "EVT_A", websocket)
        await user_manager_local.subscribe_to_event("user-1", "EVT_B", websocket)

        assert user_manager_local.user_subscriptions["user-1"] == {"EVT_A", "EVT_B"}

    async def test_unsubscribe_from_event_cleans_empty_key(self):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.subscribe_to_event("user-1", "EVT_A", websocket)

        await user_manager_local.unsubscribe_from_event("user-1", "EVT_A", websocket)

        assert "user-1" not in user_manager_local.user_subscriptions

    async def test_unsubscribe_keeps_other_event_types(self):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.subscribe_to_event("user-1", "EVT_A", websocket)
        await user_manager_local.subscribe_to_event("user-1", "EVT_B", websocket)

        await user_manager_local.unsubscribe_from_event("user-1", "EVT_A", websocket)

        assert user_manager_local.user_subscriptions["user-1"] == {"EVT_B"}

    async def test_unsubscribe_without_subscription_is_noop(self):
        user_manager_local = UserConnectionManager()
        await user_manager_local.unsubscribe_from_event(
            "user-1", "EVT_A", _make_websocket()
        )
        assert user_manager_local.user_subscriptions == {}

    async def test_subscribe_to_deployment_logs_registers_user(self):
        user_manager_local = UserConnectionManager()

        await user_manager_local.subscribe_to_deployment_logs(
            "user-1", "dep-1", _make_websocket()
        )

        assert user_manager_local.deployment_subscribers["dep-1"] == {"user-1"}


# ===========================================================================
# UserConnectionManager — broadcast_to_user
# ===========================================================================


class TestUserConnectionManagerBroadcastToUser:
    async def test_unknown_user_is_noop_debug(self, caplog):
        user_manager_local = UserConnectionManager()

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await user_manager_local.broadcast_to_user("ghost", MESSAGE)

        assert any(
            "No active connections for user ghost" in r.message for r in caplog.records
        )

    async def test_broadcast_reaches_all_user_connections(self):
        user_manager_local = UserConnectionManager()
        first, second = _make_websocket(), _make_websocket()
        other_user_ws = _make_websocket()
        await user_manager_local.add_connection("user-1", first)
        await user_manager_local.add_connection("user-1", second)
        await user_manager_local.add_connection("user-2", other_user_ws)

        await user_manager_local.broadcast_to_user("user-1", MESSAGE)

        first.send_json.assert_awaited_once_with(MESSAGE)
        second.send_json.assert_awaited_once_with(MESSAGE)
        other_user_ws.send_json.assert_not_awaited()

    async def test_broadcast_purges_dead_connections(self):
        """BUG-005 : la purge d'une socket morte complète sans deadlock."""
        user_manager_local = UserConnectionManager()
        dead, alive = _make_websocket(fail=True), _make_websocket()
        await user_manager_local.add_connection("user-1", dead)
        await user_manager_local.add_connection("user-1", alive)

        # Timeout court (ceinture de sécurité) : une réintroduction du
        # deadlock lèverait TimeoutError au lieu de bloquer la suite.
        await asyncio.wait_for(
            user_manager_local.broadcast_to_user("user-1", MESSAGE), timeout=1.0
        )

        assert user_manager_local.user_connections["user-1"] == {alive}
        alive.send_json.assert_awaited_once_with(MESSAGE)

    async def test_broadcast_user_lock_released_after_dead_purge(self):
        """Contre-mesure DoS (BUG-005) : après une purge de socket morte, le
        verrou du manager est réellement libéré — les opérations concurrentes
        (``add_connection`` puis ``remove_connection``) complètent sans
        bloquer."""
        user_manager_local = UserConnectionManager()
        dead = _make_websocket(fail=True)
        await user_manager_local.add_connection("user-1", dead)

        await asyncio.wait_for(
            user_manager_local.broadcast_to_user("user-1", MESSAGE), timeout=1.0
        )

        # Si _lock était encore détenu (deadlock), ces appels lèveraient
        # TimeoutError : preuve que le verrou a été libéré.
        fresh = _make_websocket()
        await asyncio.wait_for(
            user_manager_local.add_connection("user-1", fresh), timeout=1.0
        )
        await asyncio.wait_for(
            user_manager_local.remove_connection("user-1", fresh), timeout=1.0
        )

        assert "user-1" not in user_manager_local.user_connections

    async def test_broadcast_user_purges_all_dead_connections_and_keeps_alive(self):
        """Robustesse de la boucle de purge : toutes les sockets mortes sont
        purgées, la vivante reçoit le message exactement une fois."""
        user_manager_local = UserConnectionManager()
        dead_a, dead_b = _make_websocket(fail=True), _make_websocket(fail=True)
        alive = _make_websocket()
        await user_manager_local.add_connection("user-1", dead_a)
        await user_manager_local.add_connection("user-1", dead_b)
        await user_manager_local.add_connection("user-1", alive)

        await asyncio.wait_for(
            user_manager_local.broadcast_to_user("user-1", MESSAGE), timeout=1.0
        )

        assert user_manager_local.user_connections["user-1"] == {alive}
        alive.send_json.assert_awaited_once_with(MESSAGE)
        dead_a.send_json.assert_awaited_once_with(MESSAGE)
        dead_b.send_json.assert_awaited_once_with(MESSAGE)

    async def test_broadcast_user_last_dead_connection_cleans_subscriptions_and_plugin_context(
        self,
    ):
        """La purge passe bien par ``remove_connection`` (cascade complète) et
        non un simple ``discard`` : la dernière connexion morte emporte
        abonnements et contexte plugin de l'utilisateur."""
        user_manager_local = UserConnectionManager()
        dead = _make_websocket(fail=True)
        context = MagicMock()
        await user_manager_local.add_connection("user-1", dead, context=context)
        await user_manager_local.subscribe_to_event("user-1", "EVT", dead)
        assert "user-1" in user_manager_local.user_plugin_contexts

        await asyncio.wait_for(
            user_manager_local.broadcast_to_user("user-1", MESSAGE), timeout=1.0
        )

        assert "user-1" not in user_manager_local.user_connections
        assert "user-1" not in user_manager_local.user_subscriptions
        assert "user-1" not in user_manager_local.user_plugin_contexts


# ===========================================================================
# UserConnectionManager — broadcast_to_event_subscribers
# ===========================================================================


class TestBroadcastToEventSubscribers:
    async def test_subscribed_users_with_connections_receive(self):
        user_manager_local = UserConnectionManager()
        websocket_a, websocket_b = _make_websocket(), _make_websocket()
        non_subscribed = _make_websocket()
        await user_manager_local.add_connection("user-a", websocket_a)
        await user_manager_local.add_connection("user-b", websocket_b)
        await user_manager_local.add_connection("user-c", non_subscribed)
        await user_manager_local.subscribe_to_event("user-a", "EVT", websocket_a)
        await user_manager_local.subscribe_to_event("user-b", "EVT", websocket_b)
        # user-c connecté mais non abonné.

        await user_manager_local.broadcast_to_event_subscribers("EVT", MESSAGE)

        websocket_a.send_json.assert_awaited_once_with(MESSAGE)
        websocket_b.send_json.assert_awaited_once_with(MESSAGE)
        non_subscribed.send_json.assert_not_awaited()

    async def test_subscriber_without_connections_logs_warning_debug(self, caplog):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.subscribe_to_event("user-1", "EVT", websocket)
        # Aucune connexion enregistrée pour user-1.

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await user_manager_local.broadcast_to_event_subscribers("EVT", MESSAGE)

        assert any(
            "has 1 subscriber(s) but NO active connections" in r.message
            for r in caplog.records
        )

    async def test_no_subscribers_at_all_is_noop(self, caplog):
        user_manager_local = UserConnectionManager()

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await user_manager_local.broadcast_to_event_subscribers("EVT", MESSAGE)

        assert any(
            "No subscribers found for event EVT" in r.message for r in caplog.records
        )

    async def test_important_type_logs_info(self, caplog):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.add_connection("user-1", websocket)
        await user_manager_local.subscribe_to_event("user-1", "EVT", websocket)

        with caplog.at_level(logging.INFO, logger=LOGGER):
            await user_manager_local.broadcast_to_event_subscribers("EVT", MESSAGE)

        assert any(
            r.levelno == logging.INFO and "DEPLOYMENT_STATUS_CHANGED" in r.message
            for r in caplog.records
        )

    async def test_ordinary_type_logs_debug(self, caplog):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.add_connection("user-1", websocket)
        await user_manager_local.subscribe_to_event("user-1", "EVT", websocket)

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await user_manager_local.broadcast_to_event_subscribers(
                "EVT", {"type": "DEPLOYMENT_LOGS_UPDATE", "data": {}}
            )

        matching = [
            r
            for r in caplog.records
            if "broadcast successful" in r.message
            and "DEPLOYMENT_LOGS_UPDATE" in r.message
        ]
        assert matching
        assert all(r.levelno == logging.DEBUG for r in matching)

    async def test_dead_connection_of_subscriber_is_purged(self):
        user_manager_local = UserConnectionManager()
        dead, alive = _make_websocket(fail=True), _make_websocket()
        await user_manager_local.add_connection("user-1", dead)
        await user_manager_local.add_connection("user-2", alive)
        await user_manager_local.subscribe_to_event("user-1", "EVT", dead)
        await user_manager_local.subscribe_to_event("user-2", "EVT", alive)

        await user_manager_local.broadcast_to_event_subscribers("EVT", MESSAGE)

        # Purge par user (remove_connection appelé HORS lock ici — pas de deadlock).
        assert "user-1" not in user_manager_local.user_connections
        assert user_manager_local.user_connections["user-2"] == {alive}
        alive.send_json.assert_awaited_once_with(MESSAGE)


# ===========================================================================
# UserConnectionManager — broadcast_deployment_log_to_subscribers
# ===========================================================================


class TestBroadcastDeploymentLogToSubscribers:
    async def test_unknown_deployment_is_noop_debug(self, caplog):
        user_manager_local = UserConnectionManager()

        with caplog.at_level(logging.DEBUG, logger=LOGGER):
            await user_manager_local.broadcast_deployment_log_to_subscribers(
                "unknown", MESSAGE
            )

        assert any(
            "No subscribers for deployment logs unknown" in r.message
            for r in caplog.records
        )

    async def test_subscribers_receive_log(self, caplog):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.add_connection("user-1", websocket)
        await user_manager_local.subscribe_to_deployment_logs(
            "user-1", "dep-1", websocket
        )

        with caplog.at_level(logging.INFO, logger=LOGGER):
            await user_manager_local.broadcast_deployment_log_to_subscribers(
                "dep-1", MESSAGE
            )

        websocket.send_json.assert_awaited_once_with(MESSAGE)
        assert any(
            "deployment logs: dep-1" in r.message and r.levelno == logging.INFO
            for r in caplog.records
        )

    async def test_subscriber_without_connections_receives_nothing(self):
        user_manager_local = UserConnectionManager()
        websocket = _make_websocket()
        await user_manager_local.subscribe_to_deployment_logs(
            "user-1", "dep-1", websocket
        )  # abonné, aucune connexion active

        await user_manager_local.broadcast_deployment_log_to_subscribers(
            "dep-1", MESSAGE
        )

        websocket.send_json.assert_not_awaited()

    async def test_non_subscriber_never_receives(self):
        user_manager_local = UserConnectionManager()
        outsider = _make_websocket()
        await user_manager_local.add_connection("user-2", outsider)

        await user_manager_local.broadcast_deployment_log_to_subscribers(
            "dep-1", MESSAGE
        )

        outsider.send_json.assert_not_awaited()

    async def test_dead_connection_of_subscriber_is_purged(self):
        user_manager_local = UserConnectionManager()
        dead, alive = _make_websocket(fail=True), _make_websocket()
        await user_manager_local.add_connection("user-1", dead)
        await user_manager_local.add_connection("user-2", alive)
        await user_manager_local.subscribe_to_deployment_logs("user-1", "dep-1", dead)
        await user_manager_local.subscribe_to_deployment_logs("user-2", "dep-1", alive)

        await user_manager_local.broadcast_deployment_log_to_subscribers(
            "dep-1", MESSAGE
        )

        assert "user-1" not in user_manager_local.user_connections
        assert user_manager_local.user_connections["user-2"] == {alive}
        alive.send_json.assert_awaited_once_with(MESSAGE)


# ===========================================================================
# UserConnectionManager — dispatch_to_plugins
# ===========================================================================


class TestDispatchToPlugins:
    async def test_without_contexts_is_noop_debug(self, caplog):
        from app.websocket.plugin import plugin_manager

        user_manager_local = UserConnectionManager()

        with patch.object(plugin_manager, "dispatch", new=AsyncMock()) as dispatch:
            with caplog.at_level(logging.DEBUG, logger=LOGGER):
                await user_manager_local.dispatch_to_plugins("EVT", {"k": "v"})

        dispatch.assert_not_awaited()
        assert any(
            "No plugin contexts to dispatch EVT" in r.message for r in caplog.records
        )

    async def test_dispatches_to_all_contexts(self):
        from app.websocket.plugin import plugin_manager

        user_manager_local = UserConnectionManager()
        first_context, second_context = MagicMock(), MagicMock()
        user_manager_local.user_plugin_contexts["user-1"] = first_context
        user_manager_local.user_plugin_contexts["user-2"] = second_context

        with patch.object(plugin_manager, "dispatch", new=AsyncMock()) as dispatch:
            await user_manager_local.dispatch_to_plugins(
                "AUTH_LOGIN_SUCCESS", {"user_id": "user-1"}
            )

        assert dispatch.await_count == 2
        called_contexts = {call.args[2] for call in dispatch.await_args_list}
        assert called_contexts == {first_context, second_context}
        # L'event et les données sont transmis tels quels.
        first_call = dispatch.await_args_list[0]
        assert first_call.args[0] == "AUTH_LOGIN_SUCCESS"
        assert first_call.args[1] == {"user_id": "user-1"}

    async def test_dispatch_logs_context_count(self, caplog):
        from app.websocket.plugin import plugin_manager

        user_manager_local = UserConnectionManager()
        user_manager_local.user_plugin_contexts["user-1"] = MagicMock()

        with patch.object(plugin_manager, "dispatch", new=AsyncMock()):
            with caplog.at_level(logging.DEBUG, logger=LOGGER):
                await user_manager_local.dispatch_to_plugins("EVT", {})

        assert any("1 plugin context(s)" in r.message for r in caplog.records)
