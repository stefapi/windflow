"""Tests unitaires de PluginGateService (STORY-170.2 — Tâche 5).

Familles :

- **Registre** : register/unregister/idempotence/comptage ;
- **run_gates** : aucune gate → approve (le core ne bloque jamais par
  défaut), approve pass-through, deny court-circuit (2e gate non
  exécutée), timeout → ``GATE_TIMEOUT`` deny, ``on_timeout: approve`` →
  approbation, exception handler → ``gate_error`` deny (divergence n°4),
  ordre alphabétique déterministe, timeout manifest > settings ;
- **load_installed_gates** : handler valide chargé, manifest sans
  ``deploy_hooks`` ignoré (nominal sans log), handler chemin
  invalide/traversal → WARNING + ignoré (startup intact), gate pour
  plugin ``service`` hors périmètre (requête lifespan filtre).

Mocks : sessions DB substituées (pattern ``test_plugin_hooks_service``),
handlers gates = coroutines réelles espionnées.
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.plugins.gates import DeployContext, DeployImage, GateDecision
from app.services.plugin_gate_service import (
    GateOutcome,
    PluginGateService,
    get_plugin_gate_service,
    reset_plugin_gate_service,
)

# ── Helpers ─────────────────────────────────────────────────────────────────


def _ctx(images: Optional[List[DeployImage]] = None) -> DeployContext:
    """Contexte de déploiement minimal (payload sans secret)."""
    return DeployContext(
        deployment_id="dep-1",
        target={"id": "target-1", "name": "my-stack"},
        images=images or [DeployImage(name="nginx", tag="1.25")],
        trigger="manual",
    )


def _approve(ctx: DeployContext) -> GateDecision:
    """Handler gate qui approuve."""
    return GateDecision.approve()


def _deny(ctx: DeployContext) -> GateDecision:
    """Handler gate qui refuse."""
    return GateDecision.deny("policy violation")


async def _sleep_handler(ctx: DeployContext) -> GateDecision:
    """Handler gate qui dépasse le timeout (sleep long)."""
    await asyncio.sleep(5)
    return GateDecision.approve()  # pragma: no cover — jamais atteint


@pytest.fixture(autouse=True)
def _isolated_service():
    """Fournit un service frais par test (isolation du singleton)."""
    service = PluginGateService(default_timeout=2)
    yield service
    service.reset()
    reset_plugin_gate_service()


# ===========================================================================
# Registre
# ===========================================================================


class TestRegistry:
    def test_register_increments_count(self, _isolated_service):
        _isolated_service.register("plugin-a", _approve)
        assert _isolated_service.registered_count == 1

    def test_unregister_removes_gate(self, _isolated_service):
        _isolated_service.register("plugin-a", _approve)
        _isolated_service.unregister("plugin-a")
        assert _isolated_service.registered_count == 0

    def test_unregister_is_idempotent(self, _isolated_service):
        _isolated_service.unregister("plugin-ghost")  # no-op, pas d'erreur
        assert _isolated_service.registered_count == 0

    def test_reregister_replaces_handler(self, _isolated_service):
        """Idempotence par plugin : le dernier enregistrement gagne."""
        _isolated_service.register("plugin-a", _deny)
        _isolated_service.register("plugin-a", _approve)
        assert _isolated_service.registered_count == 1
        assert _isolated_service.registered_plugins == ["plugin-a"]

    def test_singleton_is_stable(self):
        svc1 = get_plugin_gate_service()
        svc2 = get_plugin_gate_service()
        assert svc1 is svc2
        svc1.register("singleton-check", _approve)
        assert svc2.registered_count >= 1
        svc2.unregister("singleton-check")


# ===========================================================================
# run_gates — comportements par défaut (AC 2)
# ===========================================================================


class TestRunGates:
    async def test_no_registered_gate_approves(self, _isolated_service):
        """Aucune gate → approve immédiat (le core ne bloque jamais)."""
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is True
        assert outcome.plugin_name is None
        assert outcome.code is None

    async def test_single_approve_passes_through(self, _isolated_service):
        _isolated_service.register("plugin-a", _approve)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is True

    async def test_single_deny_refuses(self, _isolated_service):
        _isolated_service.register("plugin-a", _deny)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is False
        assert outcome.plugin_name == "plugin-a"
        assert outcome.code == "GATE_DENIED"
        assert outcome.reason == "policy violation"

    async def test_first_deny_short_circuits(self, _isolated_service):
        """Premier deny l'emporte — les gates suivantes ne tournent pas."""
        executed: List[str] = []

        def _tracked(name: str, decision_fn):
            def handler(ctx: DeployContext) -> GateDecision:
                executed.append(name)
                return decision_fn(ctx)

            return handler

        # Ordre alphabétique : alpha-gate (deny) avant beta-gate.
        _isolated_service.register("alpha-gate", _tracked("alpha", _deny))
        _isolated_service.register("beta-gate", _tracked("beta", _approve))
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is False
        assert outcome.plugin_name == "alpha-gate"
        assert executed == ["alpha"]  # beta jamais exécutée

    async def test_all_approves_required(self, _isolated_service):
        """Deux gates approuvantes → déploiement autorisé (les 2 exécutées)."""
        _isolated_service.register("alpha-gate", _approve)
        _isolated_service.register("beta-gate", _approve)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is True

    async def test_timeout_denies_by_default(self, _isolated_service):
        """Timeout (court simulé) → refus prudent GATE_TIMEOUT."""
        _isolated_service.register("plugin-slow", _sleep_handler, timeout_override=0.05)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is False
        assert outcome.code == "GATE_TIMEOUT"
        assert outcome.plugin_name == "plugin-slow"

    async def test_on_timeout_approve_allows(self, _isolated_service):
        """``on_timeout: approve`` → déploiement autorisé au timeout."""
        _isolated_service.register(
            "plugin-slow",
            _sleep_handler,
            timeout_override=0.05,
            on_timeout="approve",
        )
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is True

    async def test_handler_exception_denies_prudently(self, _isolated_service):
        """Handler qui lève → refus prudent gate_error (divergence n°4)."""

        def _boom(ctx: DeployContext) -> GateDecision:
            raise RuntimeError("gate crashed")

        _isolated_service.register("plugin-crashy", _boom)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is False
        assert outcome.code == "gate_error"
        assert outcome.plugin_name == "plugin-crashy"

    async def test_invalid_decision_type_denies_prudently(self, _isolated_service):
        """Handler qui retourne autre chose qu'une GateDecision → refus."""

        def _bad(ctx: DeployContext):
            return {"approved": True}  # type: ignore[return-value]

        _isolated_service.register("plugin-bad-sdk", _bad)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is False
        assert outcome.code == "gate_error"

    async def test_alphabetical_order_deterministic(self, _isolated_service):
        """Itération en ordre alphabétique des noms de plugins."""
        order: List[str] = []

        def _maker(name: str):
            def handler(ctx: DeployContext) -> GateDecision:
                order.append(name)
                return GateDecision.approve()

            return handler

        _isolated_service.register("zeta", _maker("zeta"))
        _isolated_service.register("alpha", _maker("alpha"))
        _isolated_service.register("mid-plugin", _maker("mid-plugin"))
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.approved is True
        assert order == ["alpha", "mid-plugin", "zeta"]

    async def test_manifest_timeout_overrides_settings(self, _isolated_service):
        """timeout manifest (borne 1-3600) prime sur le défaut settings."""
        # default_timeout=2 (fixture) ; manifest override=0.05 → deny rapide.
        _isolated_service.register("plugin-slow", _sleep_handler, timeout_override=0.05)
        outcome = await _isolated_service.run_gates(_ctx())
        assert outcome.code == "GATE_TIMEOUT"


# ===========================================================================
# Chargement (load_installed_gates / load_gate_from_manifest)
# ===========================================================================


def _plugin_row(
    name: str,
    plugin_type: str = "extension",
    status: str = "installed",
    manifest_data: Optional[Dict[str, Any]] = None,
) -> MagicMock:
    row = MagicMock()
    row.name = name
    row.type = plugin_type
    row.status = status
    row.manifest_data = manifest_data or {}
    return row


def _session_factory(plugins: List[MagicMock]) -> MagicMock:
    """Factory de session async retournant les plugins (pattern hooks)."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = plugins
    session = AsyncMock()
    session.execute = AsyncMock(return_value=result)
    factory = MagicMock()
    factory.return_value.__aenter__ = AsyncMock(return_value=session)
    factory.return_value.__aexit__ = AsyncMock(return_value=False)
    return factory


_GATE_MODULE = (
    "from app.plugins.gates import DeployContext, GateDecision\n"
    "async def pre_deploy(ctx: DeployContext) -> GateDecision:\n"
    "    return GateDecision.approve()\n"
)


class TestLoadInstalledGates:
    async def test_valid_handler_is_loaded(self, _isolated_service, tmp_path):
        plugin_dir = tmp_path / "plugin-a"
        plugin_dir.mkdir()
        gate_file = plugin_dir / "gate_ok.py"
        gate_file.write_text(_GATE_MODULE, encoding="utf-8")
        manifest = {
            "deploy_hooks": {"pre_deploy": {"handler": "gate_ok.py:pre_deploy"}}
        }
        with patch("app.services.plugin_hooks_service.settings") as mock_settings:
            mock_settings.plugins_base_dir = str(tmp_path)
            factory = _session_factory(
                [_plugin_row("plugin-a", manifest_data=manifest)]
            )
            loaded = await _isolated_service.load_installed_gates(factory)
        assert loaded == 1
        assert _isolated_service.registered_plugins == ["plugin-a"]

    async def test_manifest_without_deploy_hooks_ignored(
        self, _isolated_service, tmp_path
    ):
        """Plugin sans deploy_hooks → ignoré, 0 chargée (nominal sans log)."""
        factory = _session_factory(
            [_plugin_row("plugin-a", manifest_data={"extensions": {}})]
        )
        loaded = await _isolated_service.load_installed_gates(factory)
        assert loaded == 0
        assert _isolated_service.registered_count == 0

    async def test_path_traversal_handler_ignored(self, _isolated_service, tmp_path):
        """Handler traversal → WARNING + ignoré, startup intact."""
        manifest = {
            "deploy_hooks": {"pre_deploy": {"handler": "../escape.py:pre_deploy"}}
        }
        factory = _session_factory([_plugin_row("plugin-a", manifest_data=manifest)])
        with patch("app.services.plugin_hooks_service.settings") as mock_settings:
            mock_settings.plugins_base_dir = str(tmp_path)
            loaded = await _isolated_service.load_installed_gates(factory)
        assert loaded == 0
        assert _isolated_service.registered_count == 0

    async def test_absolute_path_handler_ignored(self, _isolated_service, tmp_path):
        manifest = {
            "deploy_hooks": {"pre_deploy": {"handler": "/etc/passwd.py:pre_deploy"}}
        }
        factory = _session_factory([_plugin_row("plugin-a", manifest_data=manifest)])
        with patch("app.services.plugin_hooks_service.settings") as mock_settings:
            mock_settings.plugins_base_dir = str(tmp_path)
            loaded = await _isolated_service.load_installed_gates(factory)
        assert loaded == 0

    async def test_missing_function_ignored(self, _isolated_service, tmp_path):
        """Module importable mais fonction absente → WARNING + ignoré."""
        plugin_dir = tmp_path / "plugin-a"
        plugin_dir.mkdir()
        gate_file = plugin_dir / "gate_no_fn.py"
        gate_file.write_text("x = 1\n", encoding="utf-8")
        manifest = {
            "deploy_hooks": {"pre_deploy": {"handler": "gate_no_fn.py:pre_deploy"}}
        }
        factory = _session_factory([_plugin_row("plugin-a", manifest_data=manifest)])
        with patch("app.services.plugin_hooks_service.settings") as mock_settings:
            mock_settings.plugins_base_dir = str(tmp_path)
            loaded = await _isolated_service.load_installed_gates(factory)
        assert loaded == 0

    async def test_db_failure_returns_zero(self, _isolated_service):
        """Lecture DB impossible → 0 chargée, pas d'exception (startup)."""

        def _factory():
            raise RuntimeError("db down")

        loaded = await _isolated_service.load_installed_gates(_factory)
        assert loaded == 0

    async def test_timeout_override_applied_on_load(self, _isolated_service, tmp_path):
        """timeout/on_timeout du manifest enregistrés avec le handler."""
        plugin_dir = tmp_path / "plugin-a"
        plugin_dir.mkdir()
        gate_file = plugin_dir / "gate_to.py"
        gate_file.write_text(_GATE_MODULE, encoding="utf-8")
        manifest = {
            "deploy_hooks": {
                "pre_deploy": {
                    "handler": "gate_to.py:pre_deploy",
                    "timeout": 7,
                    "on_timeout": "approve",
                }
            }
        }
        with patch("app.services.plugin_hooks_service.settings") as mock_settings:
            mock_settings.plugins_base_dir = str(tmp_path)
            factory = _session_factory(
                [_plugin_row("plugin-a", manifest_data=manifest)]
            )
            await _isolated_service.load_installed_gates(factory)
        entry = _isolated_service._gates["plugin-a"]
        assert entry.timeout_override == 7.0
        assert entry.on_timeout == "approve"


class TestLoadGateFromManifest:
    def test_load_gate_from_manifest_registers(self, _isolated_service, tmp_path):
        plugin_dir = tmp_path / "plugin-a"
        plugin_dir.mkdir()
        gate_file = plugin_dir / "gate.py"
        gate_file.write_text(_GATE_MODULE, encoding="utf-8")
        manifest = {"deploy_hooks": {"pre_deploy": {"handler": "gate.py:pre_deploy"}}}
        with patch("app.services.plugin_hooks_service.settings") as mock_settings:
            mock_settings.plugins_base_dir = str(tmp_path)
            loaded = _isolated_service.load_gate_from_manifest("plugin-a", manifest)
        assert loaded is True
        assert _isolated_service.registered_plugins == ["plugin-a"]

    def test_load_gate_without_declaration_returns_false(self, _isolated_service):
        loaded = _isolated_service.load_gate_from_manifest("plugin-a", {})
        assert loaded is False

    def test_load_gate_malformed_pre_deploy_returns_false(self, _isolated_service):
        loaded = _isolated_service.load_gate_from_manifest(
            "plugin-a", {"deploy_hooks": {"pre_deploy": "not-a-dict"}}
        )
        assert loaded is False

    def test_load_gate_handler_without_colon_returns_false(self, _isolated_service):
        loaded = _isolated_service.load_gate_from_manifest(
            "plugin-a",
            {"deploy_hooks": {"pre_deploy": {"handler": "gates.py"}}},
        )
        assert loaded is False


# ===========================================================================
# SDK gates — dataclasses (couverture plugins/gates.py)
# ===========================================================================


class TestGateSdk:
    def test_approve_decision(self):
        decision = GateDecision.approve()
        assert decision.approved is True
        assert decision.reason is None

    def test_deny_decision_carries_reason(self):
        decision = GateDecision.deny("vulnerabilities found")
        assert decision.approved is False
        assert decision.reason == "vulnerabilities found"

    def test_deploy_image_defaults(self):
        img = DeployImage(name="nginx")
        assert img.tag is None
        assert img.digest is None

    def test_deploy_context_defaults(self):
        ctx = DeployContext(deployment_id="dep-1")
        assert ctx.target == {}
        assert ctx.images == []
        assert ctx.trigger == "manual"

    def test_outcome_approved_property(self):
        assert GateOutcome(decision=GateDecision.approve()).approved is True
        outcome = GateOutcome(
            decision=GateDecision.deny("no"),
            plugin_name="p",
            code="GATE_DENIED",
            reason="no",
        )
        assert outcome.approved is False
