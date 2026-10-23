"""Tests du SDK hooks plugins (STORY-163 — T1/AC 4).

Familles :

- **Registre** : ``@on_event("stack.deployed")`` /
  ``@on_event("deployment.failed")`` enregistrent les méthodes dans le
  registre d'instance (démonstrateur ≥ 2 événements canoniques) ;
- **Validation au décorateur (AC 4, rules 40)** : refus explicite des
  noms SCREAMING_SNAKE (``DEPLOYMENT_PROGRESS`` — transport WS, jamais
  un contrat d'abonnement), des extra-canoniques
  (``organization.created``) et des inconnus —
  ``InvalidEventTypeNameError`` ;
- **PluginEvent** : champs exposés + copie défensive du payload (muter
  ``data`` ne corrompt pas l'original) ;
- **Démonstrateur** : ``DemoLoggerHooks`` consomme bien 2 canoniques.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.core.exceptions import InvalidEventTypeNameError
from app.plugins.examples.demo_logger_hooks import DemoLoggerHooks
from app.plugins.hooks import PluginEvent, PluginHooks, on_event


class _DemoStackHooks(PluginHooks):
    """Hooks de test : 2 événements canoniques distincts."""

    @on_event("stack.deployed")
    async def on_deployed(self, event: PluginEvent) -> None:
        pass

    @on_event("deployment.failed")
    async def on_failed(self, event: PluginEvent) -> None:
        pass


# ===========================================================================
# Registre d'instance
# ===========================================================================


def test_on_event_registers_methods_in_instance_registry():
    """Les méthodes décorées apparaissent dans hooks, par nom canonique."""
    instance = _DemoStackHooks()
    assert set(instance.hooks.keys()) == {"stack.deployed", "deployment.failed"}
    assert len(instance.hooks["stack.deployed"]) == 1
    assert len(instance.hooks["deployment.failed"]) == 1


def test_multiple_methods_can_listen_same_event():
    """Plusieurs méthodes peuvent écouter le même événement (ordre stable)."""

    class _MultiHooks(PluginHooks):
        @on_event("host.added")
        async def first(self, event: PluginEvent) -> None:
            pass

        @on_event("host.added")
        async def second(self, event: PluginEvent) -> None:
            pass

    instance = _MultiHooks()
    handlers = instance.hooks["host.added"]
    assert len(handlers) == 2
    # Ordre de définition (base d'abord, puis sous-classes)
    assert handlers[0].__name__ == "first"


def test_function_stays_unwrapped():
    """Le décorateur conserve la fonction intacte (pas de wrapping)."""

    class _Probe(PluginHooks):
        @on_event("container.started")
        async def hook(self, event: PluginEvent) -> None:
            """Docstring preserved."""

    assert _Probe.hook.__doc__ == "Docstring preserved."
    instance = _Probe()
    assert instance.hooks["container.started"][0].__name__ == "hook"


# ===========================================================================
# Validation au décorateur — refus SCREAMING_SNAKE / extra-canoniques
# ===========================================================================


def test_screaming_snake_name_rejected_at_decorator():
    """DEPLOYMENT_PROGRESS (transport WS) → refus explicite (AC 4)."""

    with pytest.raises(InvalidEventTypeNameError):

        class _Bad(PluginHooks):
            @on_event("DEPLOYMENT_PROGRESS")  # type: ignore[arg-type]
            async def hook(self, event: PluginEvent) -> None:
                pass


def test_extra_canonical_name_rejected_at_decorator():
    """organization.created (extra-canonique) → refus explicite."""

    with pytest.raises(InvalidEventTypeNameError):

        class _BadExtra(PluginHooks):
            @on_event("organization.created")  # type: ignore[arg-type]
            async def hook(self, event: PluginEvent) -> None:
                pass


def test_security_extra_canonical_never_subscribable():
    """host.ssh_fingerprint_accepted (sécurité TOFU) → refus (rules 40)."""

    with pytest.raises(InvalidEventTypeNameError):

        class _BadSec(PluginHooks):
            @on_event("host.ssh_fingerprint_accepted")  # type: ignore[arg-type]
            async def hook(self, event: PluginEvent) -> None:
                pass


def test_unknown_name_rejected_at_decorator():
    """inconnu.total → refus explicite."""

    with pytest.raises(InvalidEventTypeNameError):

        class _BadUnknown(PluginHooks):
            @on_event("inconnu.total")  # type: ignore[arg-type]
            async def hook(self, event: PluginEvent) -> None:
                pass


def test_error_message_mentions_canonical_contract():
    """Le message d'erreur explique le contrat (canoniques uniquement)."""
    with pytest.raises(InvalidEventTypeNameError) as excinfo:
        on_event("DEPLOYMENT_PROGRESS")  # type: ignore[arg-type]
    message = str(excinfo.value)
    assert "DEPLOYMENT_PROGRESS" in message
    assert "canonique" in message


# ===========================================================================
# PluginEvent — surface exposée + copie défensive
# ===========================================================================


def test_plugin_event_fields_present():
    """name/data/timestamp/event_id sont exposés."""
    now = datetime(2026, 10, 23, 12, 0, 0)
    event = PluginEvent(
        name="stack.deployed",
        data={"stack_id": "s-1"},
        timestamp=now,
        event_id="id-42",
    )
    assert event.name == "stack.deployed"
    assert event.data == {"stack_id": "s-1"}
    assert event.timestamp == now
    assert event.event_id == "id-42"


def test_plugin_event_payload_is_defensive_copy():
    """Muter event.data ne corrompt pas le dictionnaire source."""
    source = {"stack_id": "s-1", "nested": {"a": 1}}
    event = PluginEvent(name="stack.deployed", data=dict(source))
    event.data["injected"] = "evil"
    event.data["stack_id"] = "tampered"
    assert source == {"stack_id": "s-1", "nested": {"a": 1}}


# ===========================================================================
# Démonstrateur (AC 4)
# ===========================================================================


def test_demo_logger_hooks_consumes_two_canonical_events():
    """DemoLoggerHooks consomme stack.deployed + deployment.failed (AC 4)."""
    instance = DemoLoggerHooks()
    assert set(instance.hooks.keys()) == {"stack.deployed", "deployment.failed"}


async def test_demo_logger_hooks_react_without_error():
    """Les hooks du démonstrateur s'exécutent sans lever (logs seuls)."""
    instance = DemoLoggerHooks()
    await instance.hooks["stack.deployed"][0](
        PluginEvent(name="stack.deployed", data={"stack_id": "s", "name": "nginx"})
    )
    await instance.hooks["deployment.failed"][0](
        PluginEvent(name="deployment.failed", data={"deployment_id": "d-1"})
    )
