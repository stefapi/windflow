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
      // Infrastructure
      {
        path: 'containers/:id',
        name: 'ContainerDetail',
        component: () => import('@/views/ContainerDetail.vue'),
      },
      {
        path: 'vms',
        name: 'VMs',
        component: () => import('@/views/VMs.vue'),
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
        path: 'compute',
        name: 'Compute',
        component: () => import('@/views/Compute.vue'),
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
        path: 'schedules',
        name: 'Schedules',
        component: () => import('@/views/Schedules.vue'),
      },
      {
        path: 'terminal/:containerId',
        name: 'Terminal',
        component: () => import('@/views/Terminal.vue'),
        props: true,
      },
      // Storage & Network
      {
        path: 'volumes',
        name: 'Volumes',
        component: () => import('@/views/Volumes.vue'),
      },
      {
        path: 'networks',
        name: 'Networks',
        component: () => import('@/views/Networks.vue'),
      },
      {
        path: 'images',
        name: 'Images',
        component: () => import('@/views/Images.vue'),
      },
      // Marketplace
      {
        path: 'marketplace',
        name: 'Marketplace',
        component: () => import('@/views/Marketplace.vue'),
      },
      {
        path: 'plugins',
        name: 'Plugins',
        component: () => import('@/views/Plugins.vue'),
      },
      // Administration
      {
        path: 'settings',
        name: 'Settings',
        component: () => import('@/views/Settings.vue'),
      },
      {
        path: 'audit',
        name: 'Audit',
        component: () => import('@/views/Audit.vue'),
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

  // Skip auth check if coming from login page (allows post-login navigation)
  const comingFromLogin = from.name === 'Login'

  if (requiresAuth && !authStore.isAuthenticated && !comingFromLogin) {
    // Redirect to login if not authenticated
    next({ name: 'Login', query: { redirect: to.fullPath } })
  } else if (to.name === 'Login' && authStore.isAuthenticated) {
    // Redirect away from login if already authenticated
    const redirectPath = (to.query['redirect'] as string) || '/'
    next(redirectPath)
  } else {
    next()
  }
})

export default router
