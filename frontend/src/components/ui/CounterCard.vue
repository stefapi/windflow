<template>
  <component
    :is="linkComponent"
    :to="to"
    :class="cardClasses"
    data-testid="counter-card"
  >
    <div class="counter-card__icon">
      <el-icon :size="iconSize">
        <component :is="icon" />
      </el-icon>
    </div>
    <div class="counter-card__content">
      <div class="counter-card__header">
        <span class="counter-card__count">{{ formattedCount }}</span>
        <span
          v-if="badge"
          :class="['counter-card__badge', `counter-card__badge--${badgeType}`]"
        >
          {{ badge }}
        </span>
      </div>
      <!-- Running/Stopped indicators (STORY-432) -->
      <div
        v-if="hasRunningStopped"
        class="counter-card__status"
      >
        <span class="counter-card__status-item counter-card__status-item--running">
          <span class="counter-card__status-dot">🟢</span>
          <span class="counter-card__status-count">{{ runningCount }}</span>
        </span>
        <span class="counter-card__status-item counter-card__status-item--stopped">
          <span class="counter-card__status-dot">🔴</span>
          <span class="counter-card__status-count">{{ stoppedCount }}</span>
        </span>
      </div>
      <span class="counter-card__label">{{ label }}</span>
    </div>
  </component>
</template>

<script setup lang="ts">
/**
 * CounterCard Component
 *
 * A clickable tile displaying a counter with icon and label.
 * Can be used as a router-link when `to` prop is provided.
 *
 * @example
 * <CounterCard :count="42" label="Containers" :icon="Box" />
 * <CounterCard :count="7" label="VMs" :icon="Monitor" to="/vms" />
 */

import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import type { Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'

/** Props for CounterCard component */
export interface CounterCardProps {
  /** The count value to display */
  count: number
  /** Label text below the count */
  label: string
  /** Icon component to display */
  icon: Component
  /** Router link destination (makes card clickable) */
  to?: RouteLocationRaw
  /** Size variant */
  size?: 'small' | 'default' | 'large'
  /** Optional badge text (displayed next to count) */
  badge?: string
  /** Badge type for styling */
  badgeType?: 'success' | 'warning' | 'error' | 'info'
  /** Running count (STORY-432 - displays 🟢 indicator) */
  runningCount?: number
  /** Stopped count (STORY-432 - displays 🔴 indicator) */
  stoppedCount?: number
}

const props = withDefaults(defineProps<CounterCardProps>(), {
  size: 'default',
})

// Determine if card should be a link
const linkComponent = computed(() => (props.to ? RouterLink : 'div'))

// Card classes
const cardClasses = computed(() => [
  'counter-card',
  `counter-card--${props.size}`,
  { 'counter-card--clickable': !!props.to },
])

// Icon size based on card size
const iconSize = computed(() => {
  const sizes = {
    small: 24,
    default: 32,
    large: 40,
  }
  return sizes[props.size]
})

// Format count with K/M suffix for large numbers
const formattedCount = computed(() => {
  const count = props.count
  if (count >= 1000000) {
    return `${(count / 1000000).toFixed(1)}M`
  }
  if (count >= 1000) {
    return `${(count / 1000).toFixed(1)}K`
  }
  return count.toString()
})

// Check if running/stopped indicators should be displayed (STORY-432)
const hasRunningStopped = computed(() => {
  return props.runningCount !== undefined || props.stoppedCount !== undefined
})
</script>

<style scoped>
.counter-card {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 1rem;
  background-color: var(--color-bg-card);
  border: 1px solid var(--color-border);
  border-radius: 0.5rem;
  transition: all 0.2s ease;
}

.counter-card--clickable {
  cursor: pointer;
  text-decoration: none;
}

.counter-card--clickable:hover {
  background-color: var(--color-bg-hover);
  border-color: var(--color-accent);
  transform: translateY(-2px);
  box-shadow: var(--shadow-md);
}

/* Size variants */
.counter-card--small {
  padding: 0.75rem;
  gap: 0.75rem;
}

.counter-card--large {
  padding: 1.25rem;
  gap: 1.25rem;
}

/* Icon styling */
.counter-card__icon {
  display: flex;
  justify-content: center;
  align-items: center;
  flex-shrink: 0;
  width: 3.5rem;
  height: 3.5rem;
  color: var(--color-accent);
  background-color: var(--color-accent-light);
  border-radius: 0.5rem;
}

.counter-card--small .counter-card__icon {
  width: 2.5rem;
  height: 2.5rem;
}

.counter-card--large .counter-card__icon {
  width: 4.5rem;
  height: 4.5rem;
}

/* Content styling */
.counter-card__content {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  min-width: 0;
}

.counter-card__count {
  font-size: var(--text-2xl, 1.5rem);
  font-family: var(--font-mono, monospace);
  color: var(--color-text-primary);
  font-weight: 600;
  line-height: 1.2;
}

.counter-card--small .counter-card__count {
  font-size: var(--text-xl, 1.25rem);
}

.counter-card--large .counter-card__count {
  font-size: var(--text-3xl, 1.875rem);
}

.counter-card__label {
  overflow: hidden;
  font-size: var(--text-sm, 0.875rem);
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--color-text-secondary);
}

.counter-card--large .counter-card__label {
  font-size: var(--text-base, 1rem);
}

/* Header with count and badge */
.counter-card__header {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

/* Badge styling */
.counter-card__badge {
  padding: 0.125rem 0.375rem;
  font-size: var(--text-xs, 0.75rem);
  border-radius: 0.25rem;
  font-weight: 500;
}

.counter-card__badge--success {
  color: var(--color-success);
  background-color: var(--color-success-light);
}

.counter-card__badge--warning {
  color: var(--color-warning);
  background-color: var(--color-warning-light);
}

.counter-card__badge--error {
  color: var(--color-error);
  background-color: var(--color-error-light);
}

.counter-card__badge--info {
  color: var(--color-info);
  background-color: var(--color-info-light);
}

/* Running/Stopped status indicators (STORY-432) */
.counter-card__status {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.counter-card__status-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: var(--text-xs, 0.75rem);
  color: var(--color-text-secondary);
}

.counter-card__status-dot {
  font-size: 0.625rem;
  line-height: 1;
}

.counter-card__status-count {
  font-family: var(--font-mono, monospace);
  font-weight: 500;
}

.counter-card__status-item--running .counter-card__status-count {
  color: var(--color-success);
}

.counter-card__status-item--stopped .counter-card__status-count {
  color: var(--color-error);
}
</style>
