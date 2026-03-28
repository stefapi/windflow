<template>
  <div class="section mb-6">
    <div class="section-header mb-3 flex items-center gap-2">
      <span class="inline-block w-3 h-3 rounded-sm bg-blue-600" />
      <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
        STACKS WINDFLOW
        <span class="text-gray-400 font-normal">(managées, source of truth dans WindFlow)</span>
      </span>
    </div>

    <!-- Loading -->
    <div
      v-if="loading"
      class="flex justify-center py-8"
    >
      <el-icon class="is-loading text-2xl text-blue-500">
        <Loading />
      </el-icon>
    </div>

    <!-- Empty -->
    <el-empty
      v-else-if="stacks.length === 0"
      description="Aucune stack WindFlow avec des instances actives"
    />

    <!-- Stacks collapse -->
    <el-collapse
      v-else
      class="stacks-collapse"
    >
      <el-collapse-item
        v-for="stack in stacks"
        :key="stack.id"
        :name="stack.id"
      >
        <template #title>
          <div class="flex flex-wrap items-center gap-2 w-full pr-4">
            <span class="font-semibold text-sm">{{ stack.name }}</span>
            <el-tag
              type="primary"
              size="small"
            >
              stack WindFlow
            </el-tag>
            <el-tag size="small">
              {{ stack.technology }}
            </el-tag>
            <el-tag
              size="small"
              type="info"
            >
              ● {{ stack.target_name }}
            </el-tag>
            <span
              class="text-xs font-semibold"
              :class="servicesRunningClass(stack.services_running, stack.services_total)"
            >
              {{ stack.services_running }}/{{ stack.services_total }} running
            </span>
            <div class="ml-auto flex items-center gap-1">
              <el-button
                size="small"
                text
                title="Copier ID"
                @click.stop="emit('copy-id', stack.id)"
              >
                📄
              </el-button>
              <el-button
                size="small"
                text
                title="Rafraîchir"
                @click.stop="emit('refresh')"
              >
                🔄
              </el-button>
              <el-button
                size="small"
                type="primary"
                @click.stop
              >
                Éditer stack
              </el-button>
            </div>
          </div>
        </template>

        <ContainerTable
          :items="stack.services.map(s => serviceToRow(s, stack.target_name))"
          :columns="['name', 'image', 'status', 'cpu', 'memory', 'actions']"
          :show-actions="true"
          @action="(type, item) => handleServiceAction(type, item)"
        />
      </el-collapse-item>
    </el-collapse>
  </div>
</template>

<script setup lang="ts">
/**
 * ManagedStacksSection Component
 *
 * Displays managed WindFlow stacks in a collapsible list.
 * Each stack shows its services in a ContainerTable with individual actions.
 */

import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading } from '@element-plus/icons-vue'
import { containersApi } from '@/services/api'
import ContainerTable from './ContainerTable.vue'
import { serviceToRow, servicesRunningClass } from './helpers'
import type { ContainerTableRow } from './helpers'
import type { StackWithServices } from '@/types/api'
import type { ActionType } from '@/components/ui/ActionButtons.vue'

export interface ManagedStacksSectionProps {
  stacks: StackWithServices[]
  loading: boolean
}

defineProps<ManagedStacksSectionProps>()

const emit = defineEmits<{
  (e: 'refresh'): void
  (e: 'copy-id', id: string): void
}>()

const router = useRouter()

async function handleServiceAction(type: ActionType, item: ContainerTableRow): Promise<void> {
  switch (type) {
    case 'start':
      try {
        await containersApi.start(item.id)
        ElMessage.success('Container démarré')
        emit('refresh')
      } catch {
        ElMessage.error('Erreur lors du démarrage du container')
      }
      break
    case 'stop':
      try {
        await containersApi.stop(item.id)
        ElMessage.success('Container arrêté')
        emit('refresh')
      } catch {
        ElMessage.error("Erreur lors de l'arrêt du container")
      }
      break
    case 'restart':
      try {
        await containersApi.restart(item.id)
        ElMessage.success('Container redémarré')
        emit('refresh')
      } catch {
        ElMessage.error('Erreur lors du redémarrage du container')
      }
      break
    case 'logs':
      router.push(`/containers/${item.id}`)
      break
    case 'delete':
      try {
        await ElMessageBox.confirm(
          'Supprimer ce container ? Cette action est irréversible.',
          'Confirmation',
          { confirmButtonText: 'Supprimer', cancelButtonText: 'Annuler', type: 'warning' },
        )
        await containersApi.remove(item.id)
        ElMessage.success('Container supprimé')
        emit('refresh')
      } catch (err) {
        if (err !== 'cancel') {
          ElMessage.error('Erreur lors de la suppression du container')
        }
      }
      break
  }
}
</script>

<style scoped>
.section-header {
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.stacks-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 44px;
  padding: 8px 16px;
}
</style>
