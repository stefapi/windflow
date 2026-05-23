/**
 * ContainerConfigTab.vue Unit Tests — STORY-024 + STORY-027 + STORY-028
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElMessageBox } from 'element-plus'
import ContainerConfigTab from '@/components/ContainerConfigTab.vue'
import type { ContainerDetail } from '@/types/api'

// Spy on ElMessageBox.confirm to avoid modal blocking in tests
vi.spyOn(ElMessageBox, 'confirm').mockResolvedValue(undefined)

// Mock API methods
const mockUpdateRestartPolicy = vi.fn()
const mockUpdateResources = vi.fn()
const mockRecreate = vi.fn()
const mockConnectNetwork = vi.fn()
const mockDisconnectNetwork = vi.fn()
const mockNetworksList = vi.fn()

vi.mock('@/services/api', () => ({
  containersApi: {
    updateRestartPolicy: (...args: unknown[]) => mockUpdateRestartPolicy(...args),
    updateResources: (...args: unknown[]) => mockUpdateResources(...args),
    recreate: (...args: unknown[]) => mockRecreate(...args),
    connectNetwork: (...args: unknown[]) => mockConnectNetwork(...args),
    disconnectNetwork: (...args: unknown[]) => mockDisconnectNetwork(...args),
  },
  networksApi: {
    list: (...args: unknown[]) => mockNetworksList(...args),
  },
}))

// Mock useSecretMasker
vi.mock('@/composables/useSecretMasker', () => ({
  isSecretKey: (key: string) => /password|secret|token|key/i.test(key),
  useSecretMasker: () => ({
    isRevealed: () => false,
    toggleReveal: () => {},
    getDisplayValue: (key: string, value: string) => value,
    revealedKeys: [],
  }),
}))

// Mock formatBytes
vi.mock('@/utils/format', () => ({
  formatBytes: (bytes: number) => {
    if (bytes >= 1073741824) return `${(bytes / 1073741824).toFixed(1)} GB`
    if (bytes >= 1048576) return `${(bytes / 1048576).toFixed(0)} MB`
    return `${bytes} B`
  },
}))

const baseDetail: ContainerDetail = {
  id: 'abc123',
  name: 'test-container',
  created: '2025-01-01T00:00:00Z',
  path: '/usr/bin/app',
  args: [],
  state: { status: 'running', running: true, paused: false, restarting: false, oom_killed: false, dead: false, exit_code: null, error: null, started_at: '2025-01-01T00:00:00Z', finished_at: null, health: null },
  image: 'nginx:latest',
  config: {
    hostname: null,
    domainname: null,
    user: null,
    attach_stdin: null,
    attach_stdout: null,
    attach_stderr: null,
    tty: null,
    open_stdin: null,
    stdin_once: null,
    env: ['PATH=/usr/bin', 'NODE_ENV=production', 'DB_PASSWORD=secret123'],
    cmd: null,
    entrypoint: null,
    image: null,
    working_dir: null,
    labels: { 'com.docker.compose.project': 'my-stack', version: '1.0' },
    stop_signal: null,
    stop_timeout: null,
  },
  host_config: {
    binds: null,
    container_id_file: null,
    log_config: null,
    network_mode: null,
    port_bindings: {
      '80/tcp': [{ HostIp: '0.0.0.0', HostPort: '8080' }],
      '443/tcp': [{ HostIp: '', HostPort: '8443' }],
    },
    restart_policy: { name: 'always', maximum_retry_count: null },
    auto_remove: null,
    volume_driver: null,
    volumes_from: null,
    cap_add: ['NET_ADMIN', 'SYS_PTRACE'],
    cap_drop: ['SETUID'],
    dns: null,
    privileged: true,
    readonly_rootfs: false,
    security_opt: null,
    shm_size: null,
    runtime: null,
    resources: { memory: 536870912, memory_reservation: null, memory_swap: null, cpu_shares: 1024, cpu_period: null, cpu_quota: null, cpus: null, cpuset_cpus: null, pids_limit: 100 },
  },
  network_settings: {
    networks: {
      bridge: { ip_address: '172.17.0.2', gateway: '172.17.0.1', mac_address: '02:42:ac:11:00:02', network_id: 'net1', endpoint_id: 'ep1', ipv6_gateway: null, global_ipv6_address: null, ip_prefix_len: 16, driver: 'bridge' },
      'my-custom-network': { ip_address: '192.168.1.10', gateway: '192.168.1.1', mac_address: '02:42:c0:a8:01:0a', network_id: 'net2', endpoint_id: 'ep2', ipv6_gateway: null, global_ipv6_address: null, ip_prefix_len: 24, driver: 'bridge' },
    },
  },
  mounts: [
    { Type: 'volume', Source: 'my-vol', Destination: '/app/data', RW: true },
    { Type: 'bind', Source: '/host/path', Destination: '/container/path', RW: false },
  ],
  size_rw: null,
  size_root_fs: null,
}

describe('ContainerConfigTab.vue', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockUpdateRestartPolicy.mockResolvedValue({ data: { warnings: [] } })
    mockUpdateResources.mockResolvedValue({ data: { warnings: [] } })
    mockRecreate.mockResolvedValue({
      data: {
        success: true,
        message: 'Container recréé',
        old_container_id: 'abc123',
        new_container_id: 'new456',
        container: {},
        warnings: [],
      },
    })
    mockConnectNetwork.mockResolvedValue({ data: undefined })
    mockDisconnectNetwork.mockResolvedValue({ data: undefined })
    mockNetworksList.mockResolvedValue({
      data: [
        { id: 'net1', name: 'bridge', driver: 'bridge', scope: 'local', internal: false, attachable: false, ingress: false, created: '2025-01-01', subnet: '172.17.0.0/16', gateway: '172.17.0.1' },
        { id: 'net2', name: 'my-custom-network', driver: 'bridge', scope: 'local', internal: false, attachable: false, ingress: false, created: '2025-01-01', subnet: '192.168.1.0/24', gateway: '192.168.1.1' },
        { id: 'net3', name: 'other-network', driver: 'bridge', scope: 'local', internal: false, attachable: false, ingress: false, created: '2025-01-01', subnet: '10.0.0.0/24', gateway: '10.0.0.1' },
      ],
    })
  })

  const mountComponent = async (overrides: Record<string, unknown> = {}) => {
    const props = {
      detail: baseDetail,
      ...overrides,
    }

    const wrapper = mount(ContainerConfigTab, {
      global: {
        plugins: [ElementPlus],
        stubs: {
          'el-card': { template: '<div class="el-card-stub"><slot name="header" /><slot /></div>', props: ['shadow', 'class'] },
          'el-table': { template: '<div class="el-table-stub"><slot /></div>', props: ['data'] },
          'el-table-column': { template: '<div class="el-table-column-stub" />', props: ['label', 'prop', 'width', 'minWidth'] },
          'el-input': { template: '<input class="el-input-stub" />', props: ['modelValue', 'type', 'placeholder', 'size'] },
          'el-input-number': { template: '<input class="el-input-number-stub" type="number" />', props: ['modelValue', 'min', 'max', 'size'] },
          'el-select': { template: '<select class="el-select-stub"><slot /></select>', props: ['modelValue', 'size'] },
          'el-option': { template: '<option class="el-option-stub" />', props: ['label', 'value'] },
          'el-button': { template: '<button class="el-button-stub" @click="$emit(\'click\')"><slot /></button>', props: ['type', 'size', 'loading', 'disabled', 'icon', 'circle'] },
          'el-alert': { template: '<div class="el-alert-stub"><slot /></div>', props: ['type', 'closable', 'showIcon'] },
          'el-descriptions': { template: '<div class="el-descriptions-stub"><slot /></div>', props: ['column', 'border', 'size'] },
          'el-descriptions-item': { template: '<div class="el-descriptions-item-stub"><slot /></div>', props: ['label'] },
          'el-icon': { template: '<i class="el-icon-stub"><slot /></i>' },
          'el-form': { template: '<form class="el-form-stub"><slot /></form>' },
          'el-form-item': { template: '<div class="el-form-item-stub"><slot /></div>', props: ['label'] },
          'el-checkbox': { template: '<input class="el-checkbox-stub" type="checkbox" />', props: ['modelValue'] },
          'el-switch': { template: '<input class="el-switch-stub" type="checkbox" />', props: ['modelValue'] },
          'el-tag': { template: '<span class="el-tag-stub"><slot /></span>', props: ['closable', 'size', 'type'] },
        },
      },
      props,
    })

    await flushPromises()
    return wrapper
  }

  describe('Rendering — 6 cards', () => {
    it('should mount successfully', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.exists()).toBe(true)
    })

    it('should render the config-tab container', async () => {
      const wrapper = await mountComponent()
      expect(wrapper.find('.config-tab').exists()).toBe(true)
    })

    it('should render 9 config cards', async () => {
      const wrapper = await mountComponent()
      const cards = wrapper.findAll('.el-card-stub')
      expect(cards.length).toBe(9)
    })

    it('should render card headers with correct titles', async () => {
      const wrapper = await mountComponent()
      const text = wrapper.text()
      expect(text).toContain('Variables d\'environnement')
      expect(text).toContain('Labels')
      expect(text).toContain('Image')
      expect(text).toContain('Ports')
      expect(text).toContain('Restart Policy')
      expect(text).toContain('Resource Limits')
      expect(text).toContain('Volumes')
      expect(text).toContain('Sécurité')
      expect(text).toContain('Réseaux')
    })

    it('should render Image card with correct header', async () => {
      const wrapper = await mountComponent()
      const text = wrapper.text()
      expect(text).toContain('Image')
    })

    it('should render Ports card with correct header', async () => {
      const wrapper = await mountComponent()
      const text = wrapper.text()
      expect(text).toContain('Ports')
    })

    it('should render warning alerts for image and ports sections', async () => {
      const wrapper = await mountComponent()
      const alerts = wrapper.findAll('.el-alert-stub')
      // 7 alerts total: env, labels, image, ports, volumes, security, networks (info)
      expect(alerts.length).toBe(7)
      const allText = alerts.map((a) => a.text()).join(' ')
      expect(allText).toContain('image')
      expect(allText).toContain('ports')
      expect(allText).toContain('redémarrage')
    })
  })

  describe('Pre-fill from detail', () => {
    it('should pre-fill env vars from detail', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { envVars: { key: string; value: string }[] }
      expect(vm.envVars.length).toBe(3)
      expect(vm.envVars[0]).toEqual({ key: 'PATH', value: '/usr/bin' })
      expect(vm.envVars[1]).toEqual({ key: 'NODE_ENV', value: 'production' })
      expect(vm.envVars[2]).toEqual({ key: 'DB_PASSWORD', value: 'secret123' })
    })

    it('should pre-fill labels from detail', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { labels: { key: string; value: string }[] }
      expect(vm.labels.length).toBe(2)
      expect(vm.labels).toContainEqual({ key: 'com.docker.compose.project', value: 'my-stack' })
      expect(vm.labels).toContainEqual({ key: 'version', value: '1.0' })
    })

    it('should pre-fill image input from detail.image', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { newImage: string }
      expect(vm.newImage).toBe('nginx:latest')
    })

    it('should pre-fill port bindings from detail.host_config.port_bindings', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: { hostIp: string; hostPort: number | ''; containerPort: string; protocol: string }[]
      }
      expect(vm.portBindings.length).toBe(2)
      expect(vm.portBindings[0]).toMatchObject({ hostIp: '0.0.0.0', hostPort: 8080, containerPort: '80', protocol: 'tcp' })
      expect(vm.portBindings[1]).toMatchObject({ hostIp: '0.0.0.0', hostPort: 8443, containerPort: '443', protocol: 'tcp' })
    })

    it('should handle empty port_bindings', async () => {
      const detailNoPorts: ContainerDetail = {
        ...baseDetail,
        host_config: { ...baseDetail.host_config!, port_bindings: null },
      }
      const wrapper = await mountComponent({ detail: detailNoPorts })
      const vm = wrapper.vm as unknown as { portBindings: unknown[] }
      expect(vm.portBindings.length).toBe(0)
    })

    it('should pre-fill restart policy from detail', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { restartPolicyName: string; maxRetryCount: number }
      expect(vm.restartPolicyName).toBe('always')
    })

    it('should pre-fill resources from detail', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { memoryValue: number; memoryUnit: string; cpuShares: number; pidsLimit: number }
      expect(vm.memoryValue).toBe(512)
      expect(vm.memoryUnit).toBe('MB')
      expect(vm.cpuShares).toBe(1024)
      expect(vm.pidsLimit).toBe(100)
    })

    it('should handle GB conversion for memory', async () => {
      const detailWithGB: ContainerDetail = {
        ...baseDetail,
        host_config: {
          ...baseDetail.host_config!,
          resources: { ...baseDetail.host_config!.resources!, memory: 2147483648 },
        },
      }
      const wrapper = await mountComponent({ detail: detailWithGB })
      const vm = wrapper.vm as unknown as { memoryValue: number; memoryUnit: string }
      expect(vm.memoryValue).toBe(2)
      expect(vm.memoryUnit).toBe('GB')
    })
  })

  describe('Env Vars — add/remove', () => {
    it('should add an empty env var row', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { envVars: { key: string; value: string }[]; addEnvVar: () => void }
      const initialCount = vm.envVars.length
      vm.addEnvVar()
      await flushPromises()
      expect(vm.envVars.length).toBe(initialCount + 1)
      expect(vm.envVars[vm.envVars.length - 1]).toEqual({ key: '', value: '' })
    })

    it('should remove an env var row', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { envVars: { key: string; value: string }[]; removeEnvVar: (i: number) => void }
      const initialCount = vm.envVars.length
      vm.removeEnvVar(0)
      await flushPromises()
      expect(vm.envVars.length).toBe(initialCount - 1)
    })
  })

  describe('Labels — add/remove', () => {
    it('should add an empty label row', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { labels: { key: string; value: string }[]; addLabel: () => void }
      const initialCount = vm.labels.length
      vm.addLabel()
      await flushPromises()
      expect(vm.labels.length).toBe(initialCount + 1)
      expect(vm.labels[vm.labels.length - 1]).toEqual({ key: '', value: '' })
    })

    it('should remove a label row', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { labels: { key: string; value: string }[]; removeLabel: (i: number) => void }
      const initialCount = vm.labels.length
      vm.removeLabel(0)
      await flushPromises()
      expect(vm.labels.length).toBe(initialCount - 1)
    })
  })

  describe('Ports — add/remove', () => {
    it('should add a new port binding row', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { portBindings: PortBindingRow[]; addPortBinding: () => void }
      const initialCount = vm.portBindings.length
      vm.addPortBinding()
      await flushPromises()
      expect(vm.portBindings.length).toBe(initialCount + 1)
      expect(vm.portBindings[vm.portBindings.length - 1]).toEqual({
        hostIp: '0.0.0.0',
        hostPort: '',
        containerPort: '',
        protocol: 'tcp',
      })
    })

    it('should remove a port binding row', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { portBindings: PortBindingRow[]; removePortBinding: (i: number) => void }
      const initialCount = vm.portBindings.length
      vm.removePortBinding(0)
      await flushPromises()
      expect(vm.portBindings.length).toBe(initialCount - 1)
    })
  })

  describe('Ports — validation', () => {
    it('should reject host port below 1', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: PortBindingRow[]
        validatePortBindings: () => string | null
      }
      vm.portBindings[0].hostPort = 0
      const error = vm.validatePortBindings()
      expect(error).toContain('Host port invalide')
    })

    it('should reject host port above 65535', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: PortBindingRow[]
        validatePortBindings: () => string | null
      }
      vm.portBindings[0].hostPort = 70000
      const error = vm.validatePortBindings()
      expect(error).toContain('Host port invalide')
    })

    it('should reject container port below 1', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: PortBindingRow[]
        validatePortBindings: () => string | null
      }
      vm.portBindings[0].containerPort = 0
      const error = vm.validatePortBindings()
      expect(error).toContain('Container port invalide')
    })

    it('should reject container port above 65535', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: PortBindingRow[]
        validatePortBindings: () => string | null
      }
      vm.portBindings[0].containerPort = 70000
      const error = vm.validatePortBindings()
      expect(error).toContain('Container port invalide')
    })

    it('should reject duplicate hostIp:hostPort combinations', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: PortBindingRow[]
        validatePortBindings: () => string | null
      }
      vm.portBindings[1].hostIp = '0.0.0.0'
      vm.portBindings[1].hostPort = 8080
      const error = vm.validatePortBindings()
      expect(error).toContain('Doublon')
    })

    it('should return null for valid port bindings', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { validatePortBindings: () => string | null }
      const error = vm.validatePortBindings()
      expect(error).toBeNull()
    })
  })

  describe('Warning alerts for recreation', () => {
    it('should render warning alerts for env vars and labels sections', async () => {
      const wrapper = await mountComponent()
      const alerts = wrapper.findAll('.el-alert-stub')
      expect(alerts.length).toBe(7)
      expect(alerts[0].text()).toContain('variables d\'environnement')
      expect(alerts[1].text()).toContain('labels')
    })
  })

  describe('Image — update', () => {
    it('should call recreate API when updating image', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { newImage: string; updateImage: () => Promise<void> }
      vm.newImage = 'nginx:alpine'
      await vm.updateImage()
      await flushPromises()

      expect(mockRecreate).toHaveBeenCalledWith('abc123', {
        image: 'nginx:alpine',
        pull_image: false,
      })
    })

    it('should include pull_image in recreate payload when checkbox is checked', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        newImage: string
        pullImage: boolean
        updateImage: () => Promise<void>
      }
      vm.newImage = 'nginx:alpine'
      vm.pullImage = true
      await vm.updateImage()
      await flushPromises()

      expect(mockRecreate).toHaveBeenCalledWith('abc123', {
        image: 'nginx:alpine',
        pull_image: true,
      })
    })

    it('should emit recreate-success event with new container id', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        newImage: string
        updateImage: () => Promise<void>
      }
      vm.newImage = 'nginx:alpine'
      await vm.updateImage()
      await flushPromises()

      expect(wrapper.emitted('recreate-success')).toBeTruthy()
      expect(wrapper.emitted('recreate-success')![0]).toEqual(['new456'])
    })

    it('should show error message on API failure', async () => {
      mockRecreate.mockRejectedValue(new Error('Image not found'))
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { newImage: string; updateImage: () => Promise<void> }
      vm.newImage = 'nginx:alpine'
      await vm.updateImage()
      await flushPromises()

      expect(mockRecreate).toHaveBeenCalled()
    })

    it('should not call API when image is empty', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { newImage: string; updateImage: () => Promise<void> }
      vm.newImage = '   '
      await vm.updateImage()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })

    it('should not call API when detail is null', async () => {
      const wrapper = await mountComponent({ detail: null })
      const vm = wrapper.vm as unknown as { updateImage: () => Promise<void> }
      await vm.updateImage()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })
  })

  describe('Ports — apply', () => {
    it('should call recreate API with correct port_bindings payload', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyPortBindings: () => Promise<void> }
      await vm.applyPortBindings()
      await flushPromises()

      expect(mockRecreate).toHaveBeenCalledWith('abc123', {
        port_bindings: {
          '80/tcp': [{ HostIp: '0.0.0.0', HostPort: '8080' }],
          '443/tcp': [{ HostIp: '0.0.0.0', HostPort: '8443' }],
        },
      })
    })

    it('should emit recreate-success event after applying ports', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyPortBindings: () => Promise<void> }
      await vm.applyPortBindings()
      await flushPromises()

      expect(wrapper.emitted('recreate-success')).toBeTruthy()
      expect(wrapper.emitted('recreate-success')![0]).toEqual(['new456'])
    })

    it('should show validation error for invalid port', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        portBindings: PortBindingRow[]
        applyPortBindings: () => Promise<void>
      }
      vm.portBindings[0].hostPort = 70000
      await vm.applyPortBindings()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })

    it('should not call API when detail is null', async () => {
      const wrapper = await mountComponent({ detail: null })
      const vm = wrapper.vm as unknown as { applyPortBindings: () => Promise<void> }
      await vm.applyPortBindings()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })
  })

  describe('Restart Policy — apply', () => {
    it('should call updateRestartPolicy API with correct params', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        restartPolicyName: string
        applyRestartPolicy: () => Promise<void>
      }
      vm.restartPolicyName = 'unless-stopped'
      await vm.applyRestartPolicy()
      await flushPromises()

      expect(mockUpdateRestartPolicy).toHaveBeenCalledWith('abc123', { name: 'unless-stopped' })
    })

    it('should include maximum_retry_count when policy is on-failure', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        restartPolicyName: string
        maxRetryCount: number
        applyRestartPolicy: () => Promise<void>
      }
      vm.restartPolicyName = 'on-failure'
      vm.maxRetryCount = 5
      await vm.applyRestartPolicy()
      await flushPromises()

      expect(mockUpdateRestartPolicy).toHaveBeenCalledWith('abc123', { name: 'on-failure', maximum_retry_count: 5 })
    })

    it('should not call API when detail is null', async () => {
      const wrapper = await mountComponent({ detail: null })
      const vm = wrapper.vm as unknown as { applyRestartPolicy: () => Promise<void> }
      await vm.applyRestartPolicy()
      await flushPromises()

      expect(mockUpdateRestartPolicy).not.toHaveBeenCalled()
    })

    it('should handle API error gracefully', async () => {
      mockUpdateRestartPolicy.mockRejectedValue(new Error('Network error'))
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyRestartPolicy: () => Promise<void> }
      await vm.applyRestartPolicy()
      await flushPromises()

      expect(mockUpdateRestartPolicy).toHaveBeenCalled()
    })
  })

  describe('Resources — apply', () => {
    it('should call updateResources API with correct params (MB)', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        memoryValue: number
        memoryUnit: string
        cpuShares: number
        pidsLimit: number
        applyResources: () => Promise<void>
      }
      vm.memoryValue = 256
      vm.memoryUnit = 'MB'
      vm.cpuShares = 512
      vm.pidsLimit = 50
      await vm.applyResources()
      await flushPromises()

      expect(mockUpdateResources).toHaveBeenCalledWith('abc123', {
        memory_limit: 256 * 1024 * 1024,
        cpu_shares: 512,
        pids_limit: 50,
      })
    })

    it('should call updateResources API with correct params (GB)', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        memoryValue: number
        memoryUnit: string
        cpuShares: number
        pidsLimit: number
        applyResources: () => Promise<void>
      }
      vm.memoryValue = 2
      vm.memoryUnit = 'GB'
      vm.cpuShares = 0
      vm.pidsLimit = -1
      await vm.applyResources()
      await flushPromises()

      expect(mockUpdateResources).toHaveBeenCalledWith('abc123', {
        memory_limit: 2 * 1024 * 1024 * 1024,
        cpu_shares: undefined,
        pids_limit: -1,
      })
    })

    it('should not call API when detail is null', async () => {
      const wrapper = await mountComponent({ detail: null })
      const vm = wrapper.vm as unknown as { applyResources: () => Promise<void> }
      await vm.applyResources()
      await flushPromises()

      expect(mockUpdateResources).not.toHaveBeenCalled()
    })

    it('should handle API error gracefully', async () => {
      mockUpdateResources.mockRejectedValue(new Error('Network error'))
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyResources: () => Promise<void> }
      await vm.applyResources()
      await flushPromises()

      expect(mockUpdateResources).toHaveBeenCalled()
    })
  })

  describe('Loading state', () => {
    it('should have loadingRestart ref', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { loadingRestart: boolean }
      expect(vm.loadingRestart).toBe(false)
    })

    it('should have loadingResources ref', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { loadingResources: boolean }
      expect(vm.loadingResources).toBe(false)
    })

    it('should have loadingRecreate ref', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { loadingRecreate: boolean }
      expect(vm.loadingRecreate).toBe(false)
    })
  })

  describe('Edge cases', () => {
    it('should handle null detail gracefully', async () => {
      const wrapper = await mountComponent({ detail: null })
      expect(wrapper.exists()).toBe(true)
      const vm = wrapper.vm as unknown as { envVars: unknown[]; labels: unknown[]; portBindings: unknown[] }
      expect(vm.envVars.length).toBe(0)
      expect(vm.labels.length).toBe(0)
      expect(vm.portBindings.length).toBe(0)
    })

    it('should handle detail with missing config', async () => {
      const minimalDetail = {
        id: 'abc123',
        name: 'test',
        created: '',
        path: '',
        args: [],
        state: { status: 'running' },
        image: '',
        config: null as unknown,
        host_config: null as unknown,
        network_settings: { networks: {} },
        mounts: [],
        size_rw: null,
        size_root_fs: null,
      }
      const wrapper = await mountComponent({ detail: minimalDetail })
      expect(wrapper.exists()).toBe(true)
    })

    it('should handle detail with no host_config', async () => {
      const minimalDetail = {
        ...baseDetail,
        host_config: null,
      }
      const wrapper = await mountComponent({ detail: minimalDetail })
      expect(wrapper.exists()).toBe(true)
      const vm = wrapper.vm as unknown as { portBindings: unknown[] }
      expect(vm.portBindings.length).toBe(0)
    })

    it('should handle env vars without equal sign', async () => {
      const detailWithBadEnv = {
        ...baseDetail,
        config: { ...baseDetail.config!, env: ['NOEQUALSSIGN'] },
      }
      const wrapper = await mountComponent({ detail: detailWithBadEnv })
      const vm = wrapper.vm as unknown as { envVars: { key: string; value: string }[] }
      expect(vm.envVars.length).toBe(1)
      expect(vm.envVars[0]).toEqual({ key: 'NOEQUALSSIGN', value: '' })
    })

    it('should handle empty labels', async () => {
      const detailNoLabels = {
        ...baseDetail,
        config: { ...baseDetail.config!, labels: {} },
      }
      const wrapper = await mountComponent({ detail: detailNoLabels })
      const vm = wrapper.vm as unknown as { labels: unknown[] }
      expect(vm.labels.length).toBe(0)
    })

    it('should handle zero memory resource', async () => {
      const detailNoMemory = {
        ...baseDetail,
        host_config: {
          ...baseDetail.host_config!,
          resources: { ...baseDetail.host_config!.resources!, memory: 0 },
        },
      }
      const wrapper = await mountComponent({ detail: detailNoMemory })
      const vm = wrapper.vm as unknown as { memoryValue: number; memoryUnit: string }
      expect(vm.memoryValue).toBe(0)
      expect(vm.memoryUnit).toBe('MB')
    })
  })

  describe('Networks — rendering', () => {
    it('should render Networks card with correct header', async () => {
      const wrapper = await mountComponent()
      const text = wrapper.text()
      expect(text).toContain('Réseaux')
    })

    it('should render info alert for networks section', async () => {
      const wrapper = await mountComponent()
      const alerts = wrapper.findAll('.el-alert-stub')
      const infoAlert = alerts.find((a) => a.text().includes('redémarrage'))
      expect(infoAlert).toBeTruthy()
    })

    it('should display connected networks in table', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { connectedNetworks: { name: string; ip_address: string }[] }
      expect(vm.connectedNetworks.length).toBe(2)
      expect(vm.connectedNetworks[0].name).toBe('bridge')
      expect(vm.connectedNetworks[1].name).toBe('my-custom-network')
    })
  })

  describe('Networks — loading available networks', () => {
    it('should load available networks on mount', async () => {
      await mountComponent()
      await flushPromises()
      expect(mockNetworksList).toHaveBeenCalled()
    })

    it('should filter out already connected networks from select', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { filteredAvailableNetworks: { name: string }[] }
      // bridge and my-custom-network are connected, so only other-network should be available
      expect(vm.filteredAvailableNetworks.length).toBe(1)
      expect(vm.filteredAvailableNetworks[0].name).toBe('other-network')
    })

    it('should handle empty available networks list', async () => {
      mockNetworksList.mockResolvedValue({ data: [] })
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { filteredAvailableNetworks: unknown[] }
      expect(vm.filteredAvailableNetworks.length).toBe(0)
    })

    it('should handle networks API failure gracefully', async () => {
      mockNetworksList.mockRejectedValue(new Error('Network error'))
      const wrapper = await mountComponent()
      await flushPromises()
      expect(wrapper.exists()).toBe(true)
    })
  })

  describe('Networks — connect', () => {
    it('should call connectNetwork API when Connect button is clicked', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { selectedNetwork: string; connectNetwork: () => Promise<void> }
      vm.selectedNetwork = 'net3'
      await vm.connectNetwork()
      await flushPromises()

      expect(mockConnectNetwork).toHaveBeenCalledWith('abc123', { network_id: 'net3' })
    })

    it('should emit network-changed after successful connect', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { selectedNetwork: string; connectNetwork: () => Promise<void> }
      vm.selectedNetwork = 'net3'
      await vm.connectNetwork()
      await flushPromises()

      expect(wrapper.emitted('network-changed')).toBeTruthy()
    })

    it('should not call API when no network is selected', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { selectedNetwork: string; connectNetwork: () => Promise<void> }
      vm.selectedNetwork = ''
      await vm.connectNetwork()
      await flushPromises()

      expect(mockConnectNetwork).not.toHaveBeenCalled()
    })

    it('should show error message on connect API failure', async () => {
      mockConnectNetwork.mockRejectedValue(new Error('Network not found'))
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { selectedNetwork: string; connectNetwork: () => Promise<void> }
      vm.selectedNetwork = 'net3'
      await vm.connectNetwork()
      await flushPromises()

      expect(mockConnectNetwork).toHaveBeenCalled()
    })
  })

  describe('Networks — disconnect', () => {
    it('should call disconnectNetwork API when Disconnect button is clicked', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { disconnectNetwork: (name: string) => Promise<void> }
      await vm.disconnectNetwork('bridge')
      await flushPromises()

      expect(mockDisconnectNetwork).toHaveBeenCalledWith('abc123', { network_id: 'bridge' })
    })

    it('should emit network-changed after successful disconnect', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { disconnectNetwork: (name: string) => Promise<void> }
      await vm.disconnectNetwork('bridge')
      await flushPromises()

      expect(wrapper.emitted('network-changed')).toBeTruthy()
    })

    it('should show error message on disconnect API failure', async () => {
      mockDisconnectNetwork.mockRejectedValue(new Error('Cannot disconnect'))
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { disconnectNetwork: (name: string) => Promise<void> }
      await vm.disconnectNetwork('bridge')
      await flushPromises()

      expect(mockDisconnectNetwork).toHaveBeenCalled()
    })
  })

  describe('Networks — loading states', () => {
    it('should disable connect button while loading', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { loadingConnect: boolean }
      expect(vm.loadingConnect).toBe(false)
    })

    it('should disable disconnect button while loading', async () => {
      const wrapper = await mountComponent()
      await flushPromises()
      const vm = wrapper.vm as unknown as { loadingDisconnect: Record<string, boolean> }
      expect(vm.loadingDisconnect['bridge']).toBeFalsy()
    })
  })

  describe('Networks — edge cases', () => {
    it('should handle detail null without error', async () => {
      const wrapper = await mountComponent({ detail: null })
      await flushPromises()
      const vm = wrapper.vm as unknown as { connectedNetworks: unknown[] }
      expect(vm.connectedNetworks.length).toBe(0)
    })

    it('should handle empty network_settings', async () => {
      const detailNoNetworks = {
        ...baseDetail,
        network_settings: { networks: {} },
      }
      const wrapper = await mountComponent({ detail: detailNoNetworks })
      await flushPromises()
      const vm = wrapper.vm as unknown as { connectedNetworks: unknown[] }
      expect(vm.connectedNetworks.length).toBe(0)
    })
  })

  describe('Volumes — rendering', () => {
    it('should render Volumes card with correct header', async () => {
      const wrapper = await mountComponent()
      const text = wrapper.text()
      expect(text).toContain('Volumes')
    })

    it('should render warning alert for volumes section', async () => {
      const wrapper = await mountComponent()
      const alerts = wrapper.findAll('.el-alert-stub')
      const volAlert = alerts.find((a) => a.text().includes('volumes'))
      expect(volAlert).toBeTruthy()
    })
  })

  describe('Volumes — pre-fill from detail', () => {
    it('should populate volume entries from detail.mounts', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        volumeEntries: { type: string; source: string; destination: string; mode: string }[]
      }
      expect(vm.volumeEntries.length).toBe(2)
      expect(vm.volumeEntries[0]).toEqual({ type: 'volume', source: 'my-vol', destination: '/app/data', mode: 'rw' })
      expect(vm.volumeEntries[1]).toEqual({ type: 'bind', source: '/host/path', destination: '/container/path', mode: 'ro' })
    })

    it('should handle null mounts gracefully', async () => {
      const detailNoMounts = { ...baseDetail, mounts: [] }
      const wrapper = await mountComponent({ detail: detailNoMounts })
      const vm = wrapper.vm as unknown as { volumeEntries: unknown[] }
      expect(vm.volumeEntries.length).toBe(0)
    })

    it('should parse binds when mounts is empty', async () => {
      const detailWithBinds: ContainerDetail = {
        ...baseDetail,
        mounts: [],
        host_config: {
          ...baseDetail.host_config!,
          binds: ['/host/data:/container/data:ro', '/host/logs:/container/logs:rw'],
        },
      }
      const wrapper = await mountComponent({ detail: detailWithBinds })
      const vm = wrapper.vm as unknown as {
        volumeEntries: { type: string; source: string; destination: string; mode: string }[]
      }
      expect(vm.volumeEntries.length).toBe(2)
      expect(vm.volumeEntries[0]).toEqual({ type: 'bind', source: '/host/data', destination: '/container/data', mode: 'ro' })
      expect(vm.volumeEntries[1]).toEqual({ type: 'bind', source: '/host/logs', destination: '/container/logs', mode: 'rw' })
    })
  })

  describe('Volumes — add/remove', () => {
    it('should add a new volume entry', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        volumeEntries: { type: string; source: string; destination: string; mode: string }[]
        addVolumeEntry: () => void
      }
      const initialCount = vm.volumeEntries.length
      vm.addVolumeEntry()
      await flushPromises()
      expect(vm.volumeEntries.length).toBe(initialCount + 1)
      expect(vm.volumeEntries[vm.volumeEntries.length - 1]).toEqual({ type: 'bind', source: '', destination: '', mode: 'rw' })
    })

    it('should remove a volume entry', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        volumeEntries: unknown[]
        removeVolumeEntry: (i: number) => void
      }
      const initialCount = vm.volumeEntries.length
      vm.removeVolumeEntry(0)
      await flushPromises()
      expect(vm.volumeEntries.length).toBe(initialCount - 1)
    })
  })

  describe('Volumes — validation', () => {
    it('should reject empty volume destination', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        volumeEntries: { type: string; source: string; destination: string; mode: string }[]
        validateVolumes: () => string | null
      }
      vm.volumeEntries[0].destination = '   '
      const error = vm.validateVolumes()
      expect(error).toContain('destination')
    })

    it('should reject duplicate volume destinations', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        volumeEntries: { type: string; source: string; destination: string; mode: string }[]
        validateVolumes: () => string | null
      }
      vm.volumeEntries[1].destination = '/app/data'
      const error = vm.validateVolumes()
      expect(error).toContain('Doublon')
    })

    it('should return null for valid volumes', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { validateVolumes: () => string | null }
      const error = vm.validateVolumes()
      expect(error).toBeNull()
    })
  })

  describe('Security — rendering', () => {
    it('should render Security card with correct header', async () => {
      const wrapper = await mountComponent()
      const text = wrapper.text()
      expect(text).toContain('Sécurité')
    })

    it('should render warning alert for security section', async () => {
      const wrapper = await mountComponent()
      const alerts = wrapper.findAll('.el-alert-stub')
      const secAlert = alerts.find((a) => a.text().includes('nécessitent de recréer'))
      expect(secAlert).toBeTruthy()
    })
  })

  describe('Security — pre-fill from detail', () => {
    it('should populate security fields from host_config', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        privileged: boolean
        readonlyRootfs: boolean
        capAdd: string[]
        capDrop: string[]
      }
      expect(vm.privileged).toBe(true)
      expect(vm.readonlyRootfs).toBe(false)
      expect(vm.capAdd).toEqual(['NET_ADMIN', 'SYS_PTRACE'])
      expect(vm.capDrop).toEqual(['SETUID'])
    })

    it('should handle null security fields gracefully', async () => {
      const detailNoSec: ContainerDetail = {
        ...baseDetail,
        host_config: {
          ...baseDetail.host_config!,
          cap_add: null,
          cap_drop: null,
          privileged: null,
          readonly_rootfs: null,
        },
      }
      const wrapper = await mountComponent({ detail: detailNoSec })
      const vm = wrapper.vm as unknown as {
        privileged: boolean
        readonlyRootfs: boolean
        capAdd: string[]
        capDrop: string[]
      }
      expect(vm.privileged).toBe(false)
      expect(vm.readonlyRootfs).toBe(false)
      expect(vm.capAdd).toEqual([])
      expect(vm.capDrop).toEqual([])
    })
  })

  describe('Security — capabilities add/remove', () => {
    it('should add a cap_add tag', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        capAdd: string[]
        newCapAdd: string
        addCapAdd: () => void
      }
      vm.newCapAdd = 'NET_RAW'
      vm.addCapAdd()
      await flushPromises()
      expect(vm.capAdd).toContain('NET_RAW')
      expect(vm.newCapAdd).toBe('')
    })

    it('should not add duplicate cap_add', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        capAdd: string[]
        newCapAdd: string
        addCapAdd: () => void
      }
      const initialLength = vm.capAdd.length
      vm.newCapAdd = 'NET_ADMIN'
      vm.addCapAdd()
      await flushPromises()
      expect(vm.capAdd.length).toBe(initialLength)
    })

    it('should remove a cap_add tag', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        capAdd: string[]
        removeCapAdd: (i: number) => void
      }
      const initialLength = vm.capAdd.length
      vm.removeCapAdd(0)
      await flushPromises()
      expect(vm.capAdd.length).toBe(initialLength - 1)
    })

    it('should add a cap_drop tag', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        capDrop: string[]
        newCapDrop: string
        addCapDrop: () => void
      }
      vm.newCapDrop = 'SETGID'
      vm.addCapDrop()
      await flushPromises()
      expect(vm.capDrop).toContain('SETGID')
      expect(vm.newCapDrop).toBe('')
    })

    it('should remove a cap_drop tag', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        capDrop: string[]
        removeCapDrop: (i: number) => void
      }
      const initialLength = vm.capDrop.length
      vm.removeCapDrop(0)
      await flushPromises()
      expect(vm.capDrop.length).toBe(initialLength - 1)
    })
  })

  describe('Volumes & Security — apply (recreate)', () => {
    it('should call recreate API with mounts and security payload', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyVolumesAndSecurity: () => Promise<void> }
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      expect(mockRecreate).toHaveBeenCalledWith('abc123', expect.objectContaining({
        mounts: [
          { Type: 'volume', Source: 'my-vol', Target: '/app/data', ReadOnly: false },
          { Type: 'bind', Source: '/host/path', Target: '/container/path', ReadOnly: true },
        ],
        privileged: true,
        readonly_rootfs: false,
        cap_add: ['NET_ADMIN', 'SYS_PTRACE'],
        cap_drop: ['SETUID'],
      }))
    })

    it('should emit recreate-success with new container ID', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyVolumesAndSecurity: () => Promise<void> }
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      expect(wrapper.emitted('recreate-success')).toBeTruthy()
      expect(wrapper.emitted('recreate-success')![0]).toEqual(['new456'])
    })

    it('should show error message on recreate failure', async () => {
      mockRecreate.mockRejectedValue(new Error('Recreate failed'))
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyVolumesAndSecurity: () => Promise<void> }
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      expect(mockRecreate).toHaveBeenCalled()
    })

    it('should not call API when detail is null', async () => {
      const wrapper = await mountComponent({ detail: null })
      const vm = wrapper.vm as unknown as { applyVolumesAndSecurity: () => Promise<void> }
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })

    it('should not call API when validation fails (empty destination)', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        volumeEntries: { type: string; source: string; destination: string; mode: string }[]
        applyVolumesAndSecurity: () => Promise<void>
      }
      vm.volumeEntries[0].destination = ''
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })

    it('should not call API when user cancels confirmation', async () => {
      const confirmMock = ElMessageBox.confirm as ReturnType<typeof vi.fn>
      confirmMock.mockRejectedValueOnce(new Error('cancel'))
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as { applyVolumesAndSecurity: () => Promise<void> }
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      expect(mockRecreate).not.toHaveBeenCalled()
    })

    it('should not include cap_add/cap_drop in payload when empty', async () => {
      const wrapper = await mountComponent()
      const vm = wrapper.vm as unknown as {
        capAdd: string[]
        capDrop: string[]
        applyVolumesAndSecurity: () => Promise<void>
      }
      vm.capAdd = []
      vm.capDrop = []
      await vm.applyVolumesAndSecurity()
      await flushPromises()

      const callArgs = mockRecreate.mock.calls[0][1] as Record<string, unknown>
      expect(callArgs.cap_add).toBeUndefined()
      expect(callArgs.cap_drop).toBeUndefined()
    })
  })
})
