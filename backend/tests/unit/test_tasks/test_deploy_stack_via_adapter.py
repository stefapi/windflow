"""Tests de la bascule du chemin de déploiement par l'adapter (STORY-174.1, AC 2).

Le déploiement (Docker simple et compose) passe par ``get_app_adapter`` ;
les gates pre-deploy STORY-170.2 restent exécutées **avant** toute création
de container (position spec 11) ; les jalons WS STORY-163 sont inchangés.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.tasks.background_tasks as bt


class _FakeResult:
    def __init__(self, scalar):
        self._scalar = scalar

    def scalar_one_or_none(self):
        return self._scalar


class _FakeDB:
    """Session async minimale : renvoie deployment puis stack."""

    def __init__(self, deployment, stack):
        self._queue = [_FakeResult(deployment), _FakeResult(stack)]

    async def execute(self, *_a, **_k):
        return self._queue.pop(0)

    async def commit(self):
        return None


def _deployment():
    return SimpleNamespace(id="dep-1", name="app-web")


def _stack(target_type: str):
    return SimpleNamespace(
        id="stack-1",
        name="web",
        version=1,
        target_type=target_type,
        template={"image": "nginx"},
        organization_id="org-1",
    )


def _session_factory(db):
    """Fabrique de contextes de session — un nouveau mock par ``async with``."""

    def _factory():
        ctx = AsyncMock()
        ctx.__aenter__ = AsyncMock(return_value=db)
        ctx.__aexit__ = AsyncMock(return_value=False)
        return ctx

    return _factory


def _progress_events():
    return SimpleNamespace(emit_progress_update=AsyncMock())


def _deployment_service():
    return SimpleNamespace(update_status=AsyncMock())


def _docker_service_mock(deploy_result=(True, "cid")):
    svc = MagicMock()
    svc.substitute_variables = MagicMock(side_effect=lambda tpl, cfg: dict(tpl))
    svc.validate_container_config = MagicMock(return_value=(True, ""))
    svc.deploy_container = AsyncMock(return_value=deploy_result)
    return svc


def _compose_service_mock(deploy_result=(True, "ok")):
    svc = MagicMock()
    svc.substitute_variables = MagicMock(side_effect=lambda tpl, cfg: dict(tpl))
    svc.validate_compose = MagicMock(return_value=(True, ""))
    svc.generate_compose_file = MagicMock(return_value=None)
    svc.deploy_compose = AsyncMock(return_value=deploy_result)
    return svc


class TestDeployViaAdapter:
    async def test_docker_deploy_goes_through_adapter(self, monkeypatch):
        """Le chemin Docker appelle DockerService.deploy_container (via l'adapter)."""
        db = _FakeDB(_deployment(), _stack("docker"))
        db_ctx_factory = _session_factory(db)
        docker_service = _docker_service_mock()

        monkeypatch.setattr("app.database.AsyncSessionLocal", db_ctx_factory)
        monkeypatch.setattr(
            "app.services.deployment_events.get_deployment_events", _progress_events
        )
        monkeypatch.setattr(bt, "_run_pre_deploy_gates", AsyncMock())
        monkeypatch.setattr(
            "app.services.deployment_service.DeploymentService.update_status",
            AsyncMock(),
        )

        with patch(
            "app.services.docker_service.DockerService", return_value=docker_service
        ):
            result = await bt.deploy_stack_async(
                deployment_id="dep-1",
                stack_id="stack-1",
                target_id="t-1",
                user_id="u-1",
                configuration={},
            )
        assert result["status"] == "success"
        docker_service.deploy_container.assert_awaited_once()

    async def test_gates_run_before_container_creation(self, monkeypatch):
        """Sécurité (spec 11) : gates exécutées AVANT deploy (ordre vérifié)."""
        order = []
        docker_service = _docker_service_mock()
        docker_service.deploy_container = AsyncMock(
            side_effect=lambda *a, **k: order.append("deploy") or (True, "cid")
        )

        async def gates(**kwargs):
            order.append("gates")

        db = _FakeDB(_deployment(), _stack("docker"))
        db_ctx_factory = _session_factory(db)

        monkeypatch.setattr("app.database.AsyncSessionLocal", db_ctx_factory)
        monkeypatch.setattr(
            "app.services.deployment_events.get_deployment_events", _progress_events
        )
        monkeypatch.setattr(bt, "_run_pre_deploy_gates", gates)
        monkeypatch.setattr(
            "app.services.deployment_service.DeploymentService.update_status",
            AsyncMock(),
        )

        with patch(
            "app.services.docker_service.DockerService", return_value=docker_service
        ):
            await bt.deploy_stack_async(
                deployment_id="dep-1",
                stack_id="stack-1",
                target_id="t",
                user_id="u",
                configuration={},
            )
        assert order == ["gates", "deploy"]

    async def test_compose_deploy_goes_through_adapter(self, monkeypatch):
        """Le chemin compose appelle deploy_compose (via l'adapter)."""
        db = _FakeDB(_deployment(), _stack("docker_compose"))
        db_ctx_factory = _session_factory(db)
        compose_service = _compose_service_mock()

        monkeypatch.setattr("app.database.AsyncSessionLocal", db_ctx_factory)
        monkeypatch.setattr(
            "app.services.deployment_events.get_deployment_events", _progress_events
        )
        monkeypatch.setattr(bt, "_run_pre_deploy_gates", AsyncMock())
        monkeypatch.setattr(
            "app.services.deployment_service.DeploymentService.update_status",
            AsyncMock(),
        )

        with patch(
            "app.services.docker_compose_service.DockerComposeService",
            return_value=compose_service,
        ):
            result = await bt.deploy_stack_async(
                deployment_id="dep-1",
                stack_id="stack-1",
                target_id="t-1",
                user_id="u-1",
                configuration={},
            )
        assert result["status"] == "success"
        compose_service.deploy_compose.assert_awaited_once()

    async def test_gate_denial_fails_deployment_without_deploy(self, monkeypatch):
        """Refus de gate → exception, aucun appel deploy (aucune création)."""
        from app.core.exceptions import WindFlowException

        docker_service = _docker_service_mock()

        async def gates(**kw):
            raise WindFlowException("gate denied")

        db = _FakeDB(_deployment(), _stack("docker"))
        db_ctx_factory = _session_factory(db)

        monkeypatch.setattr("app.database.AsyncSessionLocal", db_ctx_factory)
        monkeypatch.setattr(
            "app.services.deployment_events.get_deployment_events", _progress_events
        )
        monkeypatch.setattr(bt, "_run_pre_deploy_gates", gates)
        monkeypatch.setattr(
            "app.services.deployment_service.DeploymentService.update_status",
            AsyncMock(),
        )

        with pytest.raises(WindFlowException, match="gate denied"):
            with patch(
                "app.services.docker_service.DockerService", return_value=docker_service
            ):
                await bt.deploy_stack_async(
                    deployment_id="dep-1",
                    stack_id="stack-1",
                    target_id="t",
                    user_id="u",
                    configuration={},
                )
        docker_service.deploy_container.assert_not_awaited()
