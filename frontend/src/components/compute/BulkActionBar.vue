<template>
  <transition name="slide-down">
    <div
      v-if="selectedCount > 0"
      class="flex justify-between items-center px-4 py-3 mb-4 bg-accent-light border border-accent rounded-lg"
    >
      <div class="flex items-center gap-3">
        <el-tag
          type="primary"
          effect="dark"
        >
          {{ selectedCount }} sélectionné{{ selectedCount > 1 ? 's' : '' }}
        </el-tag>
        <el-button
          text
          size="small"
          @click="emit('cancel')"
        >
          Annuler la sélection
        </el-button>
      </div>
      <div class="flex items-center gap-2">
        <el-button
          size="small"
          :loading="loadingAction === 'start'"
          @click="emit('start')"
        >
          <el-icon class="el-icon--left">
            <VideoPlay />
          </el-icon>
          Démarrer
        </el-button>
        <el-button
          size="small"
          :loading="loadingAction === 'stop'"
          @click="emit('stop')"
        >
          <el-icon class="el-icon--left">
            <VideoPause />
          </el-icon>
          Arrêter
        </el-button>
        <el-button
          size="small"
          :loading="loadingAction === 'restart'"
          @click="emit('restart')"
        >
          <el-icon class="el-icon--left">
            <RefreshRight />
          </el-icon>
          Redémarrer
        </el-button>
        <el-button
          type="danger"
          size="small"
          :loading="loadingAction === 'delete'"
          @click="emit('delete')"
        >
          <el-icon class="el-icon--left">
            <Delete />
          </el-icon>
          Supprimer
        </el-button>
      </div>
    </div>
  </transition>
</template>

<script setup lang="ts">
/**
 * BulkActionBar Component
 *
 * A shared action bar for bulk operations on selected containers.
 * Displays count, cancel button, and action buttons (start/stop/restart/delete).
 * Uses slide-down transition for smooth appearance/disappearance.
 */

import { VideoPlay, VideoPause, RefreshRight, Delete } from '@element-plus/icons-vue'

export interface BulkActionBarProps {
  /** Number of selected items */
  selectedCount: number
  /** Currently loading action key (null if none) */
  loadingAction: string | null
}

defineProps<BulkActionBarProps>()

const emit = defineEmits<{
  (e: 'start'): void
  (e: 'stop'): void
  (e: 'restart'): void
  (e: 'delete'): void
  (e: 'cancel'): void
}>()
</script>

<style scoped>
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

:deep(.el-icon--left) {
  margin-right: 6px;
}
</style>
