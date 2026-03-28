import { describe, it, expect } from 'vitest'
import {
  serviceToRow,
  standaloneToRow,
  getContainerStatusColor,
  getContainerStatusType,
  getContainerStatusLabel,
  servicesRunningClass,
  servicesRunningClassObj,
  formatPort,
  getActionPastParticiple,
  DEFAULT_COLUMNS,
} from '@/components/compute/helpers'
import type { ServiceWithMetrics, StandaloneContainer } from '@/types/api'

// ─── Factory helpers ──────────────────────────────────────────────────────────

function createService(overrides: Partial<ServiceWithMetrics> = {}): ServiceWithMetrics {
  return {
    id: 'svc-1',
    name: 'nginx',
    image: 'nginx:latest',
    status: 'running',
    cpu_percent: 2.5,
    memory_usage: '50 MiB',
    ...overrides,
  }
}

function createContainer(overrides: Partial<StandaloneContainer> = {}): StandaloneContainer {
  return {
    id: 'ctr-1',
    name: 'my-container',
    image: 'redis:7',
    status: 'running',
    cpu_percent: 1.2,
    memory_usage: '30 MiB',
    target_name: 'localhost',
    uptime: '2 hours',
    ports: [
      { host_ip: '0.0.0.0', host_port: 6379, container_port: 6379, protocol: 'tcp' },
    ],
    health_status: 'healthy',
    ...overrides,
  }
}

// ─── DEFAULT_COLUMNS ─────────────────────────────────────────────────────────

describe('DEFAULT_COLUMNS', () => {
  it('should contain expected default columns', () => {
    expect(DEFAULT_COLUMNS).toEqual(['name', 'image', 'status', 'cpu', 'memory', 'actions'])
  })
})

// ─── serviceToRow ─────────────────────────────────────────────────────────────

describe('serviceToRow', () => {
  it('should normalize a service to a row', () => {
    const service = createService()
    const row = serviceToRow(service)
    expect(row).toEqual({
      id: 'svc-1',
      name: 'nginx',
      image: 'nginx:latest',
      status: 'running',
      cpuPercent: 2.5,
      memoryUsage: '50 MiB',
      targetName: undefined,
    })
  })

  it('should include targetName when provided', () => {
    const service = createService()
    const row = serviceToRow(service, 'vps-ovh')
    expect(row.targetName).toBe('vps-ovh')
  })
})

// ─── standaloneToRow ──────────────────────────────────────────────────────────

describe('standaloneToRow', () => {
  it('should normalize a container to a row', () => {
    const container = createContainer()
    const row = standaloneToRow(container)
    expect(row).toEqual({
      id: 'ctr-1',
      name: 'my-container',
      image: 'redis:7',
      status: 'running',
      cpuPercent: 1.2,
      memoryUsage: '30 MiB',
      targetName: 'localhost',
      uptime: '2 hours',
      ports: [{ host_ip: '0.0.0.0', host_port: 6379, container_port: 6379, protocol: 'tcp' }],
      healthStatus: 'healthy',
      link: '/containers/ctr-1',
    })
  })

  it('should build link from container id', () => {
    const container = createContainer({ id: 'abc-123' })
    const row = standaloneToRow(container)
    expect(row.link).toBe('/containers/abc-123')
  })
})

// ─── getContainerStatusColor ──────────────────────────────────────────────────

describe('getContainerStatusColor', () => {
  it('should return green for healthy health status', () => {
    expect(getContainerStatusColor('running', 'healthy')).toBe('text-green-500')
  })

  it('should return orange for unhealthy health status', () => {
    expect(getContainerStatusColor('running', 'unhealthy')).toBe('text-orange-500')
  })

  it('should return green for running without health status', () => {
    expect(getContainerStatusColor('running')).toBe('text-green-500')
  })

  it('should return red for exited status', () => {
    expect(getContainerStatusColor('exited')).toBe('text-red-400')
  })

  it('should return red for unknown status', () => {
    expect(getContainerStatusColor('created')).toBe('text-red-400')
  })
})

// ─── getContainerStatusType ───────────────────────────────────────────────────

describe('getContainerStatusType', () => {
  it('should return success for healthy', () => {
    expect(getContainerStatusType('running', 'healthy')).toBe('success')
  })

  it('should return warning for unhealthy', () => {
    expect(getContainerStatusType('running', 'unhealthy')).toBe('warning')
  })

  it('should return success for running without health', () => {
    expect(getContainerStatusType('running')).toBe('success')
  })

  it('should return danger for exited', () => {
    expect(getContainerStatusType('exited')).toBe('danger')
  })

  it('should return info for unknown status', () => {
    expect(getContainerStatusType('created')).toBe('info')
  })
})

// ─── getContainerStatusLabel ──────────────────────────────────────────────────

describe('getContainerStatusLabel', () => {
  it('should return "healthy" for healthy health status', () => {
    expect(getContainerStatusLabel('running', 'healthy')).toBe('healthy')
  })

  it('should return "unhealthy" for unhealthy health status', () => {
    expect(getContainerStatusLabel('running', 'unhealthy')).toBe('unhealthy')
  })

  it('should return "starting" for starting health status', () => {
    expect(getContainerStatusLabel('running', 'starting')).toBe('starting')
  })

  it('should return the raw status when no health status', () => {
    expect(getContainerStatusLabel('exited')).toBe('exited')
  })
})

// ─── servicesRunningClass ─────────────────────────────────────────────────────

describe('servicesRunningClass', () => {
  it('should return green when all running', () => {
    expect(servicesRunningClass(3, 3)).toBe('text-green-600')
  })

  it('should return red when none running', () => {
    expect(servicesRunningClass(0, 3)).toBe('text-red-500')
  })

  it('should return orange when partially running', () => {
    expect(servicesRunningClass(2, 3)).toBe('text-orange-500')
  })
})

// ─── servicesRunningClassObj ──────────────────────────────────────────────────

describe('servicesRunningClassObj', () => {
  it('should delegate to servicesRunningClass', () => {
    expect(servicesRunningClassObj({ services_running: 3, services_total: 3 })).toBe('text-green-600')
    expect(servicesRunningClassObj({ services_running: 0, services_total: 3 })).toBe('text-red-500')
    expect(servicesRunningClassObj({ services_running: 1, services_total: 3 })).toBe('text-orange-500')
  })
})

// ─── formatPort ───────────────────────────────────────────────────────────────

describe('formatPort', () => {
  it('should format a port mapping', () => {
    expect(formatPort({
      host_ip: '0.0.0.0',
      host_port: 8080,
      container_port: 80,
      protocol: 'tcp',
    })).toBe('0.0.0.0:8080->80/tcp')
  })

  it('should handle different IPs', () => {
    expect(formatPort({
      host_ip: '127.0.0.1',
      host_port: 443,
      container_port: 443,
      protocol: 'tcp',
    })).toBe('127.0.0.1:443->443/tcp')
  })
})

// ─── getActionPastParticiple ──────────────────────────────────────────────────

describe('getActionPastParticiple', () => {
  it('should return French past participle for start', () => {
    expect(getActionPastParticiple('start')).toBe('démarré(s)')
  })

  it('should return French past participle for stop', () => {
    expect(getActionPastParticiple('stop')).toBe('arrêté(s)')
  })

  it('should return French past participle for restart', () => {
    expect(getActionPastParticiple('restart')).toBe('redémarré(s)')
  })
})
