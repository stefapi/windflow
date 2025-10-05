/**
 * Main Application Entry Point
 */

import { createApp } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import 'element-plus/dist/index.css'
import '@unocss/reset/tailwind.css'
import 'uno.css'

import App from './App.vue'
import router from './router'
import { useAuthStore } from './stores/auth'

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

app.mount('#app')
