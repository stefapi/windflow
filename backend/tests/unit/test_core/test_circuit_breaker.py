"""Tests du socle CircuitBreaker (STORY-251 — AC 1, 3).

Comportement complet : ouverture après N échecs consécutifs, rejet
sans appel réseau, demi-ouvert après timeout, refermeture après
succès, failure_filter (H4), registre nommé (D1), exception typée
(D2), logs de transition avec correlation_id (D8).

Pattern : horloge fake injectable (pas de sleep réel), fixtures
autouse de reset du registre (R2).
"""

import logging
from datetime import datetime, timedelta, timezone

import pytest

from app.core.exceptions import (
    CircuitBreakerOpenError,
    ServiceUnavailableError,
    WindFlowException,
)
from app.core.resilience import (
    CircuitBreaker,
    CircuitBreakerRegistry,
    CircuitState,
    get_circuit_breaker_registry,
)


class FakeClock:
    """Horloge injectable — avancement manuel pour les transitions."""

    def __init__(self) -> None:
        self.now = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now = self.now + timedelta(seconds=seconds)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture(autouse=True)
def _reset_registry() -> None:
    """Isolation des tests : registre global vidé avant chaque test (R2)."""
    get_circuit_breaker_registry().reset_all()


def _breaker(clock: FakeClock, **kwargs) -> CircuitBreaker:
    """Breaker de test : seuils courts + horloge fake."""
    defaults = dict(failure_threshold=3, success_threshold=2, timeout=60.0)
    defaults.update(kwargs)
    return CircuitBreaker("test-circuit", clock=clock, **defaults)


async def _fail(breaker: CircuitBreaker) -> None:
    """Un appel protégé qui échoue (exception transport)."""

    async def boom() -> None:
        raise ConnectionError("transport down")

    with pytest.raises(ConnectionError):
        await breaker.call(boom)


async def _succeed(breaker: CircuitBreaker) -> None:
    """Un appel protégé qui réussit."""

    async def ok() -> str:
        return "ok"

    assert await breaker.call(ok) == "ok"


# ─── AC 1 : cycle de vie complet ────────────────────────────────


async def test_opens_after_n_consecutive_failures(clock: FakeClock):
    """AC 1 : N échecs consécutifs → état OPEN."""
    breaker = _breaker(clock, failure_threshold=3)
    for _ in range(3):
        await _fail(breaker)
    assert breaker.state is CircuitState.OPEN


async def test_open_rejects_without_calling_func(clock: FakeClock):
    """AC 1 : circuit ouvert → CircuitBreakerOpenError, func jamais appelée."""
    breaker = _breaker(clock, failure_threshold=2)
    await _fail(breaker)
    await _fail(breaker)
    assert breaker.state is CircuitState.OPEN

    call_count = 0

    async def probe() -> str:
        nonlocal call_count
        call_count += 1
        return "should not run"

    with pytest.raises(CircuitBreakerOpenError):
        await breaker.call(probe)
    assert call_count == 0  # échec rapide : aucune tentative réseau


async def test_half_open_after_timeout(clock: FakeClock):
    """AC 1 : horloge avancée de timeout → sonde autorisée, état HALF_OPEN."""
    breaker = _breaker(clock, failure_threshold=2, timeout=60.0)
    await _fail(breaker)
    await _fail(breaker)
    assert breaker.state is CircuitState.OPEN

    clock.advance(60.0)
    await _succeed(breaker)  # la sonde passe par _should_attempt_call
    assert breaker.state is CircuitState.HALF_OPEN


async def test_half_open_closes_after_success_threshold(clock: FakeClock):
    """AC 1 : success_threshold succès en half-open → CLOSED, compteurs reset."""
    breaker = _breaker(clock, failure_threshold=2, success_threshold=2)
    await _fail(breaker)
    await _fail(breaker)
    clock.advance(60.0)

    await _succeed(breaker)  # 1er succès half-open
    assert breaker.state is CircuitState.HALF_OPEN
    await _succeed(breaker)  # 2e succès → fermeture
    assert breaker.state is CircuitState.CLOSED
    assert breaker.failure_count == 0
    assert breaker.success_count == 0


async def test_half_open_reopens_on_single_failure(clock: FakeClock):
    """Un échec en HALF_OPEN → retour OPEN immédiat."""
    breaker = _breaker(clock, failure_threshold=2)
    await _fail(breaker)
    await _fail(breaker)
    clock.advance(60.0)
    await _succeed(breaker)
    assert breaker.state is CircuitState.HALF_OPEN

    await _fail(breaker)
    assert breaker.state is CircuitState.OPEN


async def test_success_resets_failure_count_in_closed(clock: FakeClock):
    """Contre-réinitialisation : un succès en CLOSED remet le compteur à 0."""
    breaker = _breaker(clock, failure_threshold=3)
    await _fail(breaker)
    await _fail(breaker)
    assert breaker.failure_count == 2
    await _succeed(breaker)
    assert breaker.failure_count == 0
    assert breaker.state is CircuitState.CLOSED


# ─── H4 : failure_filter ────────────────────────────────────────


async def test_failure_filter_excludes_non_transport_errors(clock: FakeClock):
    """H4 : une exception rejetée par le filtre est re-levée sans comptage."""
    breaker = _breaker(clock, failure_threshold=2)

    async def business_error() -> None:
        raise ValueError("exit code 1 — échec métier, pas de panne transport")

    with pytest.raises(ValueError):
        await breaker.call(
            business_error,
            failure_filter=lambda exc: isinstance(exc, ConnectionError),
        )
    # L'échec métier n'a PAS compté : le circuit reste fermé, compteur 0
    assert breaker.failure_count == 0
    assert breaker.state is CircuitState.CLOSED

    # Un échec transport accepté par le filtre compte normalement
    await _fail(breaker)
    assert breaker.failure_count == 1


# ─── D1 : registre nommé ────────────────────────────────────────


def test_registry_get_or_create_idempotent():
    """D1 : get_or_create retourne la même instance pour un même nom."""
    registry = CircuitBreakerRegistry()
    first = registry.get_or_create("docker_engine")
    second = registry.get_or_create("docker_engine")
    assert first is second
    # Le registre global expose aussi les circuits nommés
    global_first = get_circuit_breaker_registry().get_or_create("plugin_registry")
    global_second = get_circuit_breaker_registry().get_or_create("plugin_registry")
    assert global_first is global_second


def test_registry_reset_all_clears_state():
    """R2 : reset_all oublie tous les circuits (isolation des tests)."""
    registry = CircuitBreakerRegistry()
    circuit = registry.get_or_create("ssh:00000000-0000-0000-0000-000000000000")
    circuit.failure_count = 4
    registry.reset_all()
    assert registry.get_all_states() == {}
    # Le circuit suivant est une instance neuve
    fresh = registry.get_or_create("ssh:00000000-0000-0000-0000-000000000000")
    assert fresh is not circuit
    assert fresh.failure_count == 0


# ─── D2 : exception typée ───────────────────────────────────────


async def test_rejection_is_circuit_breaker_open_error(clock: FakeClock):
    """D2 : rejet typé WindFlowException → 503 sémantique, marqueur circuit_open."""
    breaker = _breaker(clock, failure_threshold=1)
    await _fail(breaker)

    async def probe() -> None:
        pass  # pragma: no cover — jamais appelée

    with pytest.raises(CircuitBreakerOpenError) as exc_info:
        await breaker.call(probe)
    err = exc_info.value
    assert isinstance(err, WindFlowException)  # rules 30 : exception héritée
    assert isinstance(err, ServiceUnavailableError)  # 503
    assert err.status_code == 503
    assert err.details["error_type"] == "circuit_open"
    assert err.details["circuit"] == "test-circuit"
    # Message générique : aucun détail interne (rules 40)
    assert "transport down" not in err.message


# ─── D8 : logs de transition ────────────────────────────────────


async def test_transition_logs_contain_circuit_and_correlation_id(
    clock: FakeClock, caplog
):
    """AC 3 : transitions loggées avec circuit/old_state/new_state/correlation_id."""
    from app.middleware.correlation import correlation_id_var

    token = correlation_id_var.set("corr-story-251")
    try:
        breaker = _breaker(clock, failure_threshold=2)
        with caplog.at_level(logging.WARNING, logger="app.core.resilience"):
            await _fail(breaker)
            await _fail(breaker)  # transition CLOSED → OPEN
        transitions = [
            r
            for r in caplog.records
            if r.getMessage() == "Circuit breaker state transition"
        ]
        assert transitions, "aucun log de transition capturé"
        extra = transitions[-1].__dict__
        assert extra["circuit"] == "test-circuit"
        assert extra["old_state"] == "closed"
        assert extra["new_state"] == "open"
        assert extra["correlation_id"] == "corr-story-251"
        # Message générique : aucun détail interne ni message d'exception
        assert "transport down" not in transitions[-1].getMessage()
    finally:
        correlation_id_var.reset(token)


async def test_transition_logged_without_correlation_id(clock: FakeClock, caplog):
    """H3 : hors requête HTTP, correlation_id=None — la transition est loggée."""
    breaker = _breaker(clock, failure_threshold=1)
    with caplog.at_level(logging.WARNING, logger="app.core.resilience"):
        await _fail(breaker)
    transitions = [
        r
        for r in caplog.records
        if r.getMessage() == "Circuit breaker state transition"
    ]
    assert transitions
    assert transitions[-1].__dict__.get("correlation_id") is None
