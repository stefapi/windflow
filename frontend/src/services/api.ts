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
  Host,
  HostCreate,
  HostUpdate,
  HostCapabilitiesResponse,
  HealthCheckResponse,
  ConnectionTestRequest,
  ConnectionTestResponse,
  HostReachabilityRequest,
  HostReachabilityResponse,
  Stack,
  StackCreate,
  StackUpdate,
  StackVersion,
  Deployment,
  DeploymentCreate,
  DeploymentLogsResponse,
  Workflow,
  WorkflowCreate,
  DashboardStats,
  StackStatsResponse,
  ScheduledTask,
  ScheduledTaskCreate,
  ScheduledTaskUpdate,
  Container,
  ContainerLogsResponse,
  ContainerDetail,
  ControlLevel,
  ComputeStatsResponse,
  ComputeGlobalView,
  TargetGroup,
  AdoptionWizardData,
  AdoptionRequest,
  AdoptionResponse,
  BatchContainerActionResponse,
  StackActionResponse,
  StackDuplicateRequest,
  StackRedeployRequest,
  StackRedeployResponse,
  ContainerUpdateRestartPolicyRequest,
  ContainerUpdateResourcesRequest,
  ContainerUpdateResponse,
  ContainerRenameRequest,
  ContainerRenameResponse,
  ContainerPromoteRequest,
  ContainerPromoteResponse,
  ContainerCreateRequest,
  ContainerRecreateRequest,
  ContainerRecreateResponse,
  ContainerNetworkConnectRequest,
  ContainerNetworkDisconnectRequest,
  VolumeResponse,
  VolumeCreateRequest,
  ImageResponse,
  ImagePullRequest,
  ImagePullResponse,
  ImageDetailResponse,
  StackImportResponse,
  NetworkResponse,
  ContainerShell,
  SystemInfoResponse,
  SystemVersionResponse,
  PingResponse,
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

  refreshToken: (refreshToken: string) => http.post<LoginResponse>('/auth/refresh', { refresh_token: refreshToken }),

  register: (data: UserCreate) => http.post<User>('/auth/register', data),

  getCurrentUser: () => http.get<User>('/users/me'), // STORY-250.2 : /auth/me déprécié

  logout: () => http.post('/auth/logout'),
}

// Users API — STORY-128 : listes paginées `?page=&per_page=`, post-unwrap
// `response.data` est la liste et `response.pagination` porte les métadonnées.
export const usersApi = {
  list: (params?: { page?: number; per_page?: number }) => http.get<User[]>('/users', { params }),

  get: (id: string) => http.get<User>(`/users/${id}`),

  create: (data: UserCreate) => http.post<User>('/users', data),

  update: (id: string, data: UserUpdate) => http.put<User>(`/users/${id}`, data),

  delete: (id: string) => http.delete(`/users/${id}`),

  bulkDelete: (userIds: string[]) => http.post<{ success: string[]; failed: string[]; message: string }>('/users/bulk/delete', { user_ids: userIds }),

  bulkAssignOrganization: (userIds: string[], organizationId: string) =>
    http.post<{ success: string[]; failed: string[]; message: string }>('/users/bulk/assign-organization', {
      user_ids: userIds,
      organization_id: organizationId,
    }),
}

// Organizations API — STORY-128 : pagination standard spec 09.
export const organizationsApi = {
  list: (params?: { page?: number; per_page?: number }) => http.get<Organization[]>('/organizations', { params }),

  get: (id: string) => http.get<Organization>(`/organizations/${id}`),

  create: (data: OrganizationCreate) => http.post<Organization>('/organizations', data),

  update: (id: string, data: OrganizationUpdate) => http.put<Organization>(`/organizations/${id}`, data),

  delete: (id: string) => http.delete(`/organizations/${id}`),

  bulkDelete: (organizationIds: string[]) => http.post<{ success: string[]; failed: string[]; message: string }>('/organizations/bulk/delete', { organization_ids: organizationIds }),
}

// Hosts API (STORY-166.6 — surface canonique /api/v1/hosts, STORY-128 : pagination standard spec 09)
export const hostsApi = {
  list: (params?: { page?: number; per_page?: number; organization_id?: string }) => http.get<Host[]>('/hosts', { params }),

  get: (id: string) => http.get<Host>(`/hosts/${id}`),

  create: (data: HostCreate) => http.post<Host>('/hosts', data),

  update: (id: string, data: HostUpdate) => http.put<Host>(`/hosts/${id}`, data),

  delete: (id: string) => http.delete(`/hosts/${id}`),

  scan: (id: string) => http.post<Host>(`/hosts/${id}/scan`),

  getCapabilities: (id: string) => http.get<HostCapabilitiesResponse>(`/hosts/${id}/capabilities`),

  testReachability: (data: HostReachabilityRequest) => http.post<HostReachabilityResponse>('/hosts/test-reachability', data),
  testConnection: (data: ConnectionTestRequest) => http.post<ConnectionTestResponse>('/hosts/test-connection', data),

  /** Perform a lightweight TCP health check on a host */
  healthCheck: (id: string) => http.post<HealthCheckResponse>(`/hosts/${id}/health-check`),
}

// Stacks API — STORY-128 : pagination standard spec 09.
export const stacksApi = {
  list: (params?: { page?: number; per_page?: number; include_archived?: boolean; organization_id?: string }) => http.get<Stack[]>('/stacks', { params }),

  get: (id: string) => http.get<Stack>(`/stacks/${id}`),

  create: (data: StackCreate) => http.post<Stack>('/stacks', data),

  update: (id: string, data: StackUpdate) => http.put<Stack>(`/stacks/${id}`, data),

  delete: (id: string) => http.delete(`/stacks/${id}`),

  validate: (data: { compose_content: string }) => http.post<{ valid: boolean; errors: string[] }>('/stacks/validate', data),

  regenerateVariable: (stackId: string, variableName: string) => http.post<{ variable_name: string; new_value: unknown; macro_template: string }>(`/stacks/${stackId}/regenerate-variable/${variableName}`),

  listVersions: (stackId: string) => http.get<StackVersion[]>(`/stacks/${stackId}/versions`),

  createVersion: (stackId: string, data: { change_summary?: string }) => http.post<StackVersion>(`/stacks/${stackId}/versions`, data),

  restoreVersion: (stackId: string, versionId: string) => http.post<Stack>(`/stacks/${stackId}/versions/${versionId}/restore`),

  start: (id: string) => http.post<StackActionResponse>(`/stacks/${id}/start`),

  stop: (id: string) => http.post<StackActionResponse>(`/stacks/${id}/stop`),

  redeploy: (id: string, data: StackRedeployRequest) => http.post<StackRedeployResponse>(`/stacks/${id}/redeploy`, data),

  duplicate: (id: string, data: StackDuplicateRequest) => http.post<Stack>(`/stacks/${id}/duplicate`, data),

  archive: (id: string) => http.post<StackActionResponse>(`/stacks/${id}/archive`),

  unarchive: (id: string) => http.post<StackActionResponse>(`/stacks/${id}/unarchive`),

  export: (id: string) => http.get<Record<string, unknown>>(`/stacks/${id}/export`),

  import: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.post<StackImportResponse>('/stacks/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },
}

// Deployments API — STORY-128 : pagination standard spec 09.
export const deploymentsApi = {
  list: (params?: { page?: number; per_page?: number; organization_id?: string }) => http.get<Deployment[]>('/deployments/', { params }),

  get: (id: string) => http.get<Deployment>(`/deployments/${id}`),

  create: (data: DeploymentCreate) => http.post<Deployment>('/deployments/', data),

  cancel: (id: string) => http.post<Deployment>(`/deployments/${id}/cancel`),

  getLogs: (id: string) => http.get<DeploymentLogsResponse>(`/deployments/${id}/logs`),

  retry: (id: string) => http.post<Deployment>(`/deployments/${id}/retry`),

  delete: (id: string) => http.delete(`/deployments/${id}`),
}

// Workflows API — STORY-128 : pagination standard spec 09 (stub backend vide).
export const workflowsApi = {
  list: (params?: { page?: number; per_page?: number; organization_id?: string }) => http.get<Workflow[]>('/workflows', { params }),

  get: (id: string) => http.get<Workflow>(`/workflows/${id}`),

  create: (data: WorkflowCreate) => http.post<Workflow>('/workflows', data),

  update: (id: string, data: Partial<WorkflowCreate>) => http.put<Workflow>(`/workflows/${id}`, data),

  delete: (id: string) => http.delete(`/workflows/${id}`),

  execute: (id: string, params?: Record<string, unknown>) => http.post<{ execution_id: string }>(`/workflows/${id}/execute`, params),
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

  getStackStats: (stackId: string) => http.get<StackStatsResponse>(`/stats/stacks/${stackId}`),
}

// Docker Containers API
export const containersApi = {
  list: (all: boolean = true) => http.get<Container[]>('/docker/containers', { params: { all } }),

  get: (id: string) => http.get<Container>(`/docker/containers/${id}`),

  inspect: (id: string) => http.get<ContainerDetail>(`/docker/containers/${id}`),

  start: (id: string) => http.post<void>(`/docker/containers/${id}/start`),

  stop: (id: string, timeout: number = 10) => http.post<void>(`/docker/containers/${id}/stop`, null, { params: { timeout } }),

  restart: (id: string, timeout: number = 10) => http.post<void>(`/docker/containers/${id}/restart`, null, { params: { timeout } }),

  pause: (id: string) => http.post<void>(`/docker/containers/${id}/pause`),

  unpause: (id: string) => http.post<void>(`/docker/containers/${id}/unpause`),

  getStats: (id: string) => http.get(`/docker/containers/${id}/stats`),

  remove: (id: string, force: boolean = false) => http.delete<void>(`/docker/containers/${id}`, { params: { force } }),

  getLogs: (id: string, tail: number = 100, timestamps: boolean = false) => http.get<ContainerLogsResponse>(`/docker/containers/${id}/logs`, { params: { tail, timestamps } }),

  batchStart: (containerIds: string[]) => http.post<BatchContainerActionResponse>('/docker/containers/batch/start', { container_ids: containerIds }),

  batchStop: (containerIds: string[]) => http.post<BatchContainerActionResponse>('/docker/containers/batch/stop', { container_ids: containerIds }),

  updateRestartPolicy: (id: string, data: ContainerUpdateRestartPolicyRequest) => http.patch<ContainerUpdateResponse>(`/docker/containers/${id}/restart-policy`, data),

  updateResources: (id: string, data: ContainerUpdateResourcesRequest) => http.patch<ContainerUpdateResponse>(`/docker/containers/${id}/resources`, data),

  rename: (id: string, data: ContainerRenameRequest) => http.post<ContainerRenameResponse>(`/docker/containers/${id}/rename`, data),

  promote: (id: string, data: ContainerPromoteRequest) => http.post<ContainerPromoteResponse>(`/docker/containers/${id}/promote`, data),

  getShells: (id: string) => http.get<ContainerShell[]>(`/docker/containers/${id}/shells`),

  create: (data: ContainerCreateRequest) => http.post<ContainerDetail>('/docker/containers', data),

  recreate: (id: string, data: ContainerRecreateRequest) => http.post<ContainerRecreateResponse>(`/docker/containers/${id}/recreate`, data),

  connectNetwork: (id: string, data: ContainerNetworkConnectRequest) => http.post<void>(`/docker/containers/${id}/networks/connect`, data),

  disconnectNetwork: (id: string, data: ContainerNetworkDisconnectRequest) => http.post<void>(`/docker/containers/${id}/networks/disconnect`, data),
}

// Docker Images API
export const imagesApi = {
  list: (all: boolean = false) => http.get<ImageResponse[]>('/docker/images', { params: { all } }),

  pull: (data: ImagePullRequest) => http.post<ImagePullResponse>('/docker/images/pull', data),

  remove: (imageId: string, force: boolean = false) => http.delete<void>(`/docker/images/${imageId}`, { params: { force } }),

  get: (imageId: string) => http.get<ImageDetailResponse>(`/docker/images/${imageId}`),

  save: (imageId: string) => http.get<Blob>(`/docker/images/${imageId}/save`, { responseType: 'blob' }),

  load: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return http.post<{ success: boolean; message: string }>('/docker/images/load', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
  },

  batchRemove: (imageIds: string[], force: boolean = false) => Promise.all(imageIds.map((id) => http.delete<void>(`/docker/images/${id}`, { params: { force } }))),
}

// Docker Volumes API
export const volumesApi = {
  list: () => http.get<VolumeResponse[]>('/docker/volumes'),

  create: (data: VolumeCreateRequest) => http.post<VolumeResponse>('/docker/volumes', data),

  remove: (name: string, force?: boolean) => http.delete<void>(`/docker/volumes/${name}`, { params: { force } }),
}

// Docker Networks API
export const networksApi = {
  list: () => http.get<NetworkResponse[]>('/docker/networks'),
}

// Docker System API
export const dockerSystemApi = {
  info: () => http.get<SystemInfoResponse>('/docker/system/info'),
  version: () => http.get<SystemVersionResponse>('/docker/system/version'),
  ping: () => http.get<PingResponse>('/docker/system/ping'),
}

// Compute API
export const computeApi = {
  getStats: (organizationId?: string) =>
    http.get<ComputeStatsResponse>('/compute/stats', {
      params: organizationId ? { organization_id: organizationId } : {},
    }),

  // Retourne ComputeGlobalView quand group_by est absent ou 'stack'
  getGlobal: (params?: { type?: ControlLevel; technology?: string; target_id?: string; status?: string; search?: string; organization_id?: string }) => http.get<ComputeGlobalView>('/compute/global', { params }),

  // Retourne TargetGroup[] quand group_by='target'
  getGlobalByTarget: (params?: { type?: ControlLevel; technology?: string; target_id?: string; status?: string; search?: string; organization_id?: string }) =>
    http.get<TargetGroup[]>('/compute/global', {
      params: { ...params, group_by: 'target' },
    }),
}

// Discovery / Adoption API
export const discoveryApi = {
  getAdoptionData: (itemType: 'container' | 'composition' | 'helm_release', itemId: string, organizationId?: string) =>
    http.get<AdoptionWizardData>(`/discovery/${itemType}/${encodeURIComponent(itemId)}/adoption-data`, { params: organizationId ? { organization_id: organizationId } : {} }),

  adopt: (data: AdoptionRequest) => http.post<AdoptionResponse>('/discovery/adopt', data),
}

export default {
  auth: authApi,
  users: usersApi,
  organizations: organizationsApi,
  hosts: hostsApi,
  stacks: stacksApi,
  deployments: deploymentsApi,
  workflows: workflowsApi,
  dashboard: dashboardApi,
  schedules: schedulesApi,
  containers: containersApi,
  images: imagesApi,
  compute: computeApi,
  discovery: discoveryApi,
  volumes: volumesApi,
  networks: networksApi,
  dockerSystem: dockerSystemApi,
}
