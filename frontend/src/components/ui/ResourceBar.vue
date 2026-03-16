<template>
  <div class="resource-bar" data-testid="resource-bar">
    <div v-if="label" class="resource-bar__header">
      <span class="resource-bar__label">{{ label }}</span>
      <span v-if="showValue" class="resource-bar__value">{{ formattedValue }}</span>
    </div>
    <div class="resource-bar__track">
      <div
        class="resource-bar__fill"
        :class="fillClass"
        :style="{ width: `${clampedValue}%` }"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * ResourceBar Component
 *
 * A progress bar that displays resource usage with dynamic color coding.
 * Color changes based on value thresholds:
 * - Green (success): < 60%
 * - Orange (warning): 60% to < 85%
 * - Red (error): >= 85%
 *
 * @example
 * <ResourceBar :value="45" label="CPU" />
 * <ResourceBar :value="92" label="RAM" :show-value="true" />
 */

import { computed } from 'vue'

/** Props for ResourceBar component */
export interface ResourceBarProps {
  /** Current value (0-100) */
  value: number
  /** Label to display above the bar */
  label?: string
  /** Whether to show the numeric value */
  showValue?: boolean
  /** Size variant */
  size?: 'small' | 'default' | 'large'
}

const props = withDefaults(defineProps<ResourceBarProps>(), {
  showValue: true,
  size: 'default',
})

// Clamp value between 0 and 100
const clampedValue = computed(() => Math.min(100, Math.max(0, props.value)))

// Format value for display
const formattedValue = computed(() => `${Math.round(clampedValue.value)}%`)

// Determine color class based on thresholds
const fillClass = computed(() => {
  const value = clampedValue.value
  if (value >= 85) {
    return 'resource-bar__fill--error'
  }
  if (value >= 60) {
    return 'resource-bar__fill--warning'
  }
  return 'resource-bar__fill--success'
})
</script>

<style scoped>
.resource-bar {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  width: 100%;
}

.resource-bar__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.resource-bar__label {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text-secondary);
  font-weight: 500;
}

.resource-bar__value {
  font-size: var(--text-sm, 0.875rem);
  color: var(--color-text-primary);
  font-weight: 600;
  font-family: var(--font-mono, monospace);
}

.resource-bar__track {
  width: 100%;
  height: 0.5rem;
  background-color: var(--color-bg-elevated);
  border-radius: 0.25rem;
  overflow: hidden;
}

.resource-bar__fill {
  height: 100%;
  border-radius: 0.25rem;
  transition: width 0.3s ease, background-color 0.3s ease;
}

/* Color variants using design tokens */
.resource-bar__fill--success {
  background-color: var(--color-success);
}

.resource-bar__fill--warning {
  background-color: var(--color-warning);
}

.resource-bar__fill--error {
  background-color: var(--color-error);
}
</style>
