# WebSocket Plugin System

## Vue d'ensemble

Le système de plugins WebSocket de WindFlow permet d'étendre facilement les fonctionnalités WebSocket sans modifier le service principal. Il offre une architecture event-driven avec un typage strict TypeScript.

## Architecture

```
websocket/
├── types.ts          # Définitions des types d'événements et données
├── plugin.ts         # Gestionnaire de plugins et interfaces
├── websocket.ts      # Service WebSocket principal
├── plugins/          # Plugins disponibles
│   ├── index.ts      # Export des plugins par défaut
│   ├── navigation.ts # Plugin de navigation
│   ├── notification.ts # Plugin de notifications
│   └── session.ts    # Plugin de gestion de session
└── README.md         # Cette documentation
```

## Utilisation

### Plugins par défaut

Les plugins par défaut sont automatiquement enregistrés au démarrage de l'application dans `main.ts`:

```typescript
import { pluginManager } from './services/websocket/plugin'
import { defaultPlugins } from './services/websocket/plugins'

// Création du contexte pour les plugins
const pluginContext: PluginContext = {
  router,
  pinia,
  helpers: {
    showNotification(notification) { /* ... */ },
    navigate(path) { /* ... */ },
    showModal(config) { /* ... */ },
    logger: console
  }
}

// Enregistrement des plugins
defaultPlugins.forEach(plugin => pluginManager.register(plugin))

// Initialisation avec le contexte
pluginManager.initialize(pluginContext)
```

### Créer un plugin personnalisé

Un plugin doit implémenter l'interface `WebSocketPlugin`:

```typescript
import type { WebSocketPlugin, PluginContext } from '../plugin'
import { WebSocketEventType } from '../types'

export class MyCustomPlugin implements WebSocketPlugin {
  name = 'my-custom-plugin'
  
  // Définir les événements écoutés
  listensFor = [
    WebSocketEventType.NOTIFICATION_SYSTEM,
    WebSocketEventType.DEPLOYMENT_STATUS_CHANGED
  ]
  
  private context?: PluginContext
  
  // Initialisation du plugin
  initialize(context: PluginContext): void {
    this.context = context
    console.log('MyCustomPlugin initialized')
  }
  
  // Gestion des événements
  async handleEvent(type: WebSocketEventType, data: any): Promise<void> {
    switch (type) {
      case WebSocketEventType.NOTIFICATION_SYSTEM:
        await this.handleSystemNotification(data)
        break
        
      case WebSocketEventType.DEPLOYMENT_STATUS_CHANGED:
        await this.handleDeploymentChange(data)
        break
    }
  }
  
  private async handleSystemNotification(data: any): Promise<void> {
    this.context?.helpers.showNotification({
      type: 'info',
      title: 'System',
      message: data.message
    })
  }
  
  private async handleDeploymentChange(data: any): Promise<void> {
    // Logique personnalisée
    this.context?.helpers.logger.log('Deployment changed:', data)
  }
  
  // Nettoyage des ressources
  cleanup(): void {
    console.log('MyCustomPlugin cleaned up')
  }
}

// Export du plugin
export const myCustomPlugin = new MyCustomPlugin()
```

### Enregistrer un plugin personnalisé

```typescript
import { pluginManager } from './services/websocket/plugin'
import { myCustomPlugin } from './services/websocket/plugins/my-custom-plugin'

// Enregistrer après les plugins par défaut
pluginManager.register(myCustomPlugin)
```

## Types d'événements disponibles

### Authentification
- `AUTH_LOGIN_SUCCESS` - Connexion réussie
- `AUTH_LOGOUT` - Déconnexion
- `AUTH_TOKEN_REFRESH` - Token rafraîchi

### Notifications
- `NOTIFICATION_SYSTEM` - Notification système
- `NOTIFICATION_USER` - Notification utilisateur
- `NOTIFICATION_DEPLOYMENT` - Notification de déploiement

### Session
- `SESSION_EXPIRED` - Session expirée
- `SESSION_AUTH_REQUIRED` - Authentification requise
- `SESSION_PERMISSION_CHANGED` - Permissions modifiées
- `SESSION_ORGANIZATION_CHANGED` - Organisation changée

### Navigation UI
- `UI_NAVIGATION_REQUEST` - Demande de navigation
- `UI_MODAL_DISPLAY` - Affichage d'un modal
- `UI_TOAST_DISPLAY` - Affichage d'un toast
- `UI_WORKFLOW_STEP` - Étape de workflow

### Déploiements
- `DEPLOYMENT_STATUS_CHANGED` - Statut de déploiement modifié
- `DEPLOYMENT_LOGS_UPDATE` - Mise à jour des logs
- `DEPLOYMENT_PROGRESS` - Progression du déploiement

### Système
- `SYSTEM_MAINTENANCE` - Maintenance système
- `SYSTEM_BROADCAST` - Message diffusé à tous

## PluginContext

Le contexte fourni aux plugins contient:

### Router
Accès au Vue Router pour la navigation programmatique:
```typescript
context.router.push('/dashboard')
```

### Pinia
Accès aux stores Pinia:
```typescript
const authStore = useAuthStore(context.pinia)
authStore.logout()
```

### Helpers

#### showNotification
Afficher une notification à l'utilisateur:
```typescript
context.helpers.showNotification({
  type: 'success' | 'warning' | 'error' | 'info',
  title: 'Titre',
  message: 'Message détaillé',
  duration: 3000 // optionnel
})
```

#### navigate
Navigation simplifiée:
```typescript
context.helpers.navigate('/deployments')
```

#### showModal
Afficher un modal (à implémenter selon vos besoins):
```typescript
context.helpers.showModal({
  title: 'Confirmation',
  message: 'Êtes-vous sûr ?',
  type: 'confirm'
})
```

#### logger
Logger pour le debugging:
```typescript
context.helpers.logger.log('Debug message')
context.helpers.logger.error('Error message')
```

## Bonnes pratiques

### 1. Typage strict
Utilisez toujours les types définis dans `types.ts` pour garantir la sécurité des types:

```typescript
import type { EventDataMap } from '../types'
import { WebSocketEventType } from '../types'

async handleEvent(
  type: WebSocketEventType, 
  data: EventDataMap[typeof type]
): Promise<void> {
  // TypeScript connaît le type exact de data en fonction de type
}
```

### 2. Gestion des erreurs
Gérez toujours les erreurs dans vos plugins:

```typescript
async handleEvent(type: WebSocketEventType, data: any): Promise<void> {
  try {
    // Logique du plugin
  } catch (error) {
    this.context?.helpers.logger.error('Plugin error:', error)
  }
}
```

### 3. Nettoyage des ressources
Implémentez `cleanup()` pour libérer les ressources:

```typescript
cleanup(): void {
  // Annuler les timers
  if (this.timer) {
    clearInterval(this.timer)
  }
  
  // Nettoyer les listeners
  this.listeners.forEach(unsubscribe => unsubscribe())
}
```

### 4. Un plugin = une responsabilité
Gardez vos plugins focalisés sur une seule fonctionnalité:
- ✅ `NotificationPlugin` gère uniquement les notifications
- ✅ `SessionPlugin` gère uniquement la session
- ❌ Ne mélangez pas les responsabilités

### 5. Tests
Testez vos plugins de manière isolée:

```typescript
import { describe, it, expect, vi } from 'vitest'
import { myCustomPlugin } from './my-custom-plugin'

describe('MyCustomPlugin', () => {
  it('should handle events correctly', async () => {
    const mockContext = {
      router: { push: vi.fn() },
      pinia: {},
      helpers: {
        showNotification: vi.fn(),
        navigate: vi.fn(),
        showModal: vi.fn(),
        logger: console
      }
    }
    
    myCustomPlugin.initialize(mockContext)
    
    await myCustomPlugin.handleEvent(
      WebSocketEventType.NOTIFICATION_SYSTEM,
      { message: 'test' }
    )
    
    expect(mockContext.helpers.showNotification).toHaveBeenCalledWith({
      type: 'info',
      title: 'System',
      message: 'test'
    })
  })
})
```

## Exemple complet

Consultez le fichier `plugins/example.ts` pour un exemple complet d'implémentation d'un plugin personnalisé.

## Debugging

Pour debugger le système de plugins:

```typescript
// Activer les logs détaillés dans plugin.ts
dispatch(type: WebSocketEventType, data: EventDataMap[typeof type]): void {
  console.log('[PluginManager] Dispatching event:', type, data)
  // ...
}
```

## Architecture interne

Le `WebSocketPluginManager` fonctionne ainsi:

1. **Enregistrement**: Les plugins s'enregistrent via `register()`
2. **Initialisation**: `initialize()` est appelé avec le contexte
3. **Dispatch**: Quand un événement WebSocket arrive, `dispatch()` appelle tous les plugins concernés
4. **Cleanup**: `cleanup()` est appelé quand l'application se ferme

## Compatibilité

Le système de plugins coexiste avec l'ancien système de callbacks:

```typescript
// Ancien système (toujours fonctionnel)
websocketService.on('deployment:status', (data) => {
  console.log(data)
})

// Nouveau système (recommandé)
class DeploymentPlugin implements WebSocketPlugin {
  // ...
}
```

Les deux systèmes fonctionnent simultanément pour permettre une migration progressive.

## Questions fréquentes

### Comment désactiver un plugin par défaut ?

```typescript
import { pluginManager } from './services/websocket/plugin'
import { defaultPlugins } from './services/websocket/plugins'

// Filtrer les plugins non désirés
const activePlugins = defaultPlugins.filter(
  p => p.name !== 'session-plugin'
)

activePlugins.forEach(plugin => pluginManager.register(plugin))
```

### Comment prioriser l'ordre d'exécution des plugins ?

L'ordre est déterminé par l'ordre d'enregistrement:

```typescript
// Ce plugin s'exécutera en premier
pluginManager.register(highPriorityPlugin)

// Ce plugin s'exécutera ensuite
pluginManager.register(normalPriorityPlugin)
```

### Comment partager des données entre plugins ?

Utilisez Pinia stores:

```typescript
// Plugin 1
const sharedStore = useSharedStore(this.context!.pinia)
sharedStore.setData('key', value)

// Plugin 2
const sharedStore = useSharedStore(this.context!.pinia)
const value = sharedStore.getData('key')
```
