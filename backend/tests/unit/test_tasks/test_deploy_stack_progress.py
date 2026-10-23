"""Tests d'émission DEPLOYMENT_PROGRESS par deploy_stack_async (STORY-163 — T5/AC 3).

Familles :

- **Chemin docker simple** : mock ``DeploymentService.update_status`` +
  ``DockerService`` (succès) + espion ``emit_progress_update`` → séquence
  **monotone** : progression croissante, premier jalon ≥ 5, dernier = 100,
  ``total_steps`` constant ;
- **Chemin compose** : jalons supplémentaires (``labels_injected``,
  ``compose_generated``) présents, séquence monotone ;
- **Échec** : ``deploy_container`` échoue → exception propagée + ``FAILED``
  via ``update_status``, **aucun** progress après l'échec ;
- **Best-effort** : ``emit_progress_update`` en erreur → le déploiement
  **réussit quand même**.

Mocks : sessions/DB entièrement substituées (aucun accès base réelle) —
``deploy_stack_async`` importe ses dépendances dans la fonction, chaque
test patche les symboles dans leurs modules sources respectifs.
"""

from __future__ import annotations

from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# ===========================================================================
# Helpers — fixtures de mocking du pipeline
# ===========================================================================


class _ProgressSpy:
    """Espion d'emit_progress_update : capture (progress, step, total)."""

    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def __call__(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


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
    """AsyncSessionLocal mockée : execute → deployment puis stack."""
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


def _pipeline_patches(
    spy: _ProgressSpy,
    deploy_success: bool = True,
    emit_raises: bool = False,
):
    """Construit les patches communs des deux chemins de déploiement."""

    async def _maybe_failing_emit(**kwargs: Any) -> None:
        if emit_raises:
            raise RuntimeError("progress broadcast down")
        await spy(**kwargs)

    update_status = AsyncMock()

    return {
        "db": patch("app.database.AsyncSessionLocal", new=None),
        "update_status": patch(
            "app.services.deployment_service.DeploymentService.update_status",
            new=update_status,
        ),
        "emit": patch(
            "app.services.deployment_events.get_deployment_events",
            return_value=MagicMock(emit_progress_update=_maybe_failing_emit),
        ),
    }, update_status


async def _run_deploy(
    stack: MagicMock,
    spy: _ProgressSpy,
    docker_service: MagicMock,
    compose_service: MagicMock | None = None,
    emit_raises: bool = False,
):
    """Exécute deploy_stack_async avec tous les mocks en place."""
    deployment = _make_deployment()
    factory = _mock_session_factory(deployment, stack)

    patches: Dict[str, Any] = {}
    patches["session"] = patch("app.database.AsyncSessionLocal", new=factory)
    patches["docker"] = patch(
        "app.services.docker_service.DockerService", return_value=docker_service
    )
    if compose_service is not None:
        patches["compose"] = patch(
            "app.services.docker_compose_service.DockerComposeService",
            return_value=compose_service,
        )

    async def _emit(**kwargs: Any) -> None:
        if emit_raises:
            raise RuntimeError("progress broadcast down")
        await spy(**kwargs)

    patches["events"] = patch(
        "app.services.deployment_events.get_deployment_events",
        return_value=MagicMock(emit_progress_update=_emit),
    )

    update_status = AsyncMock()
    patches["status"] = patch(
        "app.services.deployment_service.DeploymentService.update_status",
        new=update_status,
    )

    from app.tasks.background_tasks import deploy_stack_async

    with patches["session"], patches["docker"], patches["events"], patches["status"]:
        if compose_service is not None:
            with patches["compose"]:
                result = await deploy_stack_async(
                    deployment_id="dep-id-1",
                    stack_id="stack-id-1",
                    target_id="target-id-1",
                    user_id="user-1",
                    configuration={},
                )
                return result, update_status
        result = await deploy_stack_async(
            deployment_id="dep-id-1",
            stack_id="stack-id-1",
            target_id="target-id-1",
            user_id="user-1",
            configuration={},
        )
    return result, update_status


def _progress_sequence(spy: _ProgressSpy) -> List[int]:
    return [c["progress"] for c in spy.calls]


# ===========================================================================
# Chemin docker simple (AC 3)
# ===========================================================================


async def test_docker_path_emits_monotonic_progress_sequence():
    """Docker simple : séquence monotone, premier ≥ 5, dernier = 100."""
    spy = _ProgressSpy()
    docker_service = MagicMock()
    docker_service.substitute_variables.return_value = {"image": "nginx"}
    docker_service.validate_container_config.return_value = (True, "")
    docker_service.deploy_container = AsyncMock(return_value=(True, "abc123"))

    result, _ = await _run_deploy(_make_stack("docker"), spy, docker_service)

    assert result["status"] == "success"
    sequence = _progress_sequence(spy)
    assert sequence, "aucun progress émis"
    assert sequence[0] >= 5
    assert sequence[-1] == 100
    assert sequence == sorted(sequence), f"séquence non monotone : {sequence}"
    # total_steps constant sur tout le chemin docker
    totals = {c["total_steps"] for c in spy.calls}
    assert totals == {7}
    # Jalons attendus présents
    steps = [c["step"] for c in spy.calls]
    for expected in (
        "starting",
        "stack_loaded",
        "mode_determined",
        "variables_substituted",
        "validated",
        "deploying",
        "completed",
    ):
        assert expected in steps, f"jalon manquant : {expected}"


# ===========================================================================
# Chemin compose (AC 3)
# ===========================================================================


async def test_compose_path_emits_extra_milestones():
    """Compose : jalons labels/compose présents, séquence monotone."""
    spy = _ProgressSpy()
    docker_service = MagicMock()  # non utilisé sur ce chemin
    compose_service = MagicMock()
    compose_service.substitute_variables.return_value = {
        "services": {"web": {"image": "nginx"}}
    }
    compose_service.validate_compose.return_value = (True, "")
    compose_service.generate_compose_file.return_value = None
    compose_service.deploy_compose = AsyncMock(return_value=(True, "done"))

    result, _ = await _run_deploy(
        _make_stack("docker-compose"), spy, docker_service, compose_service
    )

    assert result["status"] == "success"
    sequence = _progress_sequence(spy)
    assert sequence == sorted(sequence)
    assert sequence[-1] == 100
    totals = {c["total_steps"] for c in spy.calls}
    assert totals == {9}
    steps = [c["step"] for c in spy.calls]
    for expected in ("labels_injected", "compose_generated"):
        assert expected in steps, f"jalon compose manquant : {expected}"


# ===========================================================================
# Échec de déploiement — aucun progress après l'échec
# ===========================================================================


async def test_failed_deployment_propagates_and_emits_no_late_progress():
    """Échec : exception propagée + FAILED via update_status, pas de progress tardif."""
    spy = _ProgressSpy()
    docker_service = MagicMock()
    docker_service.substitute_variables.return_value = {"image": "nginx"}
    docker_service.validate_container_config.return_value = (True, "")
    docker_service.deploy_container = AsyncMock(return_value=(False, "docker error"))

    with pytest.raises(Exception, match="docker error"):
        await _run_deploy(_make_stack("docker"), spy, docker_service)

    # Aucun progress d'achèvement après l'échec (dernier < 100).
    sequence = _progress_sequence(spy)
    assert sequence, "jalons pré-échec attendus"
    assert sequence[-1] < 100
    assert "completed" not in [c["step"] for c in spy.calls]


async def test_failure_marks_deployment_failed():
    """Le chemin d'erreur appelle update_status avec FAILED."""
    from unittest.mock import patch as _patch

    spy = _ProgressSpy()
    docker_service = MagicMock()
    docker_service.substitute_variables.return_value = {"image": "nginx"}
    docker_service.validate_container_config.return_value = (True, "")
    docker_service.deploy_container = AsyncMock(return_value=(False, "boom"))

    deployment = _make_deployment()
    stack = _make_stack("docker")
    factory = _mock_session_factory(deployment, stack)
    update_status = AsyncMock()

    from app.models.deployment import DeploymentStatus
    from app.tasks.background_tasks import deploy_stack_async

    async def _emit(**kwargs: Any) -> None:
        await spy(**kwargs)

    with _patch("app.database.AsyncSessionLocal", new=factory), _patch(
        "app.services.docker_service.DockerService", return_value=docker_service
    ), _patch(
        "app.services.deployment_events.get_deployment_events",
        return_value=MagicMock(emit_progress_update=_emit),
    ), _patch(
        "app.services.deployment_service.DeploymentService.update_status",
        new=update_status,
    ):
        with pytest.raises(Exception, match="boom"):
            await deploy_stack_async(
                deployment_id="dep-id-1",
                stack_id="stack-id-1",
                target_id="target-id-1",
                user_id="user-1",
                configuration={},
            )

    # Le dernier appel update_status porte FAILED
    last_call = update_status.await_args_list[-1]
    assert last_call.args[2] == DeploymentStatus.FAILED


# ===========================================================================
# Best-effort — émission en erreur ne fait pas échouer le déploiement
# ===========================================================================


async def test_progress_emission_failure_does_not_break_deployment():
    """emit_progress_update en erreur → déploiement réussit quand même."""
    spy = _ProgressSpy()
    docker_service = MagicMock()
    docker_service.substitute_variables.return_value = {"image": "nginx"}
    docker_service.validate_container_config.return_value = (True, "")
    docker_service.deploy_container = AsyncMock(return_value=(True, "abc"))

    result, _ = await _run_deploy(
        _make_stack("docker"), spy, docker_service, emit_raises=True
    )

    assert result["status"] == "success"
    assert result["container_id"] == "abc"
