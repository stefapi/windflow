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
  const refreshToken = ref<string | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)

  // Timer for automatic token refresh
  let refreshTimer: NodeJS.Timeout | null = null

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
      refreshToken.value = response.data.refresh_token
      user.value = response.data.user

      // Store tokens in localStorage
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('refresh_token', response.data.refresh_token)
      localStorage.setItem('user', JSON.stringify(response.data.user))

      // Connect WebSocket with token
      wsService.connect(response.data.access_token)

      // Schedule automatic token refresh
      scheduleTokenRefresh()
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
      await authApi.register(userData)
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
      refreshToken.value = null
      error.value = null

      // Clear localStorage
      localStorage.removeItem('access_token')
      localStorage.removeItem('refresh_token')
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
      // Check if token is still valid before using it
      if (isTokenValid(storedToken)) {
        token.value = storedToken
        try {
          user.value = JSON.parse(storedUser)
          // Verify token is still valid with server
          fetchCurrentUser()
          // Connect WebSocket with token
          wsService.connect(storedToken)
        } catch (err) {
          console.error('Failed to parse stored user:', err)
          logout()
        }
      } else {
        console.warn('Stored token is expired or invalid, clearing storage')
        logout()
      }
    }
  }

  function isTokenValid(token: string): boolean {
    try {
      const tokenParts = token.split('.')
      if (tokenParts.length !== 3) {
        return false
      }

      const payload = JSON.parse(atob(tokenParts[1]))
      const currentTime = Date.now() / 1000

      // Token is valid if it expires in more than 1 minute
      return payload.exp && (payload.exp - currentTime) > 60
    } catch (error) {
      console.error('Error validating token:', error)
      return false
    }
  }

  function isTokenNearExpiry(token: string, minutesThreshold: number = 5): boolean {
    try {
      const tokenParts = token.split('.')
      if (tokenParts.length !== 3) {
        return true // Consider invalid tokens as near expiry
      }

      const payload = JSON.parse(atob(tokenParts[1]))
      const currentTime = Date.now() / 1000

      // Token is near expiry if it expires in less than threshold minutes
      return payload.exp && (payload.exp - currentTime) < (minutesThreshold * 60)
    } catch (error) {
      console.error('Error checking token expiry:', error)
      return true // Consider tokens we can't parse as near expiry
    }
  }

  async function refreshAccessToken(): Promise<boolean> {
    if (!refreshToken.value) {
      console.warn('No refresh token available')
      return false
    }

    try {
      const response = await authApi.refreshToken(refreshToken.value)

      // Update tokens
      token.value = response.data.access_token
      refreshToken.value = response.data.refresh_token

      // Update localStorage
      localStorage.setItem('access_token', response.data.access_token)
      localStorage.setItem('refresh_token', response.data.refresh_token)

      // Update WebSocket connection
      wsService.disconnect()
      wsService.connect(response.data.access_token)

      console.log('Token refreshed successfully')
      return true
    } catch (error) {
      console.error('Failed to refresh token:', error)
      // If refresh fails, logout the user
      await logout()
      return false
    }
  }

  function scheduleTokenRefresh(): void {
    if (!token.value) {
      return
    }

    // Clear any existing timer
    if (refreshTimer) {
      clearTimeout(refreshTimer)
    }

    // Schedule refresh 2 minutes before expiry
    const refreshTime = getTimeUntilRefresh()
    if (refreshTime > 0) {
      refreshTimer = setTimeout(async () => {
        console.log('Auto-refreshing token...')
        await refreshAccessToken()
        // Schedule next refresh after successful refresh
        if (token.value) {
          scheduleTokenRefresh()
        }
      }, refreshTime)
    }
  }

  function getTimeUntilRefresh(): number {
    if (!token.value) {
      return 0
    }

    try {
      const tokenParts = token.value.split('.')
      if (tokenParts.length !== 3) {
        return 0
      }

      const payload = JSON.parse(atob(tokenParts[1]))
      const currentTime = Date.now() / 1000

      // Refresh 2 minutes before expiry
      const refreshThreshold = 2 * 60 // 2 minutes in seconds
      const timeUntilExpiry = (payload.exp - currentTime) - refreshThreshold

      return Math.max(0, timeUntilExpiry * 1000) // Convert to milliseconds
    } catch (error) {
      console.error('Error calculating refresh time:', error)
      return 0
    }
  }

  // Cleanup timer on store disposal
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', () => {
      if (refreshTimer) {
        clearTimeout(refreshTimer)
      }
    })
  }

  return {
    // State
    user,
    token,
    refreshToken,
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
    refreshAccessToken,
    scheduleTokenRefresh,
    getTimeUntilRefresh,
    isTokenValid,
    isTokenNearExpiry,
  }
})
