"""Tests d'insertion des gates pre-deploy dans le pipeline (STORY-170.2 — Tâche 9).

AC 1/AC 2 : les gates s'exécutent **après résolution d'images, avant
création des containers** — un refus annule le déploiement avant toute
création (``deploy_container``/``deploy_compose`` jamais appelés),
statut FAILED, event ``error`` data ``code=GATE_DENIED``/``plugin``/
``reason``, bus ``deployment.failed`` émis avec le payload gate.

Familles (chemin docker + miroir compose) :

- ``deny`` → annulation avant création + FAILED typé ;
- timeout court simulé (sleep + timeout 0.05 s) → ``GATE_TIMEOUT`` ;
- ``on_timeout: approve`` → déploiement poursuit ;
- deux gates (A approve, B deny) → deny l'emporte, court-circuit ;
- gate qui lève → refus prudent ``gate_error`` ;
- **aucune gate enregistrée → déploiement nominal inchangé** (AC 3).

Mocks : pattern ``test_deploy_stack_progress`` — sessions/DB
substituées, le singleton gate est réinitialisé entre les tests.
"""

from __future__ import annotations

import asyncio
from contextlib import ExitStack
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import GateDeniedError
from app.plugins.gates import DeployContext, GateDecision
from app.services.plugin_gate_service import (
    get_plugin_gate_service,
    reset_plugin_gate_service,
)

# ── Helpers (pattern test_deploy_stack_progress) ────────────────────────────


def _make_deployment(name: str = "dep-test") -> MagicMock:
    deployment = MagicMock()
    deployment.id = "dep-id-1"
    deployment.name = name
    return deployment


def _make_stack(target_type: str) -> MagicMock:
    stack = MagicMock()
    stack.id = "stack-id-1"
    stack.name = "my-stack"
    stack.version = "1.0.0"
    stack.target_type = target_type
    stack.template = {"image": "nginx:latest"}
    return stack


def _mock_session_factory(deployment: MagicMock, stack: MagicMock) -> MagicMock:
    session = AsyncMock()
    call_count = {"n": 0}

    async def execute(query: Any) -> MagicMock:
        call_count["n"] += 1
        result = MagicMock()
        if call_count["n"] == 1:
            result.scalar_one_or_none.return_value = deployment
        else:
            result.scalar_one_or_none.return_value = stack
        return result

    session.execute = execute

    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


def _docker_service_mock(deploy_result=(True, "abc123")) -> MagicMock:
    svc = MagicMock()
    svc.substitute_variables.return_value = {"image": "nginx"}
    svc.validate_container_config.return_value = (True, "")
    svc.deploy_container = AsyncMock(return_value=deploy_result)
    return svc


def _compose_service_mock(deploy_result=(True, "done")) -> MagicMock:
    svc = MagicMock()
    svc.substitute_variables.return_value = {"services": {"web": {"image": "nginx"}}}
    svc.validate_compose.return_value = (True, "")
    svc.generate_compose_file.return_value = None
    svc.deploy_compose = AsyncMock(return_value=deploy_result)
    return svc


class _Spy:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


@pytest.fixture(autouse=True)
def _clean_gate_singleton():
    """Isolation : registre de gates vide avant/après chaque test."""
    reset_plugin_gate_service()
    yield
    reset_plugin_gate_service()


async def _run_deploy(
    stack: MagicMock,
    docker_service: MagicMock,
    compose_service: MagicMock | None = None,
):
    """Exécute deploy_stack_async avec les mocks pipeline en place.

    Retourne ``(raised_exception, update_status_mock)`` — l'exception
    n'est pas propagée hors du helper pour inspection directe.
    """
    deployment = _make_deployment()
    factory = _mock_session_factory(deployment, stack)
    update_status = AsyncMock()
    spy = _Spy()

    from app.tasks.background_tasks import deploy_stack_async

    patches: Dict[str, Any] = {
        "session": patch("app.database.AsyncSessionLocal", new=factory),
        "docker": patch(
            "app.services.docker_service.DockerService", return_value=docker_service
        ),
        "events": patch(
            "app.services.deployment_events.get_deployment_events",
            return_value=MagicMock(emit_progress_update=spy),
        ),
        "status": patch(
            "app.services.deployment_service.DeploymentService.update_status",
            new=update_status,
        ),
    }
    if compose_service is not None:
        patches["compose"] = patch(
            "app.services.docker_compose_service.DockerComposeService",
            return_value=compose_service,
        )

    with ExitStack() as stack:
        for ctx in patches.values():
            stack.enter_context(ctx)
        try:
            await deploy_stack_async(
                deployment_id="dep-id-1",
                stack_id="stack-id-1",
                target_id="target-id-1",
                user_id="user-1",
                configuration={},
            )
            return None, update_status
        except Exception as exc:  # noqa: BLE001 — inspecté par les tests
            return exc, update_status


def _gate(extra_handler=None, **register_kwargs):
    """Enregistre une gate approuvante par défaut sur le singleton."""
    service = get_plugin_gate_service()

    def handler(ctx: DeployContext) -> GateDecision:
        if extra_handler is not None:
            return extra_handler(ctx)
        return GateDecision.approve()

    service.register("plugin-a", handler, **register_kwargs)
    return service


def _last_failed_call(update_status: AsyncMock) -> Any:
    """Dernier appel update_status avec FAILED → kwargs d'intérêt."""
    from app.models.deployment import DeploymentStatus

    calls = [
        c
        for c in update_status.await_args_list
        if len(c.args) >= 3 and c.args[2] == DeploymentStatus.FAILED
    ]
    assert calls, "aucun appel update_status(FAILED)"
    return calls[-1]


# ===========================================================================
# AC 1 — deny : annulation AVANT création des containers (chemin docker)
# ===========================================================================


async def test_deny_cancels_before_container_creation():
    """Gate deny → deploy_container jamais appelé + FAILED + trace gate."""
    _gate(extra_handler=lambda ctx: GateDecision.deny("vulnerable image"))
    docker_service = _docker_service_mock()

    exc, update_status = await _run_deploy(_make_stack("docker"), docker_service)

    # 1. deploy_container JAMAIS appelé (aucune création de container).
    docker_service.deploy_container.assert_not_called()
    # 2. Exception typée propagée (échec classique du pipeline).
    assert isinstance(exc, GateDeniedError)
    assert exc.details["code"] == "GATE_DENIED"
    assert exc.details["plugin"] == "plugin-a"
    assert exc.details["reason"] == "vulnerable image"
    # 3. Statut FAILED avec enrichissement event data gate.
    failed = _last_failed_call(update_status)
    assert failed.kwargs.get("event_data_extra") == {
        "code": "GATE_DENIED",
        "plugin": "plugin-a",
        "reason": "vulnerable image",
    }
    # 4. Message de log gate présent dans les logs du FAILED.
    assert "gate du plugin plugin-a" in (failed.kwargs.get("logs") or "")


async def test_deny_does_not_create_containers_and_marks_failed():
    """AC 1 bis : refus → FAILED classique, aucun appel docker résiduel."""
    _gate(extra_handler=lambda ctx: GateDecision.deny("nope"))
    docker_service = _docker_service_mock()

    exc, update_status = await _run_deploy(_make_stack("docker"), docker_service)

    assert isinstance(exc, GateDeniedError)
    docker_service.deploy_container.assert_not_called()
    _last_failed_call(update_status)  # FAILED émis exactement une fois


# ===========================================================================
# AC 2 — comportements par défaut (chemin docker)
# ===========================================================================


async def test_timeout_denies_gate_timeout():
    """Timeout court simulé → refus prudent GATE_TIMEOUT, pas de création."""
    service = get_plugin_gate_service()

    async def slow(ctx: DeployContext) -> GateDecision:
        await asyncio.sleep(5)
        return GateDecision.approve()  # pragma: no cover

    service.register("plugin-slow", slow, timeout_override=0.05)
    docker_service = _docker_service_mock()

    exc, update_status = await _run_deploy(_make_stack("docker"), docker_service)

    docker_service.deploy_container.assert_not_called()
    assert isinstance(exc, GateDeniedError)
    assert exc.details["code"] == "GATE_TIMEOUT"
    failed = _last_failed_call(update_status)
    assert failed.kwargs["event_data_extra"]["code"] == "GATE_TIMEOUT"
    assert failed.kwargs["event_data_extra"]["plugin"] == "plugin-slow"


async def test_on_timeout_approve_deploys():
    """on_timeout: approve → déploiement poursuit malgré le timeout."""
    service = get_plugin_gate_service()

    async def slow(ctx: DeployContext) -> GateDecision:
        await asyncio.sleep(5)
        return GateDecision.approve()  # pragma: no cover

    service.register("plugin-slow", slow, timeout_override=0.05, on_timeout="approve")
    docker_service = _docker_service_mock()

    exc, _ = await _run_deploy(_make_stack("docker"), docker_service)

    assert exc is None
    docker_service.deploy_container.assert_awaited_once()


async def test_multiple_gates_first_deny_wins():
    """Deux gates (A approve, B deny) → deny l'emporte, court-circuit."""
    service = get_plugin_gate_service()
    executed: List[str] = []

    def alpha_handler(ctx: DeployContext) -> GateDecision:
        executed.append("alpha")
        return GateDecision.approve()

    def beta_handler(ctx: DeployContext) -> GateDecision:
        executed.append("beta")
        return GateDecision.deny("policy")

    # Enregistrement volontairement inversé : l'exécution reste
    # alphabétique (alpha avant beta) — le deny de beta court-circuite
    # toute gate ultérieure, alpha a déjà approuvé.
    service.register("beta-gate", beta_handler)
    service.register("alpha-gate", alpha_handler)
    docker_service = _docker_service_mock()

    exc, _ = await _run_deploy(_make_stack("docker"), docker_service)

    assert isinstance(exc, GateDeniedError)
    assert exc.details["plugin"] == "beta-gate"
    assert executed == ["alpha", "beta"]
    docker_service.deploy_container.assert_not_called()


async def test_gate_error_denies_prudently():
    """Gate qui lève → refus prudent gate_error, pas de création."""
    service = get_plugin_gate_service()

    def boom(ctx: DeployContext) -> GateDecision:
        raise RuntimeError("trivy down")

    service.register("plugin-crashy", boom)
    docker_service = _docker_service_mock()

    exc, update_status = await _run_deploy(_make_stack("docker"), docker_service)

    docker_service.deploy_container.assert_not_called()
    assert isinstance(exc, GateDeniedError)
    assert exc.details["code"] == "gate_error"
    failed = _last_failed_call(update_status)
    assert failed.kwargs["event_data_extra"]["plugin"] == "plugin-crashy"


async def test_no_registered_gate_deploys_nominal():
    """AC 3 : aucune gate → déploiement nominal inchangé (non-régression)."""
    docker_service = _docker_service_mock()

    exc, update_status = await _run_deploy(_make_stack("docker"), docker_service)

    assert exc is None
    docker_service.deploy_container.assert_awaited_once()
    # Aucun enrichissement gate sur les appels.
    for call in update_status.await_args_list:
        assert not call.kwargs.get("event_data_extra")


# ===========================================================================
# Miroir compose — AC 1/AC 2 sur le chemin docker-compose
# ===========================================================================


async def test_compose_deny_cancels_before_deploy_compose():
    """Chemin compose : gate deny → deploy_compose jamais appelé + FAILED."""
    _gate(extra_handler=lambda ctx: GateDecision.deny("compose policy"))
    compose_service = _compose_service_mock()

    exc, update_status = await _run_deploy(
        _make_stack("docker-compose"), _docker_service_mock(), compose_service
    )

    compose_service.deploy_compose.assert_not_called()
    assert isinstance(exc, GateDeniedError)
    assert exc.details["code"] == "GATE_DENIED"
    failed = _last_failed_call(update_status)
    assert failed.kwargs["event_data_extra"]["plugin"] == "plugin-a"


async def test_compose_timeout_denies_gate_timeout():
    """Chemin compose : timeout → GATE_TIMEOUT, aucune création."""
    service = get_plugin_gate_service()

    async def slow(ctx: DeployContext) -> GateDecision:
        await asyncio.sleep(5)
        return GateDecision.approve()  # pragma: no cover

    service.register("plugin-slow", slow, timeout_override=0.05)
    compose_service = _compose_service_mock()

    exc, _ = await _run_deploy(
        _make_stack("docker-compose"), _docker_service_mock(), compose_service
    )

    compose_service.deploy_compose.assert_not_called()
    assert isinstance(exc, GateDeniedError)
    assert exc.details["code"] == "GATE_TIMEOUT"


async def test_compose_no_gate_deploys_nominal():
    """Chemin compose : aucune gate → déploiement nominal (non-régression)."""
    compose_service = _compose_service_mock()

    exc, _ = await _run_deploy(
        _make_stack("docker-compose"), _docker_service_mock(), compose_service
    )

    assert exc is None
    compose_service.deploy_compose.assert_awaited_once()


# ===========================================================================
# Helpers d'extraction d'images — divergence n°1 (digest au mieux)
# ===========================================================================


class TestExtractImages:
    def test_docker_path_extracts_image(self):
        from app.tasks.background_tasks import _extract_images_from_config

        images = _extract_images_from_config({"image": "nginx:1.25"})
        assert len(images) == 1
        assert images[0].name == "nginx"
        assert images[0].tag == "1.25"

    def test_compose_path_extracts_services(self):
        from app.tasks.background_tasks import _extract_images_from_config

        images = _extract_images_from_config(
            {"services": {"web": {"image": "nginx"}, "db": {"image": "postgres:16"}}}
        )
        assert {img.name for img in images} == {"nginx", "postgres"}

    def test_explicit_digest_is_kept(self):
        from app.tasks.background_tasks import _parse_image_reference

        img = _parse_image_reference("nginx@sha256:abcd")
        assert img.name == "nginx"
        assert img.digest == "sha256:abcd"

    def test_registry_port_not_mistaken_for_tag(self):
        from app.tasks.background_tasks import _parse_image_reference

        img = _parse_image_reference("registry:5000/app/web")
        assert img.name == "registry:5000/app/web"
        assert img.tag is None

    def test_none_and_invalid_inputs(self):
        from app.tasks.background_tasks import _extract_images_from_config

        assert _extract_images_from_config(None) == []
        assert _extract_images_from_config({"services": "not-a-dict"}) == []
