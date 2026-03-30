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
  last_login: string | null
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
  is_superuser?: boolean
  organization_id?: string
}

// Organization types
export interface Organization extends BaseModel {
  name: string
  slug: string
  domain: string | null
  description: string | null
  owner_id: string
  settings: Record<string, unknown>
}

export interface OrganizationCreate {
  name: string
  slug?: string
  domain?: string
  description?: string
}

export interface OrganizationUpdate {
  name?: string
  slug?: string
  domain?: string
  description?: string
}

// Target types (mirrors backend enums/target.py)
export type TargetType = 'docker' | 'docker_swarm' | 'kubernetes' | 'ssh' | 'vm' | 'physical'
export type TargetStatus = 'online' | 'offline' | 'error' | 'maintenance'
export type SSHAuthMethod = 'local' | 'password' | 'ssh_key'

// SSH Credentials
export interface SSHCredentials {
  auth_method: SSHAuthMethod
  username?: string
  password?: string
  ssh_private_key?: string
  ssh_private_key_passphrase?: string
  sudo_user?: string
  sudo_password?: string
}

export interface SSHCredentialsUpdate {
  auth_method?: SSHAuthMethod
  username?: string
  password?: string
  ssh_private_key?: string
  ssh_private_key_passphrase?: string
  sudo_user?: string
  sudo_password?: string
}

export interface ConnectionTestRequest {
  host: string
  port: number
  credentials: SSHCredentials
}

export interface ConnectionTestResponse {
  success: boolean
  message: string
  os_info?: Record<string, unknown>
}

// Target Capability types (mirrors backend enums/target.py CapabilityType)
export type CapabilityType =
  | 'docker'
  | 'docker_compose'
  | 'docker_swarm'
  | 'kubernetes'
  | 'libvirt'
  | 'virtualbox'
  | 'vagrant'
  | 'proxmox'
  | 'qemu_kvm'
  | 'podman'
  | 'kubectl'
  | 'kubeadm'
  | 'k3s'
  | 'microk8s'
  | 'helm'
  | 'lxc'
  | 'lxd'
  | 'incus'
  | 'containerd'
  | 'runc'
  | 'crun'
  | 'buildah'
  | 'skopeo'
  | 'podman_compose'
  | 'virsh'
  | 'multipass'

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
  auth_method: string | null
  username: string | null
  has_sudo: boolean
  scan_date: string | null
  scan_success: boolean | null
  platform_info: Record<string, unknown> | null
  os_info: Record<string, unknown> | null
  extra_metadata: Record<string, unknown>
  organization_id: string
  capabilities?: TargetCapability[]
}

export interface TargetCreate {
  name: string
  type: TargetType
  host: string
  port: number
  description?: string
  credentials: SSHCredentials
  organization_id: string
  extra_metadata?: Record<string, unknown>
}

export interface TargetUpdate {
  name?: string
  type?: TargetType
  host?: string
  port?: number
  description?: string
  credentials?: SSHCredentialsUpdate
  status?: TargetStatus
  extra_metadata?: Record<string, unknown>
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
  name: string | null
  stack_id: string
  target_id: string
  status: DeploymentStatus
  config: Record<string, unknown>
  container_id: string | null
  variables: Record<string, unknown>
  logs: string | null
  error_message: string | null
  metadata: Record<string, unknown>
  organization_id: string
  deployed_at: string | null
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
  skip: number
  limit: number
}

// Scheduled Task types
export type TaskType = 'cleanup_logs' | 'health_check' | 'git_sync' | 'retry_deployments' | 'custom'

export interface ScheduledTask extends BaseModel {
  name: string
  description: string | null
  task_type: TaskType
  cron_expression: string
  parameters: Record<string, unknown>
  enabled: boolean
  last_run: string | null
  last_status: string | null
  last_error: string | null
  run_count: number
  organization_id: string
}

export interface ScheduledTaskCreate {
  name: string
  description?: string
  task_type: TaskType
  cron_expression: string
  parameters?: Record<string, unknown>
  enabled?: boolean
  organization_id: string
}

export interface ScheduledTaskUpdate {
  name?: string
  description?: string
  cron_expression?: string
  parameters?: Record<string, unknown>
  enabled?: boolean
}

export interface ApiError {
  detail: string
  status_code: number
}

// Dashboard types
export type AlertSeverity = 'critical' | 'warning' | 'info'

export interface AlertItem {
  id: string
  severity: AlertSeverity
  title: string
  message: string
  source: string
  timestamp: string
  acknowledged: boolean
}

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

export interface ResourceCounter {
  total: number
  running: number
  stopped: number
}

export interface DeploymentMetrics {
  total: number
  success: number
  failed: number
  running: number
  success_rate: number
}

export interface ResourceMetricPoint {
  timestamp: string
  cpu: number
  memory: number
}

export interface ResourceMetrics {
  current_cpu: number
  current_memory: number
  total_memory_mb: number
  used_memory_mb: number
  current_disk: number
  total_disk_gb: number
  used_disk_gb: number
  uptime_seconds: number
  history: ResourceMetricPoint[]
}

export interface DashboardStats {
  // Legacy counters (conservés pour compatibilité)
  total_targets: number
  online_targets: number
  total_stacks: number
  active_deployments: number
  total_workflows: number
  // Resource counters (STORY-432)
  containers: ResourceCounter
  vms: ResourceCounter
  stacks: ResourceCounter
  vms_available: boolean
  target_health: Record<string, number>
  targets_detail: TargetHealthItem[]
  deployment_metrics: DeploymentMetrics
  resource_metrics: ResourceMetrics
  recent_activity: ActivityFeedItem[]
  alerts: AlertItem[]
}

export interface StackVersion {
  id: string
  stack_id: string
  version_number: number
  compose_content: string
  variables: Record<string, unknown>
  change_summary: string | null
  created_by: string | null
  author_name: string | null
  created_at: string
}

// Docker Container types
export type ContainerState = 'running' | 'exited' | 'paused' | 'restarting' | 'created' | 'dead'

export interface ContainerPort {
  IP?: string
  PrivatePort?: number
  PublicPort?: number
  Type?: string
}

export interface Container {
  id: string
  name: string
  image: string
  imageId: string
  command: string
  created: string
  state: ContainerState
  status: string
  ports: ContainerPort[]
  labels: Record<string, string>
  networks: string[]
  mounts: Record<string, unknown>[]
  restart_count: number
}

export interface ContainerLogsResponse {
  logs: string
  container_id: string
  timestamp: string
}

// Docker Container Detail types (for inspect)
export interface ContainerDetail {
  id: string
  name: string
  created: string
  path: string
  args: string[]
  state: Record<string, unknown>
  image: string
  config: Record<string, unknown>
  host_config: Record<string, unknown>
  network_settings: Record<string, unknown>
  mounts: Record<string, unknown>[]
}

export interface ContainerEnvVar {
  key: string
  value: string
  isSecret: boolean
}

export interface ContainerPortMapping {
  hostIp: string
  hostPort: string
  containerPort: string
  protocol: string
}

export interface ContainerMount {
  type: string
  source: string
  destination: string
  mode: string
  name?: string
}

export interface ContainerNetworkInfo {
  networkId: string
  networkName: string
  ipAddress: string
  macAddress: string
  gateway: string
}

// Container Process types
export interface ContainerProcess {
  pid: number
  user: string
  cpu: number
  mem: number
  time: string
  command: string
}

export interface ContainerProcessListResponse {
  container_id: string
  titles: string[]
  processes: ContainerProcess[]
  timestamp: string
}

// Compute types (STORY-021)
export type ControlLevel = 'managed' | 'discovered' | 'standalone'

export type ComputeTechnology = 'docker' | 'compose' | 'helm' | 'kvm' | 'proxmox' | 'lxc'

export interface ServiceWithMetrics {
  id: string
  name: string
  image: string
  status: string
  cpu_percent: number
  memory_usage: string
  memory_limit?: string
  uptime?: string | null
  ports?: StandaloneContainerPortMapping[]
  health_status?: string | null
}

export interface StackWithServices {
  id: string
  name: string
  technology: ComputeTechnology
  target_id: string
  target_name: string
  services_total: number
  services_running: number
  status: 'running' | 'partial' | 'stopped' | 'archived'
  services: ServiceWithMetrics[]
}

export interface StandaloneContainerPortMapping {
  host_ip: string
  host_port: number
  container_port: number
  protocol: string
}

export interface StandaloneContainer {
  id: string
  name: string
  image: string
  target_id: string
  target_name: string
  status: string
  cpu_percent: number
  memory_usage: string
  uptime: string | null
  ports: StandaloneContainerPortMapping[]
  health_status: string | null
}

export interface DiscoveredItem {
  id: string
  name: string
  type: 'container' | 'composition' | 'helm_release'
  technology: ComputeTechnology
  source_path?: string
  target_id: string
  target_name: string
  services_total: number
  services_running: number
  detected_at: string
  adoptable: boolean
  services?: ServiceWithMetrics[]
}

export interface ComputeGlobalView {
  managed_stacks: StackWithServices[]
  discovered_items: DiscoveredItem[]
  standalone_containers: StandaloneContainer[]
}

export interface TargetMetrics {
  cpu_total_percent: number
  memory_used: string
  memory_total: string
}

export interface TargetGroup {
  target_id: string
  target_name: string
  technology: string
  stacks: StackWithServices[]
  discovered: DiscoveredItem[]
  standalone: StandaloneContainer[]
  metrics: TargetMetrics
}

export interface ComputeStatsResponse {
  total_containers: number
  running_containers: number
  stacks_count: number
  stacks_running_count: number
  stacks_targets_count: number
  stacks_services_count: number
  discovered_count: number
  discovered_targets_count: number
  standalone_count: number
  standalone_targets_count: number
  targets_count: number
}

// Discovery / Adoption types (STORY-003)
export type VolumeStrategy = 'keep_existing' | 'create_named' | 'bind_mount'
export type NetworkStrategy = 'keep_existing' | 'create_new'

export interface AdoptionEnvVar {
  key: string
  value: string
  is_secret: boolean
}

export interface AdoptionVolume {
  source?: string | null
  destination: string
  mode: string
  type: string
}

export interface AdoptionNetwork {
  name: string
  driver: string
  is_default: boolean
}

export interface AdoptionPortMapping {
  host_ip: string
  host_port: number
  container_port: number
  protocol: string
}

export interface AdoptionServiceData {
  name: string
  image: string
  status: string
  env_vars: AdoptionEnvVar[]
  volumes: AdoptionVolume[]
  networks: AdoptionNetwork[]
  ports: AdoptionPortMapping[]
  cpu_percent: number
  memory_usage: string
}

export interface AdoptionWizardData {
  discovered_id: string
  name: string
  type: 'container' | 'composition' | 'helm_release'
  technology: string
  target_id: string
  target_name: string
  services: AdoptionServiceData[]
  generated_compose: string | null
  volumes_strategy_options: string[]
  networks_strategy_options: string[]
}

export interface HelmOptions {
  namespace: string
  release_name: string
  values_overrides: Record<string, unknown>
}

export interface AdoptionRequest {
  discovered_id: string
  type: 'container' | 'composition' | 'helm_release'
  stack_name: string
  volume_strategy: VolumeStrategy
  network_strategy: NetworkStrategy
  target_id?: string | null
  helm_options?: HelmOptions | null
  compose_content?: string | null
}

export interface AdoptionResponse {
  success: boolean
  stack_id?: string | null
  stack_name?: string | null
  deployment_id?: string | null
  message: string
}
