"""Tests unitaires du plugin démonstrateur Trivy (STORY-170.3 — Tâche 1).

Familles (AC 1 + AC 2 — la matrice de critères spec 11 est exposée
dans la config, ``never`` réel, bloquant simulé, fail-safe critère
inconnu, conventions codées en constantes) :

- **Mode ``never`` réel** : approve quelle que soit l'image — avec ou
  sans config, images multiples ou vides ;
- **Mode bloquant simulé** : chaque critère ≠ ``never`` → deny avec
  raison contenant ``[SIMULÉ]``, le nom d'image et le critère ;
- **Fail-safe** : critère inconnu → comportement ``never`` (approve) ;
- **Intégration SDK** : la gate s'exécute via ``PluginGateService.
  run_gates`` (contrat STORY-170.2 — deny simulé → ``GATE_DENIED``) ;
- **Conventions** : image épinglée sans ``:latest``, volume
  ``windflow-plugin-trivy-cache``, suffixe tag pending, matrice
  complète.

Isolation : variable d'environnement ``PLUGIN_CONFIG_BLOCK_CRITERIA``
nettoyée autour de chaque test (monkeypatch).
"""

from __future__ import annotations

from typing import List, Optional

import pytest

from app.plugins.examples.demo_trivy_gate import (
    BLOCK_CRITERIA,
    CACHE_VOLUME,
    DEFAULT_BLOCK_CRITERIA,
    PENDING_TAG_SUFFIX,
    SIMULATED_FINDINGS,
    TRIVY_IMAGE,
    pre_deploy,
)
from app.plugins.gates import DeployContext, DeployImage
from app.services.plugin_gate_service import PluginGateService

# ── Helpers ─────────────────────────────────────────────────────────────────

_CRITERIA_ENV = "PLUGIN_CONFIG_BLOCK_CRITERIA"


def _ctx(
    images: Optional[List[DeployImage]] = None,
) -> DeployContext:
    """Contexte de déploiement minimal (payload sans secret)."""
    return DeployContext(
        deployment_id="dep-1",
        target={"id": "target-1", "name": "my-stack"},
        images=(
            images
            if images is not None
            else [
                DeployImage(name="nginx:1.25", tag="1.25"),
                DeployImage(name="redis:7", tag="7"),
            ]
        ),
        trigger="manual",
    )


@pytest.fixture(autouse=True)
def _clean_criteria_env(monkeypatch: pytest.MonkeyPatch):
    """Garantit un critère absent par défaut (isolation des tests)."""
    monkeypatch.delenv(_CRITERIA_ENV, raising=False)
    yield


# ===========================================================================
# Mode never réel (AC 1) — jamais bloquant
# ===========================================================================


class TestNeverModeReal:
    async def test_never_approves_any_image(self, monkeypatch: pytest.MonkeyPatch):
        """never explicite → approve quelle que soit l'image."""
        monkeypatch.setenv(_CRITERIA_ENV, "never")
        decision = await pre_deploy(_ctx())
        assert decision.approved is True
        assert decision.reason is None

    async def test_default_without_config_approves(self):
        """Aucune config → défaut never → approve (jamais bloquant)."""
        decision = await pre_deploy(_ctx())
        assert decision.approved is True

    async def test_never_approves_single_image(self, monkeypatch: pytest.MonkeyPatch):
        """never avec une seule image (ou tag flottant inclus) → approve."""
        monkeypatch.setenv(_CRITERIA_ENV, "never")
        decision = await pre_deploy(
            _ctx(images=[DeployImage(name="nginx:latest", tag="latest")])
        )
        assert decision.approved is True

    async def test_never_approves_empty_images(self, monkeypatch: pytest.MonkeyPatch):
        """never + contexte sans image → approve (rien à scanner)."""
        monkeypatch.setenv(_CRITERIA_ENV, "never")
        decision = await pre_deploy(_ctx(images=[]))
        assert decision.approved is True


# ===========================================================================
# Mode bloquant simulé (AC 1) — chemin deny de bout en bout
# ===========================================================================


class TestSimulatedBlockingMode:
    async def test_critical_high_denies_with_image_and_simulated_marker(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """critical_high simulé → deny, raison avec [SIMULÉ] + image + critère."""
        monkeypatch.setenv(_CRITERIA_ENV, "critical_high")
        decision = await pre_deploy(_ctx())
        assert decision.approved is False
        assert decision.reason is not None
        assert "[SIMULÉ]" in decision.reason
        assert "nginx:1.25" in decision.reason
        assert "critical_high" in decision.reason

    async def test_critical_high_reason_lists_critical_and_high_counts(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """La raison cite les compteurs des sévérités visées par le critère."""
        monkeypatch.setenv(_CRITERIA_ENV, "critical_high")
        decision = await pre_deploy(_ctx())
        assert decision.reason is not None
        assert f"{SIMULATED_FINDINGS['critical']} CRITICAL" in decision.reason
        assert f"{SIMULATED_FINDINGS['high']} HIGH" in decision.reason

    @pytest.mark.parametrize("criteria", ["any", "critical", "more_than_current"])
    async def test_all_blocking_criteria_deny(
        self, monkeypatch: pytest.MonkeyPatch, criteria: str
    ):
        """Chaque critère bloquant de la matrice → deny simulé."""
        monkeypatch.setenv(_CRITERIA_ENV, criteria)
        decision = await pre_deploy(_ctx())
        assert decision.approved is False
        assert decision.reason is not None
        assert "[SIMULÉ]" in decision.reason
        assert criteria in decision.reason

    async def test_more_than_current_reason_shows_totals(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """more_than_current : la raison compare les totaux (candidate > courante)."""
        monkeypatch.setenv(_CRITERIA_ENV, "more_than_current")
        decision = await pre_deploy(_ctx())
        total = sum(SIMULATED_FINDINGS.values())
        assert decision.reason is not None
        assert f"total {total}" in decision.reason

    async def test_deny_uses_first_image(self, monkeypatch: pytest.MonkeyPatch):
        """Le refus porte sur la première image (court-circuit, comme le scan réel)."""
        monkeypatch.setenv(_CRITERIA_ENV, "any")
        ctx = _ctx(images=[DeployImage(name="app:2.0", tag="2.0")])
        decision = await pre_deploy(ctx)
        assert decision.approved is False
        assert "app:2.0" in (decision.reason or "")

    async def test_blocking_criteria_without_images_approves(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Critère bloquant + aucune image → approve (rien à scanner)."""
        monkeypatch.setenv(_CRITERIA_ENV, "critical")
        decision = await pre_deploy(_ctx(images=[]))
        assert decision.approved is True


# ===========================================================================
# Fail-safe — critère inconnu → comportement never
# ===========================================================================


class TestFailSafeUnknownCriteria:
    async def test_unknown_criteria_falls_back_to_never(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Critère inconnu → approve (on n'invente pas un blocage)."""
        monkeypatch.setenv(_CRITERIA_ENV, "block_everything")
        decision = await pre_deploy(_ctx())
        assert decision.approved is True

    async def test_unknown_criteria_logs_warning(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ):
        """Critère inconnu → WARNING (observabilité du fail-safe)."""
        monkeypatch.setenv(_CRITERIA_ENV, "nope")
        with caplog.at_level("WARNING", logger="windflow.plugins.demo"):
            decision = await pre_deploy(_ctx())
        assert decision.approved is True
        assert any("fail-safe" in rec.message for rec in caplog.records)

    async def test_criteria_value_is_normalized(self, monkeypatch: pytest.MonkeyPatch):
        """Casse/espaces ignorés : ' CRITICAL_HIGH ' → critère bloquant."""
        monkeypatch.setenv(_CRITERIA_ENV, "  CRITICAL_HIGH  ")
        decision = await pre_deploy(_ctx())
        assert decision.approved is False


# ===========================================================================
# Intégration SDK — exécution via PluginGateService.run_gates
# ===========================================================================


class TestThroughGateService:
    async def test_never_approves_through_run_gates(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """Enregistrement + run_gates : never → verdict approuvé (contrat 170.2)."""
        monkeypatch.setenv(_CRITERIA_ENV, "never")
        service = PluginGateService(default_timeout=2)
        try:
            service.register("trivy", pre_deploy)
            outcome = await service.run_gates(_ctx())
            assert outcome.approved is True
        finally:
            service.reset()

    async def test_simulated_deny_blocks_through_run_gates(
        self, monkeypatch: pytest.MonkeyPatch
    ):
        """run_gates : deny simulé → GATE_DENIED avec la raison Trivy."""
        monkeypatch.setenv(_CRITERIA_ENV, "critical_high")
        service = PluginGateService(default_timeout=2)
        try:
            service.register("trivy", pre_deploy)
            outcome = await service.run_gates(_ctx())
            assert outcome.approved is False
            assert outcome.plugin_name == "trivy"
            assert outcome.code == "GATE_DENIED"
            assert outcome.reason is not None
            assert "[SIMULÉ]" in outcome.reason
        finally:
            service.reset()


# ===========================================================================
# Conventions sécurité scanner (AC 1) — constantes de référence
# ===========================================================================


class TestConventions:
    def test_trivy_image_is_pinned_without_latest(self):
        """L'image du scanner est épinglée par version — jamais :latest."""
        assert TRIVY_IMAGE.startswith("aquasec/trivy:")
        assert ":latest" not in TRIVY_IMAGE
        # version explicite non vide après le deux-points
        version = TRIVY_IMAGE.split(":", 1)[1]
        assert version.strip() != ""

    def test_cache_volume_follows_protected_pattern(self):
        """Le volume cache respecte le pattern windflow-plugin-* (prune)."""
        assert CACHE_VOLUME == "windflow-plugin-trivy-cache"
        assert CACHE_VOLUME.startswith("windflow-plugin-")

    def test_pending_tag_suffix(self):
        """Suffixe du tag temporaire du flux protégé."""
        assert PENDING_TAG_SUFFIX == "-windflow-pending"

    def test_block_criteria_matrix_is_complete(self):
        """La matrice expose les 5 critères spec 11, never en défaut."""
        assert set(BLOCK_CRITERIA) == {
            "never",
            "any",
            "critical_high",
            "critical",
            "more_than_current",
        }
        assert DEFAULT_BLOCK_CRITERIA == "never"

    def test_simulated_findings_severities(self):
        """Compteurs simulés couvrant les 4 sévérités (matrice descriptive)."""
        assert set(SIMULATED_FINDINGS.keys()) == {
            "critical",
            "high",
            "medium",
            "low",
        }
        assert all(v > 0 for v in SIMULATED_FINDINGS.values())

    def test_pre_deploy_returns_gate_decision_type(self):
        """Contrat SDK : le handler exposé est bien la gate pre_deploy."""
        import inspect

        assert inspect.iscoroutinefunction(pre_deploy)
        sig = inspect.signature(pre_deploy)
        assert list(sig.parameters) == ["ctx"]
