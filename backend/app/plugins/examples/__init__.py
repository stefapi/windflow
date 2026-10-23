"""Plugins examples — démonstrateurs du SDK hooks (STORY-163 — T6).

Ces modules ne sont **jamais chargés automatiquement** en production :
le démonstrateur n'est actif que si ``plugin_hooks_demo_enabled=True``
(setting désactivé par défaut) ou si le module est explicitement copié
dans le ``plugins_base_dir`` d'une installation réelle (STORY-169).
"""

from .demo_logger_hooks import DemoLoggerHooks

__all__ = ["DemoLoggerHooks"]
