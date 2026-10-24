"""Tests des canaux Docker container logs/stats (STORY-165 — Tâche 8, AC 2).

Couvre ``app/websocket/container_logs.py`` (29 % → ≥ 80 %) et
``app/websocket/container_stats.py`` (17 % → ≥ 80 %) :

- **fonctions pures stats** : ``calculate_cpu_percent`` (deltas nuls,
  ``online_cpus=0`` → fallback ``percpu_usage``, cap), ``calculate_memory_percent``
  (cgroups v1/v2, cache > usage, limit=0), ``calculate_network_io``,
  ``_sum_blkio_entries``, ``_build_device_stats``, ``calculate_block_io``
  (fallback throttle), ``format_stats_response`` ;
- **container_logs** : Docker indisponible → error + close **1011** ; logs
  initiaux (``tail``) puis ``stream_status started`` ; lignes ``log`` +
  ``stream_status ended`` ; erreur de stream → ``error`` ; ping texte →
  ``pong`` ; expiration connexion muette (close **1001**) ; erreur des logs
  initiaux ; ``docker_client.close()`` au finally (assert) ;
- **container_stats** : Docker indisponible → 1011 ; message ``initial`` ;
  non-running → ``container_stopped`` **sans stream** ; running → ``started``
  + messages ``stats`` formatés par ``format_stats_response`` ; erreur de
  stream → error + arrêt ; ping/pong ; expiration muette ;
  ``container_stopped`` détecté par ``check_container_status``.

⚠️ ``check_container_status`` dort 5 s (``asyncio.sleep``) : le test dédié
patche ``asyncio.sleep`` (réveil ~50 ms, non nul pour laisser la boucle
d'événements progresser) — jamais de test qui dure 5 s.

Les endpoints sont appelés **en direct** avec une WebSocket mockée (pattern
``TestSshErrorBranches`` de ``test_ws_ssh_session.py``) : la boucle
``while streaming_active`` est bornée par un ``receive_text`` séquencé
(messages puis ``WebSocketDisconnect``), une attente synchronisée sur la fin
du stream (event), ou l'expiration muette (settings réduits 1 s × 1).
"""

from __future__ import annotations

import asyncio
from typing import Optional
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import WebSocketDisconnect

from app.config import settings
from app.websocket import container_logs as logs_module
from app.websocket import container_stats as stats_module
from app.websocket.container_stats import (
    _build_device_stats,
    _sum_blkio_entries,
    calculate_block_io,
    calculate_cpu_percent,
    calculate_memory_percent,
    calculate_network_io,
    format_stats_response,
)
from app.websocket.heartbeat import WS_CLOSE_IDLE_TIMEOUT_CODE

# Réveil des sleeps patchés (check_container_status) — assez court pour un
# test rapide, assez long pour céder la main à la boucle d'événements.
FAST_SLEEP_SECONDS = 0.05

CONTAINER_ID = "c1"


# ===========================================================================
# Helpers — WebSocket mockée + Docker mocké (patterns test_ws_ssh_session)
# ===========================================================================


def _receive_sequence(messages: list[str]) -> AsyncMock:
    """``receive_text`` rend les messages puis déconnecte le client."""
    pending = list(messages)

    async def _receive():
        if pending:
            return pending.pop(0)
        raise WebSocketDisconnect()

    return AsyncMock(side_effect=_receive)


def _receive_mute() -> AsyncMock:
    """``receive_text`` muet (connexion silencieuse — expiration attendue)."""
    return AsyncMock(side_effect=asyncio.Event().wait)


def _receive_after(event: asyncio.Event, settle: float = 0.2) -> AsyncMock:
    """Attend l'event (+ délai), puis déconnecte.

    Permet d'attendre que la tâche de streaming ait envoyé ses messages
    avant la déconnexion — asserts déterministes sur les messages stream.
    """

    async def _receive():
        await event.wait()
        await asyncio.sleep(settle)
        raise WebSocketDisconnect()

    return AsyncMock(side_effect=_receive)


def _receive_delayed(delay: float = 0.4) -> AsyncMock:
    """Déconnecte après un délai fixe (laisse le stream échouer avant)."""

    async def _receive():
        await asyncio.sleep(delay)
        raise WebSocketDisconnect()

    return AsyncMock(side_effect=_receive)


def _receive_ping_after(event: asyncio.Event) -> AsyncMock:
    """Attend l'event puis rend ``ping`` (après l'échec du stream)."""

    async def _receive():
        await event.wait()
        return "ping"

    return AsyncMock(side_effect=_receive)


def _fast_sleep() -> patch:
    """Remplace ``asyncio.sleep`` par un réveil ~50 ms.

    ``check_container_status`` dort 5 s en production : un vrai sleep
    rendrait le parcours ``container_stopped`` insoluble en moins de 5 s.
    Le réveil non nul évite tout spin bloquant (la boucle cède la main à
    chaque itération).
    """
    real_sleep = asyncio.sleep

    async def _fast(delay, *args, **kwargs):  # noqa: ARG001
        await real_sleep(FAST_SLEEP_SECONDS)

    return patch.object(asyncio, "sleep", _fast)


def _silent_ping(module) -> patch:
    """``periodic_ping`` muet (annulée au finally — aucun ping parasite)."""

    async def _ping(websocket, channel):  # noqa: ARG001
        await asyncio.Event().wait()

    return patch.object(module, "periodic_ping", _ping)


def _docker_client(
    *,
    container_status: str = "running",
    initial_lines: tuple[str, ...] = ("hist-1", "hist-2"),
    initial_error: Optional[Exception] = None,
    follow_lines: tuple[str, ...] = ("live-1", "live-2"),
    follow_error: Optional[Exception] = None,
    follow_fail_event: Optional[asyncio.Event] = None,
    follow_done: Optional[asyncio.Event] = None,
    stats_payloads: Optional[tuple[dict, ...]] = None,
    stats_error: Optional[Exception] = None,
    stats_done: Optional[asyncio.Event] = None,
) -> MagicMock:
    """Client Docker factice : get_container + container_logs/container_stats.

    ``container_logs``/``container_stats`` sont des ``MagicMock`` dont le
    ``side_effect`` est une fonction générateur async (les kwargs d'appel
    restent assertables : tail/follow/stream).
    """
    client = MagicMock()
    client.close = AsyncMock()

    async def _get_container(container_id):  # noqa: ARG001
        return MagicMock(state={"Status": container_status})

    client.get_container = AsyncMock(side_effect=_get_container)

    async def _logs(
        container_id, tail=100, timestamps=False, follow=False
    ):  # noqa: ARG001
        if not follow:
            if initial_error is not None:
                raise initial_error
            for line in initial_lines:
                yield line
            return
        if follow_error is not None:
            if follow_fail_event is not None:
                follow_fail_event.set()
            raise follow_error
        for line in follow_lines:
            yield line
        if follow_done is not None:
            follow_done.set()

    client.container_logs = MagicMock(side_effect=_logs)

    async def _stats(container_id, stream=True):  # noqa: ARG001
        if stats_error is not None:
            raise stats_error
        for payload in stats_payloads or ():
            yield payload
        if stats_done is not None:
            stats_done.set()

    client.container_stats = MagicMock(side_effect=_stats)
    return client


async def _run_logs(
    websocket: AsyncMock, client: MagicMock, *, tail: int = 100
) -> None:
    """Exécute l'endpoint logs avec ``get_docker_client`` mocké (borné 8 s)."""
    with patch(
        "app.websocket.container_logs.get_docker_client",
        AsyncMock(return_value=client),
    ):
        await asyncio.wait_for(
            logs_module.container_logs_websocket_endpoint(
                websocket, CONTAINER_ID, tail=tail, user=None
            ),
            timeout=8.0,
        )


async def _run_stats(websocket: AsyncMock, client: MagicMock) -> None:
    """Exécute l'endpoint stats avec ``get_docker_client`` mocké (borné 8 s)."""
    with patch(
        "app.websocket.container_stats.get_docker_client",
        AsyncMock(return_value=client),
    ):
        await asyncio.wait_for(
            stats_module.container_stats_websocket_endpoint(
                websocket, CONTAINER_ID, user=None
            ),
            timeout=8.0,
        )


def _sent_messages(websocket: AsyncMock) -> list[dict]:
    return [c.args[0] for c in websocket.send_json.await_args_list]


def _short_heartbeat() -> list:
    """Settings d'expiration réduits (timeout = 1 s × 1)."""
    return [
        patch.object(settings, "ws_heartbeat_interval_seconds", 1),
        patch.object(settings, "ws_heartbeat_timeout_factor", 1),
    ]


def _stats_payload() -> dict:
    """Stats Docker brutes cohérentes avec les fonctions pures attendues.

    CPU : delta 100 / système 500, 2 CPUs → 40.0 %.
    Mémoire : usage 1000 - cache 200 = 800 / limite 2000 → 40.0 %.
    Réseau : 2 interfaces → rx 300 / tx 150.
    Blkio : device (8,0) read 100 / write 40, 5 reads.
    """
    return {
        "cpu_stats": {
            "cpu_usage": {"total_usage": 200, "percpu_usage": [100, 100]},
            "system_cpu_usage": 1000,
            "online_cpus": 2,
        },
        "precpu_stats": {
            "cpu_usage": {"total_usage": 100},
            "system_cpu_usage": 500,
        },
        "memory_stats": {
            "usage": 1000,
            "limit": 2000,
            "stats": {"inactive_file": 200},
        },
        "networks": {
            "eth0": {
                "rx_bytes": 200,
                "tx_bytes": 100,
                "rx_packets": 20,
                "tx_packets": 10,
                "rx_errors": 1,
                "tx_errors": 0,
                "rx_dropped": 0,
                "tx_dropped": 2,
            },
            "eth1": {
                "rx_bytes": 100,
                "tx_bytes": 50,
                "rx_packets": 5,
                "tx_packets": 5,
                "rx_errors": 0,
                "tx_errors": 1,
                "rx_dropped": 1,
                "tx_dropped": 0,
            },
        },
        "blkio_stats": {
            "io_service_bytes_recursive": [
                {"major": 8, "minor": 0, "op": "read", "value": 100},
                {"major": 8, "minor": 0, "op": "write", "value": 40},
            ],
            "io_serviced_recursive": [
                {"major": 8, "minor": 0, "op": "read", "value": 5},
            ],
        },
    }


# ===========================================================================
# Fonctions pures — calculate_* / format_stats_response
# ===========================================================================


class TestCalculateCpuPercent:
    """calculate_cpu_percent : deltas, cap, fallback percpu."""

    def test_normal_delta_computation(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 200},
                "system_cpu_usage": 1000,
                "online_cpus": 2,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 500,
            },
        }
        # (100 / 500) × 2 CPUs × 100 = 40.0
        assert calculate_cpu_percent(stats) == 40.0

    def test_zero_deltas_return_zero(self):
        """Deltas nuls (première mesure) → 0.0, jamais de division par zéro."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 500,
                "online_cpus": 1,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 500,
            },
        }
        assert calculate_cpu_percent(stats) == 0.0

    def test_negative_system_delta_return_zero(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 200},
                "system_cpu_usage": 400,
                "online_cpus": 1,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 100},
                "system_cpu_usage": 500,
            },
        }
        assert calculate_cpu_percent(stats) == 0.0

    def test_online_cpus_zero_falls_back_to_percpu_usage(self):
        """online_cpus=0 (cgroups v2 ancien) → len(percpu_usage) utilisé."""
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 300, "percpu_usage": [10, 10, 10]},
                "system_cpu_usage": 1000,
                "online_cpus": 0,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 0},
                "system_cpu_usage": 0,
            },
        }
        # (300 / 1000) × 3 CPUs × 100 = 90.0
        assert calculate_cpu_percent(stats) == 90.0

    def test_capped_at_100_percent_per_cpu(self):
        stats = {
            "cpu_stats": {
                "cpu_usage": {"total_usage": 10_000},
                "system_cpu_usage": 1000,
                "online_cpus": 2,
            },
            "precpu_stats": {
                "cpu_usage": {"total_usage": 0},
                "system_cpu_usage": 0,
            },
        }
        # (10000/1000) × 2 × 100 = 2000 → cap 100 × 2 CPUs = 200.0
        assert calculate_cpu_percent(stats) == 200.0

    def test_missing_fields_return_zero(self):
        assert calculate_cpu_percent({}) == 0.0


class TestCalculateMemoryPercent:
    """calculate_memory_percent : cgroups v1/v2, cache, limit."""

    def test_cgroups_v1_direct_cache(self):
        stats = {"memory_stats": {"usage": 1000, "cache": 200, "limit": 2000}}
        percent, used, limit = calculate_memory_percent(stats)
        assert used == 800
        assert limit == 2000
        assert percent == 40.0

    def test_cgroups_v1_stats_cache(self):
        stats = {
            "memory_stats": {
                "usage": 1000,
                "stats": {"cache": 200},
                "limit": 2000,
            }
        }
        assert calculate_memory_percent(stats)[0] == 40.0

    def test_cgroups_v2_inactive_file(self):
        """cgroups v2 : le cache vit dans stats.inactive_file."""
        stats = {
            "memory_stats": {
                "usage": 1000,
                "stats": {"inactive_file": 200},
                "limit": 2000,
            }
        }
        percent, used, _ = calculate_memory_percent(stats)
        assert used == 800
        assert percent == 40.0

    def test_cache_greater_than_usage_keeps_usage(self):
        """cache > usage (données incohérentes) → used = usage, jamais négatif."""
        stats = {"memory_stats": {"usage": 100, "cache": 500, "limit": 2000}}
        percent, used, _ = calculate_memory_percent(stats)
        assert used == 100
        assert percent == 5.0

    def test_zero_limit_returns_zero_percent(self):
        stats = {"memory_stats": {"usage": 500, "cache": 100, "limit": 0}}
        percent, used, limit = calculate_memory_percent(stats)
        assert percent == 0.0
        assert used == 400
        assert limit == 0

    def test_percent_capped_at_100(self):
        stats = {"memory_stats": {"usage": 5000, "limit": 1000}}
        assert calculate_memory_percent(stats)[0] == 100.0


class TestCalculateNetworkIo:
    """calculate_network_io : totaux + détail par interface."""

    def test_two_interfaces_totals_and_details(self):
        stats = {
            "networks": {
                "eth0": {"rx_bytes": 200, "tx_bytes": 100, "rx_errors": 1},
                "eth1": {"rx_bytes": 100, "tx_bytes": 50, "tx_dropped": 2},
            }
        }
        result = calculate_network_io(stats)
        assert result["rx_bytes"] == 300
        assert result["tx_bytes"] == 150
        assert result["total_rx_errors"] == 1
        assert result["total_tx_dropped"] == 2
        assert {i["name"] for i in result["interfaces"]} == {"eth0", "eth1"}
        eth0 = next(i for i in result["interfaces"] if i["name"] == "eth0")
        assert eth0["rx_bytes"] == 200
        assert eth0["rx_errors"] == 1

    def test_no_networks_returns_zero_totals(self):
        result = calculate_network_io({})
        assert result["rx_bytes"] == 0
        assert result["tx_bytes"] == 0
        assert result["interfaces"] == []


class TestBlkioHelpers:
    """_sum_blkio_entries / _build_device_stats / calculate_block_io."""

    def test_sum_entries_read_write_and_malformed(self):
        entries = [
            {"op": "Read", "value": 10},  # casse normalisée
            {"op": "write", "value": 20},
            {"op": "discard", "value": 99},  # op inconnue → ignorée
            "not-a-dict",  # entrée malformée → ignorée
            {"op": 42, "value": 5},  # op non-str → ignorée
            {"op": "read", "value": None},  # value None → 0
        ]
        assert _sum_blkio_entries(entries) == (10, 20)

    def test_sum_entries_none_or_empty(self):
        assert _sum_blkio_entries(None) == (0, 0)
        assert _sum_blkio_entries([]) == (0, 0)

    def test_build_device_stats_aggregates_bytes_and_iops(self):
        service_bytes = [
            {"major": 8, "minor": 0, "op": "read", "value": 100},
            {"major": 8, "minor": 0, "op": "write", "value": 40},
            {"major": 253, "minor": 1, "op": "read", "value": 7},
            "garbage",
        ]
        serviced = [{"major": 8, "minor": 0, "op": "read", "value": 5}]
        devices = _build_device_stats(service_bytes, serviced)
        assert len(devices) == 2
        dev = next(d for d in devices if d["major"] == 8 and d["minor"] == 0)
        assert dev["read_bytes"] == 100
        assert dev["write_bytes"] == 40
        assert dev["read_ops"] == 5
        assert dev["write_ops"] == 0

    def test_build_device_stats_iops_only_creates_device(self):
        """Device présent uniquement dans io_serviced → bytes à 0."""
        devices = _build_device_stats(
            None, [{"major": 8, "minor": 2, "op": "write", "value": 3}]
        )
        assert devices == [
            {
                "major": 8,
                "minor": 2,
                "read_bytes": 0,
                "write_bytes": 0,
                "read_ops": 0,
                "write_ops": 3,
            }
        ]

    def test_block_io_main_entries(self):
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [
                    {"major": 8, "minor": 0, "op": "read", "value": 100},
                    {"major": 8, "minor": 0, "op": "write", "value": 40},
                ]
            }
        }
        result = calculate_block_io(stats)
        assert result["read_bytes"] == 100
        assert result["write_bytes"] == 40
        assert len(result["devices"]) == 1

    def test_block_io_fallback_throttle_when_main_empty(self):
        """cgroups v2 ancien : fallback throttle_io_service_bytes_recursive."""
        stats = {
            "blkio_stats": {
                "io_service_bytes_recursive": [],
                "throttle_io_service_bytes_recursive": [
                    {"major": 8, "minor": 0, "op": "read", "value": 60}
                ],
            }
        }
        result = calculate_block_io(stats)
        assert result["read_bytes"] == 60
        assert result["write_bytes"] == 0

    def test_block_io_no_data_returns_zeros(self):
        result = calculate_block_io({"blkio_stats": {}})
        assert result == {"read_bytes": 0, "write_bytes": 0, "devices": []}


class TestFormatStatsResponse:
    """format_stats_response : structure complète du message ``stats``."""

    def test_full_structure(self):
        result = format_stats_response("c1", _stats_payload())
        assert result["type"] == "stats"
        assert result["container_id"] == "c1"
        assert isinstance(result["timestamp"], str)
        assert result["cpu"] == {"percent": 40.0}
        assert result["memory"] == {"percent": 40.0, "used": 800, "limit": 2000}
        assert result["network"]["rx_bytes"] == 300
        assert result["network"]["tx_bytes"] == 150
        assert len(result["network"]["interfaces"]) == 2
        assert result["block_io"]["read_bytes"] == 100
        assert result["block_io"]["write_bytes"] == 40
        device = result["block_io"]["devices"][0]
        assert device["read_ops"] == 5


# ===========================================================================
# Endpoint container_logs — handler direct, WebSocket mockée
# ===========================================================================


class TestContainerLogsEndpoint:
    """Canal /ws/docker/containers/{id}/logs (Docker mocké)."""

    async def test_docker_unavailable_sends_error_and_closes_1011(self):
        """Docker indisponible → message error + close 1011."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()

        with patch(
            "app.websocket.container_logs.get_docker_client",
            AsyncMock(side_effect=RuntimeError("socket unreachable")),
        ):
            await asyncio.wait_for(
                logs_module.container_logs_websocket_endpoint(
                    websocket, CONTAINER_ID, tail=100, user=None
                ),
                timeout=3.0,
            )

        sent = _sent_messages(websocket)
        error = next(m for m in sent if m["type"] == "error")
        assert "Docker not available" in error["message"]
        websocket.close.assert_awaited_once_with(code=1011)

    async def test_initial_logs_started_pong_and_docker_closed(self):
        """Parcours nominal : initial (tail) + started + pong + close Docker."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_sequence(["ping"])
        client = _docker_client()

        with _silent_ping(logs_module):
            await _run_logs(websocket, client, tail=50)

        sent = _sent_messages(websocket)
        initial = next(m for m in sent if m["type"] == "initial")
        assert initial["container_id"] == CONTAINER_ID
        assert initial["logs"] == "hist-1\nhist-2"
        assert any(
            m["type"] == "stream_status" and m["status"] == "started" for m in sent
        )
        assert any(m["type"] == "pong" for m in sent)
        # Le client Docker est bien fermé au finally.
        client.close.assert_awaited_once()
        # Contrat d'appel : historique tail=N, puis follow tail=0.
        client.container_logs.assert_any_call(
            CONTAINER_ID, tail=50, timestamps=False, follow=False
        )
        client.container_logs.assert_any_call(
            CONTAINER_ID, tail=0, timestamps=False, follow=True
        )

    async def test_follow_stream_lines_then_ended(self):
        """Stream follow : lignes log puis stream_status ended à la fin."""
        follow_done = asyncio.Event()
        websocket = AsyncMock()
        websocket.receive_text = _receive_after(follow_done, settle=0.3)
        client = _docker_client(follow_done=follow_done)

        with _silent_ping(logs_module):
            await _run_logs(websocket, client)

        sent = _sent_messages(websocket)
        log_lines = [m["data"] for m in sent if m["type"] == "log"]
        assert log_lines == ["live-1", "live-2"]
        assert any(
            m["type"] == "stream_status" and m["status"] == "ended" for m in sent
        )
        client.close.assert_awaited_once()

    async def test_follow_stream_error_sends_error_message(self):
        """Erreur pendant le stream → message error « Log streaming error »."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_delayed(0.5)
        client = _docker_client(
            follow_error=RuntimeError("boom"), follow_lines=("live-1",)
        )

        with _silent_ping(logs_module):
            await _run_logs(websocket, client)

        sent = _sent_messages(websocket)
        error = next(m for m in sent if m["type"] == "error")
        assert error["message"] == "Log streaming error: boom"
        client.close.assert_awaited_once()

    async def test_initial_logs_error_sends_generic_error(self):
        """Erreur pendant la lecture des logs initiaux → error + cleanup."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()
        client = _docker_client(initial_error=RuntimeError("nope"))

        with _silent_ping(logs_module):
            await _run_logs(websocket, client)

        sent = _sent_messages(websocket)
        error = next(m for m in sent if m["type"] == "error")
        assert error["message"] == "nope"
        client.close.assert_awaited_once()

    async def test_mute_connection_expired_closes_1001(self):
        """Expiration : client muet → close serveur 1001 (settings réduits)."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()
        client = _docker_client()

        patches = _short_heartbeat()
        with _silent_ping(logs_module):
            with patches[0], patches[1]:
                await _run_logs(websocket, client)

        kwargs = websocket.close.await_args.kwargs
        assert kwargs.get("code") == WS_CLOSE_IDLE_TIMEOUT_CODE
        client.close.assert_awaited_once()

    async def test_send_log_failure_breaks_stream_silently(self):
        """Échec d'envoi d'une ligne → break du stream, aucune error propagée."""
        websocket = AsyncMock()

        async def _send_json(message):
            if message.get("type") == "log":
                raise RuntimeError("client gone")

        websocket.send_json = AsyncMock(side_effect=_send_json)
        websocket.receive_text = _receive_delayed(0.4)
        client = _docker_client()

        with _silent_ping(logs_module):
            await _run_logs(websocket, client)

        sent = _sent_messages(websocket)
        # Le stream a tenté d'envoyer des lignes puis s'est arrêté…
        assert any(m.get("type") == "log" for m in sent)
        # …sans jamais remonter d'erreur applicative.
        assert not any(m.get("type") == "error" for m in sent)
        client.close.assert_awaited_once()

    async def test_streaming_task_error_stops_main_loop(self):
        """Boucle principale : tâche de stream échouée → détectée → arrêt."""
        failed = asyncio.Event()
        websocket = AsyncMock()
        websocket.receive_text = _receive_ping_after(failed)
        client = _docker_client(
            follow_error=RuntimeError("stream died"),
            follow_fail_event=failed,
        )

        with _silent_ping(logs_module):
            await _run_logs(websocket, client)

        # L'erreur de streaming est signalée (par la tâche) et la boucle
        # principale est sortie proprement (client Docker fermé).
        sent = _sent_messages(websocket)
        assert any(
            m.get("type") == "error" and "stream died" in m.get("message", "")
            for m in sent
        )
        client.close.assert_awaited_once()

    async def test_check_status_error_keeps_streaming(self):
        """Erreur de check_container_status → debug seulement, stream continue."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()
        client = _docker_client()
        client.get_container = AsyncMock(side_effect=RuntimeError("inspect failed"))

        patches = _short_heartbeat()
        with _silent_ping(logs_module):
            with _fast_sleep():
                with patches[0], patches[1]:
                    await _run_logs(websocket, client)

        sent = _sent_messages(websocket)
        assert any(m["type"] == "initial" for m in sent)
        # Une erreur d'inspect n'arrête jamais le stream ni la connexion
        # (fermée ici par expiration muette, pas par l'erreur).
        assert not any(m["type"] == "error" for m in sent)
        kwargs = websocket.close.await_args.kwargs
        assert kwargs.get("code") == WS_CLOSE_IDLE_TIMEOUT_CODE
        client.close.assert_awaited_once()

    async def test_container_stopped_detected_by_status_check(self):
        """check_container_status (sleep patché) → container_stopped.

        Le container passe « exited » : la tâche de vérification envoie
        ``stream_status container_stopped`` et stoppe le stream ; la boucle
        principale (receive muet) sort par expiration 1001.
        """
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()
        client = _docker_client(container_status="exited")

        patches = _short_heartbeat()
        with _silent_ping(logs_module):
            with _fast_sleep():
                with patches[0], patches[1]:
                    await _run_logs(websocket, client)

        sent = _sent_messages(websocket)
        stopped = [
            m
            for m in sent
            if m["type"] == "stream_status" and m["status"] == "container_stopped"
        ]
        assert stopped
        assert stopped[0]["message"] == "Container is exited"
        client.close.assert_awaited_once()


# ===========================================================================
# Endpoint container_stats — handler direct, WebSocket mockée
# ===========================================================================


class TestContainerStatsEndpoint:
    """Canal /ws/docker/containers/{id}/stats (Docker mocké)."""

    async def test_docker_unavailable_sends_error_and_closes_1011(self):
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()

        with patch(
            "app.websocket.container_stats.get_docker_client",
            AsyncMock(side_effect=RuntimeError("docker down")),
        ):
            await asyncio.wait_for(
                stats_module.container_stats_websocket_endpoint(
                    websocket, CONTAINER_ID, user=None
                ),
                timeout=3.0,
            )

        sent = _sent_messages(websocket)
        error = next(m for m in sent if m["type"] == "error")
        assert "Docker not available" in error["message"]
        websocket.close.assert_awaited_once_with(code=1011)

    async def test_non_running_container_stopped_without_stream(self):
        """Container non-running au connect → initial + container_stopped."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()
        client = _docker_client(
            container_status="paused", stats_payloads=(_stats_payload(),)
        )

        with _silent_ping(stats_module):
            await _run_stats(websocket, client)

        sent = _sent_messages(websocket)
        initial = next(m for m in sent if m["type"] == "initial")
        assert initial["container_id"] == CONTAINER_ID
        assert initial["container_status"] == "paused"
        stopped = [
            m
            for m in sent
            if m["type"] == "stream_status" and m["status"] == "container_stopped"
        ]
        assert stopped
        assert stopped[0]["message"] == "Container is paused"
        # Aucun stream lancé pour un container arrêté.
        client.container_stats.assert_not_called()
        client.close.assert_awaited_once()

    async def test_running_streams_formatted_stats(self):
        """Running → started puis message stats formaté (fonctions pures)."""
        stats_done = asyncio.Event()
        websocket = AsyncMock()
        websocket.receive_text = _receive_after(stats_done, settle=0.3)
        client = _docker_client(
            stats_payloads=(_stats_payload(),), stats_done=stats_done
        )

        with _silent_ping(stats_module):
            await _run_stats(websocket, client)

        sent = _sent_messages(websocket)
        initial = next(m for m in sent if m["type"] == "initial")
        assert initial["container_status"] == "running"
        assert any(
            m["type"] == "stream_status" and m["status"] == "started" for m in sent
        )
        stats_message = next(m for m in sent if m["type"] == "stats")
        assert stats_message["container_id"] == CONTAINER_ID
        assert stats_message["cpu"] == {"percent": 40.0}
        assert stats_message["memory"] == {
            "percent": 40.0,
            "used": 800,
            "limit": 2000,
        }
        assert stats_message["network"]["rx_bytes"] == 300
        assert stats_message["block_io"]["read_bytes"] == 100
        # Contrat d'appel : streaming temps réel.
        client.container_stats.assert_called_once_with(CONTAINER_ID, stream=True)
        client.close.assert_awaited_once()

    async def test_stats_stream_error_sends_error_message(self):
        """Erreur pendant le stream stats → error « Stats streaming error »."""
        websocket = AsyncMock()
        websocket.receive_text = _receive_delayed(0.5)
        client = _docker_client(stats_error=RuntimeError("stats boom"))

        with _silent_ping(stats_module):
            await _run_stats(websocket, client)

        sent = _sent_messages(websocket)
        error = next(m for m in sent if m["type"] == "error")
        assert error["message"] == "Stats streaming error: stats boom"
        client.close.assert_awaited_once()

    async def test_ping_text_answered_with_pong(self):
        websocket = AsyncMock()
        websocket.receive_text = _receive_sequence(["ping"])
        client = _docker_client(stats_payloads=(_stats_payload(),))

        with _silent_ping(stats_module):
            await _run_stats(websocket, client)

        sent = _sent_messages(websocket)
        pong = next(m for m in sent if m["type"] == "pong")
        assert "timestamp" in pong

    async def test_mute_connection_expired_closes_1001(self):
        websocket = AsyncMock()
        websocket.receive_text = _receive_mute()
        client = _docker_client(stats_payloads=(_stats_payload(),))

        patches = _short_heartbeat()
        with _silent_ping(stats_module):
            with patches[0], patches[1]:
                await _run_stats(websocket, client)

        kwargs = websocket.close.await_args.kwargs
        assert kwargs.get("code") == WS_CLOSE_IDLE_TIMEOUT_CODE
        client.close.assert_awaited_once()
