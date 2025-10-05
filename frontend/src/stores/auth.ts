/**
 * Auth Store
 * Manages user authentication and session state
 */

import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/services/api'
import type { User, LoginRequest, UserCreate } from '@/types/api'
import wsService from '@/services/websocket'

export const useAuthStore = defineStore('auth', () => {
  // State
  const user = ref<User | null>(null)
  const token = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Getters
  const isAuthenticated = computed(() => !!token.value && !!user.value)
  const isSuperuser = computed(() => user.value?.is_superuser ?? false)
  const organizationId = computed(() => user.value?.organization_id ?? null)

  // Actions
  async function login(credentials: LoginRequest): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await authApi.login(credentials)
      token.value = response.data.access_token
      user.value = response.data.user

      // Store token in localStorage
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('user', JSON.stringify(response.data.user))

      // Connect WebSocket
      wsService.connect()
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Login failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function register(userData: UserCreate): Promise<void> {
    loading.value = true
    error.value = null

    try {
      const response = await authApi.register(userData)
      // After registration, login automatically
      await login({
        username: userData.username,
        password: userData.password,
      })
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Registration failed'
      throw err
    } finally {
      loading.value = false
    }
  }

  async function logout(): Promise<void> {
    loading.value = true

    try {
      await authApi.logout()
    } catch (err) {
      console.error('Logout error:', err)
    } finally {
      // Clear state
      user.value = null
      token.value = null
      error.value = null

      // Clear localStorage
      localStorage.removeItem('access_token')
      localStorage.removeItem('user')

      // Disconnect WebSocket
      wsService.disconnect()

      loading.value = false
    }
  }

  async function fetchCurrentUser(): Promise<void> {
    if (!token.value) {
      return
    }

    loading.value = true
    error.value = null

    try {
      const response = await authApi.getCurrentUser()
      user.value = response.data
      localStorage.setItem('user', JSON.stringify(response.data))
    } catch (err: unknown) {
      error.value = err instanceof Error ? err.message : 'Failed to fetch user'
      // If fetching current user fails, logout
      await logout()
    } finally {
      loading.value = false
    }
  }

  function initFromStorage(): void {
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      token.value = storedToken
      try {
        user.value = JSON.parse(storedUser)
        // Verify token is still valid
        fetchCurrentUser()
        // Connect WebSocket
        wsService.connect()
      } catch (err) {
        console.error('Failed to parse stored user:', err)
        logout()
      }
    }
  }

  return {
    // State
    user,
    token,
    loading,
    error,
    // Getters
    isAuthenticated,
    isSuperuser,
    organizationId,
    // Actions
    login,
    register,
    logout,
    fetchCurrentUser,
    initFromStorage,
  }
}, {
  persist: {
    enabled: false, // We handle persistence manually with localStorage
  },
})
