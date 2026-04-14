<template>
  <div class="images">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Images</span>
          <el-button
            type="primary"
            :icon="Download"
            @click="pullDialogVisible = true"
          >
            Pull image
          </el-button>
          <el-input
            v-model="searchQuery"
            placeholder="Rechercher par tag ou ID..."
            clearable
            style="width: 300px"
            :prefix-icon="Search"
          />
        </div>
      </template>
      <el-table
        v-loading="loading"
        :data="filteredImages"
        stripe
      >
        <el-table-column
          label="ID"
          width="180"
        >
          <template #default="{ row }">
            <span :title="row.id">{{ row.id.substring(0, 12) }}...</span>
          </template>
        </el-table-column>
        <el-table-column label="Tags">
          <template #default="{ row }">
            <template v-if="row.repoTags.length > 0">
              <el-tag
                v-for="tag in row.repoTags"
                :key="tag"
                size="small"
                class="tag-spacing"
              >
                {{ tag }}
              </el-tag>
            </template>
            <span
              v-else
              class="none-label"
            >{{ noneLabel }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Taille"
          width="150"
        >
          <template #default="{ row }">
            {{ formatBytes(row.size) }}
          </template>
        </el-table-column>
        <el-table-column
          label="Date de création"
          width="220"
        >
          <template #default="{ row }">
            {{ formatDate(row.created) }}
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="120"
        >
          <template #default="{ row }">
            <el-button
              type="danger"
              :icon="Delete"
              size="small"
              @click="handleDelete(row)"
            />
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!loading && images.length === 0"
        description="Aucune image trouvée"
      />
    </el-card>

    <el-dialog
      v-model="pullDialogVisible"
      title="Pull une image"
      width="450px"
    >
      <el-form label-width="120px">
        <el-form-item label="Nom de l'image">
          <el-input
            v-model="pullForm.name"
            placeholder="ex: nginx"
          />
        </el-form-item>
        <el-form-item label="Tag">
          <el-input
            v-model="pullForm.tag"
            placeholder="latest"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="pullDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="pulling"
          @click="handlePull"
        >
          Pull
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { imagesApi } from '@/services/api'
import type { ImageResponse, ImagePullRequest } from '@/types/api'
import { formatBytes } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download, Delete } from '@element-plus/icons-vue'

const images = ref<ImageResponse[]>([])
const loading = ref(false)
const searchQuery = ref('')
const noneLabel = '<none>'

const pullDialogVisible = ref(false)
const pullForm = ref({ name: '', tag: 'latest' })
const pulling = ref(false)

const filteredImages = computed(() => {
  if (!searchQuery.value) return images.value
  const query = searchQuery.value.toLowerCase()
  return images.value.filter((img) => {
    const idMatch = img.id.toLowerCase().includes(query)
    const tagMatch = img.repoTags.some((tag) => tag.toLowerCase().includes(query))
    return idMatch || tagMatch
  })
})

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

async function fetchImages() {
  loading.value = true
  try {
    const { data } = await imagesApi.list()
    images.value = data
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors du chargement des images'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

async function handlePull() {
  if (!pullForm.value.name.trim()) {
    ElMessage.warning('Veuillez entrer un nom d\'image')
    return
  }
  pulling.value = true
  try {
    const pullData: ImagePullRequest = {
      name: pullForm.value.name.trim(),
      tag: pullForm.value.tag.trim() || 'latest',
    }
    const { data } = await imagesApi.pull(pullData)
    ElMessage.success(data.status || 'Image pullée avec succès')
    pullDialogVisible.value = false
    pullForm.value = { name: '', tag: 'latest' }
    await fetchImages()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors du pull de l\'image'
    ElMessage.error(message)
  } finally {
    pulling.value = false
  }
}

async function handleDelete(image: ImageResponse) {
  const displayName = image.repoTags.length > 0
    ? image.repoTags[0]
    : image.id.substring(0, 12)
  try {
    await ElMessageBox.confirm(
      `Supprimer l'image "${displayName}" ? Cette action est irréversible.`,
      'Confirmation',
      { type: 'warning' },
    )
  } catch {
    return // utilisateur a annulé
  }
  try {
    await imagesApi.remove(image.id)
    ElMessage.success('Image supprimée avec succès')
    await fetchImages()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors de la suppression de l\'image'
    ElMessage.error(message)
  }
}

onMounted(() => {
  fetchImages()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.tag-spacing {
  margin-right: 4px;
  margin-bottom: 2px;
}

.none-label {
  color: var(--el-text-color-placeholder);
  font-style: italic;
}
</style>
