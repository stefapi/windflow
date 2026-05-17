<template>
  <div class="images">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Images</span>
          <div class="header-actions">
            <el-button
              type="primary"
              :icon="Upload"
              @click="handleImportClick"
            >
              Importer
            </el-button>
            <input
              ref="fileInputRef"
              type="file"
              accept=".tar"
              style="display: none"
              @change="handleFileChange"
            >
            <el-button
              type="primary"
              :icon="Download"
              @click="pullDialogVisible = true"
            >
              Pull image
            </el-button>
            <el-select
              v-model="usageFilter"
              placeholder="Filtrer par utilisation"
              style="width: 180px"
              clearable
            >
              <el-option
                label="Toutes"
                value=""
              />
              <el-option
                label="Utilisées"
                value="used"
              />
              <el-option
                label="Non utilisées"
                value="unused"
              />
            </el-select>
            <el-input
              v-model="searchQuery"
              placeholder="Rechercher par tag ou ID..."
              clearable
              style="width: 300px"
              :prefix-icon="Search"
            />
          </div>
        </div>
      </template>

      <!-- Bulk actions bar -->
      <div
        v-if="selectedImages.length > 0"
        class="bulk-actions-bar"
      >
        <el-tag type="info">
          {{ selectedImages.length }} sélectionnée(s)
        </el-tag>
        <el-button
          type="danger"
          :icon="Delete"
          @click="handleBulkRemove(false)"
        >
          Remove
        </el-button>
        <el-button
          type="danger"
          :icon="DeleteFilled"
          @click="handleBulkRemove(true)"
        >
          Force Remove
        </el-button>
        <el-button
          type="primary"
          :icon="Download"
          @click="handleBulkExport"
        >
          Export
        </el-button>
      </div>

      <el-table
        v-loading="loading"
        :data="filteredImages"
        stripe
        @selection-change="handleSelectionChange"
        @row-click="handleRowClick"
      >
        <el-table-column
          type="selection"
          width="55"
        />
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
          label="Utilisation"
          width="180"
        >
          <template #default="{ row }">
            <el-tag
              v-if="row.inUse"
              type="success"
              size="small"
            >
              ✓ Utilisée ({{ row.containersCount }})
            </el-tag>
            <el-tag
              v-else
              type="info"
              size="small"
            >
              Non utilisée
            </el-tag>
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
              @click.stop="handleDelete(row)"
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
import { useRouter } from 'vue-router'
import { imagesApi } from '@/services/api'
import type { ImageResponse, ImagePullRequest } from '@/types/api'
import { formatBytes } from '@/utils/format'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Search, Download, Delete, DeleteFilled, Upload } from '@element-plus/icons-vue'

const router = useRouter()
const images = ref<ImageResponse[]>([])
const loading = ref(false)
const searchQuery = ref('')
const usageFilter = ref('')
const noneLabel = '<none>'
const selectedImages = ref<ImageResponse[]>([])
const fileInputRef = ref<HTMLInputElement | null>(null)

const pullDialogVisible = ref(false)
const pullForm = ref({ name: '', tag: 'latest' })
const pulling = ref(false)

const filteredImages = computed(() => {
  let result = images.value

  // Filter by usage
  if (usageFilter.value === 'used') {
    result = result.filter((img) => img.inUse)
  } else if (usageFilter.value === 'unused') {
    result = result.filter((img) => !img.inUse)
  }

  // Filter by search query
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    result = result.filter((img) => {
      const idMatch = img.id.toLowerCase().includes(query)
      const tagMatch = img.repoTags.some((tag) => tag.toLowerCase().includes(query))
      return idMatch || tagMatch
    })
  }

  return result
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

function handleSelectionChange(val: ImageResponse[]) {
  selectedImages.value = val
}

function handleRowClick(row: ImageResponse) {
  router.push({ name: 'ImageDetail', params: { id: row.id } })
}

async function handleBulkRemove(force: boolean) {
  const count = selectedImages.value.length
  const label = force ? 'force-supprimer' : 'supprimer'
  try {
    await ElMessageBox.confirm(
      `${label.charAt(0).toUpperCase() + label.slice(1)} ${count} image(s) ? Cette action est irréversible.`,
      'Confirmation',
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    const ids = selectedImages.value.map((img) => img.id)
    await imagesApi.batchRemove(ids, force)
    ElMessage.success(`${count} image(s) supprimée(s) avec succès`)
    selectedImages.value = []
    await fetchImages()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors de la suppression en lot'
    ElMessage.error(message)
  }
}

async function handleBulkExport() {
  for (const img of selectedImages.value) {
    try {
      const { data } = await imagesApi.save(img.id)
      const url = window.URL.createObjectURL(data)
      const link = document.createElement('a')
      link.href = url
      const tagName = img.repoTags.length > 0 ? (img.repoTags[0] ?? '').replace(/[:/]/g, '_') : img.id.substring(0, 12)
      link.download = `${tagName}.tar`
      link.click()
      window.URL.revokeObjectURL(url)
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : `Erreur lors de l'export de l'image ${img.id.substring(0, 12)}`
      ElMessage.error(message)
    }
  }
}

function handleImportClick() {
  fileInputRef.value?.click()
}

async function handleFileChange(event: Event) {
  const target = event.target as HTMLInputElement
  const file = target.files?.[0]
  if (!file) return

  try {
    await imagesApi.load(file)
    ElMessage.success('Image importée avec succès')
    await fetchImages()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : "Erreur lors de l'import de l'image"
    ElMessage.error(message)
  } finally {
    // Reset file input
    if (fileInputRef.value) {
      fileInputRef.value.value = ''
    }
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

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bulk-actions-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 12px;
  background-color: var(--el-fill-color-light);
  border-radius: 4px;
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
