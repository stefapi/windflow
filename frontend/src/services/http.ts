/**
 * HTTP Client Configuration
 * Axios instance with interceptors for authentication and error handling
 */

import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types/api'
import { useAuthStore } from '@/stores/auth'

// Retry configuration for 401 errors
const MAX_RETRY_ATTEMPTS = 3
const RETRY_DELAYS = [1000, 2000, 4000] // Exponential backoff: 1s, 2s, 4s
let retryAttempts = 0
let isRetrying = false

// Create axios instance with custom backend URL from environment
const baseURL = import.meta.env['VITE_API_BASE_URL']
  ? `${import.meta.env['VITE_API_BASE_URL']}/api/v1`
  : '/api/v1'

// Display API address for debugging
console.log('🔌 API Base URL:', baseURL)

const http: AxiosInstance = axios.create({
  baseURL,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor - Add auth token
http.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = localStorage.getItem('access_token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => {
    return Promise.reject(error)
  }
)

// Response interceptor - Handle errors
http.interceptors.response.use(
  (response) => {
    // Reset retry counter on successful response
    retryAttempts = 0
    isRetrying = false
    return response
  },
  async (error: AxiosError<ApiError>) => {
    if (error.response) {
      const { status, data } = error.response

      // Handle 401 - Unauthorized with exponential backoff retry logic
      if (status === 401) {
        const token = localStorage.getItem('access_token')

        // If no token, logout immediately without API call
        if (!token) {
          console.warn('No token found, redirecting to login')
          const authStore = useAuthStore()
          await authStore.logout()
          return Promise.reject(error)
        }

        // Prevent multiple simultaneous retry attempts
        if (isRetrying) {
          return Promise.reject(error)
        }

        // Check if we've exceeded max retry attempts
        if (retryAttempts >= MAX_RETRY_ATTEMPTS) {
          console.error(`Max retry attempts (${MAX_RETRY_ATTEMPTS}) reached, logging out`)
          retryAttempts = 0
          isRetrying = false

          const authStore = useAuthStore()
          await authStore.logout()
          window.location.href = '/login'
          return Promise.reject(error)
        }

        // Validate token structure and expiration
        try {
          const tokenParts = token.split('.')
          if (tokenParts.length !== 3 || !tokenParts[1]) {
            console.warn('Malformed token, logging out')
            const authStore = useAuthStore()
            await authStore.logout()
            window.location.href = '/login'
            return Promise.reject(error)
          }

          const payload = JSON.parse(atob(tokenParts[1]))
          const currentTime = Date.now() / 1000

          // If token is expired by more than 5 minutes, don't retry
          if (payload.exp && (currentTime - payload.exp) > 300) {
            console.warn('Token expired by more than 5 minutes, logging out')
            retryAttempts = 0
            const authStore = useAuthStore()
            await authStore.logout()
            window.location.href = '/login'
            return Promise.reject(error)
          }

          // Implement exponential backoff retry
          isRetrying = true
          const delay = RETRY_DELAYS[retryAttempts]
          retryAttempts++

          console.warn(
            `Token validation issue, retrying in ${delay}ms (attempt ${retryAttempts}/${MAX_RETRY_ATTEMPTS})`
          )

          return new Promise((resolve, reject) => {
            setTimeout(async () => {
              try {
                // Retry the original request
                const retryConfig = { ...error.config }
                const response = await axios.request(retryConfig)

                // Success! Reset counters
                retryAttempts = 0
                isRetrying = false
                resolve(response)
              } catch (retryError) {
                isRetrying = false

                // If this was the last attempt, logout
                if (retryAttempts >= MAX_RETRY_ATTEMPTS) {
                  console.error('All retry attempts failed, logging out')
                  retryAttempts = 0
                  const authStore = useAuthStore()
                  await authStore.logout()
                  window.location.href = '/login'
                }

                reject(retryError)
              }
            }, delay)
          })
        } catch (decodeError) {
          console.error('Error decoding token:', decodeError)
          console.warn('Invalid token format, logging out')
          retryAttempts = 0
          const authStore = useAuthStore()
          await authStore.logout()
          window.location.href = '/login'
          return Promise.reject(decodeError instanceof Error ? decodeError : new Error('Token decode failed'))
        }
      }

      // Handle 403 - Forbidden
      if (status === 403) {
        console.error('Access forbidden:', data.detail)
      }

      // Handle 404 - Not Found
      if (status === 404) {
        console.error('Resource not found:', data.detail)
      }

      // Handle 500 - Server Error
      if (status >= 500) {
        console.error('Server error:', data.detail)
      }
    } else if (error.request) {
      console.error('Network error: No response received')
    } else {
      console.error('Request error:', error.message)
    }

    return Promise.reject(error)
  }
)

export { baseURL }
export default http
