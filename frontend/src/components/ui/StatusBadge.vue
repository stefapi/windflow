<template>
  <span
    :class="badgeClasses"
    data-testid="status-badge"
  >
    <el-icon
      v-if="showIcon"
      class="status-badge__icon"
    >
      <component :is="iconComponent" />
    </el-icon>
    <span class="status-badge__label">{{ displayLabel }}</span>
  </span>
</template>

<script setup lang="ts">
/**
 * StatusBadge Component
 *
 * A colored badge that displays status information with an optional icon.
 * Uses design system tokens for consistent styling across themes.
 *
 * @example
 * <StatusBadge status="running" />
 * <StatusBadge status="error" :show-icon="false" label="Custom Label" />
 */

import { computed } from 'vue'
import {
  VideoPlay,
  VideoPause,
  CircleClose,
  Loading,
  Document,
  CircleCheck,
  Tools,
  Clock,
} from '@element-plus/icons-vue'

/** Status types for the badge */
export type StatusType = 'running' | 'stopped' | 'error' | 'deploying' | 'draft' | 'deployed' | 'online' | 'offline' | 'maintenance' | 'pending' | 'failed'

/** Props for StatusBadge component */
export interface StatusBadgeProps {
  /** The status to display */
  status: StatusType
  /** Custom label (overrides default status label) */
  label?: string
  /** Whether to show the status icon */
  showIcon?: boolean
  /** Size variant */
  size?: 'small' | 'default' | 'large'
}

const props = withDefaults(defineProps<StatusBadgeProps>(), {
  showIcon: true,
  size: 'default',
})

// Status configuration mapping
const statusConfig: Record<StatusType, { label: string; icon: typeof VideoPlay; class: string }> = {
  running: {
    label: 'En cours',
    icon: VideoPlay,
    class: 'status-badge--success',
  },
  stopped: {
    label: 'Arrêté',
    icon: VideoPause,
    class: 'status-badge--info',
  },
  error: {
    label: 'Erreur',
    icon: CircleClose,
    class: 'status-badge--error',
  },
  deploying: {
    label: 'Déploiement',
    icon: Loading,
    class: 'status-badge--warning',
  },
  draft: {
    label: 'Brouillon',
    icon: Document,
    class: 'status-badge--neutral',
  },
  deployed: {
    label: 'Déployé',
    icon: CircleCheck,
    class: 'status-badge--success',
  },
  online: {
    label: 'En ligne',
    icon: CircleCheck,
    class: 'status-badge--success',
  },
  offline: {
    label: 'Hors ligne',
    icon: CircleClose,
    class: 'status-badge--error',
  },
  maintenance: {
    label: 'Maintenance',
    icon: Tools,
    class: 'status-badge--warning',
  },
  pending: {
    label: 'En attente',
    icon: Clock,
    class: 'status-badge--neutral',
  },
  failed: {
    label: 'Échoué',
    icon: CircleClose,
    class: 'status-badge--error',
  },
}

// Computed properties
const config = computed(() => statusConfig[props.status])
const iconComponent = computed(() => config.value.icon)
const displayLabel = computed(() => props.label ?? config.value.label)

const badgeClasses = computed(() => [
  'status-badge',
  config.value.class,
  `status-badge--${props.size}`,
])
</script>

<style scoped>
.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  font-weight: 500;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
}

/* Size variants */
.status-badge--small {
  padding: 0.125rem 0.375rem;
  font-size: var(--text-xs, 0.75rem);
}

.status-badge--default {
  padding: 0.25rem 0.5rem;
  font-size: var(--text-sm, 0.875rem);
}

.status-badge--large {
  padding: 0.375rem 0.75rem;
  font-size: var(--text-base, 1rem);
}

/* Status color variants using design tokens */
.status-badge--success {
  background-color: var(--color-success-light);
  color: var(--color-success);
}

.status-badge--info {
  background-color: var(--color-info-light);
  color: var(--color-info);
}

.status-badge--error {
  background-color: var(--color-error-light);
  color: var(--color-error);
}

.status-badge--warning {
  background-color: var(--color-warning-light);
  color: var(--color-warning);
}

.status-badge--neutral {
  background-color: var(--color-bg-elevated);
  color: var(--color-text-secondary);
}

/* Icon styling */
.status-badge__icon {
  font-size: 1em;
}

/* Animations for deploying state */
.status-badge--warning .status-badge__icon {
  animation: spin 1.5s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
