"""Package applicatif des plugins WindFlow — SDK hooks d'événements.

⚠️ Ne pas confondre avec ``app.websocket.plugins`` (modules de broadcast
interne du temps réel, famille G38) : ce package est le **SDK public des
plugins marketplace** (extension/hybrid) qui consomment le bus
d'événements canonique via les hooks ``@on_event`` (STORY-163).

Le nom applicatif importable est ``app.plugins.hooks`` — divergence
assumée vs l'exemple illustratif ``windflow.plugins.hooks`` de la spec 11
(le package applicatif s'importe ``app.*``), documentée dans
``docs/technical_specs/EVENT-BUS.md``.
"""

from .hooks import PluginEvent, PluginHooks, on_event

__all__ = ["PluginEvent", "PluginHooks", "on_event"]
