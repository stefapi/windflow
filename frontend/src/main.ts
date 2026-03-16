/**
 * Main Application Entry Point
 */

import { createApp, h } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus, { ElMessage } from 'element-plus'
import 'element-plus/dist/index.css'
import '@unocss/reset/tailwind.css'
import 'uno.css'

// Theme CSS (must be imported after element-plus to override styles)
import './styles/theme.css'

import App from './App.vue'
import SplashScreen from './components/SplashScreen.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

// WebSocket plugins
import { pluginManager } from './services/websocket/plugin'
import { defaultPlugins } from './services/websocket/plugins'
import type { PluginContext } from './services/websocket/plugin'

/**
 * Initialize WebSocket plugins
 */
const initWebSocketPlugins = async (pinia: any) => {
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

/**
 * Initialize application with splash screen
 */
async function initializeApp() {
  // Create and mount splash screen
  const splashApp = createApp({
    render: () => h(SplashScreen, { message: 'Vérification de la session...' })
  })
  splashApp.mount('#app')

  try {
    // Create main app
    const app = createApp(App)
    const pinia = createPinia()

    // Register Pinia
    app.use(pinia)

    // Initialize auth store from localStorage BEFORE router
    // This ensures the navigation guard has access to the correct auth state
    const authStore = useAuthStore()

    console.log('🔐 Initializing authentication...')
    let isAuthenticated = await authStore.initFromStorage()

    if (isAuthenticated) {
      console.log('✅ Authentication restored from storage')
    } else {
      // No stored session — try auto-login (works only if backend has DISABLE_AUTH=true)
      console.log('ℹ️ No valid session found, trying auto-login...')
      isAuthenticated = await authStore.tryAutoLogin()

      if (!isAuthenticated) {
        console.log('ℹ️ Auto-login not available, manual login required')
      }
    }

    // Register router after auth is initialized
    app.use(router)
    app.use(ElementPlus)

    // Initialize WebSocket plugins
    console.log('🔌 Initializing WebSocket plugins...')
    await initWebSocketPlugins(pinia)

    // Unmount splash and mount main app
    splashApp.unmount()
    app.mount('#app')

    console.log('🚀 Application initialized successfully')
  } catch (error) {
    console.error('❌ Failed to initialize application:', error)

    // Show error on splash screen
    splashApp.unmount()
    const errorApp = createApp({
      render: () => h(SplashScreen, {
        message: 'Erreur d\'initialisation. Rechargez la page.'
      })
    })
    errorApp.mount('#app')
  }
}

// Start initialization
initializeApp()
