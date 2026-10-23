"""
WebSocket Plugins - Default plugins package.

Contains default plugins for handling WebSocket events:
- AuditLoggerPlugin: Logs security-related events
- DeploymentMonitorPlugin: Monitors deployment lifecycle
- DeploymentNotificationsPlugin: Real-time deployment notifications
  (STORY-163 — était défini mais jamais enregistré)
- SubscriptionHandler: Handles subscription messages from clients
"""

from .audit_logger import AuditLoggerPlugin
from .deployment_monitor import DeploymentMonitorPlugin
from .deployment_notifications import DeploymentNotificationsPlugin
from .subscription import SubscriptionHandler

# List of default event plugins to register automatically (SERVER → CLIENT)
default_plugins = [
    AuditLoggerPlugin(),
    DeploymentMonitorPlugin(),
    DeploymentNotificationsPlugin(),
]

# List of default message handlers to register automatically (CLIENT → SERVER)
default_message_handlers = [SubscriptionHandler()]

__all__ = [
    "AuditLoggerPlugin",
    "DeploymentMonitorPlugin",
    "DeploymentNotificationsPlugin",
    "SubscriptionHandler",
    "default_plugins",
    "default_message_handlers",
]
