<template>
  <div
    class="action-buttons"
    data-testid="action-buttons"
  >
    <el-tooltip
      v-for="action in visibleActions"
      :key="action.type"
      :content="action.tooltip"
      :disabled="action.disabled"
      placement="top"
    >
      <span>
        <el-button
          :class="['action-buttons__btn', `action-buttons__btn--${action.type}`]"
          :size="size"
          :disabled="action.disabled"
          circle
          @click.stop="handleAction(action.type)"
        >
          <el-icon>
            <component :is="getActionIcon(action.type)" />
          </el-icon>
        </el-button>
      </span>
    </el-tooltip>
  </div>
</template>

<script setup lang="ts">
/**
 * ActionButtons Component
 *
 * A group of inline action buttons with icons and tooltips.
 * Used for container/VM management actions like start, stop, restart, etc.
 *
 * @example
 * <ActionButtons :actions="['start', 'stop', 'restart']" @action="onAction" />
 * <ActionButtons :actions="[{ type: 'logs', tooltip: 'View logs' }]" />
 */

import { computed } from 'vue'
import {
  VideoPlay,
  VideoPause,
  RefreshRight,
  Refresh,
  Document,
  Delete,
  Edit,
  Upload,
  Check,
  Key,
} from '@element-plus/icons-vue'

/** Predefined action types */
export type ActionType = 'start' | 'stop' | 'restart' | 'logs' | 'delete' | 'edit' | 'deploy' | 'scan' | 'select' | 'password'

/** Action configuration (simplified for string usage) */
export type ActionConfig = ActionType | ActionConfigObject

/** Full action configuration object */
export interface ActionConfigObject {
  /** Action type */
  type: ActionType
  /** Tooltip text (overrides default) */
  tooltip?: string
  /** Whether the action is disabled */
  disabled?: boolean
}

/** Props for ActionButtons component */
export interface ActionButtonsProps {
  /** Actions to display (can be strings or objects) */
  actions: ActionConfig[]
  /** Button size */
  size?: 'small' | 'default' | 'large'
}

const props = withDefaults(defineProps<ActionButtonsProps>(), {
  size: 'small',
})

// Emits
const emit = defineEmits<{
  /** Emitted when an action is clicked */
  (e: 'action', type: ActionType): void
}>()

// Default action configurations
const defaultActionConfig: Record<ActionType, { icon: typeof VideoPlay; tooltip: string }> = {
  start: {
    icon: VideoPlay,
    tooltip: 'Démarrer',
  },
  stop: {
    icon: VideoPause,
    tooltip: 'Arrêter',
  },
  restart: {
    icon: RefreshRight,
    tooltip: 'Redémarrer',
  },
  logs: {
    icon: Document,
    tooltip: 'Voir les logs',
  },
  delete: {
    icon: Delete,
    tooltip: 'Supprimer',
  },
  edit: {
    icon: Edit,
    tooltip: 'Modifier',
  },
  deploy: {
    icon: Upload,
    tooltip: 'Déployer',
  },
  scan: {
    icon: Refresh,
    tooltip: 'Scanner',
  },
  select: {
    icon: Check,
    tooltip: 'Sélectionner',
  },
  password: {
    icon: Key,
    tooltip: 'Changer le mot de passe',
  },
}

// Normalize actions to objects
const visibleActions = computed<ActionConfigObject[]>(() =>
  props.actions.map((action) =>
    typeof action === 'string'
      ? { type: action, tooltip: defaultActionConfig[action].tooltip }
      : {
          type: action.type,
          tooltip: action.tooltip ?? defaultActionConfig[action.type].tooltip,
          disabled: action.disabled,
        }
  )
)

// Get icon component for action type
function getActionIcon(type: ActionType): typeof VideoPlay {
  return defaultActionConfig[type].icon
}

// Handle action click
function handleAction(type: ActionType): void {
  emit('action', type)
}
</script>

<style scoped>
.action-buttons {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.action-buttons__btn {
  color: var(--color-text-secondary);
  background-color: var(--color-bg-elevated);
  border-color: var(--color-border);
  transition: all 0.2s ease;
}

.action-buttons__btn:hover:not(:disabled) {
  color: var(--color-text-primary);
  background-color: var(--color-bg-hover);
}

.action-buttons__btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Action-specific hover colors */
.action-buttons__btn--start:hover:not(:disabled) {
  color: var(--color-success);
  border-color: var(--color-success);
}

.action-buttons__btn--stop:hover:not(:disabled) {
  color: var(--color-warning);
  border-color: var(--color-warning);
}

.action-buttons__btn--restart:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.action-buttons__btn--logs:hover:not(:disabled) {
  color: var(--color-info);
  border-color: var(--color-info);
}

.action-buttons__btn--delete:hover:not(:disabled) {
  color: var(--color-error);
  border-color: var(--color-error);
}

.action-buttons__btn--edit:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.action-buttons__btn--deploy:hover:not(:disabled) {
  color: var(--color-success);
  border-color: var(--color-success);
}

.action-buttons__btn--scan:hover:not(:disabled) {
  color: var(--color-accent);
  border-color: var(--color-accent);
}

.action-buttons__btn--select:hover:not(:disabled) {
  color: var(--color-success);
  border-color: var(--color-success);
}

.action-buttons__btn--password:hover:not(:disabled) {
  color: var(--color-warning);
  border-color: var(--color-warning);
}
</style>
