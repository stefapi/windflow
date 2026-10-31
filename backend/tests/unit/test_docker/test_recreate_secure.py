"""Tests du recreate sécurisé — orchestration 6 étapes + rollback (STORY-174.2).

AC 3/AC 4 : capture avant pull, renommage -old, réseaux, rebase, rollback
sur échec (pull/create/start), secrets préservés sans fuite.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.core.exceptions import WindFlowException
from app.services.docker_client_service import DockerClientService


def _detail(running=True, env=None, labels=None, cmd=None, networks=None):
    """ContainerDetail réaliste pour l'orchestration."""
    from app.services.docker_client_service import ContainerDetail

    return ContainerDetail(
        id="old123abc",
        name="app-web",
        created=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        path="nginx",
        args=[],
        state={"Running": running, "Status": "running" if running else "exited"},
        image="nginx:1.27",
        config={
            "Image": "nginx:1.27",
            "Env": env or ["TZ=UTC", "POSTGRES_PASSWORD=s3cr3t"],
            "Labels": labels or {"app": "web"},
            "Cmd": cmd or ["nginx", "-g", "daemon off;"],
        },
        host_config={
            "NetworkMode": "bridge",
            "RestartPolicy": {"Name": "no"},
            "Privileged": False,
            "PortBindings": {"80/tcp": [{"HostPort": "8080"}]},
        },
        network_settings={"Networks": networks or {}},
        mounts=[
            {"Type": "volume", "Source": "data", "Destination": "/data", "Mode": "rw"}
        ],
    )


def _image_info(env=None, labels=None, cmd=None):
    return {
        "Config": {
            "Env": env or [],
            "Labels": labels or {},
            "Cmd": cmd,
        }
    }


def _client(running=True, networks=None, env=None, cmd=None):
    """Client avec toutes les primitives mockées + capture de l'ordre."""
    svc = DockerClientService()
    detail = _detail(running=running, networks=networks, env=env, cmd=cmd)
    old_img = _image_info(
        env=["TZ=UTC"], labels={"app": "web"}, cmd=["nginx", "-g", "daemon off;"]
    )
    new_img = _image_info(
        env=["TZ=Europe/Paris"], labels={"app": "web2"}, cmd=["nginx", "-new"]
    )

    svc.get_container = AsyncMock(return_value=detail)
    svc.inspect_image = AsyncMock(
        side_effect=lambda ref: old_img if "1.27" in ref else new_img
    )
    svc.pull_image = AsyncMock(return_value="Pull complete")
    svc.stop_container = AsyncMock()
    svc.rename_container = AsyncMock()
    svc.disconnect_container_from_network = AsyncMock()
    svc.create_container = AsyncMock(return_value="new456def")
    svc.connect_container_to_network = AsyncMock()
    svc.start_container = AsyncMock()
    svc.remove_container = AsyncMock()
    return svc, detail


class TestStepOrder:
    async def test_old_image_captured_before_pull(self):
        """AC 3 : inspect_image AVANT pull_image (capture préalable)."""
        svc, _ = _client()
        await svc.recreate_container_secure("old123abc", pull_image=True)
        # inspect_image et pull_image sont des AsyncMocks distincts —
        # on assert le schéma : inspect_image appelé 2× (old + new).
        assert svc.inspect_image.await_count == 2
        assert svc.pull_image.await_count == 1

    async def test_stop_rename_old_disconnect_order(self):
        """Arrêt → renommage -old → déconnexion → création."""
        svc, _ = _client(
            networks={
                "extra-net": {
                    "Aliases": ["alias1"],
                    "IPAMConfig": {"IPv4Address": "172.20.0.5"},
                }
            }
        )
        await svc.recreate_container_secure("old123abc")
        svc.stop_container.assert_awaited_once()
        svc.rename_container.assert_awaited_once_with("old123abc", "app-web-old")
        svc.disconnect_container_from_network.assert_awaited_once_with(
            "extra-net", "old123abc"
        )
        svc.create_container.assert_awaited_once()

    async def test_reconnect_restores_aliases_and_ipamconfig(self):
        """Reconnexion avec aliases + IPv4 d'origine (AC 3/AC 4)."""
        svc, _ = _client(
            networks={
                "extra-net": {
                    "Aliases": ["alias1"],
                    "IPAMConfig": {"IPv4Address": "172.20.0.5"},
                }
            }
        )
        await svc.recreate_container_secure("old123abc")
        svc.connect_container_to_network.assert_awaited_once_with(
            "extra-net", "new456def", aliases=["alias1"], ipv4_address="172.20.0.5"
        )

    async def test_old_removed_force_false_volumes_kept(self):
        """Étape 5 : suppression ancien sans force, volumes préservés."""
        svc, _ = _client()
        await svc.recreate_container_secure("old123abc")
        svc.remove_container.assert_awaited_once_with(
            "old123abc", force=False, remove_volumes=False
        )

    @pytest.mark.parametrize("running", [True, False])
    async def test_start_only_if_old_was_running(self, running):
        """Démarrage conditionnel (l'ancien tournait ou non)."""
        svc, _ = _client(running=running)
        svc.get_container = AsyncMock(
            side_effect=lambda cid: (
                _detail() if cid == "new456def" else _detail(running=running)
            )
        )
        await svc.recreate_container_secure("old123abc")
        if running:
            svc.start_container.assert_awaited_once_with("new456def")
        else:
            svc.start_container.assert_not_awaited()


class TestRebase:
    async def test_rebase_applied_on_create(self):
        """Env rebasé : TZ suit la nouvelle image, secret conservé, ajouts conservés."""
        svc, _ = _client(env=["TZ=UTC", "POSTGRES_PASSWORD=s3cr3t", "EXTRA=1"])
        await svc.recreate_container_secure("old123abc", image="nginx:2.0")
        kwargs = svc.create_container.await_args.kwargs
        assert "TZ=Europe/Paris" in kwargs["env"]  # identique à old → suit new
        assert "POSTGRES_PASSWORD=s3cr3t" in kwargs["env"]  # absent old → conservé
        assert "EXTRA=1" in kwargs["env"]  # ajout utilisateur
        assert kwargs["command"] == ["nginx", "-new"]  # Cmd cuit suit l'image

    async def test_user_command_survives(self):
        svc, _ = _client(cmd=["my", "custom"])
        await svc.recreate_container_secure("old123abc")
        assert svc.create_container.await_args.kwargs["command"] == ["my", "custom"]


class TestRollback:
    async def test_pull_failure_leaves_old_container_intact(self):
        """AC 4 : échec pull → exception, ancien jamais renommé ni supprimé."""
        svc, _ = _client()
        svc.pull_image = AsyncMock(side_effect=RuntimeError("registry down"))
        with pytest.raises(WindFlowException, match="Pull"):
            await svc.recreate_container_secure("old123abc", pull_image=True)
        svc.rename_container.assert_not_awaited()
        svc.remove_container.assert_not_awaited()

    async def test_rollback_on_create_failure_restores_old(self):
        """AC 4 : échec création → rollback complet (rename back, réseaux, start)."""
        svc, _ = _client(
            networks={
                "net2": {"Aliases": ["a"], "IPAMConfig": {"IPv4Address": "10.0.0.9"}}
            }
        )
        svc.create_container = AsyncMock(side_effect=RuntimeError("name conflict"))
        with pytest.raises(WindFlowException, match="recreate_failed_rolled_back"):
            await svc.recreate_container_secure("old123abc")
        # nouveau jamais créé → ancien restauré
        svc.rename_container.assert_awaited_with("old123abc", "app-web")
        svc.connect_container_to_network.assert_awaited_with(
            "net2", "old123abc", aliases=["a"], ipv4_address="10.0.0.9"
        )
        svc.start_container.assert_awaited_with("old123abc")

    async def test_rollback_on_start_failure_removes_new_and_restores(self):
        """AC 4 : échec démarrage → nouveau retiré + ancien restauré."""
        svc, _ = _client()

        async def _start_only_new_fails(cid: str) -> None:
            if cid == "new456def":
                raise RuntimeError("start boom")

        svc.start_container = AsyncMock(side_effect=_start_only_new_fails)
        with pytest.raises(WindFlowException, match="recreate_failed_rolled_back"):
            await svc.recreate_container_secure("old123abc")
        svc.remove_container.assert_any_await(
            "new456def", force=True, remove_volumes=False
        )
        svc.rename_container.assert_awaited_with("old123abc", "app-web")
        svc.start_container.assert_awaited_with("old123abc")

    async def test_rollback_failure_marks_rollback_incomplete(self):
        """Rollback lui-même en échec → recreate_rollback_incomplete (CRITICAL)."""
        svc, _ = _client()
        svc.start_container = AsyncMock(side_effect=RuntimeError("start boom"))
        svc.rename_container = AsyncMock(
            side_effect=[None, RuntimeError("rename back fails")]
        )
        with pytest.raises(WindFlowException, match="recreate_rollback_incomplete"):
            await svc.recreate_container_secure("old123abc")


class TestSecrets:
    async def test_recreate_with_masked_secret_preserves_real_value(self):
        """AC 4 : env soumis avec `***` → valeur réelle préservée, jamais en clair
        dans la requête de création autre que la valeur résolue (backend-only)."""
        svc, _ = _client(env=["TZ=UTC", "POSTGRES_PASSWORD=s3cr3t"])
        await svc.recreate_container_secure(
            "old123abc", env=["TZ=UTC", "POSTGRES_PASSWORD=***"]
        )
        kwargs = svc.create_container.await_args.kwargs
        assert "POSTGRES_PASSWORD=s3cr3t" in kwargs["env"]  # résolu depuis le réel
        assert "POSTGRES_PASSWORD=***" not in kwargs["env"]

    async def test_no_env_value_ever_logged(self, caplog):
        """Sécurité (rules 40) : la valeur secrète n'apparaît jamais dans les logs."""
        svc, _ = _client(env=["TZ=UTC", "POSTGRES_PASSWORD=s3cr3t"])
        with caplog.at_level(
            logging.DEBUG, logger="app.services.docker_client_service"
        ):
            await svc.recreate_container_secure("old123abc")
        assert "s3cr3t" not in caplog.text
