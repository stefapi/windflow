/**
 * ContainerConfigTab.vue Unit Tests — STORY-024 + STORY-027
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
vi.mock('@/services/api', () => ({
  containersApi: {
    updateRestartPolicy: (...args: unknown[]) => mockUpdateRestartPolicy(...args),
    updateResources: (...args: unknown[]) => mockUpdateResources(...args),
    recreate: (...args: unknown[]) => mockRecreate(...args),
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
    cap_add: null,
    cap_drop: null,
    dns: null,
    privileged: null,
    readonly_rootfs: null,
    security_opt: null,
    shm_size: null,
    runtime: null,
    resources: { memory: 536870912, memory_reservation: null, memory_swap: null, cpu_shares: 1024, cpu_period: null, cpu_quota: null, cpus: null, cpuset_cpus: null, pids_limit: 100 },
  },
  network_settings: { networks: {} },
  mounts: [],
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

    it('should render 6 config cards', async () => {
      const wrapper = await mountComponent()
      const cards = wrapper.findAll('.el-card-stub')
      expect(cards.length).toBe(6)
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
      // 4 alerts total: env, labels, image, ports
      expect(alerts.length).toBe(4)
      const allText = alerts.map((a) => a.text()).join(' ')
      expect(allText).toContain('image')
      expect(allText).toContain('ports')
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
      expect(alerts.length).toBe(4)
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
})
