<template>
  <div class="image-detail">
    <el-card>
      <template #header>
        <div class="card-header">
          <el-button
            :icon="ArrowLeft"
            @click="router.push({ name: 'Images' })"
          >
            Retour
          </el-button>
          <span>Détail de l'image</span>
        </div>
      </template>

      <div v-loading="loading">
        <template v-if="image">
          <!-- Identité -->
          <h3>Identité</h3>
          <el-descriptions
            :column="1"
            border
          >
            <el-descriptions-item label="ID">
              <code>{{ image.id }}</code>
            </el-descriptions-item>
            <el-descriptions-item label="Tags">
              <el-tag
                v-for="tag in image.repoTags"
                :key="tag"
                size="small"
                class="tag-spacing"
              >
                {{ tag }}
              </el-tag>
              <span
                v-if="image.repoTags.length === 0"
                class="none-label"
              >{{ noneLabel }}</span>
            </el-descriptions-item>
            <el-descriptions-item label="Digests">
              <div
                v-for="digest in image.repoDigests"
                :key="digest"
                class="digest-item"
              >
                <code>{{ digest }}</code>
              </div>
              <span
                v-if="image.repoDigests.length === 0"
                class="none-label"
              >Aucun</span>
            </el-descriptions-item>
            <el-descriptions-item label="Date de création">
              {{ formatDate(image.created) }}
            </el-descriptions-item>
            <el-descriptions-item label="Taille">
              {{ formatBytes(image.size) }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- Configuration -->
          <h3 style="margin-top: 24px">
            Configuration
          </h3>
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item label="Architecture">
              {{ image.architecture || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="OS">
              {{ image.os || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="Commande (Cmd)">
              <code v-if="image.cmd">{{ image.cmd.join(' ') }}</code>
              <span
                v-else
                class="none-label"
              >-</span>
            </el-descriptions-item>
            <el-descriptions-item label="Entrypoint">
              <code v-if="image.entrypoint">{{ image.entrypoint.join(' ') }}</code>
              <span
                v-else
                class="none-label"
              >-</span>
            </el-descriptions-item>
            <el-descriptions-item label="Docker Version">
              {{ image.dockerVersion || '-' }}
            </el-descriptions-item>
            <el-descriptions-item label="Auteur">
              {{ image.author || '-' }}
            </el-descriptions-item>
          </el-descriptions>

          <!-- Variables d'environnement -->
          <template v-if="image.env && image.env.length > 0">
            <h4 style="margin-top: 16px">
              Variables d'environnement
            </h4>
            <el-table
              :data="image.env.map((e) => ({ full: e, name: e.split('=')[0], value: e.substring(e.indexOf('=') + 1) }))"
              size="small"
              border
            >
              <el-table-column
                prop="name"
                label="Nom"
                width="250"
              />
              <el-table-column
                prop="value"
                label="Valeur"
              />
            </el-table>
          </template>

          <!-- Ports exposés -->
          <template v-if="image.exposedPorts && Object.keys(image.exposedPorts).length > 0">
            <h4 style="margin-top: 16px">
              Ports exposés
            </h4>
            <div class="ports-list">
              <el-tag
                v-for="port in Object.keys(image.exposedPorts)"
                :key="port"
                size="small"
                class="tag-spacing"
              >
                {{ port }}
              </el-tag>
            </div>
          </template>

          <!-- Labels -->
          <template v-if="Object.keys(image.labels).length > 0">
            <h3 style="margin-top: 24px">
              Labels
            </h3>
            <el-descriptions
              :column="1"
              border
            >
              <el-descriptions-item
                v-for="(value, key) in image.labels"
                :key="key"
                :label="String(key)"
              >
                {{ value }}
              </el-descriptions-item>
            </el-descriptions>
          </template>
        </template>

        <el-empty
          v-if="!loading && !image && error"
          :description="error"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { imagesApi } from '@/services/api'
import type { ImageDetailResponse } from '@/types/api'
import { formatBytes } from '@/utils/format'
import { ElMessage } from 'element-plus'
import { ArrowLeft } from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()

const image = ref<ImageDetailResponse | null>(null)
const loading = ref(false)
const error = ref('')
const noneLabel = '<none>'

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

async function fetchImage() {
  const imageId = route.params['id'] as string
  if (!imageId) {
    error.value = 'ID image manquant'
    return
  }

  loading.value = true
  error.value = ''
  try {
    const { data } = await imagesApi.get(imageId)
    image.value = data
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors du chargement de l\'image'
    error.value = message
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  fetchImage()
})
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.tag-spacing {
  margin-right: 4px;
  margin-bottom: 2px;
}

.none-label {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}

.digest-item {
  margin-bottom: 2px;
}

.ports-list {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}
</style>
