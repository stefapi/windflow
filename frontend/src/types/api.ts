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
export type TargetType = 'docker_compose' | 'docker_swarm' | 'kubernetes' | 'vm'
export type TargetStatus = 'active' | 'inactive' | 'error' | 'maintenance'

export interface Target extends BaseModel {
  name: string
  type: TargetType
  host: string
  port: number
  description: string | null
  status: TargetStatus
  metadata: Record<string, unknown>
  organization_id: string
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
