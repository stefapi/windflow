<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useDeploymentsStore } from '@/stores'
import { ElMessage } from 'element-plus'
import { ArrowLeft, ArrowRight } from '@element-plus/icons-vue'
import ContainerTerminal from '@/components/ContainerTerminal.vue'
import type { Deployment } from '@/types/api'

const route = useRoute()
const router = useRouter()
const deploymentsStore = useDeploymentsStore()

// Props from router
const containerIdFromRoute = computed(() => route.params['containerId'] as string)

// État local
const selectedContainerId = ref<string>('')
const selectedShell = ref('/bin/sh')
const isLoading = ref(false)

// Options de shell
const shellOptions = [
  { value: '/bin/bash', label: 'Bash' },
  { value: '/bin/sh', label: 'Shell (sh)' },
  { value: '/bin/zsh', label: 'Zsh' },
  { value: '/bin/ash', label: 'Ash (Alpine)' },
]

// Charger les déploiements au montage
onMounted(async () => {
  isLoading.value = true
  try {
    await deploymentsStore.fetchDeployments()

    // Si un containerId est fourni dans l'URL, l'utiliser
    if (containerIdFromRoute.value) {
      selectedContainerId.value = containerIdFromRoute.value
    }
  } catch (error) {
    ElMessage.error('Failed to load deployments')
  } finally {
    isLoading.value = false
  }
})

// Computed: liste des containers disponibles (deployments running)
const availableContainers = computed(() => {
  const containers: { id: string; name: string; status: string }[] = []

  for (const deployment of deploymentsStore.deployments) {
    // Support both backend and frontend status values
    if ((deployment.status === 'running' || deployment.status === 'completed') && deployment.container_id) {
      containers.push({
        id: deployment.container_id,
        name: deployment.name || deployment.id.slice(0, 12),
        status: deployment.status
      })
    }
  }

  return containers
})

// Computed: déploiement actuellement sélectionné
const selectedDeployment = computed<Deployment | null>(() => {
  if (!selectedContainerId.value) return null
  return deploymentsStore.deployments.find(
    d => d.container_id === selectedContainerId.value
  ) || null
})

// Gérer le changement de container
function onContainerChange(containerId: string) {
  selectedContainerId.value = containerId
  // Mettre à jour l'URL
  if (containerId) {
    router.replace({ path: `/terminal/${containerId}` })
  } else {
    router.replace({ path: '/terminal' })
  }
}

// Fonction pour formater l'ID du container
function formatContainerId(id: string): string {
  return id.length > 12 ? id.slice(0, 12) + '...' : id
}
</script>

<template>
  <div class="terminal-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <el-button
          text
          class="back-button"
          @click="$router.push('/deployments')"
        >
          <el-icon><ArrowLeft /></el-icon>
          Back to Deployments
        </el-button>
        <h1 class="page-title">
          Terminal
        </h1>
      </div>
    </div>

    <!-- Sélecteur de container -->
    <el-card class="selector-card">
      <el-row
        :gutter="20"
        align="middle"
      >
        <el-col :span="12">
          <el-form-item label="Container">
            <el-select
              v-model="selectedContainerId"
              placeholder="Select a running container"
              filterable
              :loading="isLoading"
              style="width: 100%"
              @change="onContainerChange"
            >
              <el-option
                v-for="container in availableContainers"
                :key="container.id"
                :label="`${container.name} (${formatContainerId(container.id)})`"
                :value="container.id"
              >
                <div class="container-option">
                  <span class="container-name">{{ container.name }}</span>
                  <el-tag
                    size="small"
                    type="success"
                  >
                    {{ container.status }}
                  </el-tag>
                  <code class="container-id">{{ formatContainerId(container.id) }}</code>
                </div>
              </el-option>
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :span="6">
          <el-form-item label="Shell">
            <el-select
              v-model="selectedShell"
              style="width: 100%"
            >
              <el-option
                v-for="shell in shellOptions"
                :key="shell.value"
                :label="shell.label"
                :value="shell.value"
              />
            </el-select>
          </el-form-item>
        </el-col>

        <el-col :span="6">
          <div class="header-actions">
            <el-button
              v-if="selectedDeployment"
              text
              type="primary"
              @click="$router.push(`/deployments/${selectedDeployment.id}`)"
            >
              View Deployment
              <el-icon><ArrowRight /></el-icon>
            </el-button>
          </div>
        </el-col>
      </el-row>

      <!-- Message si aucun container disponible -->
      <el-empty
        v-if="!isLoading && availableContainers.length === 0"
        description="No running containers found. Deploy a stack first to access the terminal."
        :image-size="80"
      >
        <el-button
          type="primary"
          @click="$router.push('/stacks')"
        >
          Go to Stacks
        </el-button>
      </el-empty>
    </el-card>

    <!-- Terminal -->
    <el-card
      v-if="selectedContainerId"
      class="terminal-card"
    >
      <ContainerTerminal
        :container-id="selectedContainerId"
        :shell="selectedShell"
        :user="'root'"
        :theme="'dark'"
        :font-size="14"
      />
    </el-card>

    <!-- Message d'aide -->
    <el-card
      v-else
      class="help-card"
    >
      <el-alert
        type="info"
        :closable="false"
      >
        <template #title>
          <span>How to use the terminal</span>
        </template>
        <div class="help-content">
          <p>Select a running container from the dropdown above to start an interactive terminal session.</p>
          <ul>
            <li><code>Ctrl+L</code> - Clear terminal</li>
            <li><code>Ctrl+Shift+C</code> - Copy selected text</li>
            <li><code>Ctrl+Shift+V</code> - Paste</li>
            <li>The terminal supports xterm-256color</li>
          </ul>
        </div>
      </el-alert>
    </el-card>
  </div>
</template>

<style scoped>
.terminal-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
  height: calc(100vh - 100px);
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.back-button {
  display: flex;
  align-items: center;
  gap: 4px;
}

.page-title {
  font-size: 24px;
  font-weight: 600;
  margin: 0;
}

.selector-card {
  flex-shrink: 0;
}

.selector-card :deep(.el-card__body) {
  padding: 16px 20px;
}

.container-option {
  display: flex;
  align-items: center;
  gap: 12px;
}

.container-name {
  font-weight: 500;
}

.container-id {
  margin-left: auto;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.header-actions {
  display: flex;
  justify-content: flex-end;
}

.terminal-card {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}

.terminal-card :deep(.el-card__body) {
  flex: 1;
  padding: 0;
  display: flex;
  min-height: 400px;
}

.help-card {
  flex-shrink: 0;
}

.help-content {
  margin-top: 8px;
}

.help-content ul {
  margin: 8px 0 0 0;
  padding-left: 20px;
}

.help-content li {
  margin: 4px 0;
}

.help-content code {
  background-color: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 4px;
  font-size: 12px;
}
</style>
