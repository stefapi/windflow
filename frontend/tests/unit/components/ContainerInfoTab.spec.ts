import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ContainerInfoTab from '@/components/ContainerInfoTab.vue'

// Mock useSecretMasker
vi.mock('@/composables/useSecretMasker', () => ({
  useSecretMasker: () => ({
    revealedKeys: new Set(),
    toggleSecret: vi.fn(),
    isRevealed: vi.fn(() => false),
  }),
  isSecretKey: (key: string) => /password|secret|key|token/i.test(key),
  maskValue: (value: string) => {
    if (!value || value.length === 0) return ''
    if (value.length <= 4) return '****'
    return `${value.substring(0, 2)}${'*'.repeat(Math.min(value.length - 4, 10))}${value.substring(value.length - 2)}`
  },
}))

// Mock formatBytes
vi.mock('@/utils/format', () => ({
  formatBytes: (bytes: number) => {
    if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(1)} MB`
    if (bytes >= 1024) return `${(bytes / 1024).toFixed(1)} KB`
    return `${bytes} B`
  },
}))

// Stub Element Plus components
const globalStubs = {
  'el-card': {
    template: '<div class="el-card"><slot name="header" /><slot /></div>',
    props: ['shadow', 'class'],
  },
  'el-descriptions': {
    template: '<div class="el-descriptions"><slot /></div>',
  },
  'el-descriptions-item': {
    template: '<div class="el-descriptions-item"><slot /></div>',
    props: ['label', 'span'],
  },
  'el-table': {
    template: '<div class="el-table"><slot /></div>',
    props: ['data'],
  },
  'el-table-column': {
    template: '<div class="el-table-column" />',
    props: ['prop', 'label', 'width', 'minWidth'],
  },
  'el-tag': {
    template: '<span class="el-tag"><slot /></span>',
    props: ['type', 'size', 'effect'],
  },
  'el-button': {
    template: '<button class="el-button"><slot /></button>',
    props: ['link', 'size'],
  },
  'el-icon': {
    template: '<span class="el-icon"><slot /></span>',
  },
  'el-input': {
    template: '<input class="el-input" />',
    props: ['modelValue', 'placeholder', 'size', 'clearable'],
  },
  'el-progress': {
    template: '<div class="el-progress" />',
    props: ['percentage', 'strokeWidth', 'format'],
  },
  CopyDocument: { template: '<span />' },
  Search: { template: '<span />' },
  View: { template: '<span />' },
  Hide: { template: '<span />' },
  InfoFilled: { template: '<span />' },
  Warning: { template: '<span />' },
  Setting: { template: '<span />' },
  PriceTag: { template: '<span />' },
  Lock: { template: '<span />' },
  Coin: { template: '<span />' },
  Connection: { template: '<span />' },
  FolderOpened: { template: '<span />' },
  Share: { template: '<span />' },
  Document: { template: '<span />' },
  Cpu: { template: '<span />' },
}

function createContainer() {
  return {
    id: 'abc123def456',
    name: 'test-container',
    created: '2024-01-15T10:30:00Z',
    path: '/app',
    args: ['--port', '3000'],
    state: {
      status: 'running',
      running: true,
      paused: false,
      restarting: false,
      oom_killed: false,
      dead: false,
      exit_code: 0,
      error: null,
      started_at: '2024-01-01T00:00:00Z',
      finished_at: '0001-01-01T00:00:00Z',
      health: null,
    },
    image: 'nginx:latest',
    config: {
      hostname: 'test-container',
      user: '',
      working_dir: '',
      tty: false,
      open_stdin: false,
      stop_signal: null,
      stop_timeout: null,
      entrypoint: null,
      cmd: null,
      env: null,
      labels: null,
    },
    host_config: {
      restart_policy: null,
      network_mode: 'bridge',
      privileged: false,
      auto_remove: false,
      log_config: null,
      runtime: 'runc',
      shm_size: null,
      cap_add: null,
      cap_drop: null,
      port_bindings: null,
      resources: null,
    },
    network_settings: {
      networks: {},
    },
    mounts: [],
    size_rw: null as number | null,
    size_root_fs: null as number | null,
  } as Record<string, unknown>
}

function mountComponent(detail: Record<string, unknown>) {
  return mount(ContainerInfoTab, {
    props: { detail },
    global: {
      stubs: globalStubs,
    },
  })
}

describe('ContainerInfoTab', () => {
  it('renders general info section with ID and Image', () => {
    const wrapper = mountComponent(createContainer())
    expect(wrapper.text()).toContain('Informations générales')
    expect(wrapper.text()).toContain('abc123def456')
    expect(wrapper.text()).toContain('nginx:latest')
  })

  it('renders state section with status', () => {
    const detail = createContainer()
    detail.state = {
      status: 'running',
      running: true,
      paused: false,
      restarting: false,
      oom_killed: false,
      dead: false,
      exit_code: 0,
      error: null,
      started_at: '2024-01-01T00:00:00Z',
      finished_at: '0001-01-01T00:00:00Z',
      health: null,
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('État du container')
    expect(wrapper.text()).toContain('running')
  })

  it('shows OOM Killed when oom_killed is true', () => {
    const detail = createContainer()
    detail.state = {
      status: 'dead',
      running: false,
      paused: false,
      restarting: false,
      oom_killed: true,
      dead: true,
      exit_code: 137,
      error: 'OOM',
      started_at: '2024-01-01T00:00:00Z',
      finished_at: '2024-01-01T02:00:00Z',
      health: null,
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('OUI')
  })

  it('shows health check section when health is present', () => {
    const detail = createContainer()
    detail.state = {
      status: 'running',
      running: true,
      paused: false,
      restarting: false,
      oom_killed: false,
      dead: false,
      exit_code: 0,
      error: null,
      started_at: '2024-01-01T00:00:00Z',
      finished_at: '0001-01-01T00:00:00Z',
      health: {
        status: 'healthy',
        failing_streak: 0,
        log: [
          { start: '2024-01-01T00:00:00Z', end: '2024-01-01T00:00:01Z', exit_code: 0, output: 'OK' },
        ],
      },
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Health Check')
    expect(wrapper.text()).toContain('healthy')
  })

  it('hides health check section when health is null', () => {
    const detail = createContainer()
    detail.state = {
      status: 'running',
      running: true,
      paused: false,
      restarting: false,
      oom_killed: false,
      dead: false,
      exit_code: 0,
      error: null,
      started_at: '2024-01-01T00:00:00Z',
      finished_at: '0001-01-01T00:00:00Z',
      health: null,
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).not.toContain('Health Check')
  })

  it('renders configuration section with User and Entrypoint', () => {
    const detail = createContainer()
    detail.config = {
      hostname: 'my-container',
      user: 'nginx',
      working_dir: '/app',
      tty: true,
      open_stdin: false,
      stop_signal: 'SIGQUIT',
      stop_timeout: 10,
      entrypoint: ['/docker-entrypoint.sh'],
      cmd: ['nginx'],
      env: ['PATH=/usr/bin'],
      labels: null,
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Configuration du container')
    expect(wrapper.text()).toContain('nginx')
    expect(wrapper.text()).toContain('/docker-entrypoint.sh')
  })

  it('renders labels section when labels exist', () => {
    const detail = createContainer()
    detail.config = {
      ...createContainer().config,
      labels: { 'com.docker.compose.project': 'myapp', version: '1.0' },
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Labels')
  })

  it('renders host config section with restart policy', () => {
    const detail = createContainer()
    detail.host_config = {
      ...createContainer().host_config,
      restart_policy: { name: 'always', maximum_retry_count: 0 },
      log_config: { type: 'json-file', config: {} },
      shm_size: 67108864,
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Configuration hôte & Ressources')
    expect(wrapper.text()).toContain('always')
  })

  it('shows privileged badge when true', () => {
    const detail = createContainer()
    detail.host_config = {
      ...createContainer().host_config,
      privileged: true,
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Oui')
  })

  it('renders resource limits when present', () => {
    const detail = createContainer()
    detail.host_config = {
      ...createContainer().host_config,
      resources: {
        memory: 536870912,
        memory_reservation: 268435456,
        memory_swap: -1,
        cpu_shares: 1024,
        cpu_period: null,
        cpu_quota: null,
        cpus: null,
        cpuset_cpus: null,
        pids_limit: 100,
      },
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Limites de ressources')
    expect(wrapper.text()).toContain('512.0 MB')
  })

  it('renders capabilities (cap_add/cap_drop)', () => {
    const detail = createContainer()
    detail.host_config = {
      ...createContainer().host_config,
      cap_add: ['NET_ADMIN', 'SYS_PTRACE'],
      cap_drop: ['MKNOD'],
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Capabilities')
    expect(wrapper.text()).toContain('NET_ADMIN')
    expect(wrapper.text()).toContain('MKNOD')
  })

  it('renders disk usage section when size_rw/size_root_fs present', () => {
    const detail = createContainer()
    detail.size_rw = 536870912
    detail.size_root_fs = 2147483648
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('Occupation disque')
  })

  it('hides disk usage when sizes are null', () => {
    const wrapper = mountComponent(createContainer())
    expect(wrapper.text()).not.toContain('Occupation disque')
  })

  it('renders ports section', () => {
    const wrapper = mountComponent(createContainer())
    expect(wrapper.text()).toContain('Ports')
  })

  it('renders volumes section', () => {
    const wrapper = mountComponent(createContainer())
    expect(wrapper.text()).toContain('Volumes')
  })

  it('renders network section', () => {
    const wrapper = mountComponent(createContainer())
    expect(wrapper.text()).toContain('Réseau')
  })

  it('renders environment variables section', () => {
    const detail = createContainer()
    detail.config = {
      ...createContainer().config,
      env: ['PATH=/usr/bin', 'NODE_ENV=production'],
    }
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain("Variables d'environnement")
  })
})

describe('Card-based layout', () => {
  it('renders all expected section cards', () => {
    const wrapper = mountComponent(createContainer())
    const cards = wrapper.findAll('.el-card')
    // general, state, config, host, ports, volumes, network, env = 8 cards
    expect(cards.length).toBeGreaterThanOrEqual(8)
  })

  it('renders header color classes', () => {
    const wrapper = mountComponent(createContainer())
    const html = wrapper.html()
    expect(html).toContain('header-blue')
    expect(html).toContain('header-orange')
    expect(html).toContain('header-purple')
    expect(html).toContain('header-green')
  })
})

describe('formatBytes (via component)', () => {
  it('formats bytes correctly through disk usage section', () => {
    const detail = createContainer()
    detail.size_rw = 512
    detail.size_root_fs = 1048576
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('512 B')
    expect(wrapper.text()).toContain('1.0 MB')
  })

  it('formats GB values', () => {
    const detail = createContainer()
    detail.size_rw = 1073741824
    detail.size_root_fs = 2147483648
    const wrapper = mountComponent(detail)
    expect(wrapper.text()).toContain('1.0 GB')
    expect(wrapper.text()).toContain('2.0 GB')
  })
})
