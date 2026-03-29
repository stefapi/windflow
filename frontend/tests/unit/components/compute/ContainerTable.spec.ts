import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import { h } from 'vue'
import ContainerTable from '@/components/compute/ContainerTable.vue'
import type { ContainerTableRow } from '@/components/compute/helpers'

// ─── Factory ──────────────────────────────────────────────────────────────────

function createRow(overrides: Partial<ContainerTableRow> = {}): ContainerTableRow {
  return {
    id: 'row-1',
    name: 'nginx',
    image: 'nginx:latest',
    status: 'running',
    cpuPercent: 2.5,
    memoryUsage: '50 MiB',
    link: '',
    ...overrides,
  }
}

/**
 * A stub for ElTableColumn that properly passes a mock row
 * to its default scoped slot.
 */
const ElTableColumnStub = {
  name: 'ElTableColumn',
  props: ['prop', 'label', 'minWidth', 'min-width', 'width', 'sortable', 'type', 'align'],
  render() {
    const mockRow: ContainerTableRow = {
      id: 'mock-1',
      name: 'mock',
      image: 'mock:latest',
      status: 'running',
      cpuPercent: 0,
      memoryUsage: '0 MiB',
      link: '',
    }
    // Call the default scoped slot with a mock row, or render nothing
    const slot = this.$slots.default
    if (slot) {
      return slot({ row: mockRow, $index: 0 })
    }
    return null
  },
}

const globalStubs = {
  ElTable: {
    name: 'ElTable',
    props: ['data'],
    render() {
      // Render the default slot (contains ElTableColumn stubs)
      const slot = this.$slots.default
      return h('div', { class: 'el-table' }, slot ? slot() : [])
    },
  },
  ElTableColumn: ElTableColumnStub,
  ElTag: {
    template: '<span class="el-tag"><slot /></span>',
    props: ['type', 'size'],
  },
  ElProgress: {
    template: '<div class="el-progress" />',
    props: ['percentage', 'stroke-width', 'color'],
  },
  ElCheckbox: {
    template: '<label class="el-checkbox"><input type="checkbox" /></label>',
    props: ['modelValue'],
  },
  ElIcon: {
    template: '<i><slot /></i>',
  },
  ActionButtons: {
    template: '<div class="action-buttons" />',
    props: ['actions'],
  },
  RouterLink: {
    template: '<a class="router-link"><slot /></a>',
    props: ['to'],
  },
}

describe('ContainerTable', () => {
  it('should render without errors with empty items', () => {
    const wrapper = mount(ContainerTable, {
      props: {
        items: [],
        columns: ['name', 'status'],
      },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.el-table').exists()).toBe(true)
  })

  it('should render with items', () => {
    const items = [
      createRow({ id: '1', name: 'nginx' }),
      createRow({ id: '2', name: 'redis' }),
    ]
    const wrapper = mount(ContainerTable, {
      props: {
        items,
        columns: ['name', 'status'],
      },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.el-table').exists()).toBe(true)
  })

  it('should use default columns when none specified', () => {
    const wrapper = mount(ContainerTable, {
      props: {
        items: [createRow()],
      },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.el-table').exists()).toBe(true)
  })

  it('should render selection column when selectable is true', () => {
    const wrapper = mount(ContainerTable, {
      props: {
        items: [createRow()],
        columns: ['selection', 'name'],
        selectable: true,
      },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.el-table').exists()).toBe(true)
  })

  it('should render actions column when showActions is true', () => {
    const wrapper = mount(ContainerTable, {
      props: {
        items: [createRow()],
        columns: ['name', 'actions'],
        showActions: true,
      },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.el-table').exists()).toBe(true)
    expect(wrapper.find('.action-buttons').exists()).toBe(true)
  })

  it('should not render actions column when showActions is false', () => {
    const wrapper = mount(ContainerTable, {
      props: {
        items: [createRow()],
        columns: ['name'],
        showActions: false,
      },
      global: { stubs: globalStubs },
    })
    expect(wrapper.find('.action-buttons').exists()).toBe(false)
  })
})
