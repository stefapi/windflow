/**
 * Unit tests for AdoptionWizard.vue
 *
 * Tests the wizard's 3-step flow: inventory → options → confirmation.
 * Uses vitest + @vue/test-utils.
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import AdoptionWizard from '@/components/compute/AdoptionWizard.vue'
import type { AdoptionWizardData, AdoptionResponse } from '@/types/api'

// ── Mock data ─────────────────────────────────────────────────────────────────

const mockWizardData: AdoptionWizardData = {
  discovered_id: 'compose:myproject@local',
  name: 'myproject',
  type: 'composition',
  technology: 'docker-compose',
  target_id: 'local',
  target_name: 'local',
  services: [
    {
      name: 'web',
      image: 'nginx:latest',
      status: 'running',
      env_vars: [
        { key: 'NODE_ENV', value: 'production', is_secret: false },
        { key: 'DB_PASSWORD', value: 'secret123', is_secret: true },
      ],
      volumes: [
        { source: '/host/data', destination: '/data', mode: 'rw', type: 'bind' },
      ],
      networks: [{ name: 'myproject_default', driver: 'bridge', is_default: true }],
      ports: [{ host_ip: '0.0.0.0', host_port: 8080, container_port: 80, protocol: 'tcp' }],
      cpu_percent: 2.5,
      memory_usage: '32M',
    },
    {
      name: 'db',
      image: 'postgres:15',
      status: 'running',
      env_vars: [],
      volumes: [],
      networks: [],
      ports: [],
      cpu_percent: 1.0,
      memory_usage: '128M',
    },
  ],
  generated_compose: 'version: "3.8"\nservices:\n  web:\n    image: nginx:latest\n',
  volumes_strategy_options: ['keep_existing', 'create_named', 'bind_mount'],
  networks_strategy_options: ['keep_existing', 'create_new'],
}

const mockAdoptionResponse: AdoptionResponse = {
  success: true,
  stack_id: 'stack-uuid-123',
  stack_name: 'myproject',
  deployment_id: 'deploy-uuid-456',
  message: "Objet 'compose:myproject@local' adopté avec succès.",
}

// ── Mocks using vi.hoisted to avoid hoisting reference errors ─────────────────

const { mockGetAdoptionData, mockAdopt } = vi.hoisted(() => ({
  mockGetAdoptionData: vi.fn(),
  mockAdopt: vi.fn(),
}))

vi.mock('@/services/api', () => ({
  discoveryApi: {
    getAdoptionData: mockGetAdoptionData,
    adopt: mockAdopt,
  },
}))

// Mock ElMessage to avoid UI side effects
vi.mock('element-plus', async () => {
  const actual = await vi.importActual('element-plus')
  return {
    ...actual,
    ElMessage: {
      success: vi.fn(),
      error: vi.fn(),
      warning: vi.fn(),
    },
  }
})

// ── Helpers ───────────────────────────────────────────────────────────────────

/** Flush microtasks then Vue tick */
async function flush(): Promise<void> {
  // Flush microtask queue by awaiting a resolved promise in a setTimeout
  await new Promise<void>((resolve) => {
    setTimeout(resolve, 0)
  })
  await nextTick()
}

function mountWizard(props = {}) {
  return mount(AdoptionWizard, {
    props: {
      modelValue: true,
      itemType: 'composition' as const,
      itemId: 'compose:myproject@local',
      itemName: 'myproject',
      ...props,
    },
    global: {
      stubs: {
        ElDialog: {
          template: '<div class="el-dialog"><slot /><slot name="footer" /></div>',
          props: ['modelValue'],
        },
        ElSteps: { template: '<div class="el-steps"><slot /></div>' },
        ElStep: { template: '<div class="el-step" />' },
        ElTable: { template: '<div class="el-table"><slot /></div>' },
        ElTableColumn: { template: '<div class="el-table-column" />' },
        ElCollapse: { template: '<div class="el-collapse"><slot /></div>' },
        ElCollapseItem: { template: '<div class="el-collapse-item"><slot /></div>' },
        ElForm: { template: '<div class="el-form"><slot /></div>' },
        ElFormItem: { template: '<div class="el-form-item"><slot /></div>' },
        ElInput: { template: '<input class="el-input" />', props: ['modelValue'] },
        ElSelect: { template: '<div class="el-select"><slot /></div>' },
        ElOption: { template: '<div class="el-option" />' },
        ElButton: {
          template: '<button class="el-button" @click="$emit(\'click\')"><slot /></button>',
          props: ['disabled', 'loading', 'type'],
        },
        ElTag: { template: '<span class="el-tag"><slot /></span>' },
        ElDescriptions: { template: '<div class="el-descriptions"><slot /></div>' },
        ElDescriptionsItem: { template: '<div class="el-descriptions-item"><slot /></div>' },
        ElAlert: { template: '<div class="el-alert"><slot /></div>' },
        ElResult: { template: '<div class="el-result"><slot /></div>' },
        ElEmpty: { template: '<div class="el-empty" />' },
      },
    },
  })
}

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function getVm(wrapper: ReturnType<typeof mount>): any {
  return wrapper.vm
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('AdoptionWizard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mockGetAdoptionData.mockResolvedValue({ data: mockWizardData })
    mockAdopt.mockResolvedValue({ data: mockAdoptionResponse })
  })

  it('renders the wizard dialog when modelValue is true', async () => {
    const wrapper = mountWizard()
    await flush()
    expect(wrapper.find('.el-dialog').exists()).toBe(true)
  })

  it('calls getAdoptionData on mount', async () => {
    mountWizard()
    await flush()

    expect(mockGetAdoptionData).toHaveBeenCalledWith(
      'composition',
      'compose:myproject@local',
    )
  })

  it('populates stack_name from discovered name after load', async () => {
    const wrapper = mountWizard()
    // Double flush to ensure the async loadAdoptionData resolves completely
    await flush()
    await flush()

    const vm = getVm(wrapper)
    expect(vm.form.stack_name).toBe('myproject')
  })

  it('emits update:modelValue=false when handleClose is called', async () => {
    const wrapper = mountWizard()
    await flush()

    const vm = getVm(wrapper)
    vm.handleClose()
    await nextTick()

    expect(wrapper.emitted('update:modelValue')).toBeTruthy()
    expect(wrapper.emitted('update:modelValue')![0]).toEqual([false])
  })

  it('calls adopt API and emits adopted event on handleAdopt', async () => {
    const wrapper = mountWizard()
    // Wait for data to load
    await flush()
    await flush()

    const vm = getVm(wrapper)

    // Verify data is loaded before testing adopt
    expect(vm.wizardData).toBeTruthy()

    // Go to step 3 and trigger adopt
    vm.currentStep = 2
    await nextTick()

    await vm.handleAdopt()
    await flush()

    expect(mockAdopt).toHaveBeenCalledWith(
      expect.objectContaining({
        discovered_id: 'compose:myproject@local',
        type: 'composition',
        stack_name: 'myproject',
        volume_strategy: 'keep_existing',
        network_strategy: 'keep_existing',
      }),
    )

    expect(wrapper.emitted('adopted')).toBeTruthy()
    expect(vm.adoptionResult.success).toBe(true)
  })

  it('still mounts when modelValue is false', async () => {
    const wrapper = mountWizard({ modelValue: false })
    await flush()
    // The dialog stub is always mounted
    expect(wrapper.find('.el-dialog').exists()).toBe(true)
  })
})
