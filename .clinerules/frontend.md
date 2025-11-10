# Règles de Développement Frontend - WindFlow

## Stack Technologique Frontend

### Framework Principal
- **Vue.js 3** avec Composition API obligatoire
- **TypeScript** strict mode activé
- **Element Plus** pour les composants UI
- **UnoCSS** pour le styling utilitaire
- **Pinia** pour la gestion d'état
- **Vue Router** pour le routage

## Conventions TypeScript

### Types Stricts Obligatoires
```typescript
// ✅ CORRECT - Types explicites
interface DeploymentCreateRequest {
  name: string
  stackId: string
  targetType: 'docker' | 'kubernetes' | 'vm' | 'physical'
  configuration?: Record<string, unknown>
  enableLlmOptimization?: boolean
}

interface ApiResponse<T> {
  data: T
  message: string
  status: 'success' | 'error'
  timestamp: string
}

// ❌ INCORRECT - Types any
function createDeployment(data: any): Promise<any> {
  // ...
}
```

### Configuration TypeScript Stricte
```json
// tsconfig.json
{
  "compilerOptions": {
    "strict": true,
    "noImplicitAny": true,
    "noImplicitReturns": true,
    "noImplicitThis": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "exactOptionalPropertyTypes": true
  }
}
```

## Composition API et Composables

### Structure des Composables
```typescript
// composables/useDeployments.ts
import { ref, computed, readonly } from 'vue'
import type { Deployment, DeploymentCreateRequest } from '@/types'
import { deploymentService } from '@/services'

export function useDeployments() {
  const deployments = ref<Deployment[]>([])
  const loading = ref(false)
  const error = ref<string | null>(null)

  const activeDeployments = computed(() =>
    deployments.value.filter(d => d.status === 'running')
  )

  const pendingCount = computed(() =>
    deployments.value.filter(d => d.status === 'pending').length
  )

  const fetchDeployments = async (): Promise<void> => {
    loading.value = true
    error.value = null
    
    try {
      const response = await deploymentService.getAll()
      deployments.value = response.data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erreur inconnue'
      throw err
    } finally {
      loading.value = false
    }
  }

  const createDeployment = async (request: DeploymentCreateRequest): Promise<Deployment> => {
    loading.value = true
    error.value = null

    try {
      const response = await deploymentService.create(request)
      deployments.value.push(response.data)
      return response.data
    } catch (err) {
      error.value = err instanceof Error ? err.message : 'Erreur lors de la création'
      throw err
    } finally {
      loading.value = false
    }
  }

  return {
    // État en lecture seule
    deployments: readonly(deployments),
    loading: readonly(loading),
    error: readonly(error),
    
    // Computed
    activeDeployments,
    pendingCount,
    
    // Actions
    fetchDeployments,
    createDeployment
  }
}
```

### Conventions Composants Vue 3
```vue
<template>
  <div class="deployment-card p-6 border border-gray-200 rounded-lg">
    <header class="flex items-center justify-between mb-4">
      <h3 class="text-lg font-semibold text-gray-900">
        {{ deployment.name }}
      </h3>
      <el-tag 
        :type="statusVariant" 
        :effect="deployment.status === 'running' ? 'light' : 'plain'"
      >
        {{ deployment.status }}
      </el-tag>
    </header>

    <div class="space-y-3">
      <div class="flex items-center text-sm text-gray-600">
        <el-icon class="mr-2"><Document /></el-icon>
        <span>Target: {{ deployment.targetType }}</span>
      </div>
      
      <div class="flex items-center text-sm text-gray-600">
        <el-icon class="mr-2"><Clock /></el-icon>
        <span>{{ formattedDate }}</span>
      </div>
    </div>

    <footer class="mt-6 flex space-x-2">
      <el-button 
        size="small" 
        @click="emit('view-logs', deployment.id)"
      >
        Voir les logs
      </el-button>
      
      <el-button 
        v-if="deployment.status === 'running'"
        size="small" 
        type="danger" 
        @click="emit('stop-deployment', deployment.id)"
      >
        Arrêter
      </el-button>
    </footer>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { ElButton, ElTag, ElIcon } from 'element-plus'
import { Document, Clock } from '@element-plus/icons-vue'
import type { Deployment } from '@/types'

interface Props {
  deployment: Deployment
}

interface Emits {
  'view-logs': [deploymentId: string]
  'stop-deployment': [deploymentId: string]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const statusVariant = computed(() => {
  const variants = {
    pending: 'warning',
    running: 'success',
    success: 'success',
    failed: 'danger'
  } as const
  
  return variants[props.deployment.status] || 'info'
})

const formattedDate = computed(() => {
  return new Intl.DateTimeFormat('fr-FR', {
    dateStyle: 'short',
    timeStyle: 'short'
  }).format(new Date(props.deployment.createdAt))
})
</script>
```

## Gestion d'État avec Pinia

### Structure des Stores
```typescript
// stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import type { User, LoginCredentials, AuthResponse } from '@/types'
import { authService } from '@/services'

export const useAuthStore = defineStore('auth', () => {
  // État
  const user = ref<User | null>(null)
  const token = ref<string>('')
  const refreshToken = ref<string>('')
  const loading = ref(false)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isAdmin = computed(() => user.value?.isSuperadmin ?? false)
  const userPermissions = computed(() => user.value?.permissions ?? [])

  // Actions
  const login = async (credentials: LoginCredentials): Promise<void> => {
    loading.value = true
    
    try {
      const response = await authService.login(credentials)
      
      user.value = response.user
      token.value = response.accessToken
      refreshToken.value = response.refreshToken
      
      // Configuration automatique des headers
      authService.setAuthHeader(response.accessToken)
      
      // Programmation du refresh token
      scheduleTokenRefresh(response.expiresIn)
      
    } catch (error) {
      // Reset de l'état en cas d'erreur
      user.value = null
      token.value = ''
      refreshToken.value = ''
      throw error
    } finally {
      loading.value = false
    }
  }

  const logout = async (): Promise<void> => {
    try {
      if (token.value) {
        await authService.logout()
      }
    } finally {
      // Reset de l'état dans tous les cas
      user.value = null
      token.value = ''
      refreshToken.value = ''
      authService.clearAuthHeader()
      
      // Redirection vers login
      const router = useRouter()
      await router.push('/login')
    }
  }

  const refreshAccessToken = async (): Promise<void> => {
    if (!refreshToken.value) {
      throw new Error('No refresh token available')
    }

    try {
      const response = await authService.refreshToken(refreshToken.value)
      
      token.value = response.accessToken
      authService.setAuthHeader(response.accessToken)
      
      scheduleTokenRefresh(response.expiresIn)
    } catch (error) {
      // En cas d'échec du refresh, déconnecter l'utilisateur
      await logout()
      throw error
    }
  }

  const scheduleTokenRefresh = (expiresIn: number): void => {
    // Programmer le refresh 5 minutes avant expiration
    const refreshTime = (expiresIn - 300) * 1000
    
    setTimeout(() => {
      if (isAuthenticated.value) {
        refreshAccessToken().catch(console.error)
      }
    }, refreshTime)
  }

  return {
    // État
    user: readonly(user),
    loading: readonly(loading),
    
    // Getters
    isAuthenticated,
    isAdmin,
    userPermissions,
    
    // Actions
    login,
    logout,
    refreshAccessToken
  }
}, {
  persist: {
    paths: ['user', 'token', 'refreshToken'],
    storage: localStorage
  }
})
```

## Services API

### Configuration HTTP Client
```typescript
// services/api.ts
import axios, { type AxiosInstance, type AxiosResponse } from 'axios'
import { useAuthStore } from '@/stores/auth'
import { ElMessage } from 'element-plus'

class ApiClient {
  private client: AxiosInstance

  constructor(baseURL: string) {
    this.client = axios.create({
      baseURL,
      timeout: 30000,
      headers: {
        'Content-Type': 'application/json'
      }
    })

    this.setupInterceptors()
  }

  private setupInterceptors(): void {
    // Request interceptor pour ajouter le token
    this.client.interceptors.request.use(
      (config) => {
        const authStore = useAuthStore()
        if (authStore.token) {
          config.headers.Authorization = `Bearer ${authStore.token}`
        }
        return config
      },
      (error) => Promise.reject(error)
    )

    // Response interceptor pour gérer les erreurs
    this.client.interceptors.response.use(
      (response) => response,
      async (error) => {
        const authStore = useAuthStore()
        
        if (error.response?.status === 401) {
          try {
            await authStore.refreshAccessToken()
            // Retry la requête avec le nouveau token
            return this.client.request(error.config)
          } catch {
            await authStore.logout()
            return Promise.reject(error)
          }
        }

        // Affichage des erreurs utilisateur
        if (error.response?.data?.message) {
          ElMessage.error(error.response.data.message)
        }

        return Promise.reject(error)
      }
    )
  }

  async get<T>(url: string, params?: Record<string, unknown>): Promise<AxiosResponse<T>> {
    return this.client.get(url, { params })
  }

  async post<T>(url: string, data?: unknown): Promise<AxiosResponse<T>> {
    return this.client.post(url, data)
  }

  async put<T>(url: string, data?: unknown): Promise<AxiosResponse<T>> {
    return this.client.put(url, data)
  }

  async delete<T>(url: string): Promise<AxiosResponse<T>> {
    return this.client.delete(url)
  }
}

export const apiClient = new ApiClient(import.meta.env.VITE_API_BASE_URL)
```

### Services Métier
```typescript
// services/deployment.service.ts
import type { 
  Deployment, 
  DeploymentCreateRequest, 
  DeploymentListResponse,
  ApiResponse 
} from '@/types'
import { apiClient } from './api'

class DeploymentService {
  private readonly basePath = '/api/v1/deployments'

  async getAll(page = 1, limit = 20): Promise<DeploymentListResponse> {
    const response = await apiClient.get<DeploymentListResponse>(
      this.basePath,
      { page, limit }
    )
    return response.data
  }

  async getById(id: string): Promise<ApiResponse<Deployment>> {
    const response = await apiClient.get<ApiResponse<Deployment>>(
      `${this.basePath}/${id}`
    )
    return response.data
  }

  async create(data: DeploymentCreateRequest): Promise<ApiResponse<Deployment>> {
    const response = await apiClient.post<ApiResponse<Deployment>>(
      this.basePath,
      data
    )
    return response.data
  }

  async stop(id: string): Promise<ApiResponse<void>> {
    const response = await apiClient.post<ApiResponse<void>>(
      `${this.basePath}/${id}/stop`
    )
    return response.data
  }

  async getLogs(id: string): Promise<ApiResponse<string[]>> {
    const response = await apiClient.get<ApiResponse<string[]>>(
      `${this.basePath}/${id}/logs`
    )
    return response.data
  }

  async delete(id: string): Promise<ApiResponse<void>> {
    const response = await apiClient.delete<ApiResponse<void>>(
      `${this.basePath}/${id}`
    )
    return response.data
  }
}

export const deploymentService = new DeploymentService()
```

## Routing et Navigation

### Configuration Router
```typescript
// router/index.ts
import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    redirect: '/dashboard'
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/auth/LoginView.vue'),
    meta: { requiresGuest: true }
  },
  {
    path: '/dashboard',
    name: 'Dashboard',
    component: () => import('@/layouts/AppLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'DashboardHome',
        component: () => import('@/views/dashboard/DashboardHome.vue')
      },
      {
        path: 'deployments',
        name: 'Deployments',
        component: () => import('@/views/deployments/DeploymentsList.vue')
      },
      {
        path: 'deployments/:id',
        name: 'DeploymentDetails',
        component: () => import('@/views/deployments/DeploymentDetails.vue'),
        props: true
      }
    ]
  },
  {
    path: '/admin',
    name: 'Admin',
    component: () => import('@/layouts/AdminLayout.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
    children: [
      {
        path: 'organizations',
        name: 'Organizations',
        component: () => import('@/views/admin/OrganizationsView.vue')
      },
      {
        path: 'users',
        name: 'Users',
        component: () => import('@/views/admin/UsersView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Navigation guards
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()

  // Vérification authentification
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next({ name: 'Login', query: { redirect: to.fullPath } })
    return
  }

  // Redirection si déjà connecté
  if (to.meta.requiresGuest && authStore.isAuthenticated) {
    next({ name: 'Dashboard' })
    return
  }

  // Vérification privilèges admin
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    next({ name: 'Dashboard' })
    return
  }

  next()
})

export default router
```

## UnoCSS et Styling

### Configuration UnoCSS
```typescript
// uno.config.ts
import { defineConfig, presetUno, presetAttributify } from 'unocss'

export default defineConfig({
  presets: [
    presetUno(),
    presetAttributify()
  ],
  theme: {
    colors: {
      primary: {
        50: '#eff6ff',
        500: '#3b82f6',
        600: '#2563eb',
        700: '#1d4ed8'
      },
      gray: {
        50: '#f9fafb',
        100: '#f3f4f6',
        600: '#4b5563',
        900: '#111827'
      }
    }
  },
  shortcuts: {
    'btn-primary': 'bg-primary-600 text-white px-4 py-2 rounded hover:bg-primary-700 transition-colors',
    'card': 'bg-white rounded-lg shadow border border-gray-200 p-6',
    'input-field': 'border border-gray-300 rounded px-3 py-2 focus:ring-2 focus:ring-primary-500 focus:border-primary-500'
  }
})
```

## Tests Frontend

### Tests Unitaires avec Vitest
```typescript
// tests/components/DeploymentCard.test.ts
import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { ElButton, ElTag } from 'element-plus'
import DeploymentCard from '@/components/features/DeploymentCard.vue'
import type { Deployment } from '@/types'

const mockDeployment: Deployment = {
  id: 'test-123',
  name: 'Test Deployment',
  status: 'running',
  targetType: 'docker',
  createdAt: '2024-01-15T10:00:00Z',
  updatedAt: '2024-01-15T10:30:00Z'
}

describe('DeploymentCard', () => {
  it('affiche les informations du déploiement', () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    expect(wrapper.text()).toContain('Test Deployment')
    expect(wrapper.text()).toContain('docker')
    expect(wrapper.text()).toContain('running')
  })

  it('émet l\'événement view-logs au clic', async () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    await wrapper.find('[data-test="view-logs-btn"]').trigger('click')
    
    expect(wrapper.emitted('view-logs')).toEqual([['test-123']])
  })

  it('affiche le bouton d\'arrêt pour les déploiements en cours', () => {
    const wrapper = mount(DeploymentCard, {
      props: { deployment: mockDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    expect(wrapper.find('[data-test="stop-btn"]').exists()).toBe(true)
  })

  it('n\'affiche pas le bouton d\'arrêt pour les déploiements terminés', () => {
    const finishedDeployment = { ...mockDeployment, status: 'success' as const }
    
    const wrapper = mount(DeploymentCard, {
      props: { deployment: finishedDeployment },
      global: {
        components: { ElButton, ElTag }
      }
    })

    expect(wrapper.find('[data-test="stop-btn"]').exists()).toBe(false)
  })
})
```

### Tests E2E avec Playwright
```typescript
// tests/e2e/deployment-workflow.test.ts
import { test, expect } from '@playwright/test'

test.describe('Workflow de déploiement', () => {
  test.beforeEach(async ({ page }) => {
    // Mock de l'authentification
    await page.goto('/login')
    await page.fill('[data-test="username"]', 'test@windflow.local')
    await page.fill('[data-test="password"]', 'password')
    await page.click('[data-test="login-btn"]')
    await expect(page).toHaveURL('/dashboard')
  })

  test('création d\'un nouveau déploiement', async ({ page }) => {
    // Navigation vers la page de déploiements
    await page.click('[data-test="nav-deployments"]')
    await expect(page).toHaveURL('/dashboard/deployments')

    // Clic sur le bouton de création
    await page.click('[data-test="create-deployment-btn"]')

    // Remplissage du formulaire
    await page.fill('[data-test="deployment-name"]', 'Test E2E Deployment')
    await page.selectOption('[data-test="target-type"]', 'docker')
    
    // Soumission
    await page.click('[data-test="submit-btn"]')

    // Vérification de la création
    await expect(page.locator('[data-test="deployment-card"]')).toContainText('Test E2E Deployment')
    await expect(page.locator('[data-test="status-badge"]')).toContainText('pending')
  })

  test('visualisation des logs de déploiement', async ({ page }) => {
    // Clic sur un déploiement existant
    await page.click('[data-test="deployment-card"]:first-child')
    
    // Vérification de la page de détails
    await expect(page).toHaveURL(/\/dashboard\/deployments\/.*/)
    
    // Clic sur l'onglet logs
    await page.click('[data-test="logs-tab"]')
    
    // Vérification de l'affichage des logs
    await expect(page.locator('[data-test="logs-container"]')).toBeVisible()
  })
})
```

## Performance et Optimisations

### Lazy Loading et Code Splitting
```typescript
// Lazy loading des vues
const routes = [
  {
    path: '/dashboard',
    component: () => import('@/layouts/AppLayout.vue'),
    children: [
      {
        path: 'deployments',
        // Préchargement pour les routes critiques
        component: () => import(/* webpackPreload: true */ '@/views/deployments/DeploymentsList.vue')
      },
      {
        path: 'admin',
        // Lazy loading pour les routes d'admin
        component: () => import(/* webpackChunkName: "admin" */ '@/views/admin/AdminDashboard.vue')
      }
    ]
  }
]
```

### Optimisation des Re-renders
```vue
<script setup lang="ts">
import { computed, shallowRef } from 'vue'

// Utilisation de shallowRef pour les gros objets
const deployments = shallowRef<Deployment[]>([])

// Memoization des calculs coûteux
const deploymentStats = computed(() => {
  if (!deployments.value.length) return null
  
  return {
    total: deployments.value.length,
    running: deployments.value.filter(d => d.status === 'running').length,
    failed: deployments.value.filter(d => d.status === 'failed').length
  }
})
</script>
```

Ces règles garantissent un développement frontend moderne, performant et maintenable pour WindFlow.
