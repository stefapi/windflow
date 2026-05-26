<script setup lang="ts">
/**
 * AppGridTile Component
 *
 * Displays a single application as a clickable tile in the dashboard grid.
 * Shows app icon, name, status dot, and domain. Clicking navigates to
 * the App Detail view.
 *
 * @see docs/general_specs/11-UI-mockups.md — Écran 1 (Dashboard)
 */

import { computed } from 'vue'
import { useRouter } from 'vue-router'
import type { AppCardData } from '@/components/compute/helpers'

export interface AppGridTileProps {
  /** The app data to display */
  app: AppCardData
}

const props = defineProps<AppGridTileProps>()

const router = useRouter()

/** Status dot CSS class based on status color */
const statusDotClass = computed(() => {
  switch (props.app.statusColor) {
    case 'success': return 'bg-green-500'
    case 'danger': return 'bg-red-500'
    case 'warning': return 'bg-yellow-500'
    default: return 'bg-blue-400'
  }
})

/** Navigate to the App Detail view */
function navigateToDetail(): void {
  router.push(`/containers/${props.app.containerId}`)
}
</script>

<template>
  <div
    class="app-grid-tile"
    data-testid="app-grid-tile"
    tabindex="0"
    role="button"
    :aria-label="`Ouvrir ${app.displayName}`"
    @click="navigateToDetail"
    @keyup.enter="navigateToDetail"
  >
    <!-- Icon -->
    <span
      class="app-grid-tile__icon"
      data-testid="app-grid-tile-icon"
    >{{ app.icon }}</span>

    <!-- Name -->
    <span
      class="app-grid-tile__name"
      data-testid="app-grid-tile-name"
      :title="app.displayName"
    >{{ app.displayName }}</span>

    <!-- Status row -->
    <div class="app-grid-tile__status">
      <span
        class="app-grid-tile__dot"
        :class="statusDotClass"
        data-testid="app-grid-tile-dot"
      />
      <span
        class="app-grid-tile__status-label"
        data-testid="app-grid-tile-status"
      >{{ app.statusLabel }}</span>
    </div>

    <!-- Domain (if available) -->
    <span
      v-if="app.domain"
      class="app-grid-tile__domain"
      data-testid="app-grid-tile-domain"
    >{{ app.domain }}</span>
  </div>
</template>

<style scoped>
.app-grid-tile {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 16px 8px;
  border-radius: 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
  text-align: center;
  min-height: 120px;
}

.app-grid-tile:hover {
  transform: translateY(-2px);
  box-shadow: var(--el-box-shadow-light);
}

.app-grid-tile:focus-visible {
  outline: 2px solid var(--el-color-primary);
  outline-offset: 2px;
}

.app-grid-tile__icon {
  font-size: 2rem;
  line-height: 1;
  margin-bottom: 8px;
}

.app-grid-tile__name {
  font-size: 0.8rem;
  font-weight: 600;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--el-text-color-primary);
}

.app-grid-tile__status {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 4px;
}

.app-grid-tile__dot {
  display: inline-block;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  flex-shrink: 0;
}

.app-grid-tile__status-label {
  font-size: 0.65rem;
  color: var(--el-text-color-secondary);
}

.app-grid-tile__domain {
  font-size: 0.6rem;
  color: var(--el-text-color-placeholder);
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  margin-top: 2px;
}
</style>
