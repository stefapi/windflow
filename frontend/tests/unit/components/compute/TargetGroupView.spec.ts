/**
 * TargetGroupView.vue Unit Tests
 */

import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import TargetGroupView from '@/components/compute/TargetGroupView.vue'
import type { TargetGroupItem } from '@/components/compute/TargetGroupView.vue'

// ─── Test Data ───────────────────────────────────────────────────────

function createMockGroup(overrides: Partial<TargetGroupItem> = {}): TargetGroupItem {
  return {
    target_id: 'target-001',
    target_name: 'Local Docker',
    technology: 'Docker Engine 26.1',
    stacks: [
      {
        id: 'stack-001',
        name: 'Test Stack',
        technology: 'docker',
        target_id: 'target-001',
        target_name: 'Local Docker',
        services_total: 2,
        services_running: 2,
        status: 'running',
        services: [
          { id: 'svc-1', name: 'web', image: 'nginx:latest', status: 'running', cpu_percent: 1.5, memory_usage: '50M' },
        ],
      },
    ],
    discovered: [
      {
        id: 'disc-001',
        name: 'monitoring',
        type: 'composition',
        technology: 'compose',
        target_id: 'target-001',
        target_name: 'Local Docker',
        services_total: 1,
        services_running: 1,
        detected_at: '2024-01-01T00:00:00Z',
        adoptable: true,
        services: [
          { id: 'svc-2', name: 'prometheus', image: 'prom/prometheus', status: 'running', cpu_percent: 2.0, memory_usage: '120M' },
        ],
      },
    ],
    standalone: [
      {
        id: 'c-1',
        name: 'traefik',
        image: 'traefik:v2.10',
        target_id: 'target-001',
        target_name: 'Local Docker',
        status: 'running',
        cpu_percent: 2.5,
        memory_usage: '80M',
        uptime: '3 days',
        ports: [],
        health_status: null,
      },
    ],
    metrics: {
      cpu_total_percent: 15.5,
      memory_used: '4.2G',
      memory_total: '16G',
    },
    ...overrides,
  }
}

// ─── Mount helper ────────────────────────────────────────────────────

function mountComponent(props = {}) {
  return mount(TargetGroupView, {
    props: {
      groups: [createMockGroup()],
      loading: false,
      ...props,
    },
    global: {
      plugins: [ElementPlus],
      stubs: {
        'el-collapse': {
          name: 'ElCollapse',
          template: '<div class="el-collapse-stub"><slot /></div>',
        },
        'el-collapse-item': {
          name: 'ElCollapseItem',
          template: '<div class="el-collapse-item-stub" :name="name"><slot /><slot name="title" /></div>',
          props: ['name'],
        },
        'el-empty': {
          name: 'ElEmpty',
          template: '<div class="el-empty-stub"><slot /></div>',
        },
        'el-icon': {
          name: 'ElIcon',
          template: '<i class="el-icon-stub"><slot /></i>',
        },
        'el-tag': {
          name: 'ElTag',
          template: '<span class="el-tag-stub"><slot /></span>',
          props: ['type', 'size'],
        },
        'ContainerTable': {
          name: 'ContainerTable',
          template: '<div class="container-table-stub"><slot /></div>',
          props: ['items', 'columns', 'showActions', 'size'],
        },
      },
    },
  })
}

// ─── Tests ───────────────────────────────────────────────────────────

describe('TargetGroupView', () => {
  // ─── Rendu ───────────────────────────────────────────────────────

  describe('rendu', () => {
    it('affiche le spinner pendant le chargement', () => {
      const wrapper = mountComponent({ loading: true, groups: [] })
      expect(wrapper.find('.el-icon-stub').exists()).toBe(true)
    })

    it('affiche el-empty quand aucun groupe', () => {
      const wrapper = mountComponent({ groups: [] })
      expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    })

    it('affiche les groupes avec target_name, technologie et métriques CPU/RAM', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Local Docker')
      expect(wrapper.text()).toContain('Docker Engine 26.1')
      expect(wrapper.text()).toContain('CPU: 15.5%')
      expect(wrapper.text()).toContain('RAM: 4.2G/16G')
    })

    it('affiche la sous-section Stacks avec ContainerTable', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Stacks (1)')
      const tables = wrapper.findAll('.container-table-stub')
      expect(tables.length).toBeGreaterThanOrEqual(1)
    })

    it('affiche la sous-section Discovered avec ContainerTable', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Discovered (1)')
      const tables = wrapper.findAll('.container-table-stub')
      expect(tables.length).toBeGreaterThanOrEqual(2)
    })

    it('affiche la sous-section Standalone avec ContainerTable', () => {
      const wrapper = mountComponent()
      expect(wrapper.text()).toContain('Standalone (1)')
      const tables = wrapper.findAll('.container-table-stub')
      expect(tables.length).toBeGreaterThanOrEqual(3)
    })

    it('affiche el-empty si un groupe n\'a aucune ressource', () => {
      const wrapper = mountComponent({
        groups: [createMockGroup({ stacks: [], discovered: [], standalone: [] })],
      })
      expect(wrapper.find('.el-empty-stub').exists()).toBe(true)
    })

    it('n\'affiche pas les sous-sections vides', () => {
      const wrapper = mountComponent({
        groups: [createMockGroup({ stacks: [], discovered: [] })],
      })
      expect(wrapper.text()).not.toContain('Stacks')
      expect(wrapper.text()).not.toContain('Discovered')
      expect(wrapper.text()).toContain('Standalone')
    })
  })
})
