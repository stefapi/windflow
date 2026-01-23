# WebSocket System - Backend

Système modulaire et extensible pour gérer les connexions WebSocket et les événements temps-réel dans WindFlow.

## Vue d'ensemble

Le système WebSocket backend est organisé en modules spécialisés pour une meilleure maintenabilité et réutilisabilité. Il permet de gérer les connexions, broadcaster des événements et étendre les fonctionnalités via un système de plugins.

### Architecture

```
websocket/
├── __init__.py              # Exports publics du package
├── connection_managers.py   # Gestion des connexions WebSocket
├── broadcasting.py          # Fonctions de broadcasting
├── event_bridge.py          # Pont entre événements internes et WebSocket
├── plugin.py                # Core du système de plugins
├── plugins/                 # Plugins par défaut
│   ├── __init__.py
│   ├── audit_logger.py      # Logging des événements de sécurité
│   ├── deployment_monitor.py # Monitoring des déploiements
│   └── subscription.py      # Gestion des abonnements
└── README.md                # Cette documentation
```

## Modules

### 1. Connection Managers (`connection_managers.py`)

Gère les connexions WebSocket actives et leur cycle de vie.

#### BroadcastManager

Gestionnaire de base avec support multi-connexions par entité :

```python
from backend.app.websocket import BroadcastManager

manager = BroadcastManager()

# Ajouter une connexion
await manager.connect(entity_id, websocket)

# Broadcaster à toutes les connexions d'une entité
await manager.broadcast(entity_id, message)

# Déconnecter
manager.disconnect(entity_id, websocket)
```

#### ConnectionManager

Gestionnaire spécialisé pour les déploiements avec une seule connexion par entité :

```python
from backend.app.websocket import ConnectionManager

manager = ConnectionManager()

# Connecter (remplace la connexion existante)
await manager.connect(deployment_id, websocket)

# Envoyer un message
await manager.send_personal_message(message, deployment_id)

# Broadcaster à tous les déploiements
await manager.broadcast(message)
```

#### UserConnectionManager

Gestionnaire pour les connexions utilisateurs avec support multi-connexions :

```python
from backend.app.websocket import UserConnectionManager

user_manager = UserConnectionManager()

# Connecter un utilisateur
await user_manager.connect(user_id, websocket)

# Broadcaster à toutes les connexions d'un utilisateur
await user_manager.broadcast_to_user(user_id, message)

# Déconnecter
user_manager.disconnect(user_id, websocket)
```

**Instances globales** : Le module exporte `manager` (ConnectionManager) et `user_manager` (UserConnectionManager) prêts à l'emploi.

### 2. Broadcasting (`broadcasting.py`)

Fonctions utilitaires pour broadcaster des événements spécifiques.

#### Broadcasts de déploiement

```python
from backend.app.websocket import (
    broadcast_deployment_log,
    broadcast_deployment_status,
    broadcast_deployment_progress,
    broadcast_deployment_complete
)

# Logs de déploiement
await broadcast_deployment_log(
    deployment_id="dep-123",
    log_message="Starting deployment...",
    level="info"
)

# Changement de statut
await broadcast_deployment_status(
    deployment_id="dep-123",
    status="running",
    message="Deployment in progress"
)

# Progression
await broadcast_deployment_progress(
    deployment_id="dep-123",
    progress=50,
    step="Installing dependencies",
    total_steps=10,
    current_step=5
)

# Déploiement terminé
await broadcast_deployment_complete(
    deployment_id="dep-123",
    status="success",
    message="Deployment completed",
    result={"containers": ["web", "db"]}
)
```

#### Broadcasts utilisateur

```python
from backend.app.websocket import (
    broadcast_to_user,
    broadcast_to_event_subscribers
)

# Broadcaster à un utilisateur spécifique
await broadcast_to_user(
    user_id="user-123",
    message={
        "type": "NOTIFICATION_SENT",
        "data": {"title": "New notification"}
    }
)

# Broadcaster à tous les abonnés d'un événement
await broadcast_to_event_subscribers(
    event_type="DEPLOYMENT_STATUS_CHANGED",
    event_data={"deploymentId": "dep-123", "status": "running"}
)
```

#### Gestion des connexions utilisateur

```python
from backend.app.websocket import (
    add_user_connection,
    remove_user_connection
)

# Ajouter une connexion
await add_user_connection(user_id="user-123", websocket=websocket)

# Retirer une connexion
remove_user_connection(user_id="user-123", websocket=websocket)
```

#### Gestion des abonnements

```python
from backend.app.websocket import (
    subscribe_to_event,
    unsubscribe_from_event,
    subscribe_to_deployment_logs
)

# S'abonner à un événement
await subscribe_to_event(
    websocket=websocket,
    event_type="DEPLOYMENT_STATUS_CHANGED",
    user_id="user-123"
)

# Se désabonner
await unsubscribe_from_event(
    websocket=websocket,
    event_type="DEPLOYMENT_STATUS_CHANGED",
    user_id="user-123"
)

# S'abonner aux logs d'un déploiement
await subscribe_to_deployment_logs(
    websocket=websocket,
    deployment_id="dep-123",
    user_id="user-123"
)
```

### 3. Event Bridge (`event_bridge.py`)

Pont entre les événements internes de l'application et le système WebSocket.

```python
from backend.app.websocket import EventBridge

# Initialiser le pont
bridge = EventBridge(redis_client)
await bridge.start()

# Les événements Redis sont automatiquement broadcastés via WebSocket
```

### 4. Plugin System (`plugin.py`)

Système de plugins extensible pour réagir aux événements WebSocket.

#### Créer un plugin

```python
from backend.app.websocket import WebSocketPlugin, PluginContext
from backend.app.schemas.websocket_events import WebSocketEventType

class MyPlugin(WebSocketPlugin):
    """Plugin personnalisé."""
    
    # Définir les événements écoutés
    event_types = [
        WebSocketEventType.DEPLOYMENT_STATUS_CHANGED,
        WebSocketEventType.NOTIFICATION_SENT
    ]
    
    async def initialize(self, context: PluginContext) -> None:
        """Initialisation lors de la connexion."""
        context.logger.info(f"Plugin initialized for user {context.user.id}")
    
    async def handle_event(
        self,
        event_type: str,
        event_data: dict,
        context: PluginContext
    ) -> None:
        """Traiter un événement."""
        context.logger.info(f"Handling {event_type}")
        # Logique métier...
    
    async def cleanup(self, context: PluginContext) -> None:
        """Nettoyage lors de la déconnexion."""
        context.logger.info("Plugin cleaned up")
```

#### Enregistrer un plugin

```python
from backend.app.websocket import plugin_manager

# Enregistrer
plugin_manager.register(MyPlugin())

# Le plugin sera automatiquement appelé pour les événements configurés
```

#### Plugin Context

```python
@dataclass
class PluginContext:
    """Contexte partagé entre tous les plugins."""
    
    db: Optional[AsyncSession]              # Session DB (peut être None)
    user: Optional[User]                    # Utilisateur authentifié
    websocket: WebSocket                    # Connexion WebSocket
    logger: logging.Logger                  # Logger structuré
    broadcast_to_user: Optional[Callable]   # Fonction broadcast utilisateur
    broadcast_to_event_subscribers: Optional[Callable]  # Fonction broadcast abonnés
```

## Endpoints WebSocket

Les endpoints sont définis dans `backend/app/api/v1/websockets.py` :

### 1. Endpoint Global (`/ws`)

Connexion WebSocket principale avec gestion d'événements via plugins :

```python
# Frontend
const ws = new WebSocket('ws://localhost:8000/api/v1/ws?token=<jwt_token>')

# Envoyer un événement
ws.send(JSON.stringify({
    type: 'DEPLOYMENT_STATUS_CHANGED',
    data: { deploymentId: 'dep-123', status: 'running' }
}))

# Recevoir des événements
ws.onmessage = (event) => {
    const message = JSON.parse(event.data)
    console.log(message.type, message.data)
}
```

### 2. Endpoint Déploiement (`/ws/deployment/{deployment_id}`)

Connexion WebSocket spécifique à un déploiement :

```python
# Frontend
const ws = new WebSocket('ws://localhost:8000/api/v1/ws/deployment/dep-123?token=<jwt_token>')

# Recevoir les logs et mises à jour
ws.onmessage = (event) => {
    const message = JSON.parse(event.data)
    if (message.type === 'log') {
        console.log(message.message)
    }
}
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
- `DEPLOYMENT_COMPLETE` : Déploiement terminé

### Notifications
- `NOTIFICATION_SENT` : Nouvelle notification
- `NOTIFICATION_READ` : Notification lue

### Système
- `WEBSOCKET_ERROR` : Erreur WebSocket
- `WEBSOCKET_PING` : Heartbeat
- `WEBSOCKET_PONG` : Réponse heartbeat

## Utilisation dans le code

### Broadcaster depuis un service

```python
from backend.app.websocket import broadcast_deployment_status

class DeploymentService:
    async def update_status(self, deployment_id: str, status: str):
        # Mettre à jour en base
        await self.repository.update_status(deployment_id, status)
        
        # Broadcaster via WebSocket
        await broadcast_deployment_status(
            deployment_id=deployment_id,
            status=status,
            message=f"Deployment {status}"
        )
```

### Broadcaster depuis une tâche background

```python
from backend.app.websocket import broadcast_deployment_log

async def deploy_stack():
    deployment_id = "dep-123"
    
    try:
        await broadcast_deployment_log(
            deployment_id,
            "Starting deployment...",
            level="info"
        )
        
        # Logique de déploiement...
        
        await broadcast_deployment_log(
            deployment_id,
            "Deployment completed",
            level="success"
        )
    except Exception as e:
        await broadcast_deployment_log(
            deployment_id,
            f"Error: {e}",
            level="error"
        )
```

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

### DeploymentMonitorPlugin

Monitore le cycle de vie des déploiements :

```python
from backend.app.websocket.plugins.deployment_monitor import DeploymentMonitorPlugin

# Événements monitorés :
# - DEPLOYMENT_STATUS_CHANGED
# - DEPLOYMENT_LOGS_UPDATE
# - DEPLOYMENT_PROGRESS
```

### SubscriptionPlugin

Gère les abonnements aux événements :

```python
# Les clients peuvent s'abonner à des événements spécifiques
ws.send(JSON.stringify({
    type: 'subscribe',
    event: 'DEPLOYMENT_STATUS_CHANGED'
}))

# Se désabonner
ws.send(JSON.stringify({
    type: 'unsubscribe',
    event: 'DEPLOYMENT_STATUS_CHANGED'
}))
```

## Bonnes pratiques

### 1. Gestion d'erreurs

Toujours encapsuler la logique dans des try/except :

```python
async def broadcast_something(entity_id: str):
    try:
        await manager.broadcast(entity_id, {"type": "update"})
    except Exception as e:
        logger.error(f"Broadcast error: {e}", exc_info=True)
        # Ne pas bloquer l'exécution
```

### 2. Performance

- Les broadcasts sont asynchrones et non-bloquants
- Les plugins s'exécutent en parallèle via `asyncio.gather`
- Utiliser des timeouts pour les opérations réseau :

```python
async with asyncio.timeout(5):
    await manager.broadcast(entity_id, message)
```

### 3. Logging structuré

Utiliser des champs extra pour le contexte :

```python
logger.info(
    "Broadcasting deployment status",
    extra={
        "deployment_id": deployment_id,
        "status": status,
        "user_id": user_id
    }
)
```

### 4. Tests

Tester les broadcasts avec des mocks :

```python
import pytest
from unittest.mock import AsyncMock, patch

@pytest.mark.asyncio
async def test_broadcast_deployment_status():
    with patch('backend.app.websocket.broadcasting.manager') as mock_manager:
        mock_manager.broadcast = AsyncMock()
        
        await broadcast_deployment_status("dep-123", "running")
        
        mock_manager.broadcast.assert_called_once()
```

## Synchronisation Frontend/Backend

Les événements sont **strictement synchronisés** entre frontend et backend via l'enum `WebSocketEventType`. Toute modification doit être faite dans les deux fichiers :

- **Backend** : `backend/app/schemas/websocket_events.py`
- **Frontend** : `frontend/src/services/websocket/types.ts`

Les noms d'événements doivent être identiques (UPPER_CASE).

## Dépannage

### Les messages ne sont pas reçus

1. Vérifier la connexion WebSocket dans les DevTools réseau
2. Vérifier l'authentification (token JWT valide)
3. Vérifier les logs backend pour les erreurs de broadcast
4. S'assurer que l'entité (deployment_id, user_id) est correcte

### Les plugins ne réagissent pas

1. Vérifier que le plugin est enregistré :
   ```python
   from backend.app.websocket import plugin_manager
   print(plugin_manager._plugins)
   ```

2. Vérifier que `event_types` contient le bon événement
3. Vérifier les logs pour les erreurs d'initialisation

### Performance lente

1. Vérifier le nombre de connexions actives :
   ```python
   print(len(manager._connections))
   print(len(user_manager._connections))
   ```

2. Limiter la taille des messages broadcastés
3. Utiliser des timeouts appropriés
4. Considérer la pagination pour les gros volumes de logs

## Architecture de référence

### Flux d'un événement

```
Service/Task → Broadcasting Function → Connection Manager → WebSocket → Frontend
     ↓
  Plugin Manager → Plugins (parallel execution)
```

### Exemple complet

```python
# 1. Service émet un événement
class DeploymentService:
    async def start_deployment(self, deployment_id: str):
        # Logique métier
        deployment = await self.create(deployment_id)
        
        # 2. Broadcast via WebSocket
        await broadcast_deployment_status(
            deployment_id=deployment_id,
            status="running",
            message="Deployment started"
        )
        
        # 3. Les plugins réagissent automatiquement
        # 4. Le frontend reçoit la mise à jour temps-réel
```

## Ressources

- [Documentation WebSocket Frontend](../../../frontend/src/services/websocket/README.md)
- [Événements WebSocket](../schemas/websocket_events.py)
- [FastAPI WebSocket](https://fastapi.tiangolo.com/advanced/websockets/)
- [asyncio Documentation](https://docs.python.org/3/library/asyncio.html)

---

**Version** : 2.0  
**Dernière mise à jour** : 23/01/2026  
**Refactoring** : Architecture modulaire avec séparation des responsabilités
