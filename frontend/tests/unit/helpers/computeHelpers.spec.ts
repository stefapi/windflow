/**
 * Unit tests for compute/helpers.ts
 * STORY-025: Status helpers for all 6 Docker states
 */

import { describe, it, expect } from 'vitest'
import {
  getContainerStatusColor,
  getContainerStatusType,
  getContainerStatusLabel,
} from '@/components/compute/helpers'

describe('getContainerStatusType', () => {
  it('returns success for running', () => {
    expect(getContainerStatusType('running')).toBe('success')
  })

  it('returns warning for paused', () => {
    expect(getContainerStatusType('paused')).toBe('warning')
  })

  it('returns danger for exited', () => {
    expect(getContainerStatusType('exited')).toBe('danger')
  })

  it('returns danger for dead', () => {
    expect(getContainerStatusType('dead')).toBe('danger')
  })

  it('returns info for created', () => {
    expect(getContainerStatusType('created')).toBe('info')
  })

  it('returns warning for restarting', () => {
    expect(getContainerStatusType('restarting')).toBe('warning')
  })

  it('returns info for unknown status', () => {
    expect(getContainerStatusType('unknown')).toBe('info')
  })

  it('prioritizes healthy health status', () => {
    expect(getContainerStatusType('running', 'healthy')).toBe('success')
    expect(getContainerStatusType('exited', 'healthy')).toBe('success')
  })

  it('prioritizes unhealthy health status', () => {
    expect(getContainerStatusType('running', 'unhealthy')).toBe('warning')
  })
})

describe('getContainerStatusColor', () => {
  it('returns green for running', () => {
    expect(getContainerStatusColor('running')).toBe('text-green-500')
  })

  it('returns yellow for paused', () => {
    expect(getContainerStatusColor('paused')).toBe('text-yellow-500')
  })

  it('returns red-400 for exited', () => {
    expect(getContainerStatusColor('exited')).toBe('text-red-400')
  })

  it('returns red-600 for dead', () => {
    expect(getContainerStatusColor('dead')).toBe('text-red-600')
  })

  it('returns blue for created', () => {
    expect(getContainerStatusColor('created')).toBe('text-blue-400')
  })

  it('returns orange for restarting', () => {
    expect(getContainerStatusColor('restarting')).toBe('text-orange-500')
  })

  it('returns gray for unknown', () => {
    expect(getContainerStatusColor('unknown')).toBe('text-gray-400')
  })

  it('prioritizes healthy health status', () => {
    expect(getContainerStatusColor('running', 'healthy')).toBe('text-green-500')
    expect(getContainerStatusColor('exited', 'healthy')).toBe('text-green-500')
  })

  it('prioritizes unhealthy health status', () => {
    expect(getContainerStatusColor('running', 'unhealthy')).toBe('text-orange-500')
  })
})

describe('getContainerStatusLabel', () => {
  it('returns correct French labels for all 6 Docker states', () => {
    expect(getContainerStatusLabel('running')).toBe('En cours')
    expect(getContainerStatusLabel('paused')).toBe('En pause')
    expect(getContainerStatusLabel('exited')).toBe('Arrêté')
    expect(getContainerStatusLabel('dead')).toBe('Mort')
    expect(getContainerStatusLabel('created')).toBe('Créé')
    expect(getContainerStatusLabel('restarting')).toBe('Redémarrage')
  })

  it('returns raw status for unknown states', () => {
    expect(getContainerStatusLabel('custom-state')).toBe('custom-state')
  })

  it('prioritizes health status labels', () => {
    expect(getContainerStatusLabel('running', 'healthy')).toBe('Sain')
    expect(getContainerStatusLabel('running', 'unhealthy')).toBe('Non sain')
    expect(getContainerStatusLabel('running', 'starting')).toBe('Démarrage...')
  })
})
