/**
 * API Type Definitions
 * Mirrors backend schemas for type safety
 */

// Base types
export interface BaseModel {
  id: string
  created_at: string
  updated_at: string
}

// User types
export interface User extends BaseModel {
  email: string
  username: string
  full_name: string | null
  is_active: boolean
  is_superuser: boolean
  organization_id: string | null
}

export interface UserCreate {
  email: string
  username: string
  password: string
  full_name?: string
  organization_id?: string
}

export interface UserUpdate {
  email?: string
  username?: string
  full_name?: string
  password?: string
  is_active?: boolean
}

// Organization types
export interface Organization extends BaseModel {
  name: string
  description: string | null
  owner_id: string
}

export interface OrganizationCreate {
  name: string
  description?: string
}

export interface OrganizationUpdate {
  name?: string
  description?: string
}

// Target types
export type TargetType = 'docker' | 'docker_swarm' | 'kubernetes' | 'vm' | 'physical'
export type TargetStatus = 'online' | 'offline' | 'error' | 'maintenance'

// Target Capability types
export type CapabilityType =
  | 'libvirt'
  | 'virtualbox'
  | 'vagrant'
  | 'proxmox'
  | 'qemu_kvm'
  | 'docker'
  | 'docker_compose'
  | 'docker_swarm'
  | 'podman'
  | 'kubectl'
  | 'kubeadm'
  | 'k3s'
  | 'microk8s'

export interface TargetCapability extends BaseModel {
  target_id: string
  capability_type: CapabilityType
  is_available: boolean
  version: string | null
  details: Record<string, unknown> | null
  detected_at: string
}

export interface TargetCapabilitiesResponse {
  scan_date: string | null
  scan_success: boolean | null
  platform_info: Record<string, unknown> | null
  os_info: Record<string, unknown> | null
  capabilities: TargetCapability[]
}

export interface Target extends BaseModel {
  name: string
  type: TargetType
  host: string
  port: number
  description: string | null
  status: TargetStatus
  metadata: Record<string, unknown>
  organization_id: string
  capabilities?: TargetCapability[]
}

export interface TargetCreate {
  name: string
  type: TargetType
  host: string
  port: number
  description?: string
  metadata?: Record<string, unknown>
  organization_id: string
}

export interface TargetUpdate {
  name?: string
  type?: TargetType
  host?: string
  port?: number
  description?: string
  status?: TargetStatus
  metadata?: Record<string, unknown>
}

// Stack types
export interface Stack extends BaseModel {
  name: string
  description: string | null
  compose_content: string
  metadata: Record<string, unknown>
  organization_id: string
  default_name?: string
}

export interface StackCreate {
  name: string
  description?: string
  compose_content: string
  metadata?: Record<string, unknown>
  organization_id: string
}

export interface StackUpdate {
  name?: string
  description?: string
  compose_content?: string
  metadata?: Record<string, unknown>
}

// Deployment types
export type DeploymentStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

export interface Deployment extends BaseModel {
  stack_id: string
  target_id: string
  status: DeploymentStatus
  logs: string | null
  metadata: Record<string, unknown>
  organization_id: string
  stack?: Stack
  target?: Target
}

export interface DeploymentCreate {
  stack_id: string
  target_id: string
  metadata?: Record<string, unknown>
}

export interface DeploymentLogsResponse {
  deployment_id: string
  logs: string | null
  updated_at: string
}

// Workflow types
export interface WorkflowNode {
  id: string
  type: string
  position: { x: number; y: number }
  data: Record<string, unknown>
}

export interface WorkflowEdge {
  id: string
  source: string
  target: string
  type?: string
}

export interface Workflow extends BaseModel {
  name: string
  description: string | null
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  metadata: Record<string, unknown>
  organization_id: string
}

export interface WorkflowCreate {
  name: string
  description?: string
  nodes: WorkflowNode[]
  edges: WorkflowEdge[]
  metadata?: Record<string, unknown>
  organization_id: string
}

// Template types
export interface Template extends BaseModel {
  name: string
  description: string | null
  category: string
  tags: string[]
  compose_content: string
  rating: number
  downloads: number
  author: string
  metadata: Record<string, unknown>
}

// Auth types
export interface LoginRequest {
  username: string
  password: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface RefreshTokenRequest {
  refresh_token: string
}

export interface RefreshTokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

// API Response types
export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  pages: number
}

export interface ApiError {
  detail: string
  status_code: number
}

// Dashboard types
export interface TargetHealthItem {
  id: string
  name: string
  status: string
  host: string
  last_check: string | null
}

export interface ActivityFeedItem {
  id: string
  type: string
  title: string
  status: string
  timestamp: string
  details: string | null
}

export interface DeploymentMetrics {
  total: number
  success: number
  failed: number
  running: number
  success_rate: number
}

export interface DashboardStats {
  total_targets: number
  online_targets: number
  total_stacks: number
  active_deployments: number
  total_workflows: number
  target_health: Record<string, number>
  targets_detail: TargetHealthItem[]
  deployment_metrics: DeploymentMetrics
  recent_activity: ActivityFeedItem[]
}
