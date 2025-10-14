/**
 * HTTP Client Configuration
 * Axios instance with interceptors for authentication and error handling
 */

import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types/api'

// Create axios instance with custom backend URL from environment
const baseURL = import.meta.env.VITE_API_BASE_URL
  ? `${import.meta.env.VITE_API_BASE_URL}/api/v1`
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
    return response
  },
  async (error: AxiosError<ApiError>) => {
    if (error.response) {
      const { status, data } = error.response

      // Handle 401 - Unauthorized with retry logic
      if (status === 401) {
        const token = localStorage.getItem('access_token')

        // If no token, redirect immediately
        if (!token) {
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          window.location.href = '/login'
          return Promise.reject(error)
        }

        // Check if token is really expired or if it's a temporary issue
        try {
          // Try to decode the token to check expiration
          const tokenParts = token.split('.')
          if (tokenParts.length === 3) {
            const payload = JSON.parse(atob(tokenParts[1]))
            const currentTime = Date.now() / 1000

            // If token is expired by more than 5 minutes, redirect
            if (payload.exp && (currentTime - payload.exp) > 300) {
              localStorage.removeItem('access_token')
              localStorage.removeItem('user')
              window.location.href = '/login'
              return Promise.reject(error)
            }

            // If token is still valid or recently expired, try refreshing user data
            // This handles edge cases where the token is valid but server rejects it
            console.warn('Token validation issue, attempting to refresh user data')

            // Try one more request to /auth/me to verify the token
            try {
              await http.get('/auth/me')
              // If successful, the token is actually valid, return original error
              return Promise.reject(error)
            } catch (refreshError) {
              // If refresh also fails, clear storage and redirect
              localStorage.removeItem('access_token')
              localStorage.removeItem('user')
              window.location.href = '/login'
              return Promise.reject(error)
            }
          } else {
            // Malformed token, redirect immediately
            localStorage.removeItem('access_token')
            localStorage.removeItem('user')
            window.location.href = '/login'
            return Promise.reject(error)
          }
        } catch (decodeError) {
          // Error decoding token, redirect immediately
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
          window.location.href = '/login'
          return Promise.reject(error)
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
