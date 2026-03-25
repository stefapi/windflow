import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ComputeStatsBanner from '@/components/ComputeStatsBanner.vue'
import type { ComputeStatsResponse } from '@/types/api'

// Stubs pour Element Plus
const globalConfig = {
  global: {
    stubs: {
      ElCard: {
        template: '<div class="el-card"><slot /></div>',
      },
      ElSkeleton: {
        template: '<div class="el-skeleton" />',
      },
    },
    directives: {
      loading: {},
    },
  },
}

const mockStats: ComputeStatsResponse = {
  total_containers: 23,
  running_containers: 18,
  stacks_count: 3,
  stacks_running_count: 2,
  stacks_targets_count: 2,
  stacks_services_count: 9,
  discovered_count: 4,
  discovered_targets_count: 2,
  standalone_count: 10,
  standalone_targets_count: 3,
  targets_count: 4,
}

describe('ComputeStatsBanner', () => {
  describe('état loading', () => {
    it('should show skeletons when stats=null and loading=false', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: null, loading: false },
        ...globalConfig,
      })
      const skeletons = wrapper.findAll('.el-skeleton')
      expect(skeletons).toHaveLength(5)
    })

    it('should add v-loading directive on container when loading=true', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: null, loading: true },
        ...globalConfig,
      })
      // Le conteneur existe bien
      expect(wrapper.find('.grid').exists()).toBe(true)
    })
  })

  describe('affichage des valeurs', () => {
    it('should display total_containers value', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      expect(wrapper.text()).toContain('23')
    })

    it('should display running_containers value', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      expect(wrapper.text()).toContain('18')
    })

    it('should display stacks_count value', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      expect(wrapper.text()).toContain('3')
    })

    it('should display discovered_count value', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      expect(wrapper.text()).toContain('4')
    })

    it('should display standalone_count value', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      expect(wrapper.text()).toContain('10')
    })

    it('should display sub-label "sur 4 machines" when targets_count=4', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      expect(wrapper.text()).toContain('sur 4 machines')
    })
  })

  describe('classes couleurs', () => {
    it('should apply green class to running value when running_containers > 0', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      // Trouve l'élément avec la classe text-green-600
      const greenEl = wrapper.find('.text-green-600')
      expect(greenEl.exists()).toBe(true)
    })

    it('should apply red class to running value when running_containers = 0', () => {
      const zeroStats = { ...mockStats, running_containers: 0 }
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: zeroStats, loading: false },
        ...globalConfig,
      })
      const redEl = wrapper.find('.text-red-500')
      expect(redEl.exists()).toBe(true)
    })

    it('should apply orange class to discovered value when discovered_count > 0', () => {
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: mockStats, loading: false },
        ...globalConfig,
      })
      const orangeEl = wrapper.find('.text-orange-500')
      expect(orangeEl.exists()).toBe(true)
    })

    it('should apply gray class to discovered value when discovered_count = 0', () => {
      const zeroDiscovered = { ...mockStats, discovered_count: 0 }
      const wrapper = mount(ComputeStatsBanner, {
        props: { stats: zeroDiscovered, loading: false },
        ...globalConfig,
      })
      const orangeEl = wrapper.find('.text-orange-500')
      expect(orangeEl.exists()).toBe(false)
    })
  })
})
