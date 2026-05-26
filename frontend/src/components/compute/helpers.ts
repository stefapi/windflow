/**
 * Compute Helpers
 *
 * Shared types, normalization functions, and utility helpers
 * for the compute section components.
 */

import type {
  ServiceWithMetrics,
  StandaloneContainer,
  StandaloneContainerPortMapping,
  StackWithServices,
  DiscoveredItem,
} from '@/types/api'
import { getAppDisplayName, getAppStatus } from '@/composables/useAppVocabulary'

// ─── Types ────────────────────────────────────────────────────────────────────

/** Normalized row data for ContainerTable */
export interface ContainerTableRow {
  id: string
  name: string
  image: string
  status: string
  cpuPercent: number
  memoryUsage: string
  targetName?: string
  uptime?: string | null
  ports?: StandaloneContainerPortMapping[]
  healthStatus?: string | null
  link?: string
}

/** Union of column keys available in ContainerTable */
export type ColumnKey =
  | 'selection'
  | 'name'
  | 'image'
  | 'target'
  | 'status'
  | 'cpu'
  | 'memory'
  | 'uptime'
  | 'ports'
  | 'actions'

/** Default visible columns when none specified */
export const DEFAULT_COLUMNS: ColumnKey[] = ['name', 'image', 'status', 'cpu', 'memory', 'actions']

// ─── Normalization Functions ──────────────────────────────────────────────────

/**
 * Convert a ServiceWithMetrics (managed/discovered service) to a ContainerTableRow.
 */
export function serviceToRow(service: ServiceWithMetrics, targetName?: string): ContainerTableRow {
  return {
    id: service.id,
    name: service.name,
    image: service.image,
    status: service.status,
    cpuPercent: service.cpu_percent,
    memoryUsage: service.memory_usage,
    targetName,
    uptime: service.uptime ?? null,
    ports: service.ports ?? [],
    healthStatus: service.health_status ?? null,
    link: `/containers/${service.id}`,
  }
}

/**
 * Convert a StandaloneContainer to a ContainerTableRow.
 */
export function standaloneToRow(container: StandaloneContainer): ContainerTableRow {
  return {
    id: container.id,
    name: container.name,
    image: container.image,
    status: container.status,
    cpuPercent: container.cpu_percent,
    memoryUsage: container.memory_usage,
    targetName: container.target_name,
    uptime: container.uptime,
    ports: container.ports,
    healthStatus: container.health_status,
    link: `/containers/${container.id}`,
  }
}

// ─── Status Helpers ───────────────────────────────────────────────────────────

/**
 * Return a Tailwind CSS color class based on container status and health.
 * Supports all 6 Docker states: running, paused, exited, dead, created, restarting.
 */
export function getContainerStatusColor(status: string, healthStatus?: string | null): string {
  if (healthStatus === 'healthy') return 'text-green-500'
  if (healthStatus === 'unhealthy') return 'text-orange-500'
  switch (status) {
    case 'running': return 'text-green-500'
    case 'paused': return 'text-yellow-500'
    case 'exited': return 'text-red-400'
    case 'dead': return 'text-red-600'
    case 'created': return 'text-blue-400'
    case 'restarting': return 'text-orange-500'
    default: return 'text-gray-400'
  }
}

/**
 * Return an Element Plus tag type based on container status and health.
 * Supports all 6 Docker states: running, paused, exited, dead, created, restarting.
 */
export function getContainerStatusType(
  status: string,
  healthStatus?: string | null,
): 'success' | 'warning' | 'danger' | 'info' {
  if (healthStatus === 'healthy') return 'success'
  if (healthStatus === 'unhealthy') return 'warning'
  switch (status) {
    case 'running': return 'success'
    case 'paused': return 'warning'
    case 'exited': return 'danger'
    case 'dead': return 'danger'
    case 'created': return 'info'
    case 'restarting': return 'warning'
    default: return 'info'
  }
}

/**
 * Return a human-readable French status label.
 * Shows health status when available (healthy/unhealthy/starting),
 * otherwise shows the container state with a French label.
 */
export function getContainerStatusLabel(status: string, healthStatus?: string | null): string {
  if (healthStatus === 'healthy') return 'Sain'
  if (healthStatus === 'unhealthy') return 'Non sain'
  if (healthStatus === 'starting') return 'Démarrage...'
  const labels: Record<string, string> = {
    running: 'En cours',
    paused: 'En pause',
    exited: 'Arrêté',
    dead: 'Mort',
    created: 'Créé',
    restarting: 'Redémarrage',
  }
  return labels[status] ?? status
}

/**
 * Return a Tailwind CSS color class for the "X/Y running" counter of a stack or discovered item.
 */
export function servicesRunningClass(running: number, total: number): string {
  if (running === total) return 'text-green-600'
  if (running === 0) return 'text-red-500'
  return 'text-orange-500'
}

/**
 * Overload accepting a StackWithServices or similar object with services_running / services_total.
 */
export function servicesRunningClassObj(obj: { services_running: number; services_total: number }): string {
  return servicesRunningClass(obj.services_running, obj.services_total)
}

// ─── Formatting Helpers ───────────────────────────────────────────────────────

/**
 * Format a port mapping as "host_ip:host_port->container_port/protocol".
 */
export function formatPort(port: StandaloneContainerPortMapping): string {
  return `${port.host_ip}:${port.host_port}->${port.container_port}/${port.protocol}`
}

/**
 * Return the French past participle for a bulk action verb.
 */
export function getActionPastParticiple(action: 'start' | 'stop' | 'restart'): string {
  const map: Record<string, string> = {
    start: 'démarré(s)',
    stop: 'arrêté(s)',
    restart: 'redémarré(s)',
  }
  return map[action] || action
}

// ─── App Card Data (Mode App) ────────────────────────────────────────────────

/** Category of an app card in Mode App */
export type AppCardCategory = 'managed' | 'standalone' | 'discovered'

/** Unified data structure for displaying an app card in Mode App */
export interface AppCardData {
  /** Unique identifier (container or service ID) */
  id: string
  /** Technical name (container/service name) */
  name: string
  /** User-facing display name (via getAppDisplayName) */
  displayName: string
  /** Version extracted from image tag (e.g. "1.26" from "nginx:1.26") */
  version: string
  /** Icon emoji or identifier for the app */
  icon: string
  /** Domain URL if HTTP port is exposed */
  domain: string | null
  /** Technical Docker status string */
  status: string
  /** User-facing Mode App status label */
  statusLabel: string
  /** Element Plus color token for status badge */
  statusColor: string
  /** Memory usage string (e.g. "342 MB") */
  ram: string
  /** CPU percentage */
  cpuPercent: number
  /** Category: managed stack, standalone container, or discovered */
  category: AppCardCategory
  /** Total number of services (for stacks/discovered items) */
  servicesTotal: number
  /** Number of running services */
  servicesRunning: number
  /** Target/server name where the app runs */
  targetName: string
  /** Whether an update is available */
  updateAvailable: boolean
  /** Container ID for API actions */
  containerId: string
  /** Container labels for context menu */
  labels: Record<string, string>
}

/** Default icon mapping for common stack names */
const STACK_ICON_MAP: Record<string, string> = {
  nginx: '🌐',
  nextcloud: '☁️',
  gitea: '🐙',
  grafana: '📊',
  jellyfin: '🎬',
  vaultwarden: '🔒',
  portainer: '🐳',
  traefik: '🔀',
  postgres: '🐘',
  mysql: '🗄️',
  redis: '🔴',
  mongodb: '🍃',
  wordpress: '📝',
  pihole: '🛡️',
  adguard: '🛡️',
  uptime: '⏱️',
  prometheus: '📈',
  chat: '💬',
  mattermost: '💬',
  filebrowser: '📁',
}

/**
 * Extract a version string from a Docker image tag.
 * @example extractVersion("nginx:1.26") → "1.26"
 * @example extractVersion("nextcloud:28.0.4") → "28.0.4"
 * @example extractVersion("myapp") → ""
 */
export function extractVersion(image: string): string {
  // Digest-based images use @ (e.g. "myapp@sha256:abc123") — no version to extract
  if (image.includes('@')) return ''
  const colonIndex = image.lastIndexOf(':')
  if (colonIndex === -1) return ''
  const tag = image.slice(colonIndex + 1)
  // Skip "latest" tag
  if (tag === 'latest') return ''
  return tag
}

/**
 * Get an icon emoji for a given app/service name.
 * Falls back to 📦 for unknown apps.
 */
export function getAppIcon(name: string): string {
  const lowerName = name.toLowerCase()
  for (const [key, icon] of Object.entries(STACK_ICON_MAP)) {
    if (lowerName.includes(key)) return icon
  }
  return '📦'
}

/**
 * Deduce a domain URL from exposed ports.
 * Returns the first HTTP/HTTPS port found, or null.
 */
export function deduceDomain(ports: StandaloneContainerPortMapping[]): string | null {
  // Prefer port 443 (HTTPS), then 80 (HTTP), then any other port
  const httpsPort = ports.find(p => p.container_port === 443)
  if (httpsPort) {
    return `https://${httpsPort.host_ip === '0.0.0.0' ? 'localhost' : httpsPort.host_ip}:${httpsPort.host_port}`
  }
  const httpPort = ports.find(p => p.container_port === 80)
  if (httpPort) {
    return `http://${httpPort.host_ip === '0.0.0.0' ? 'localhost' : httpPort.host_ip}:${httpPort.host_port}`
  }
  // Any port exposed on a public interface
  const publicPort = ports.find(p => p.host_port > 0 && p.host_ip !== '127.0.0.1')
  if (publicPort) {
    return `http://${publicPort.host_ip === '0.0.0.0' ? 'localhost' : publicPort.host_ip}:${publicPort.host_port}`
  }
  return null
}

/**
 * Convert a ServiceWithMetrics to an AppCardData.
 */
function serviceToAppCard(
  service: ServiceWithMetrics,
  category: AppCardCategory,
  targetName: string,
  servicesTotal: number,
  servicesRunning: number,
): AppCardData {
  const statusMapping = getAppStatus(service.status)
  const ports = service.ports ?? []

  return {
    id: service.id,
    name: service.name,
    displayName: getAppDisplayName({ name: service.name, labels: {} }),
    version: extractVersion(service.image),
    icon: getAppIcon(service.name),
    domain: deduceDomain(ports),
    status: service.status,
    statusLabel: statusMapping.app,
    statusColor: statusMapping.color,
    ram: service.memory_usage,
    cpuPercent: service.cpu_percent,
    category,
    servicesTotal,
    servicesRunning,
    targetName,
    updateAvailable: false,
    containerId: service.id,
    labels: {},
  }
}

/**
 * Convert a StackWithServices to an array of AppCardData.
 * Each service in the stack becomes one card.
 */
export function stackToAppCards(stack: StackWithServices): AppCardData[] {
  return stack.services.map(service =>
    serviceToAppCard(
      service,
      'managed',
      stack.target_name,
      stack.services_total,
      stack.services_running,
    ),
  )
}

/**
 * Convert a DiscoveredItem to an array of AppCardData.
 * Each service in the item becomes one card.
 */
export function discoveredToAppCards(item: DiscoveredItem): AppCardData[] {
  return (item.services ?? []).map(service =>
    serviceToAppCard(
      service,
      'discovered',
      item.target_name,
      item.services_total,
      item.services_running,
    ),
  )
}

/**
 * Convert a StandaloneContainer to an AppCardData.
 */
export function standaloneToAppCard(container: StandaloneContainer): AppCardData {
  const statusMapping = getAppStatus(container.status)
  const ports = container.ports ?? []

  return {
    id: container.id,
    name: container.name,
    displayName: getAppDisplayName({ name: container.name }),
    version: extractVersion(container.image),
    icon: getAppIcon(container.name),
    domain: deduceDomain(ports),
    status: container.status,
    statusLabel: statusMapping.app,
    statusColor: statusMapping.color,
    ram: container.memory_usage,
    cpuPercent: container.cpu_percent,
    category: 'standalone',
    servicesTotal: 1,
    servicesRunning: container.status === 'running' ? 1 : 0,
    targetName: container.target_name,
    updateAvailable: false,
    containerId: container.id,
    labels: {},
  }
}
