/**
 * HTTP Client Configuration
 * Axios instance with interceptors for authentication and error handling
 */

import axios, { type AxiosInstance, type AxiosError, type InternalAxiosRequestConfig } from 'axios'
import type { ApiError } from '@/types/api'

// Create axios instance
const http: AxiosInstance = axios.create({
  baseURL: '/api/v1',
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
  (error: AxiosError<ApiError>) => {
    if (error.response) {
      const { status, data } = error.response

      // Handle 401 - Unauthorized
      if (status === 401) {
        localStorage.removeItem('access_token')
        localStorage.removeItem('user')
        window.location.href = '/login'
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

export default http
