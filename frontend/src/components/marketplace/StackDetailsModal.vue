<template>
  <el-dialog
    v-model="visible"
    :title="stack?.name || 'Chargement...'"
    width="900px"
    @close="handleClose"
  >
    <div v-if="loading" v-loading="true" class="h-96" />

    <div v-else-if="stack" class="stack-details">
      <!-- En-tête avec image et infos principales -->
      <div class="flex gap-6 mb-6 pb-6 border-b">
        <!-- Image/Icône -->
        <div class="flex-shrink-0">
          <div class="w-24 h-24 bg-gradient-to-br from-primary-50 to-primary-100 rounded-lg flex items-center justify-center">
            <img
              v-if="stack.icon_url"
              :src="stack.icon_url"
              :alt="stack.name"
              class="w-20 h-20 object-contain"
            >
            <el-icon v-else class="text-5xl text-primary-400">
              <Box />
            </el-icon>
          </div>
        </div>

        <!-- Informations -->
        <div class="flex-1">
          <div class="flex items-start justify-between mb-2">
            <div>
              <h2 class="text-2xl font-bold text-gray-900">
                {{ stack.name }}
              </h2>
              <p class="text-gray-600">
                Version {{ stack.version }}
                <span v-if="stack.author" class="ml-2">• par {{ stack.author }}</span>
              </p>
            </div>

            <el-tag v-if="stack.category" :type="getCategoryType(stack.category)">
              {{ stack.category }}
            </el-tag>
          </div>

          <p class="text-gray-700 mb-4">
            {{ stack.description }}
          </p>

          <!-- Stats -->
          <div class="flex items-center gap-6 text-sm">
            <div class="flex items-center gap-1">
              <el-icon><Download /></el-icon>
              <span>{{ stack.downloads }} téléchargements</span>
            </div>

            <div v-if="stack.rating > 0" class="flex items-center gap-1">
              <el-icon class="text-yellow-500"><StarFilled /></el-icon>
              <span>{{ stack.rating.toFixed(1) }} / 5</span>
            </div>

            <div v-if="stack.license" class="flex items-center gap-1">
              <el-icon><Document /></el-icon>
              <span>{{ stack.license }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Tags -->
      <div v-if="stack.tags.length > 0" class="mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">Tags</h3>
        <div class="flex flex-wrap gap-2">
          <el-tag
            v-for="tag in stack.tags"
            :key="tag"
            effect="plain"
            size="small"
          >
            {{ tag }}
          </el-tag>
        </div>
      </div>

      <!-- Screenshots -->
      <div v-if="stack.screenshots.length > 0" class="mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">Captures d'écran</h3>
        <div class="grid grid-cols-2 gap-4">
          <img
            v-for="(screenshot, index) in stack.screenshots"
            :key="index"
            :src="screenshot"
            :alt="`Screenshot ${index + 1}`"
            class="rounded-lg border border-gray-200 w-full h-48 object-cover cursor-pointer hover:opacity-80 transition-opacity"
            @click="viewScreenshot(screenshot)"
          >
        </div>
      </div>

      <!-- Informations techniques -->
      <div class="mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">Informations techniques</h3>
        <el-descriptions :column="2" border>
          <el-descriptions-item label="Services">
            {{ Object.keys(stack.template.services || {}).length }} service(s)
          </el-descriptions-item>
          <el-descriptions-item label="Volumes">
            {{ Object.keys(stack.template.volumes || {}).length }} volume(s)
          </el-descriptions-item>
          <el-descriptions-item label="Réseaux">
            {{ Object.keys(stack.template.networks || {}).length }} réseau(x)
          </el-descriptions-item>
          <el-descriptions-item label="Version Compose">
            {{ stack.template.version || 'N/A' }}
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <!-- Variables configurables -->
      <div class="mb-6">
        <h3 class="text-sm font-semibold text-gray-700 mb-2">
          Variables configurables
          <el-tag size="small" class="ml-2">
            {{ Object.keys(stack.variables).length }} paramètre(s)
          </el-tag>
        </h3>
        <el-table :data="variablesArray" size="small">
          <el-table-column prop="name" label="Nom" width="200" />
          <el-table-column prop="label" label="Libellé" />
          <el-table-column prop="type" label="Type" width="100">
            <template #default="{ row }">
              <el-tag size="small" effect="plain">
                {{ row.type }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="required" label="Requis" width="80" align="center">
            <template #default="{ row }">
              <el-icon v-if="row.required" class="text-red-500">
                <CircleCheck />
              </el-icon>
            </template>
          </el-table-column>
        </el-table>
      </div>

      <!-- Documentation -->
      <div v-if="stack.documentation_url" class="mb-6">
        <el-alert type="info" :closable="false">
          <div class="flex items-center justify-between">
            <span>Documentation officielle disponible</span>
            <el-button
              size="small"
              :icon="Link"
              @click="openDocumentation"
            >
              Consulter
            </el-button>
          </div>
        </el-alert>
      </div>
    </div>

    <template #footer>
      <div class="flex justify-between items-center">
        <el-button @click="handleClose">
          Fermer
        </el-button>
        <div class="flex gap-2">
          <el-button
            v-if="stack"
            :icon="FolderAdd"
            @click="installToOrganization"
            :loading="installing"
          >
            Installer dans mon organisation
          </el-button>
          <el-button
            v-if="stack"
            type="primary"
            :icon="Promotion"
            @click="startDeployment"
          >
            Déployer
          </el-button>
        </div>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useMarketplaceStore } from '@/stores/marketplace'
import type { StackDetails } from '@/types/marketplace'
import {
  Box,
  Download,
  StarFilled,
  Document,
  CircleCheck,
  Link,
  FolderAdd,
  Promotion
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface Props {
  stackId: string
  visible: boolean
}

interface Emits {
  'update:visible': [value: boolean]
  deploy: [stack: StackDetails]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const store = useMarketplaceStore()
const stack = ref<StackDetails | null>(null)
const loading = ref(false)
const installing = ref(false)

// Computed
const variablesArray = computed(() => {
  if (!stack.value) return []

  return Object.entries(stack.value.variables).map(([name, variable]) => ({
    name,
    label: variable.label,
    type: variable.type,
    required: variable.required || false,
    description: variable.description
  }))
})

// Watchers
watch(() => props.visible, async (isVisible) => {
  if (isVisible && props.stackId) {
    await loadStackDetails()
  }
})

// Methods
async function loadStackDetails() {
  loading.value = true
  try {
    stack.value = await store.fetchStackDetails(props.stackId)
  } catch (err) {
    ElMessage.error('Erreur lors du chargement des détails')
    handleClose()
  } finally {
    loading.value = false
  }
}

function handleClose() {
  emit('update:visible', false)
  stack.value = null
}

function getCategoryType(category: string): string {
  const types: Record<string, string> = {
    'database': 'primary',
    'cms': 'success',
    'dev-tools': 'warning',
    'monitoring': 'info',
    'storage': 'danger'
  }
  return types[category] || ''
}

function viewScreenshot(url: string) {
  window.open(url, '_blank')
}

function openDocumentation() {
  if (stack.value?.documentation_url) {
    window.open(stack.value.documentation_url, '_blank')
  }
}

async function installToOrganization() {
  if (!stack.value) return

  installing.value = true
  try {
    await store.installStack(stack.value.id)
    handleClose()
  } catch (err) {
    // Erreur gérée par le store
  } finally {
    installing.value = false
  }
}

function startDeployment() {
  if (stack.value) {
    emit('deploy', stack.value)
  }
}
</script>

<style scoped>
.stack-details {
  max-height: 70vh;
  overflow-y: auto;
}
</style>
