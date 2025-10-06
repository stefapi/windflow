<template>
  <div class="deployment-history p-6">
    <h1 class="text-2xl font-bold mb-6">Historique des déploiements</h1>

    <!-- Filtres -->
    <el-card class="mb-6">
      <el-form :inline="true">
        <el-form-item label="Stack">
          <el-select v-model="filters.stackId" placeholder="Tous" clearable @change="loadHistory">
            <el-option label="Tous les stacks" value="" />
            <!-- Options stacks dynamiques -->
          </el-select>
        </el-form-item>
        <el-form-item label="Statut">
          <el-select v-model="filters.status" placeholder="Tous" clearable @change="loadHistory">
            <el-option label="Tous" value="" />
            <el-option label="Succès" value="success" />
            <el-option label="Échec" value="failed" />
            <el-option label="En cours" value="running" />
          </el-select>
        </el-form-item>
      </el-form>
    </el-card>

    <!-- Timeline -->
    <el-timeline v-if="deployments.length > 0">
      <el-timeline-item
        v-for="deployment in deployments"
        :key="deployment.id"
        :timestamp="formatDate(deployment.created_at)"
        :type="getStatusType(deployment.status)"
      >
        <el-card>
          <div class="flex justify-between items-start">
            <div>
              <h3 class="text-lg font-medium">{{ deployment.name }}</h3>
              <p class="text-sm text-gray-600">Stack: {{ deployment.stack?.name }}</p>
              <p class="text-sm text-gray-600">Cible: {{ deployment.target?.name }}</p>
            </div>
            <el-tag :type="getStatusTagType(deployment.status)">
              {{ deployment.status }}
            </el-tag>
          </div>
        </el-card>
      </el-timeline-item>
    </el-timeline>

    <div v-else class="text-center py-12 text-gray-500">
      Aucun déploiement dans l'historique
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'

const deployments = ref<any[]>([])
const filters = ref({
  stackId: '',
  status: ''
})

async function loadHistory() {
  try {
    const response = await axios.get('/api/v1/deployments', {
      params: filters.value
    })
    deployments.value = response.data.data || []
  } catch (error) {
    console.error(error)
  }
}

function formatDate(dateString: string): string {
  return new Date(dateString).toLocaleString('fr-FR')
}

function getStatusType(status: string): string {
  const types: Record<string, string> = {
    success: 'success',
    failed: 'danger',
    running: 'primary',
    pending: 'info'
  }
  return types[status] || 'info'
}

function getStatusTagType(status: string): string {
  return getStatusType(status)
}

onMounted(() => {
  loadHistory()
})
</script>
