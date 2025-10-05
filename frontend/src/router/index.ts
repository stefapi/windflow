/**
 * Vue Router Configuration
 * Routing with authentication guards
 */

import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

// Extend Vue Router's RouteMeta interface for type safety
declare module 'vue-router' {
  interface RouteMeta {
    requiresAuth?: boolean
  }
}

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { requiresAuth: false },
  },
  {
    path: '/',
    component: () => import('@/layouts/MainLayout.vue'),
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
      },
      {
        path: 'targets',
        name: 'Targets',
        component: () => import('@/views/Targets.vue'),
      },
      {
        path: 'stacks',
        name: 'Stacks',
        component: () => import('@/views/Stacks.vue'),
      },
      {
        path: 'deployments',
        name: 'Deployments',
        component: () => import('@/views/Deployments.vue'),
      },
      {
        path: 'deployments/:id',
        name: 'DeploymentDetail',
        component: () => import('@/views/DeploymentDetail.vue'),
      },
      {
        path: 'workflows',
        name: 'Workflows',
        component: () => import('@/views/Workflows.vue'),
      },
      {
        path: 'workflows/:id/edit',
        name: 'WorkflowEditor',
        component: () => import('@/views/WorkflowEditor.vue'),
      },
      {
        path: 'marketplace',
        name: 'Marketplace',
        component: () => import('@/views/Marketplace.vue'),
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

// Navigation guard for authentication
router.beforeEach((to, from, next) => {
  const authStore = useAuthStore()
  const requiresAuth = to.meta.requiresAuth !== false

  if (requiresAuth && !authStore.isAuthenticated) {
    // Redirect to login if not authenticated
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && authStore.isAuthenticated) {
    // Redirect to dashboard if already authenticated
    next({ name: 'Dashboard' })
  } else {
    next()
  }
})

export default router
