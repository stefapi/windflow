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
      // Continue avec le nettoyage même si l'appel API échoue
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

      // Redirection vers login - toujours exécutée, même si l'API logout échoue
      // Import dynamique pour éviter les dépendances circulaires
      import('@/router').then(({ default: router }) => {
        router.push('/login')
      }).catch((error) => {
        console.error('Failed to redirect to login:', error)
        // Fallback: redirection directe si le router n'est pas accessible
        window.location.href = '/login'
      })
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
      // Don't logout here - let the caller decide what to do
      throw err
    } finally {
      loading.value = false
    }
  }

  async function initFromStorage(): Promise<boolean> {
    const storedToken = localStorage.getItem('access_token')
    const storedUser = localStorage.getItem('user')

    if (storedToken && storedUser) {
      // Check if token is still valid before using it
      if (isTokenValid(storedToken)) {
        token.value = storedToken
        try {
          user.value = JSON.parse(storedUser)

          // Verify token is still valid with server
          try {
            await fetchCurrentUser()

            // Only connect WebSocket if token is valid
            wsService.connect(storedToken)

            // Schedule token refresh
            scheduleTokenRefresh()

            return true
          } catch (err: unknown) {
            console.error('Failed to verify token with server:', err)

            // Only logout if it's an authentication error (401)
            // This means the token is actually invalid or expired
            const isAuthError = err && typeof err === 'object' && 'response' in err &&
                               (err as { response?: { status?: number } }).response?.status === 401

            if (isAuthError) {
              console.warn('Token is invalid (401 Unauthorized), logging out')
              await logout()
              return false
            }

            // For other errors (network, timeout, 5xx server errors), keep the session
            // The user can continue with cached data and the token might be valid
            console.warn('Could not verify token with server (network/server error), keeping session for retry')

            // Still connect WebSocket and schedule refresh to try again later
            wsService.connect(storedToken)
            scheduleTokenRefresh()

            return true
          }
        } catch (err) {
          console.error('Failed to parse stored user:', err)
          await logout()
          return false
        }
      } else {
        console.warn('Stored token is expired or invalid, clearing storage')
        await logout()
        return false
      }
    }

    return false
  }

  function isTokenValid(token: string): boolean {
    try {
      const tokenParts = token.split('.')
      if (tokenParts.length !== 3 || !tokenParts[1]) {
        return false
      }

      const payload = JSON.parse(window.atob(tokenParts[1]))
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
      if (tokenParts.length !== 3 || !tokenParts[1]) {
        return true // Consider invalid tokens as near expiry
      }

      const payload = JSON.parse(window.atob(tokenParts[1]))
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
      const newAccessToken = response.data.access_token
      const newRefreshToken = response.data.refresh_token

      if (!newAccessToken || !newRefreshToken) {
        console.error('Invalid token refresh response')
        await logout()
        return false
      }

      token.value = newAccessToken
      refreshToken.value = newRefreshToken

      // Update localStorage
      localStorage.setItem('access_token', newAccessToken)
      localStorage.setItem('refresh_token', newRefreshToken)

      // Update WebSocket connection
      wsService.disconnect()
      wsService.connect(newAccessToken)

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
    const currentToken = token.value
    if (!currentToken) {
      return
    }

    // Clear any existing timer
    if (refreshTimer) {
      clearTimeout(refreshTimer)
    }

    // Schedule refresh 2 minutes before expiry
    const refreshTime = getTimeUntilRefresh(currentToken)
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

  function getTimeUntilRefresh(tokenValue?: string | null): number {
    const tokenToCheck = tokenValue ?? token.value
    if (!tokenToCheck) {
      return 0
    }

    try {
      const tokenParts = tokenToCheck.split('.')
      if (tokenParts.length !== 3 || !tokenParts[1]) {
        return 0
      }

      const payload = JSON.parse(window.atob(tokenParts[1]))
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
