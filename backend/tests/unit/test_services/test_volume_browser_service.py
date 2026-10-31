"""Tests unitaires du service `volume_browser` (STORY-173 — sécurité D3).

Garde structurelle : image épinglée, montage read-only, réseau none,
exec args-liste sans shell, anti-traversal, nettoyage garanti du
conteneur éphémère même sur erreur.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from app.core.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
    UnprocessableEntityError,
)
from app.services import volume_browser_service
from app.services.volume_browser_service import browse_volume


def _fake_volume(name: str):
    return SimpleNamespace(
        name=name,
        driver="local",
        mountpoint=f"/var/lib/docker/volumes/{name}",
        created_at=datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc),
        labels={},
        scope="local",
    )


def _client2(
    volume_exists: bool = True, exit_code: int = 0, output: str = "data/\nfile.txt\n"
):
    """Client Docker factice — exec retourne un ExecResult-like stable."""
    client = AsyncMock()
    client.list_volumes.return_value = [_fake_volume("mydata")] if volume_exists else []
    client.create_container.return_value = "eph-container-id"
    client.start_container = AsyncMock()
    client.remove_container = AsyncMock()
    client.close = AsyncMock()
    client.exec_in_container = AsyncMock(
        return_value=SimpleNamespace(exit_code=exit_code, output=output, error="")
    )
    return client


# =============================================================================
# Validations d'entrée (422 — jamais de conteneur créé)
# =============================================================================


async def test_browse_validates_volume_name_regex():
    """Nom invalide → UnprocessableEntityError, AUCUN conteneur créé."""
    client = _client2()
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        with pytest.raises(UnprocessableEntityError):
            await browse_volume("../etc", None, 1, 20)
        with pytest.raises(UnprocessableEntityError):
            await browse_volume("bad name", None, 1, 20)
        with pytest.raises(UnprocessableEntityError):
            await browse_volume("-leading-dash", None, 1, 20)

    client.create_container.assert_not_awaited()


async def test_browse_rejects_traversal_subpath():
    """`../` et chemin absolu → 422, aucun conteneur créé."""
    client = _client2()
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        with pytest.raises(UnprocessableEntityError):
            await browse_volume("mydata", "../../host", 1, 20)
        with pytest.raises(UnprocessableEntityError):
            await browse_volume("mydata", "/etc/passwd", 1, 20)
        with pytest.raises(UnprocessableEntityError):
            await browse_volume("mydata", "ok/../../../root", 1, 20)

    client.create_container.assert_not_awaited()


# =============================================================================
# Existence & disponibilité
# =============================================================================


async def test_browse_unknown_volume_404():
    """list_volumes vide → NotFoundError."""
    client = _client2(volume_exists=False)
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        with pytest.raises(NotFoundError):
            await browse_volume("ghost", None, 1, 20)
    client.create_container.assert_not_awaited()


async def test_browse_docker_unavailable_explicit_error():
    """Docker indisponible → ServiceUnavailableError (pas de 200 vide)."""
    client = _client2()
    client.list_volumes.side_effect = RuntimeError("socket down")
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        with pytest.raises(ServiceUnavailableError):
            await browse_volume("mydata", None, 1, 20)
    client.close.assert_awaited_once()


# =============================================================================
# Garde structurelle du conteneur éphémère (D3)
# =============================================================================


async def test_browse_uses_pinned_image_readonly_none_network():
    """image=busybox:1.37, mount mode=ro, network_mode=none, pas de privileged."""
    client = _client2()
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        await browse_volume("mydata", None, 1, 20)

    kwargs = client.create_container.await_args.kwargs
    assert kwargs["image"] == "busybox:1.37"  # épinglée — jamais :latest
    assert kwargs["network_mode"] == "none"
    assert kwargs["privileged"] is False
    assert kwargs["readonly_rootfs"] is True
    assert kwargs["labels"] == {"windflow.transient": "true"}
    mounts = kwargs["mounts"]
    assert len(mounts) == 1
    assert mounts[0]["source"] == "mydata"
    assert mounts[0]["destination"] == "/vol"
    assert mounts[0]["mode"] == "ro"
    assert kwargs["name"].startswith("windflow-browse-")
    client.remove_container.assert_awaited_once_with("eph-container-id", force=True)
    client.close.assert_awaited_once()


async def test_browse_exec_uses_arg_list_no_shell():
    """exec reçoit ["ls", "-1p", "/vol[...]"] — liste, aucun string shell."""
    client = _client2()
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        await browse_volume("mydata", None, 1, 20)
        await browse_volume("mydata", "sub/dir", 1, 20)

    first_cmd = client.exec_in_container.await_args_list[0].args[1]
    assert first_cmd == ["ls", "-1p", "/vol"]
    second_cmd = client.exec_in_container.await_args_list[1].args[1]
    assert second_cmd == ["ls", "-1p", "/vol/sub/dir"]
    for call in client.exec_in_container.await_args_list:
        cmd = call.args[1]
        assert isinstance(cmd, list)
        assert cmd[0] == "ls"
        assert not any(";" in part or "&&" in part for part in cmd)


async def test_browse_parses_ls_output_dirs_and_files():
    """Sortie ls -1p (suffixe /) → is_dir correct + pagination."""
    client = _client2(output="dir-a/\ndir-b/\nfile-1.txt\nfile-2.yml\n")
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        result = await browse_volume("mydata", None, 1, 2)

    assert len(result.data) == 2  # page 1, per_page 2
    assert result.data[0].name == "dir-a"
    assert result.data[0].is_dir is True
    assert result.data[0].path == "dir-a"
    assert result.data[1].name == "dir-b"
    assert result.data[1].is_dir is True
    assert result.pagination.total == 4
    assert result.pagination.pages == 2


async def test_browse_cleans_up_container_on_exec_error():
    """exec lève → remove_container appelé quand même (finally), erreur propagée."""

    client = _client2()
    client.exec_in_container = AsyncMock(side_effect=RuntimeError("exec boom"))
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        with pytest.raises(RuntimeError, match="exec boom"):
            await browse_volume("mydata", None, 1, 20)

    client.remove_container.assert_awaited_once_with("eph-container-id", force=True)
    client.close.assert_awaited_once()


async def test_browse_exec_nonzero_exit_raises_windflow_exception():
    """exec exit != 0 (ex. sous-chemin inexistant) → WindFlowException explicite."""
    from app.core.exceptions import WindFlowException

    client = _client2(exit_code=1, output="")
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        with pytest.raises(WindFlowException):
            await browse_volume("mydata", "inexistant", 1, 20)
    client.remove_container.assert_awaited_once()


async def test_browse_cleanup_failure_is_swallowed():
    """Échec du remove_container (best-effort) ne masque pas le résultat."""
    client = _client2()
    client.remove_container = AsyncMock(side_effect=RuntimeError("already gone"))
    with patch.object(
        volume_browser_service, "DockerClientService", return_value=client
    ):
        result = await browse_volume("mydata", None, 1, 20)

    assert result.pagination.total == 2
    client.close.assert_awaited_once()
