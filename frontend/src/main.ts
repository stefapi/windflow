/**
 * Main Application Entry Point
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import '@unocss/reset/tailwind.css'
import 'uno.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

// WebSocket plugins
import { pluginManager } from './services/websocket/plugin'
import { defaultPlugins } from './services/websocket/plugins'
import type { PluginContext } from './services/websocket/plugin'

const app = createApp(App)
const pinia = createPinia()

// Register Pinia first
app.use(pinia)

// Initialize auth store from localStorage BEFORE router
// This ensures the navigation guard has access to the correct auth state
const authStore = useAuthStore()
authStore.initFromStorage()

// Register router after auth is initialized
app.use(router)
app.use(ElementPlus)

// Initialize WebSocket plugins
const initWebSocketPlugins = async () => {
  // Créer le contexte pour les plugins
  const pluginContext: PluginContext = {
    router,
    pinia,

    showNotification: (notification) => {
      ElMessage({
        message: notification.message,
        type: notification.type,
        duration: notification.duration || 3000,
        showClose: true,
        ...(notification.title && { title: notification.title })
      })
    },

    navigate: (route, options = {}) => {
      if (options.replace) {
        router.replace({
          name: route,
          params: options.params,
          query: options.query,
          state: options.state
        })
      } else {
        router.push({
          name: route,
          params: options.params,
          query: options.query,
          state: options.state
        })
      }
    },

    showModal: (component, props) => {
      // TODO: Implémenter un système de modales global
      console.warn('Modal system not yet implemented:', component, props)
    },

    logger: {
      debug: (message, ...args) => console.debug(`[WS Plugin]`, message, ...args),
      info: (message, ...args) => console.info(`[WS Plugin]`, message, ...args),
      warn: (message, ...args) => console.warn(`[WS Plugin]`, message, ...args),
      error: (message, ...args) => console.error(`[WS Plugin]`, message, ...args)
    }
  }

  // Enregistrer les plugins par défaut
  defaultPlugins.forEach(plugin => {
    pluginManager.register(plugin)
  })

  // Initialiser tous les plugins
  await pluginManager.initializeAll(pluginContext)

  console.log('✅ WebSocket plugins initialized:', pluginManager.list().map(p => p.name))
}

// Initialiser les plugins après le montage
initWebSocketPlugins().catch(error => {
  console.error('Failed to initialize WebSocket plugins:', error)
})

app.mount('#app')
