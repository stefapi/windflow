# WebSocket Plugin System - Backend

Système de plugins extensible pour gérer les événements WebSocket côté backend de WindFlow.

## Vue d'ensemble

Le système de plugins backend permet d'étendre les fonctionnalités WebSocket de manière modulaire et maintenable. Chaque plugin peut réagir à des événements WebSocket spécifiques sans modifier le code principal de l'endpoint WebSocket.

### Caractéristiques

- **Architecture événementielle** : Les plugins s'abonnent à des événements spécifiques
- **Exécution parallèle** : Les handlers s'exécutent en parallèle avec `asyncio.gather`
- **Type-safe** : Utilisation de l'enum `WebSocketEventType` synchronisé avec le frontend
- **Contexte partagé** : Accès aux dépendances via `PluginContext`
- **Lifecycle management** : Hooks d'initialisation et de nettoyage

## Architecture

```
websocket/
├── __init__.py              # Exports publics
├── plugin.py                # Core du système de plugins
├── plugins/                 # Plugins par défaut
│   ├── __init__.py
│   ├── audit_logger.py      # Logging des événements de sécurité
│   └── deployment_monitor.py # Monitoring des déploiements
└── README.md                # Cette documentation
```

## Utilisation

### Créer un plugin

```python
from backend.app.websocket.plugin import WebSocketPlugin, PluginContext
from backend.app.schemas.websocket_events import WebSocketEventType

class MyCustomPlugin(WebSocketPlugin):
    """Plugin personnalisé pour gérer des événements spécifiques."""
    
    # Définir les événements écoutés
    event_types = [
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        WebSocketEventType.NOTIFICATION_SENT
    ]
    
    async def initialize(self, context: PluginContext) -> None:
        """Initialisation du plugin lors de la connexion WebSocket."""
        context.logger.info(f"MyCustomPlugin initialized for user {context.user.id}")
        # Initialiser des ressources si nécessaire
        self.some_state = {}
    
    async def handle_event(
        self,
        event_type: str,
        event_data: dict,
        context: PluginContext
    ) -> None:
        """Traiter un événement WebSocket."""
        
        if event_type == WebSocketEventType.DEPLOYMENT_STATUS_CHANGED:
            await self._handle_deployment_status(event_data, context)
        elif event_type == WebSocketEventType.NOTIFICATION_SENT:
            await self._handle_notification(event_data, context)
    
    async def _handle_deployment_status(
        self,
        event_data: dict,
        context: PluginContext
    ) -> None:
        """Gérer un changement de statut de déploiement."""
        deployment_id = event_data.get('deploymentId')
        new_status = event_data.get('newStatus')
        
        context.logger.info(
            f"Deployment {deployment_id} status changed to {new_status}"
        )
        
        # Logique métier du plugin
        # ...
    
    async def _handle_notification(
        self,
        event_data: dict,
        context: PluginContext
    ) -> None:
        """Gérer une notification."""
        # Logique métier
        pass
    
    async def cleanup(self, context: PluginContext) -> None:
        """Nettoyage lors de la déconnexion WebSocket."""
        context.logger.info("MyCustomPlugin cleaned up")
        # Libérer les ressources
        self.some_state.clear()
```

### Enregistrer un plugin

Dans votre module (par exemple `backend/app/websocket/plugins/custom.py`) :

```python
# Créer une instance du plugin
my_plugin = MyCustomPlugin()

# L'ajouter à la liste des plugins par défaut
from backend.app.websocket.plugins import default_plugins
default_plugins.append(my_plugin)
```

Ou enregistrer manuellement dans le code :

```python
from backend.app.websocket.plugin import plugin_manager
from backend.app.websocket.plugins.custom import MyCustomPlugin

# Enregistrer le plugin
plugin_manager.register(MyCustomPlugin())
```

## Plugin Context

Le `PluginContext` fournit l'accès aux dépendances et utilitaires :

```python
@dataclass
class PluginContext:
    """Contexte partagé entre tous les plugins."""
    
    db: Optional[AsyncSession]              # Session base de données (peut être None)
    user: Optional[User]                    # Utilisateur authentifié
    websocket: WebSocket                    # Connexion WebSocket
    logger: logging.Logger                  # Logger structuré
    broadcast_to_user: Optional[Callable]   # Fonction pour broadcaster à un utilisateur
    broadcast_to_event_subscribers: Optional[Callable]  # Fonction pour broadcaster à des abonnés
```

### Utiliser le contexte

```python
async def handle_event(
    self,
    event_type: str,
    event_data: dict,
    context: PluginContext
) -> None:
    # Accéder à l'utilisateur
    user_id = str(context.user.id)
    
    # Logger avec contexte
    context.logger.info(
        f"Processing event {event_type} for user {user_id}",
        extra={"event_type": event_type, "user_id": user_id}
    )
    
    # Broadcaster à l'utilisateur actuel
    if context.broadcast_to_user:
        await context.broadcast_to_user(user_id, {
            "type": "custom_notification",
            "message": "Event processed"
        })
    
    # Broadcaster à tous les abonnés d'un événement
    if context.broadcast_to_event_subscribers:
        await context.broadcast_to_event_subscribers(
            WebSocketEventType.CUSTOM_EVENT,
            {"data": "some data"}
        )
```

## Événements disponibles

Les événements sont définis dans `backend/app/schemas/websocket_events.py` et synchronisés avec le frontend :

### Authentification
- `AUTH_LOGIN_SUCCESS` : Connexion réussie
- `AUTH_LOGOUT` : Déconnexion
- `AUTH_TOKEN_REFRESH` : Rafraîchissement du token

### Session
- `SESSION_EXPIRED` : Session expirée
- `SESSION_AUTH_REQUIRED` : Authentification requise
- `SESSION_PERMISSION_CHANGED` : Changement de permissions
- `SESSION_ORGANIZATION_CHANGED` : Changement d'organisation

### Déploiements
- `DEPLOYMENT_STATUS_CHANGED` : Changement de statut
- `DEPLOYMENT_LOGS_UPDATE` : Nouveaux logs
- `DEPLOYMENT_PROGRESS` : Progression du déploiement
- `DEPLOYMENT_CREATED` : Nouveau déploiement
- `DEPLOYMENT_DELETED` : Déploiement supprimé

### Notifications
- `NOTIFICATION_SENT` : Nouvelle notification
- `NOTIFICATION_READ` : Notification lue

### Autres
- `WEBSOCKET_ERROR` : Erreur WebSocket
- `WEBSOCKET_PING` : Heartbeat
- `WEBSOCKET_PONG` : Réponse heartbeat

## Plugins par défaut

### AuditLoggerPlugin

Log tous les événements de sécurité pour audit :

```python
from backend.app.websocket.plugins.audit_logger import AuditLoggerPlugin

# Événements audités :
# - AUTH_LOGIN_SUCCESS
# - AUTH_LOGOUT
# - AUTH_TOKEN_REFRESH
# - SESSION_EXPIRED
# - SESSION_AUTH_REQUIRED
# - SESSION_PERMISSION_CHANGED
# - SESSION_ORGANIZATION_CHANGED
```

Exemple de log produit :

```json
{
  "timestamp": "2024-01-15T10:30:00Z",
  "level": "INFO",
  "message": "Security audit log",
  "event_type": "AUTH_LOGIN_SUCCESS",
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "organization_id": "org-123",
  "event_data": {
    "username": "john.doe",
    "ip_address": "192.168.1.100"
  }
}
```

### DeploymentMonitorPlugin

Monitore le cycle de vie des déploiements :

```python
from backend.app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin

# Événements monitorés :
# - DEPLOYMENT_STATUS_CHANGED
# - DEPLOYMENT_LOGS_UPDATE
# - DEPLOYMENT_PROGRESS
```

Exemple de log produit :

```json
{
  "timestamp": "2024-01-15T10:35:00Z",
  "level": "INFO",
  "message": "Deployment lifecycle event",
  "event_type": "DEPLOYMENT_STATUS_CHANGED",
  "deployment_id": "dep-456",
  "old_status": "pending",
  "new_status": "running"
}
```

## Plugin Manager

Le `WebSocketPluginManager` gère l'enregistrement et l'exécution des plugins :

```python
from backend.app.websocket.plugin import plugin_manager

# Enregistrer un plugin
plugin_manager.register(MyPlugin())

# Initialiser tous les plugins
await plugin_manager.initialize_all(context)

# Dispatcher un événement à tous les plugins concernés
await plugin_manager.dispatch(
    WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
    {"deploymentId": "dep-123", "newStatus": "running"},
    context
)

# Nettoyer tous les plugins
await plugin_manager.cleanup_all(context)
```

### Méthodes du manager

- `register(plugin)` : Enregistre un nouveau plugin
- `initialize_all(context)` : Initialise tous les plugins
- `dispatch(event_type, event_data, context)` : Dispatch un événement
- `cleanup_all(context)` : Nettoie tous les plugins

Les handlers sont exécutés **en parallèle** pour des performances optimales.

## Bonnes pratiques

### 1. Gestion d'erreurs

Toujours encapsuler la logique dans des try/except :

```python
async def handle_event(
    self,
    event_type: str,
    event_data: dict,
    context: PluginContext
) -> None:
    try:
        # Logique du plugin
        await self._process_event(event_data, context)
    except Exception as e:
        context.logger.error(
            f"Error in plugin {self.__class__.__name__}: {e}",
            exc_info=True,
            extra={"event_type": event_type}
        )
        # Ne pas re-lever l'exception pour ne pas bloquer les autres plugins
```

### 2. Logging structuré

Utiliser le logger du contexte avec des champs extra :

```python
context.logger.info(
    "Processing deployment event",
    extra={
        "event_type": event_type,
        "deployment_id": event_data.get('deploymentId'),
        "user_id": str(context.user.id) if context.user else None,
        "plugin": self.__class__.__name__
    }
)
```

### 3. Performance

- Éviter les opérations bloquantes
- Utiliser `asyncio` pour les opérations I/O
- Ne pas garder de grosses structures en mémoire
- Nettoyer les ressources dans `cleanup()`

```python
async def handle_event(self, event_type, event_data, context):
    # ❌ MAUVAIS - opération bloquante
    time.sleep(5)
    
    # ✅ BON - opération async
    await asyncio.sleep(0)  # Yield control
    
    # ✅ BON - opération async avec timeout
    async with asyncio.timeout(5):
        await some_async_operation()
```

### 4. Accès à la base de données

Le contexte peut avoir `db=None` car la session n'est pas gardée ouverte. Si vous avez besoin d'accéder à la base :

```python
async def handle_event(self, event_type, event_data, context):
    # Créer une nouvelle session si nécessaire
    from backend.app.database import db as database
    
    async with database.session() as db:
        # Utiliser la session
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
```

### 5. Tests

Tester vos plugins avec des mocks :

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from backend.app.websocket.plugin import PluginContext
from backend.app.websocket.plugins.my_plugin import MyPlugin

@pytest.mark.asyncio
async def test_my_plugin_handles_event():
    # Arrange
    plugin = MyPlugin()
    context = PluginContext(
        db=None,
        user=MagicMock(id="user-123"),
        websocket=AsyncMock(),
        logger=MagicMock(),
        broadcast_to_user=AsyncMock(),
        broadcast_to_event_subscribers=AsyncMock()
    )
    
    event_data = {"deploymentId": "dep-456", "newStatus": "running"}
    
    # Act
    await plugin.handle_event(
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        event_data,
        context
    )
    
    # Assert
    context.logger.info.assert_called()
    assert context.broadcast_to_user.called
```

## Synchronisation Frontend/Backend

Les événements sont **strictement synchronisés** entre frontend et backend via l'enum `WebSocketEventType`. Toute modification doit être faite dans les deux fichiers :

- **Backend** : `backend/app/schemas/websocket_events.py`
- **Frontend** : `frontend/src/services/websocket/types.ts`

Les noms d'événements doivent être identiques (UPPER_CASE).

## Exemples avancés

### Plugin avec état partagé

```python
class StatePlugin(WebSocketPlugin):
    """Plugin avec état partagé entre connexions."""
    
    def __init__(self):
        super().__init__()
        self._shared_state = {}  # État partagé entre toutes les instances
        self._lock = asyncio.Lock()
    
    async def handle_event(self, event_type, event_data, context):
        async with self._lock:
            # Accès thread-safe à l'état partagé
            self._shared_state[event_type] = event_data
```

### Plugin avec périodicité

```python
class PeriodicPlugin(WebSocketPlugin):
    """Plugin qui exécute une tâche périodique."""
    
    def __init__(self):
        super().__init__()
        self._task = None
    
    async def initialize(self, context):
        # Démarrer une tâche périodique
        self._task = asyncio.create_task(self._periodic_check(context))
    
    async def _periodic_check(self, context):
        while True:
            try:
                await asyncio.sleep(60)  # Toutes les 60 secondes
                # Faire quelque chose
                context.logger.debug("Periodic check executed")
            except asyncio.CancelledError:
                break
    
    async def cleanup(self, context):
        # Arrêter la tâche périodique
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
```

### Plugin avec broadcast conditionnel

```python
class ConditionalBroadcastPlugin(WebSocketPlugin):
    """Plugin qui broadcast selon des conditions."""
    
    event_types = [WebSocketEventType.DEPLOYMENT_STATUS_CHANGED]
    
    async def handle_event(self, event_type, event_data, context):
        new_status = event_data.get('newStatus')
        
        # Ne broadcaster que si le statut est "failed"
        if new_status == 'failed' and context.broadcast_to_event_subscribers:
            await context.broadcast_to_event_subscribers(
                WebSocketEventType.NOTIFICATION_SENT,
                {
                    "level": "error",
                    "title": "Deployment Failed",
                    "message": f"Deployment {event_data.get('deploymentId')} failed"
                }
            )
```

## Dépannage

### Le plugin ne reçoit pas les événements

1. Vérifier que le plugin est bien enregistré :
   ```python
   from backend.app.websocket.plugin import plugin_manager
   print(plugin_manager._plugins)  # Doit contenir votre plugin
   ```

2. Vérifier que `event_types` contient le bon événement :
   ```python
   assert WebSocketEventType.MY_EVENT in MyPlugin.event_types
   ```

3. Vérifier les logs pour les erreurs d'initialisation

### Erreur "db is None"

Le contexte n'a pas de session DB active. Créez-en une manuellement :

```python
from backend.app.database import db as database

async with database.session() as db:
    # Utiliser db ici
```

### Le plugin bloque les autres

Vérifiez que vous n'avez pas d'opérations bloquantes. Utilisez `asyncio` pour toutes les opérations I/O.

## Ressources

- [Documentation WebSocket Frontend](../../../frontend/src/services/websocket/README.md)
- [Événements WebSocket](../schemas/websocket_events.py)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [asyncio Documentation](https://docs.python.org/3/library/asyncio.html)

---

**Version** : 1.0  
**Dernière mise à jour** : 17/11/2025
