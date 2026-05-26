<script setup lang="ts">
/**
 * AppContextMenu Component
 *
 * Canonical `[⋯ Plus]` dropdown menu for the App family.
 * Displays 3 ordered sections: Primary actions, Tools, Advanced.
 * A separator divides Tools from Advanced.
 *
 * Usable from the Apps list, dashboard, and App detail views.
 * In Mode App, technical vocabulary only appears in the Advanced section.
 *
 * @see docs/general_specs/11b-workload-families-and-adapters.md §2.4
 */

import { computed } from 'vue'
import { MoreFilled } from '@element-plus/icons-vue'
import { useAppContextMenu } from '@/composables/useAppContextMenu'
import type { AppContextMenuProps } from '@/types/context-menu'

const props = withDefaults(defineProps<AppContextMenuProps>(), {
  domain: undefined,
  labels: undefined,
  size: 'small',
})

const emit = defineEmits<{
  /** Emitted when a menu action is clicked */
  (e: 'action', action: string, containerId: string): void
}>()

const { sections, isMenuVisible } = useAppContextMenu(props)

/**
 * Whether the Advanced section should have a divider above it.
 * The divider appears between Tools and Advanced sections.
 */
const advancedSectionIndex = computed(() =>
  sections.value.findIndex((s) => s.key === 'advanced'),
)

/**
 * Handle a menu item click — emit the action event.
 */
function handleAction(action: string): void {
  emit('action', action, props.containerId)
}
</script>

<template>
  <el-dropdown
    v-if="isMenuVisible"
    trigger="click"
    :size="size"
    data-testid="app-context-menu"
    @command="handleAction"
  >
    <el-button
      :size="size"
      :icon="MoreFilled"
      circle
      data-testid="app-context-menu-trigger"
    />
    <template #dropdown>
      <el-dropdown-menu>
        <template
          v-for="(section, sectionIndex) in sections"
          :key="section.key"
        >
          <!-- Section title (non-clickable header) -->
          <el-dropdown-item
            disabled
            :class="[
              'context-menu-section-title',
              `context-menu-section-${section.key}`,
            ]"
          >
            {{ section.label }}
          </el-dropdown-item>

          <!-- Section items -->
          <el-dropdown-item
            v-for="item in section.items"
            :key="item.action"
            :command="item.action"
            :disabled="item.disabled"
            :divided="sectionIndex === advancedSectionIndex && section.items.indexOf(item) === 0"
            :class="[
              'context-menu-item',
              `context-menu-item-${item.action}`,
              { 'context-menu-item--danger': item.danger },
            ]"
            :data-testid="`menu-item-${item.action}`"
          >
            <el-icon class="context-menu-item-icon">
              <component :is="item.icon" />
            </el-icon>
            {{ item.label }}
          </el-dropdown-item>
        </template>
      </el-dropdown-menu>
    </template>
  </el-dropdown>
</template>

<style scoped>
.context-menu-section-title {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  cursor: default !important;
  padding: 4px 16px 2px;
  min-height: auto;
  line-height: 1.5;
}

.context-menu-section-title:hover {
  background-color: transparent !important;
  color: var(--el-text-color-secondary) !important;
}

.context-menu-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.context-menu-item-icon {
  font-size: 16px;
}

.context-menu-item--danger {
  color: var(--el-color-danger);
}

.context-menu-item--danger:hover {
  color: var(--el-color-danger);
  background-color: var(--el-color-danger-light-9);
}
</style>
