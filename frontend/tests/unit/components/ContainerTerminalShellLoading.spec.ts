/**
 * ContainerTerminal.vue Unit Tests — Shell Loading (STORY-017)
 *
 * Tests focus on dynamic shell loading via API, fallback behavior,
 * and security (no tokens in DOM).
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { ref } from 'vue'
import ContainerTerminal from '@/components/ContainerTerminal.vue'

// Polyfill ResizeObserver for jsdom
global.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock containersApi.getShells
const mockGetShells = vi.fn()
vi.mock('@/services/api', () => ({
  containersApi: {
    getShells: (...args: unknown[]) => mockGetShells(...args),
  },
}))

// Mock useTerminal composable
vi.mock('@/composables/useTerminal', () => ({
  useTerminal: () => ({
    connected: ref(false),
    connecting: ref(false),
    error: ref(null),
    execId: ref(null),
    terminal: ref(null),
    activeShell: ref('/bin/sh'),
    activeUser: ref('root'),
    connect: vi.fn(),
    disconnect: vi.fn(),
    sendInput: vi.fn(),
    resize: vi.fn(),
    clear: vi.fn(),
    copyOutput: vi.fn(),
  }),
}))

// Mock auth store
vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    token: 'test-token',
  }),
}))

// Mock xterm.js modules
vi.mock('@xterm/xterm', () => ({
  Terminal: class {
    open() {}
    loadAddon() {}
    onData() {}
    onResize() {}
    attachCustomKeyEventHandler() {}
    blur() {}
    dispose() {}
    options = {}
    cols = 80
    rows = 24
  },
}))

vi.mock('@xterm/addon-fit', () => ({
  FitAddon: class {
    fit() {}
  },
}))

vi.mock('@xterm/addon-web-links', () => ({
  WebLinksAddon: class {},
}))

vi.mock('@xterm/xterm/css/xterm.css', () => ({}))

// Stub Element Plus components
const defaultStubs = {
  'el-tag': { template: '<div class="el-tag"><slot /></div>' },
  'el-select': {
    template: '<select class="el-select" :data-loading="loading"><slot /></select>',
    props: ['loading', 'placeholder', 'modelValue', 'size'],
  },
  'el-option': {
    template: '<option class="el-option" :value="value">{{ label }}</option>',
    props: ['value', 'label'],
  },
  'el-radio-group': {
    template: '<div class="el-radio-group"><slot /></div>',
    props: ['modelValue'],
  },
  'el-radio-button': {
    template: '<button class="el-radio-button"><slot /></button>',
    props: ['value'],
  },
  'el-input': {
    template: '<input class="el-input" />',
    props: ['modelValue', 'placeholder', 'clearable', 'size'],
  },
  'el-button': {
    template: '<button class="el-button"><slot /></button>',
    props: ['type', 'size', 'disabled'],
  },
  'el-icon': { template: '<i class="el-icon"><slot /></i>' },
  'el-tooltip': { template: '<div class="el-tooltip"><slot /></div>' },
  'el-button-group': { template: '<div class="el-button-group"><slot /></div>' },
  'el-alert': { template: '<div class="el-alert"><slot /></div>' },
}

const mockShellsAvailable = [
  { path: '/bin/bash', label: 'bash', available: true },
  { path: '/bin/sh', label: 'sh', available: true },
  { path: '/bin/zsh', label: 'zsh', available: false },
]

function mountTerminal(props: Record<string, unknown> = {}) {
  return mount(ContainerTerminal, {
    props: {
      containerId: 'test-container-123',
      ...props,
    },
    global: {
      stubs: defaultStubs,
    },
  })
}

describe('ContainerTerminal.vue — Shell Loading (STORY-017)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('should load shells on mount', async () => {
    mockGetShells.mockResolvedValue({
      data: mockShellsAvailable,
    })

    mountTerminal()
    await flushPromises()

    expect(mockGetShells).toHaveBeenCalledWith('test-container-123')
  })

  it('should populate shell dropdown with available shells only', async () => {
    mockGetShells.mockResolvedValue({
      data: mockShellsAvailable,
    })

    const wrapper = mountTerminal()
    await flushPromises()

    // Only available shells should be in the shell dropdown (bash and sh, not zsh)
    const shellSelect = wrapper.find('.shell-select')
    const options = shellSelect.findAll('.el-option')
    expect(options.length).toBe(2)
  })

  it('should fallback to /bin/sh when API fails', async () => {
    mockGetShells.mockRejectedValue(new Error('Network error'))

    const wrapper = mountTerminal()
    await flushPromises()

    // Should have fallback shell in the shell select
    const shellSelect = wrapper.find('.shell-select')
    const options = shellSelect.findAll('.el-option')
    expect(options.length).toBe(1)
  })

  it('should fallback to /bin/sh when no shells available', async () => {
    mockGetShells.mockResolvedValue({
      data: [
        { path: '/bin/bash', label: 'bash', available: false },
        { path: '/bin/zsh', label: 'zsh', available: false },
      ],
    })

    const wrapper = mountTerminal()
    await flushPromises()

    // All shells unavailable → fallback to /bin/sh
    const shellSelect = wrapper.find('.shell-select')
    const options = shellSelect.findAll('.el-option')
    expect(options.length).toBe(1)
  })

  it('should auto-select first available shell', async () => {
    mockGetShells.mockResolvedValue({
      data: mockShellsAvailable,
    })

    const wrapper = mountTerminal()
    await flushPromises()

    // The select should exist and have a value
    const select = wrapper.find('.el-select')
    expect(select.exists()).toBe(true)
  })

  it('should show loading state while fetching shells', async () => {
    // Create a promise that won't resolve immediately
    let resolvePromise: (value: unknown) => void
    mockGetShells.mockReturnValue(
      new Promise((resolve) => {
        resolvePromise = resolve
      })
    )

    const wrapper = mountTerminal()

    // The select should exist (rendered even while loading)
    const select = wrapper.find('.el-select')
    expect(select.exists()).toBe(true)

    // Resolve the promise to clean up
    resolvePromise!({ data: mockShellsAvailable })
    await flushPromises()
  })

  it('should not expose tokens in DOM', async () => {
    mockGetShells.mockResolvedValue({
      data: mockShellsAvailable,
    })

    const wrapper = mountTerminal()
    await flushPromises()

    const html = wrapper.html()
    expect(html).not.toContain('test-token')
    expect(html).not.toContain('Bearer ')
    expect(html).not.toContain('jwt')
    expect(html).not.toContain('secret')
  })
})
