/**
 * Helpers de mock API pour les tests E2E Playwright
 * Intercepte les appels API et retourne des données de test.
 */

import type { Page } from '@playwright/test'

// ─── Compute ─────────────────────────────────────────────────────────────────

export interface MockComputeStatsData {
  total_containers: number
  running_containers: number
  stacks_count: number
  stacks_services_count: number
  discovered_count: number
  standalone_count: number
  targets_count: number
}

export const DEFAULT_COMPUTE_STATS: MockComputeStatsData = {
  total_containers: 23,
  running_containers: 18,
  stacks_count: 3,
  stacks_services_count: 9,
  discovered_count: 4,
  standalone_count: 10,
  targets_count: 4,
}

export function mockComputeStats(page: Page, data: MockComputeStatsData = DEFAULT_COMPUTE_STATS): Promise<void> {
  return page.route('**/api/v1/compute/stats**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
  })
}

export interface MockService {
  id: string
  name: string
  image: string
  status: string
  cpu_percent: number
  memory_usage: string
  memory_limit?: string
}

export interface MockStack {
  id: string
  name: string
  technology: string
  target_id: string
  target_name: string
  services_total: number
  services_running: number
  status: 'running' | 'partial' | 'stopped' | 'archived'
  services: MockService[]
}

export interface MockDiscoveredItem {
  id: string
  name: string
  type: 'container' | 'composition' | 'helm_release'
  technology: string
  source_path?: string
  target_id: string
  target_name: string
  services_total: number
  services_running: number
  detected_at: string
  adoptable: boolean
  services: MockService[]
}

export interface MockStandaloneContainer {
  id: string
  name: string
  image: string
  target_id: string
  target_name: string
  status: string
  cpu_percent: number
  memory_usage: string
}

export interface MockComputeGlobalData {
  managed_stacks: MockStack[]
  discovered_items: MockDiscoveredItem[]
  standalone_containers: MockStandaloneContainer[]
}

export interface MockTargetGroup {
  target_id: string
  target_name: string
  technology: string
  stacks: MockStack[]
  discovered: MockDiscoveredItem[]
  standalone: MockStandaloneContainer[]
  metrics: {
    cpu_total_percent: number
    memory_used: string
    memory_total: string
  }
}

export const DEFAULT_TARGET_GROUPS: MockTargetGroup[] = [
  {
    target_id: 'target-001',
    target_name: 'localhost',
    technology: 'Docker Engine 26.1',
    stacks: [],
    discovered: [],
    standalone: [],
    metrics: { cpu_total_percent: 5.2, memory_used: '2.1G', memory_total: '8G' },
  },
  {
    target_id: 'target-002',
    target_name: 'vps-ovh',
    technology: 'Docker Engine 25.0',
    stacks: [],
    discovered: [],
    standalone: [],
    metrics: { cpu_total_percent: 3.1, memory_used: '1.5G', memory_total: '4G' },
  },
  {
    target_id: 'target-003',
    target_name: 'pi4-home',
    technology: 'Docker Engine 24.0',
    stacks: [],
    discovered: [],
    standalone: [],
    metrics: { cpu_total_percent: 1.8, memory_used: '800M', memory_total: '2G' },
  },
]

export const DEFAULT_COMPUTE_GLOBAL: MockComputeGlobalData = {
  managed_stacks: [
    {
      id: 'stack-001',
      name: 'monitoring',
      technology: 'compose',
      target_id: 'target-001',
      target_name: 'localhost',
      services_total: 3,
      services_running: 3,
      status: 'running',
      services: [
        { id: 'svc-001', name: 'grafana', image: 'grafana/grafana:latest', status: 'running', cpu_percent: 2.5, memory_usage: '120M' },
        { id: 'svc-002', name: 'prometheus', image: 'prom/prometheus:latest', status: 'running', cpu_percent: 5.1, memory_usage: '340M' },
        { id: 'svc-003', name: 'loki', image: 'grafana/loki:latest', status: 'running', cpu_percent: 1.2, memory_usage: '80M' },
      ],
    },
    {
      id: 'stack-002',
      name: 'web-apps',
      technology: 'compose',
      target_id: 'target-001',
      target_name: 'localhost',
      services_total: 2,
      services_running: 0,
      status: 'stopped',
      services: [],
    },
  ],
  discovered_items: [
    {
      id: 'disc-001',
      name: 'orphan-monitoring',
      type: 'composition',
      technology: 'compose',
      source_path: '/home/user/monitoring/docker-compose.yml',
      target_id: 'target-002',
      target_name: 'vps-ovh',
      services_total: 2,
      services_running: 2,
      detected_at: '2026-05-20T10:00:00Z',
      adoptable: true,
      services: [
        { id: 'dsvc-001', name: 'node-exporter', image: 'prom/node-exporter:latest', status: 'running', cpu_percent: 0.5, memory_usage: '20M' },
        { id: 'dsvc-002', name: 'cadvisor', image: 'gcr.io/cadvisor/cadvisor:latest', status: 'running', cpu_percent: 1.8, memory_usage: '60M' },
      ],
    },
    {
      id: 'disc-002',
      name: 'legacy-db',
      type: 'container',
      technology: 'docker',
      target_id: 'target-001',
      target_name: 'localhost',
      services_total: 1,
      services_running: 1,
      detected_at: '2026-05-19T08:00:00Z',
      adoptable: false,
      services: [
        { id: 'dsvc-003', name: 'legacy-db', image: 'mysql:5.7', status: 'running', cpu_percent: 3.2, memory_usage: '450M' },
      ],
    },
  ],
  standalone_containers: [
    {
      id: 'standalone-001',
      name: 'traefik',
      image: 'traefik:v3.0',
      target_id: 'target-001',
      target_name: 'localhost',
      status: 'running',
      cpu_percent: 1.5,
      memory_usage: '80M',
    },
    {
      id: 'standalone-002',
      name: 'pihole',
      image: 'pihole/pihole:latest',
      target_id: 'target-003',
      target_name: 'pi4-home',
      status: 'running',
      cpu_percent: 0.8,
      memory_usage: '120M',
    },
  ],
}

export function mockComputeGlobal(
  page: Page,
  data: MockComputeGlobalData = DEFAULT_COMPUTE_GLOBAL,
  targetGroupsData: MockTargetGroup[] = DEFAULT_TARGET_GROUPS,
): Promise<void> {
  return page.route('**/api/v1/compute/global**', async (route) => {
    const url = route.request().url()
    if (url.includes('group_by=target')) {
      // Vue "Par machine" mode: return TargetGroup[] format
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(targetGroupsData) })
    } else {
      // Standard mode: return ComputeGlobalView format
      await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
    }
  })
}

// ─── Discovery / Adoption ────────────────────────────────────────────────────

export interface MockAdoptionWizardData {
  discovered_id: string
  name: string
  type: string
  technology: string
  target_name: string
  services: Array<{
    name: string
    image: string
    status: string
    env_vars: string[]
    volumes: string[]
    networks: string[]
    ports: string[]
  }>
  generated_compose: string
}

export const DEFAULT_ADOPTION_DATA: MockAdoptionWizardData = {
  discovered_id: 'disc-001',
  name: 'orphan-monitoring',
  type: 'composition',
  technology: 'compose',
  target_name: 'vps-ovh',
  services: [
    {
      name: 'node-exporter',
      image: 'prom/node-exporter:latest',
      status: 'running',
      env_vars: [],
      volumes: ['/proc:/host/proc:ro'],
      networks: ['monitoring_default'],
      ports: ['9100:9100'],
    },
    {
      name: 'cadvisor',
      image: 'gcr.io/cadvisor/cadvisor:latest',
      status: 'running',
      env_vars: [],
      volumes: ['/var/run/docker.sock:/var/run/docker.sock:ro'],
      networks: ['monitoring_default'],
      ports: ['8080:8080'],
    },
  ],
  generated_compose: `version: "3.8"
services:
  node-exporter:
    image: prom/node-exporter:latest
    ports:
      - "9100:9100"
  cadvisor:
    image: gcr.io/cadvisor/cadvisor:latest
    ports:
      - "8080:8080"
`,
}

export function mockAdoptionData(
  page: Page,
  discoveredId: string,
  type: string,
  data: MockAdoptionWizardData = DEFAULT_ADOPTION_DATA,
): Promise<void> {
  return page.route(`**/api/v1/discovery/${type}/${discoveredId}/adoption-data**`, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
  })
}

export function mockAdoptPost(page: Page, response: { success: boolean; message: string; stack_id?: string }): Promise<void> {
  return page.route('**/api/v1/discovery/adopt**', async (route) => {
    await route.fulfill({ status: response.success ? 200 : 500, contentType: 'application/json', body: JSON.stringify(response) })
  })
}

// ─── Stacks ──────────────────────────────────────────────────────────────────

export function mockStacksList(page: Page, stacks: Array<{ id: string; name: string; status: string }>): Promise<void> {
  return page.route('**/api/v1/stacks**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(stacks) })
  })
}

export function mockStackStart(page: Page, stackId: string, response: { success: boolean; message: string }): Promise<void> {
  return page.route(`**/api/v1/stacks/${stackId}/start**`, async (route) => {
    await route.fulfill({ status: response.success ? 200 : 500, contentType: 'application/json', body: JSON.stringify(response) })
  })
}

export function mockStackStop(page: Page, stackId: string, response: { success: boolean; message: string }): Promise<void> {
  return page.route(`**/api/v1/stacks/${stackId}/stop**`, async (route) => {
    await route.fulfill({ status: response.success ? 200 : 500, contentType: 'application/json', body: JSON.stringify(response) })
  })
}

export function mockStackRedeploy(page: Page, stackId: string, response: { success: boolean; message: string }): Promise<void> {
  return page.route(`**/api/v1/stacks/${stackId}/redeploy**`, async (route) => {
    await route.fulfill({ status: response.success ? 200 : 500, contentType: 'application/json', body: JSON.stringify(response) })
  })
}

export function mockStackExport(page: Page, stackId: string, data: Record<string, unknown>): Promise<void> {
  return page.route(`**/api/v1/stacks/${stackId}/export**`, async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(data) })
  })
}

export function mockStackImport(page: Page, response: { message: string; stack_id: string; name: string }): Promise<void> {
  return page.route('**/api/v1/stacks/import**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) })
  })
}

// ─── Images ──────────────────────────────────────────────────────────────────

export interface MockImage {
  id: string
  repoTags: string[]
  repoDigests: string[]
  created: string
  size: number
  virtualSize: number
  labels: Record<string, string>
  inUse: boolean
  containersCount: number
}

export const DEFAULT_IMAGES: MockImage[] = [
  {
    id: 'sha256:abc123def456',
    repoTags: ['nginx:latest', 'nginx:1.25'],
    repoDigests: [],
    created: '2026-05-15T10:00:00Z',
    size: 187_000_000,
    virtualSize: 187_000_000,
    labels: {},
    inUse: true,
    containersCount: 2,
  },
  {
    id: 'sha256:xyz789uvw012',
    repoTags: ['redis:7-alpine'],
    repoDigests: [],
    created: '2026-05-10T08:00:00Z',
    size: 45_000_000,
    virtualSize: 45_000_000,
    labels: {},
    inUse: false,
    containersCount: 0,
  },
]

export function mockImagesList(page: Page, images: MockImage[] = DEFAULT_IMAGES): Promise<void> {
  return page.route('**/api/v1/docker/images**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(images) })
  })
}

export function mockImagePull(page: Page, response: { status: string; id?: string }): Promise<void> {
  return page.route('**/api/v1/docker/images/pull**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(response) })
  })
}

export function mockImageRemove(page: Page, imageId: string, success = true): Promise<void> {
  return page.route(`**/api/v1/docker/images/${encodeURIComponent(imageId)}**`, async (route) => {
    if (success) {
      await route.fulfill({ status: 204 })
    } else {
      await route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ detail: 'Image is in use' }) })
    }
  })
}

// ─── Targets ─────────────────────────────────────────────────────────────────

export function mockTargetsList(page: Page, targets: Array<{ id: string; name: string; host: string }>): Promise<void> {
  return page.route('**/api/v1/targets**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(targets) })
  })
}

// ─── Auth / User ─────────────────────────────────────────────────────────────

export function mockCurrentUser(page: Page, user: { id: string; email: string; role: string; organization_id: string }): Promise<void> {
  return page.route('**/api/v1/users/me**', async (route) => {
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(user) })
  })
}

// ─── Catch-all ───────────────────────────────────────────────────────────────

/**
 * Intercepte TOUTES les requêtes API non mockées et retourne une réponse vide.
 * Empêche les appels réseau réels vers le backend (qui n'existe pas en E2E).
 * ⚠️ À appeler EN DERNIER dans beforeEach, après les mocks spécifiques.
 */
export function mockCatchAllApi(page: Page): Promise<void> {
  return page.route('**/api/**', async (route) => {
    // Si la requête a déjà été interceptée par un mock spécifique, elle n'arrive pas ici.
    // Ce catch-all ne gère que les routes non mockées.
    await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify([]) })
  })
}
