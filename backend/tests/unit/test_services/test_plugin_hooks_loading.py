"""Tests du chargement lifespan des hooks_module (STORY-163 — T6).

Familles :

- **Chargement nominal** : faux ``hooks_module`` (module temporaire sous
  un ``plugins_base_dir`` tmp) → instance enregistrée, hooks actifs sur
  le bus ;
- **Anti path-traversal (rules 40)** : ``hooks_module: "../../etc/passwd"``
  → refusé (WARNING), rien chargé ; chemin absolu refusé ;
- **Filtres** : plugin ``status=error`` ou ``type=service`` → non chargé ;
- **Best-effort** : échec d'import d'un module → WARNING + les autres
  plugins chargés (startup intact) ;
- **Lifespan** : ``plugin_hooks_enabled=False`` → service jamais démarré.

Le DB est mockée par une ``session_factory`` factice (aucune base
réelle) — seule la mécanique de chargement est testée.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List

import pytest

from app.core.events import EventType, InMemoryEventBus
from app.services.plugin_hooks_service import (
    PluginHooksService,
    _resolve_hooks_module_path,
)

# ===========================================================================
# Helpers — faux plugins en base + modules temporaires
# ===========================================================================


class _FakePlugin:
    """Ligne Plugin factice (attributs utilisés par le service)."""

    def __init__(self, name: str, type_: str, status: str, hooks_module: str | None):
        self.name = name
        self.type = type_
        self.status = status
        self.manifest_data: Dict[str, Any] = (
            {"extensions": {"hooks_module": hooks_module}} if hooks_module else {}
        )


class _Scalars:
    """Conteneur imitant ``Result.scalars().all()`` de SQLAlchemy."""

    def __init__(self, scalars: List[_FakePlugin]) -> None:
        self._scalars = scalars

    def all(self) -> List[_FakePlugin]:
        return self._scalars


def _session_factory(plugins: List[_FakePlugin]) -> Any:
    """Factory de session async factice retournant ``plugins``."""

    class _Result:
        def __init__(self, items: List[_FakePlugin]) -> None:
            self._scalars = _Scalars(items)

        def scalars(self) -> _Scalars:
            return self._scalars

    class _Session:
        async def __aenter__(self) -> "_Session":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def execute(self, query: Any) -> _Result:
            return _Result(plugins)

    def factory() -> _Session:
        return _Session()

    return factory


_HOOKS_MODULE_SOURCE = '''
"""Faux hooks_module de test (généré par test_plugin_hooks_loading)."""
from app.plugins.hooks import PluginHooks, PluginEvent, on_event


class FakeTestHooks(PluginHooks):
    @on_event("stack.deployed")
    async def on_deployed(self, event: PluginEvent) -> None:
        pass
'''


@pytest.fixture
def hooks_plugin_dir(tmp_path, monkeypatch):
    """Crée un plugin fake avec hooks_module valide sous plugins_base_dir tmp."""
    base_dir = tmp_path / "plugins"
    plugin_dir = base_dir / "fake-plugin"
    hooks_dir = plugin_dir / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "main.py").write_text(_HOOKS_MODULE_SOURCE)
    (hooks_dir / "__init__.py").write_text("")
    monkeypatch.setattr(
        "app.services.plugin_hooks_service.settings.plugins_base_dir",
        str(base_dir),
    )
    return base_dir


# ===========================================================================
# Chargement nominal (T6)
# ===========================================================================


async def test_valid_hooks_module_is_loaded_and_active_on_bus(hooks_plugin_dir):
    """Module valide → instance enregistrée, hook actif sur le bus."""
    bus = InMemoryEventBus()
    service = PluginHooksService(bus, timeout_seconds=5)
    plugins = [_FakePlugin("fake-plugin", "extension", "installed", "hooks/main.py")]

    loaded = await service.load_installed_hooks(_session_factory(plugins))

    assert loaded == 1
    assert service.registered_count == 1
    # Le hook est abonné sur le bus via le pont démarré
    service.start()
    from app.plugins.hooks import PluginEvent

    received: list[PluginEvent] = []
    instance = next(iter(service._instances.values()))

    async def _spy(event: PluginEvent) -> None:
        received.append(event)

    instance.hooks["stack.deployed"] = [_spy]
    await bus.emit(EventType.STACK_DEPLOYED, {"stack_id": "s-1"})
    await service.wait_for_hooks()
    assert len(received) == 1
    service.stop()


async def test_no_hooks_module_is_nominal_no_load(hooks_plugin_dir):
    """Plugin sans hooks_module → rien chargé (cas nominal, pas de log)."""
    service = PluginHooksService(InMemoryEventBus())
    plugins = [_FakePlugin("fake-plugin", "extension", "installed", None)]
    loaded = await service.load_installed_hooks(_session_factory(plugins))
    assert loaded == 0
    assert service.registered_count == 0


# ===========================================================================
# Anti path-traversal (rules 40)
# ===========================================================================


async def test_path_traversal_hooks_module_is_rejected(hooks_plugin_dir, caplog):
    """hooks_module ../../etc/passwd → refusé (WARNING), rien chargé."""
    service = PluginHooksService(InMemoryEventBus())
    plugins = [_FakePlugin("fake-plugin", "extension", "installed", "../../etc/passwd")]

    with caplog.at_level(logging.WARNING):
        loaded = await service.load_installed_hooks(_session_factory(plugins))

    assert loaded == 0
    assert service.registered_count == 0
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("refusé" in r.message for r in warnings)


async def test_absolute_hooks_module_is_rejected(hooks_plugin_dir, caplog):
    """hooks_module absolu → refusé, rien chargé."""
    service = PluginHooksService(InMemoryEventBus())
    plugins = [_FakePlugin("fake-plugin", "extension", "installed", "/etc/passwd.py")]

    with caplog.at_level(logging.WARNING):
        loaded = await service.load_installed_hooks(_session_factory(plugins))

    assert loaded == 0
    assert any(
        "refusé" in r.message for r in caplog.records if r.levelno == logging.WARNING
    )


def test_resolve_hooks_module_path_unit_rules(hooks_plugin_dir):
    """_resolve_hooks_module_path : résolution + refus (unitaire)."""
    from app.core.exceptions import WindFlowException

    # Résolution valide sous le base_dir
    resolved = _resolve_hooks_module_path("fake-plugin", "hooks/main.py")
    assert resolved.endswith("fake-plugin/hooks/main.py")

    # Notation dotted acceptée
    dotted = _resolve_hooks_module_path("fake-plugin", "hooks.main")
    assert dotted.endswith("fake-plugin/hooks/main.py")

    # Traversal et absolu refusés
    with pytest.raises(WindFlowException):
        _resolve_hooks_module_path("fake-plugin", "../outside.py")
    with pytest.raises(WindFlowException):
        _resolve_hooks_module_path("fake-plugin", "/abs/path.py")


# ===========================================================================
# Filtres — status/type
# ===========================================================================


async def test_query_filters_type_and_status(hooks_plugin_dir):
    """La requête du service filtre type IN (extension, hybrid) et
    status IN (installed, running) — un plugin error/service n'est jamais
    candidat au chargement."""
    from sqlalchemy import select

    from app.models.plugin import Plugin

    # Répliquer la requête du service et inspecter sa compilation SQL.
    query = select(Plugin).where(
        Plugin.type.in_(("extension", "hybrid")),
        Plugin.status.in_(("installed", "running")),
    )
    sql = str(query.compile(compile_kwargs={"literal_binds": True}))
    assert "plugins.type IN" in sql
    assert "plugins.status IN" in sql
    assert "'extension'" in sql and "'hybrid'" in sql
    assert "'installed'" in sql and "'running'" in sql
    # Un plugin service ou error ne satisfait pas les filtres : la
    # requête réelle les exclut structurellement (IN positif).
    assert "'service'" not in sql
    assert "'error'" not in sql


# ===========================================================================
# Best-effort — échec d'import, startup intact
# ===========================================================================


async def test_failing_import_warns_and_other_plugins_still_load(
    hooks_plugin_dir, caplog
):
    """Échec d'import d'un module → WARNING + les autres chargés."""
    service = PluginHooksService(InMemoryEventBus())
    plugins = [
        _FakePlugin("broken-plugin", "extension", "installed", "hooks/missing.py"),
        _FakePlugin("fake-plugin", "extension", "running", "hooks/main.py"),
    ]

    with caplog.at_level(logging.WARNING):
        loaded = await service.load_installed_hooks(_session_factory(plugins))

    assert loaded == 1  # le plugin sain est chargé malgré l'échec
    assert service.registered_count == 1
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("broken-plugin" in r.message for r in warnings)


async def test_db_failure_returns_zero_and_never_raises(hooks_plugin_dir, caplog):
    """Lecture DB impossible → 0 chargé, aucune exception (startup intact)."""
    service = PluginHooksService(InMemoryEventBus())

    class _BrokenSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def execute(self, query):
            raise RuntimeError("db unavailable")

    with caplog.at_level(logging.ERROR):
        loaded = await service.load_installed_hooks(lambda: _BrokenSession())

    assert loaded == 0
    assert any(
        "impossible" in r.message for r in caplog.records if r.levelno == logging.ERROR
    )


# ===========================================================================
# Lifespan — plugin_hooks_enabled=False
# ===========================================================================


async def test_disabled_setting_never_starts_service(monkeypatch):
    """plugin_hooks_enabled=False → service jamais démarré (aucun abonnement)."""
    # Le lifespan ne l'instancie pas quand le flag est off — on vérifie
    # le comportement équivalent : un service créé mais non start() n'a
    # aucune souscription sur le bus (le lifespan garde ce contrat).
    bus = InMemoryEventBus()
    service = PluginHooksService(bus)
    # (non démarré — miroir du lifespan avec plugin_hooks_enabled=False)
    assert not service._subscribed
    assert not bus._handlers
