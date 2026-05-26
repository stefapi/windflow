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
  extractVersion,
  getAppIcon,
  deduceDomain,
  stackToAppCards,
  discoveredToAppCards,
  standaloneToAppCard,
} from '@/components/compute/helpers'
import type { ServiceWithMetrics, StandaloneContainer, StackWithServices, DiscoveredItem } from '@/types/api'

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
      uptime: null,
      ports: [],
      healthStatus: null,
      link: '/containers/svc-1',
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

  it('should return blue for created status', () => {
    expect(getContainerStatusColor('created')).toBe('text-blue-400')
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
  it('should return "Sain" for healthy health status', () => {
    expect(getContainerStatusLabel('running', 'healthy')).toBe('Sain')
  })

  it('should return "Non sain" for unhealthy health status', () => {
    expect(getContainerStatusLabel('running', 'unhealthy')).toBe('Non sain')
  })

  it('should return "Démarrage..." for starting health status', () => {
    expect(getContainerStatusLabel('running', 'starting')).toBe('Démarrage...')
  })

  it('should return the French label when no health status', () => {
    expect(getContainerStatusLabel('exited')).toBe('Arrêté')
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

// ─── extractVersion ─────────────────────────────────────────────────────────

describe('extractVersion', () => {
  it('should extract version from image tag', () => {
    expect(extractVersion('nginx:1.26')).toBe('1.26')
  })

  it('should extract semver version', () => {
    expect(extractVersion('nextcloud:28.0.4')).toBe('28.0.4')
  })

  it('should return empty string for image without tag', () => {
    expect(extractVersion('myapp')).toBe('')
  })

  it('should return empty string for latest tag', () => {
    expect(extractVersion('nginx:latest')).toBe('')
  })

  it('should return empty string for sha256 digest', () => {
    expect(extractVersion('myapp@sha256:abc123')).toBe('')
  })
})

// ─── getAppIcon ─────────────────────────────────────────────────────────────

describe('getAppIcon', () => {
  it('should return nginx icon', () => {
    expect(getAppIcon('nginx')).toBe('🌐')
  })

  it('should return nextcloud icon', () => {
    expect(getAppIcon('nextcloud-app')).toBe('☁️')
  })

  it('should return default icon for unknown app', () => {
    expect(getAppIcon('my-custom-app')).toBe('📦')
  })

  it('should be case-insensitive', () => {
    expect(getAppIcon('Nginx')).toBe('🌐')
  })
})

// ─── deduceDomain ───────────────────────────────────────────────────────────

describe('deduceDomain', () => {
  it('should return HTTPS URL for port 443', () => {
    const ports = [{ host_ip: '0.0.0.0', host_port: 443, container_port: 443, protocol: 'tcp' }]
    expect(deduceDomain(ports)).toBe('https://localhost:443')
  })

  it('should return HTTP URL for port 80', () => {
    const ports = [{ host_ip: '0.0.0.0', host_port: 8080, container_port: 80, protocol: 'tcp' }]
    expect(deduceDomain(ports)).toBe('http://localhost:8080')
  })

  it('should return null for empty ports', () => {
    expect(deduceDomain([])).toBeNull()
  })

  it('should return null when only loopback port is exposed', () => {
    const ports = [{ host_ip: '127.0.0.1', host_port: 3000, container_port: 3000, protocol: 'tcp' }]
    expect(deduceDomain(ports)).toBeNull()
  })

  it('should return HTTP URL for any public port', () => {
    const ports = [{ host_ip: '0.0.0.0', host_port: 9090, container_port: 9090, protocol: 'tcp' }]
    expect(deduceDomain(ports)).toBe('http://localhost:9090')
  })
})

// ─── stackToAppCards ────────────────────────────────────────────────────────

describe('stackToAppCards', () => {
  it('should convert a stack with services to cards', () => {
    const stack: StackWithServices = {
      id: 'stack-1',
      name: 'nextcloud',
      technology: 'docker_compose',
      target_id: 'target-1',
      target_name: 'localhost',
      services_total: 3,
      services_running: 2,
      status: 'running',
      services: [
        {
          id: 'svc-1',
          name: 'nginx',
          image: 'nginx:1.26',
          status: 'running',
          cpu_percent: 2.5,
          memory_usage: '50 MiB',
        },
        {
          id: 'svc-2',
          name: 'php-fpm',
          image: 'nextcloud:28',
          status: 'running',
          cpu_percent: 5.0,
          memory_usage: '200 MiB',
        },
      ],
    }

    const cards = stackToAppCards(stack)
    expect(cards).toHaveLength(2)
    expect(cards[0].category).toBe('managed')
    expect(cards[0].name).toBe('nginx')
    expect(cards[0].version).toBe('1.26')
    expect(cards[0].targetName).toBe('localhost')
    expect(cards[0].servicesTotal).toBe(3)
    expect(cards[0].servicesRunning).toBe(2)
    expect(cards[1].name).toBe('php-fpm')
    expect(cards[1].version).toBe('28')
  })

  it('should return empty array for stack with no services', () => {
    const stack: StackWithServices = {
      id: 'stack-2',
      name: 'empty-stack',
      technology: 'docker_compose',
      target_id: 'target-1',
      target_name: 'localhost',
      services_total: 0,
      services_running: 0,
      status: 'stopped',
      services: [],
    }

    expect(stackToAppCards(stack)).toHaveLength(0)
  })
})

// ─── discoveredToAppCards ───────────────────────────────────────────────────

describe('discoveredToAppCards', () => {
  it('should convert a discovered item with services to cards', () => {
    const item: DiscoveredItem = {
      id: 'disc-1',
      name: 'my-discovered',
      type: 'composition',
      technology: 'docker_compose',
      target_id: 'target-1',
      target_name: 'vps-ovh',
      services_total: 2,
      services_running: 1,
      detected_at: '2026-01-01T00:00:00Z',
      adoptable: true,
      services: [
        {
          id: 'svc-d1',
          name: 'web',
          image: 'myapp:2.0',
          status: 'running',
          cpu_percent: 10,
          memory_usage: '100 MiB',
        },
      ],
    }

    const cards = discoveredToAppCards(item)
    expect(cards).toHaveLength(1)
    expect(cards[0].category).toBe('discovered')
    expect(cards[0].name).toBe('web')
    expect(cards[0].version).toBe('2.0')
    expect(cards[0].targetName).toBe('vps-ovh')
  })

  it('should return empty array for item with no services', () => {
    const item: DiscoveredItem = {
      id: 'disc-2',
      name: 'empty-disc',
      type: 'container',
      technology: 'docker',
      target_id: 'target-1',
      target_name: 'localhost',
      services_total: 0,
      services_running: 0,
      detected_at: '2026-01-01T00:00:00Z',
      adoptable: false,
    }

    expect(discoveredToAppCards(item)).toHaveLength(0)
  })
})

// ─── standaloneToAppCard ────────────────────────────────────────────────────

describe('standaloneToAppCard', () => {
  it('should convert a standalone container to a card', () => {
    const container: StandaloneContainer = {
      id: 'ctr-1',
      name: 'my-redis',
      image: 'redis:7',
      status: 'running',
      cpu_percent: 1.2,
      memory_usage: '30 MiB',
      target_id: 'target-1',
      target_name: 'localhost',
      uptime: '2 hours',
      ports: [
        { host_ip: '0.0.0.0', host_port: 6379, container_port: 6379, protocol: 'tcp' },
      ],
      health_status: 'healthy',
    }

    const card = standaloneToAppCard(container)
    expect(card.id).toBe('ctr-1')
    expect(card.name).toBe('my-redis')
    expect(card.version).toBe('7')
    expect(card.category).toBe('standalone')
    expect(card.statusLabel).toBe('En cours')
    expect(card.statusColor).toBe('success')
    expect(card.ram).toBe('30 MiB')
    expect(card.targetName).toBe('localhost')
    expect(card.servicesTotal).toBe(1)
    expect(card.servicesRunning).toBe(1)
    expect(card.containerId).toBe('ctr-1')
  })

  it('should handle stopped container', () => {
    const container: StandaloneContainer = {
      id: 'ctr-2',
      name: 'old-app',
      image: 'myapp:1.0',
      status: 'exited',
      cpu_percent: 0,
      memory_usage: '0 B',
      target_id: 'target-1',
      target_name: 'localhost',
      uptime: null,
      ports: [],
      health_status: null,
    }

    const card = standaloneToAppCard(container)
    expect(card.statusLabel).toBe('Terminé')
    expect(card.servicesRunning).toBe(0)
    expect(card.domain).toBeNull()
  })
})
