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
} from '@/types/api'

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
