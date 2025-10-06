<template>
  <div class="target-selector">
    <el-alert
      type="info"
      :closable="false"
      class="mb-4"
    >
      <p class="text-sm">
        Sélectionnez la cible où vous souhaitez déployer ce stack
      </p>
    </el-alert>

    <div v-loading="loading">
      <!-- Liste des targets -->
      <div v-if="targets.length > 0" class="targets-list space-y-3">
        <div
          v-for="target in targets"
          :key="target.id"
          class="target-item p-4 border rounded-lg cursor-pointer transition-all"
          :class="{
            'border-primary bg-primary-50': modelValue === target.id,
            'border-gray-200 hover:border-primary-300 hover:bg-gray-50': modelValue !== target.id
          }"
          @click="selectTarget(target.id)"
        >
          <div class="flex items-start justify-between">
            <div class="flex items-start gap-3 flex-1">
              <!-- Icône type de cible -->
              <div class="flex-shrink-0">
                <div
                  class="w-12 h-12 rounded-lg flex items-center justify-center"
                  :class="getTargetIconBg(target.type)"
                >
                  <el-icon :size="24" :class="getTargetIconColor(target.type)">
                    <component :is="getTargetIcon(target.type)" />
                  </el-icon>
                </div>
              </div>

              <!-- Infos -->
              <div class="flex-1">
                <div class="flex items-center gap-2 mb-1">
                  <h4 class="font-semibold text-gray-900">
                    {{ target.name }}
                  </h4>
                  <el-tag size="small" effect="plain">
                    {{ target.type }}
                  </el-tag>
                  <el-tag
                    v-if="target.status"
                    :type="target.status === 'online' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ target.status }}
                  </el-tag>
                </div>

                <p class="text-sm text-gray-600 mb-2">
                  {{ target.host }}
                </p>

                <p v-if="target.description" class="text-sm text-gray-500">
                  {{ target.description }}
                </p>
              </div>

              <!-- Radio button -->
              <div class="flex-shrink-0">
                <el-radio
                  :model-value="modelValue"
                  :label="target.id"
                  @click.stop="selectTarget(target.id)"
                />
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Message vide -->
      <el-empty
        v-else-if="!loading"
        description="Aucune cible de déploiement disponible"
        :image-size="150"
      >
        <el-button type="primary" @click="goToTargetsPage">
          Configurer une cible
        </el-button>
      </el-empty>
    </div>

    <!-- Aide -->
    <el-alert
      type="warning"
      :closable="false"
      class="mt-4"
      v-if="targets.length > 0"
    >
      <div class="flex items-start gap-2">
        <el-icon><Warning /></el-icon>
        <div class="text-sm">
          <p class="font-medium mb-1">À propos des cibles</p>
          <ul class="list-disc list-inside space-y-1">
            <li><strong>Docker:</strong> Déploiement local ou serveur distant via Docker Compose</li>
            <li><strong>Kubernetes:</strong> Déploiement sur cluster K8s</li>
            <li><strong>VM:</strong> Machine virtuelle dédiée</li>
            <li><strong>Physical:</strong> Serveur physique</li>
          </ul>
        </div>
      </div>
    </el-alert>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import type { Target } from '@/types/marketplace'
import {
  Monitor,
  Platform,
  Server,
  Box,
  Warning
} from '@element-plus/icons-vue'

interface Props {
  modelValue: string
}

interface Emits {
  'update:modelValue': [value: string]
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const router = useRouter()
const targets = ref<Target[]>([])
const loading = ref(false)

function selectTarget(targetId: string) {
  emit('update:modelValue', targetId)
}

function getTargetIcon(type: string) {
  const icons: Record<string, any> = {
    'docker': Box,
    'kubernetes': Platform,
    'vm': Monitor,
    'physical': Server
  }
  return icons[type] || Box
}

function getTargetIconBg(type: string): string {
  const backgrounds: Record<string, string> = {
    'docker': 'bg-blue-100',
    'kubernetes': 'bg-purple-100',
    'vm': 'bg-green-100',
    'physical': 'bg-orange-100'
  }
  return backgrounds[type] || 'bg-gray-100'
}

function getTargetIconColor(type: string): string {
  const colors: Record<string, string> = {
    'docker': 'text-blue-600',
    'kubernetes': 'text-purple-600',
    'vm': 'text-green-600',
    'physical': 'text-orange-600'
  }
  return colors[type] || 'text-gray-600'
}

function goToTargetsPage() {
  router.push('/targets')
}

async function loadTargets() {
  loading.value = true
  try {
    // TODO: Implémenter avec le vrai service targets
    // const response = await targetsService.list()
    // targets.value = response.data

    // Mock pour développement
    targets.value = [
      {
        id: 'target-docker-local',
        name: 'Docker Local',
        type: 'docker',
        host: 'localhost',
        description: 'Docker local sur cette machine',
        status: 'online'
      },
      {
        id: 'target-k8s-prod',
        name: 'Kubernetes Production',
        type: 'kubernetes',
        host: 'k8s.exemple.com',
        description: 'Cluster Kubernetes de production',
        status: 'online'
      }
    ]
  } catch (err) {
    console.error('Erreur chargement des cibles:', err)
  } finally {
    loading.value = false
  }
}

onMounted(async () => {
  await loadTargets()
})
</script>

<style scoped>
.target-item {
  transition: all 0.2s;
}

.target-item:hover {
  transform: translateY(-2px);
}
</style>
