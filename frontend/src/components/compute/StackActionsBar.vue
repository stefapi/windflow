<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { stacksApi } from '@/services/api'
import type { StackWithServices, RedeployStrategy } from '@/types/api'

const props = defineProps<{
  stack: StackWithServices
}>()

const emit = defineEmits<{
  (e: 'action-completed', stackId: string): void
}>()

const loading = ref(false)
const redeployDialogVisible = ref(false)
const selectedStrategy = ref<RedeployStrategy>('stop_start')

const statusColor = computed(() => {
  switch (props.stack.status) {
    case 'running':
      return 'success'
    case 'partial':
      return 'warning'
    case 'stopped':
      return 'danger'
    default:
      return 'info'
  }
})

const statusLabel = computed(() => {
  switch (props.stack.status) {
    case 'running':
      return 'En cours'
    case 'partial':
      return 'Partiel'
    case 'stopped':
      return 'Arrêté'
    case 'archived':
      return 'Archivé'
    default:
      return props.stack.status
  }
})

const allRunning = computed(() => props.stack.services_running === props.stack.services_total)
const allStopped = computed(() => props.stack.services_running === 0)

async function handleStart() {
  try {
    await ElMessageBox.confirm(
      `Démarrer tous les services de la stack "${props.stack.name}" ?`,
      'Démarrer la stack',
      { confirmButtonText: 'Démarrer', cancelButtonText: 'Annuler', type: 'info' },
    )
  } catch {
    return
  }

  loading.value = true
  try {
    const { data } = await stacksApi.start(props.stack.id)
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.warning(data.message)
    }
    emit('action-completed', props.stack.id)
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Erreur lors du démarrage'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

async function handleStop() {
  try {
    await ElMessageBox.confirm(
      `Arrêter tous les services de la stack "${props.stack.name}" ?`,
      'Arrêter la stack',
      { confirmButtonText: 'Arrêter', cancelButtonText: 'Annuler', type: 'warning' },
    )
  } catch {
    return
  }

  loading.value = true
  try {
    const { data } = await stacksApi.stop(props.stack.id)
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.warning(data.message)
    }
    emit('action-completed', props.stack.id)
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Erreur lors de l\'arrêt'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}

function openRedeployDialog() {
  selectedStrategy.value = 'stop_start'
  redeployDialogVisible.value = true
}

async function handleRedeploy() {
  redeployDialogVisible.value = false
  loading.value = true
  try {
    const { data } = await stacksApi.redeploy(props.stack.id, {
      strategy: selectedStrategy.value,
    })
    if (data.success) {
      ElMessage.success(data.message)
    } else {
      ElMessage.warning(data.message)
    }
    emit('action-completed', props.stack.id)
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : 'Erreur lors du redéploiement'
    ElMessage.error(msg)
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="stack-actions-bar">
    <div class="stack-info">
      <span class="stack-name">{{ stack.name }}</span>
      <el-tag :type="statusColor" size="small" effect="dark" class="status-tag">
        {{ statusLabel }}
      </el-tag>
      <span class="services-count">
        {{ stack.services_running }}/{{ stack.services_total }} services
      </span>
    </div>

    <div class="stack-actions">
      <el-button
        type="success"
        size="small"
        :icon="'VideoPlay'"
        :loading="loading"
        :disabled="allRunning"
        @click="handleStart"
      >
        Démarrer
      </el-button>

      <el-button
        type="warning"
        size="small"
        :icon="'VideoPause'"
        :loading="loading"
        :disabled="allStopped"
        @click="handleStop"
      >
        Arrêter
      </el-button>

      <el-button
        type="primary"
        size="small"
        :icon="'RefreshRight'"
        :loading="loading"
        @click="openRedeployDialog"
      >
        Redéployer
      </el-button>
    </div>

    <!-- Redeploy Dialog -->
    <el-dialog
      v-model="redeployDialogVisible"
      title="Redéployer la stack"
      width="450px"
      :close-on-click-modal="false"
    >
      <p class="redeploy-info">
        Choisissez la stratégie de redéploiement pour la stack
        <strong>{{ stack.name }}</strong> :
      </p>

      <el-radio-group v-model="selectedStrategy" class="strategy-group">
        <el-radio value="stop_start" size="large" class="strategy-radio">
          <div class="strategy-option">
            <strong>Arrêt puis démarrage</strong>
            <p>Arrête tous les services, puis les redémarre. Temps d'arrêt court garanti.</p>
          </div>
        </el-radio>
        <el-radio value="rolling" size="large" class="strategy-radio">
          <div class="strategy-option">
            <strong>Rolling (séquentiel)</strong>
            <p>Redémarre les services un par un. Maintient la disponibilité si possible.</p>
          </div>
        </el-radio>
      </el-radio-group>

      <template #footer>
        <el-button @click="redeployDialogVisible = false">Annuler</el-button>
        <el-button
          type="primary"
          :loading="loading"
          @click="handleRedeploy"
        >
          Redéployer
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stack-actions-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 12px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  gap: 12px;
}

.stack-info {
  display: flex;
  align-items: center;
  gap: 8px;
}

.stack-name {
  font-weight: 600;
  font-size: 14px;
}

.status-tag {
  text-transform: capitalize;
}

.services-count {
  color: var(--el-text-color-secondary);
  font-size: 12px;
}

.stack-actions {
  display: flex;
  gap: 6px;
}

.redeploy-info {
  margin-bottom: 16px;
  color: var(--el-text-color-regular);
}

.strategy-group {
  display: flex;
  flex-direction: column;
  gap: 12px;
  width: 100%;
}

.strategy-radio {
  display: flex;
  align-items: flex-start;
  width: 100%;
}

.strategy-option strong {
  display: block;
  margin-bottom: 4px;
}

.strategy-option p {
  margin: 0;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
