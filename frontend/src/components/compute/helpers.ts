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
 */
export function getContainerStatusColor(status: string, healthStatus?: string | null): string {
  if (healthStatus === 'healthy') return 'text-green-500'
  if (healthStatus === 'unhealthy') return 'text-orange-500'
  if (status === 'running') return 'text-green-500'
  return 'text-red-400'
}

/**
 * Return an Element Plus tag type based on container status and health.
 */
export function getContainerStatusType(
  status: string,
  healthStatus?: string | null,
): 'success' | 'warning' | 'danger' | 'info' {
  if (healthStatus === 'healthy') return 'success'
  if (healthStatus === 'unhealthy') return 'warning'
  if (status === 'running') return 'success'
  if (status === 'exited') return 'danger'
  return 'info'
}

/**
 * Return a human-readable status label.
 */
export function getContainerStatusLabel(status: string, healthStatus?: string | null): string {
  if (healthStatus === 'healthy') return 'healthy'
  if (healthStatus === 'unhealthy') return 'unhealthy'
  if (healthStatus === 'starting') return 'starting'
  return status
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
