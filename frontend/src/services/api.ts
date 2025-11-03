/**
 * API Service Layer
 * CRUD operations for all entities
 */

import http from './http'
import type {
  LoginRequest,
  LoginResponse,
  User,
  UserCreate,
  UserUpdate,
  Organization,
  OrganizationCreate,
  OrganizationUpdate,
  Target,
  TargetCreate,
  TargetUpdate,
  TargetCapabilitiesResponse,
  Stack,
  StackCreate,
  StackUpdate,
  Deployment,
  DeploymentCreate,
  Workflow,
  WorkflowCreate,
  Template,
  PaginatedResponse,
} from '@/types/api'

// Auth API
export const authApi = {
  login: (data: LoginRequest) => {
    // OAuth2PasswordRequestForm expects form-data, not JSON
    const formData = new URLSearchParams()
    formData.append('username', data.username)
    formData.append('password', data.password)

    return http.post<LoginResponse>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    })
  },

  refreshToken: (refreshToken: string) =>
    http.post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken }),

  register: (data: UserCreate) =>
    http.post<User>('/auth/register', data),

  getCurrentUser: () =>
    http.get<User>('/auth/me'),

  logout: () =>
    http.post('/auth/logout'),
}

// Users API
export const usersApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    http.get<PaginatedResponse<User>>('/users', { params }),

  get: (id: string) =>
    http.get<User>(`/users/${id}`),

  create: (data: UserCreate) =>
    http.post<User>('/users', data),

  update: (id: string, data: UserUpdate) =>
    http.put<User>(`/users/${id}`, data),

  delete: (id: string) =>
    http.delete(`/users/${id}`),
}

// Organizations API
export const organizationsApi = {
  list: (params?: { skip?: number; limit?: number }) =>
    http.get<PaginatedResponse<Organization>>('/organizations', { params }),

  get: (id: string) =>
    http.get<Organization>(`/organizations/${id}`),

  create: (data: OrganizationCreate) =>
    http.post<Organization>('/organizations', data),

  update: (id: string, data: OrganizationUpdate) =>
    http.put<Organization>(`/organizations/${id}`, data),

  delete: (id: string) =>
    http.delete(`/organizations/${id}`),
}

// Targets API
export const targetsApi = {
  list: (params?: { skip?: number; limit?: number; organization_id?: string }) =>
    http.get<PaginatedResponse<Target>>('/targets', { params }),

  get: (id: string) =>
    http.get<Target>(`/targets/${id}`),

  create: (data: TargetCreate) =>
    http.post<Target>('/targets', data),

  update: (id: string, data: TargetUpdate) =>
    http.put<Target>(`/targets/${id}`, data),

  delete: (id: string) =>
    http.delete(`/targets/${id}`),

  scan: (id: string) =>
    http.post<Target>(`/targets/${id}/scan`),

  getCapabilities: (id: string) =>
    http.get<TargetCapabilitiesResponse>(`/targets/${id}/capabilities`),
}

// Stacks API
export const stacksApi = {
  list: (params?: { skip?: number; limit?: number; organization_id?: string }) =>
    http.get<PaginatedResponse<Stack>>('/stacks', { params }),

  get: (id: string) =>
    http.get<Stack>(`/stacks/${id}`),

  create: (data: StackCreate) =>
    http.post<Stack>('/stacks', data),

  update: (id: string, data: StackUpdate) =>
    http.put<Stack>(`/stacks/${id}`, data),

  delete: (id: string) =>
    http.delete(`/stacks/${id}`),

  validate: (data: { compose_content: string }) =>
    http.post<{ valid: boolean; errors: string[] }>('/stacks/validate', data),
}

// Deployments API
export const deploymentsApi = {
  list: (params?: { skip?: number; limit?: number; organization_id?: string }) =>
    http.get<PaginatedResponse<Deployment>>('/deployments/', { params }),

  get: (id: string) =>
    http.get<Deployment>(`/deployments/${id}`),

  create: (data: DeploymentCreate) =>
    http.post<Deployment>('/deployments/', data),

  cancel: (id: string) =>
    http.post<Deployment>(`/deployments/${id}/cancel`),

  getLogs: (id: string) =>
    http.get<{ logs: string }>(`/deployments/${id}/logs`),

  retry: (id: string) =>
    http.post<Deployment>(`/deployments/${id}/retry`),
}

// Workflows API
export const workflowsApi = {
  list: (params?: { skip?: number; limit?: number; organization_id?: string }) =>
    http.get<PaginatedResponse<Workflow>>('/workflows', { params }),

  get: (id: string) =>
    http.get<Workflow>(`/workflows/${id}`),

  create: (data: WorkflowCreate) =>
    http.post<Workflow>('/workflows', data),

  update: (id: string, data: Partial<WorkflowCreate>) =>
    http.put<Workflow>(`/workflows/${id}`, data),

  delete: (id: string) =>
    http.delete(`/workflows/${id}`),

  execute: (id: string, params?: Record<string, unknown>) =>
    http.post<{ execution_id: string }>(`/workflows/${id}/execute`, params),
}

// Templates/Marketplace API
export const templatesApi = {
  list: (params?: {
    skip?: number
    limit?: number
    category?: string
    tags?: string[]
    search?: string
  }) =>
    http.get<PaginatedResponse<Template>>('/templates', { params }),

  get: (id: string) =>
    http.get<Template>(`/templates/${id}`),

  download: (id: string) =>
    http.post<{ stack_id: string }>(`/templates/${id}/download`),

  rate: (id: string, rating: number) =>
    http.post(`/templates/${id}/rate`, { rating }),

  categories: () =>
    http.get<string[]>('/templates/categories'),

  popular: (limit?: number) =>
    http.get<Template[]>('/templates/popular', { params: { limit } }),
}

export default {
  auth: authApi,
  users: usersApi,
  organizations: organizationsApi,
  targets: targetsApi,
  stacks: stacksApi,
  deployments: deploymentsApi,
  workflows: workflowsApi,
  templates: templatesApi,
}
