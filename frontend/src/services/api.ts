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
  StackVersion,
  Deployment,
  DeploymentCreate,
  DeploymentLogsResponse,
  Workflow,
  WorkflowCreate,
  PaginatedResponse,
  DashboardStats,
  ScheduledTask,
  ScheduledTaskCreate,
  ScheduledTaskUpdate,
  Container,
  ContainerLogsResponse,
  ContainerDetail,
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

  bulkDelete: (userIds: string[]) =>
    http.post<{ success: string[]; failed: string[]; message: string }>('/users/bulk/delete', { user_ids: userIds }),

  bulkAssignOrganization: (userIds: string[], organizationId: string) =>
    http.post<{ success: string[]; failed: string[]; message: string }>('/users/bulk/assign-organization', {
      user_ids: userIds,
      organization_id: organizationId,
    }),
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

  bulkDelete: (organizationIds: string[]) =>
    http.post<{ success: string[]; failed: string[]; message: string }>('/organizations/bulk/delete', { organization_ids: organizationIds }),
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

  regenerateVariable: (stackId: string, variableName: string) =>
    http.post<{ variable_name: string; new_value: unknown; macro_template: string }>(
      `/stacks/${stackId}/regenerate-variable/${variableName}`
    ),

  listVersions: (stackId: string) =>
    http.get<StackVersion[]>(`/stacks/${stackId}/versions`),

  createVersion: (stackId: string, data: { change_summary?: string }) =>
    http.post<StackVersion>(`/stacks/${stackId}/versions`, data),

  restoreVersion: (stackId: string, versionId: string) =>
    http.post<Stack>(`/stacks/${stackId}/versions/${versionId}/restore`),
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
    http.get<DeploymentLogsResponse>(`/deployments/${id}/logs`),

  retry: (id: string) =>
    http.post<Deployment>(`/deployments/${id}/retry`),

  delete: (id: string) =>
    http.delete(`/deployments/${id}`),
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

// Dashboard API
export const schedulesApi = {
  list: (organizationId?: string) => {
    const params = organizationId ? { organization_id: organizationId } : {}
    return http.get<ScheduledTask[]>('/schedules', { params })
  },
  get: (id: string) => http.get<ScheduledTask>(`/schedules/${id}`),
  create: (data: ScheduledTaskCreate) => http.post<ScheduledTask>('/schedules', data),
  update: (id: string, data: ScheduledTaskUpdate) => http.put<ScheduledTask>(`/schedules/${id}`, data),
  delete: (id: string) => http.delete(`/schedules/${id}`),
  toggle: (id: string) => http.post<ScheduledTask>(`/schedules/${id}/toggle`),
}

export const dashboardApi = {
  getStats: (organizationId?: string) => {
    const params = organizationId ? { organization_id: organizationId } : {}
    return http.get<DashboardStats>('/stats/dashboard', { params })
  },
}

// Docker Containers API
export const containersApi = {
  list: (all: boolean = true) =>
    http.get<Container[]>('/docker/containers', { params: { all } }),

  get: (id: string) =>
    http.get<Container>(`/docker/containers/${id}`),

  inspect: (id: string) =>
    http.get<ContainerDetail>(`/docker/containers/${id}`),

  start: (id: string) =>
    http.post<void>(`/docker/containers/${id}/start`),

  stop: (id: string, timeout: number = 10) =>
    http.post<void>(`/docker/containers/${id}/stop`, null, { params: { timeout } }),

  restart: (id: string, timeout: number = 10) =>
    http.post<void>(`/docker/containers/${id}/restart`, null, { params: { timeout } }),

  remove: (id: string, force: boolean = false) =>
    http.delete<void>(`/docker/containers/${id}`, { params: { force } }),

  getLogs: (id: string, tail: number = 100, timestamps: boolean = false) =>
    http.get<ContainerLogsResponse>(`/docker/containers/${id}/logs`, { params: { tail, timestamps } }),
}

export default {
  auth: authApi,
  users: usersApi,
  organizations: organizationsApi,
  targets: targetsApi,
  stacks: stacksApi,
  deployments: deploymentsApi,
  workflows: workflowsApi,
  dashboard: dashboardApi,
  schedules: schedulesApi,
  containers: containersApi,
}
