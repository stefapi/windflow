<template>
  <div class="volumes">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Volumes</span>
          <el-button
            type="primary"
            @click="createDialogVisible = true"
          >
            Créer un volume
          </el-button>
          <el-input
            v-model="searchQuery"
            placeholder="Rechercher par nom..."
            clearable
            style="width: 300px"
            :prefix-icon="Search"
          />
        </div>
      </template>
      <el-table
        v-loading="loading"
        :data="filteredVolumes"
        stripe
      >
        <el-table-column
          label="Nom"
          min-width="150"
        >
          <template #default="{ row }">
            <span :title="row.name">{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column
          label="Driver"
          width="120"
          prop="driver"
        />
        <el-table-column
          label="Mountpoint"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tooltip
              :content="row.mountpoint"
              placement="top"
            >
              <span class="truncated-text">{{ row.mountpoint }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column
          label="Date de création"
          width="200"
        >
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
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
              @click="openDeleteConfirm(row)"
            />
          </template>
        </el-table-column>
      </el-table>
      <el-empty
        v-if="!loading && volumes.length === 0"
        description="Aucun volume trouvé"
      />
    </el-card>

    <!-- Dialog de création -->
    <el-dialog
      v-model="createDialogVisible"
      title="Créer un volume"
      width="450px"
    >
      <el-form label-width="130px">
        <el-form-item label="Nom du volume">
          <el-input
            v-model="createForm.name"
            placeholder="ex: my-volume"
          />
        </el-form-item>
        <el-form-item label="Driver">
          <el-input
            v-model="createForm.driver"
            placeholder="local"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="primary"
          :loading="creating"
          @click="handleCreate"
        >
          Créer
        </el-button>
      </template>
    </el-dialog>

    <!-- Dialog de confirmation de suppression -->
    <el-dialog
      v-model="deleteDialogVisible"
      title="Supprimer le volume"
      width="450px"
    >
      <p>
        Voulez-vous vraiment supprimer le volume
        <strong>{{ volumeToDelete?.name }}</strong> ?
        Cette action est irréversible.
      </p>
      <el-checkbox v-model="forceDelete">
        Forcer la suppression (le volume peut être en cours d'utilisation)
      </el-checkbox>
      <template #footer>
        <el-button @click="deleteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="danger"
          :loading="deleting"
          @click="handleDelete"
        >
          Supprimer
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { volumesApi } from '@/services/api'
import type { VolumeResponse, VolumeCreateRequest } from '@/types/api'
import { ElMessage } from 'element-plus'
import { Search, Delete } from '@element-plus/icons-vue'

const volumes = ref<VolumeResponse[]>([])
const loading = ref(false)
const searchQuery = ref('')

// États du dialog de création
const createDialogVisible = ref(false)
const createForm = ref({ name: '', driver: 'local' })
const creating = ref(false)

// États du dialog de suppression
const deleteDialogVisible = ref(false)
const volumeToDelete = ref<VolumeResponse | null>(null)
const forceDelete = ref(false)
const deleting = ref(false)

const filteredVolumes = computed(() => {
  if (!searchQuery.value) return volumes.value
  const query = searchQuery.value.toLowerCase()
  return volumes.value.filter((vol) =>
    vol.name.toLowerCase().includes(query),
  )
})

function formatDate(dateStr: string): string {
  try {
    return new Date(dateStr).toLocaleString()
  } catch {
    return dateStr
  }
}

async function fetchVolumes() {
  loading.value = true
  try {
    const { data } = await volumesApi.list()
    volumes.value = data
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors du chargement des volumes'
    ElMessage.error(message)
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!createForm.value.name.trim()) {
    ElMessage.warning('Veuillez entrer un nom de volume')
    return
  }
  creating.value = true
  try {
    const data: VolumeCreateRequest = {
      name: createForm.value.name.trim(),
      driver: createForm.value.driver.trim() || 'local',
    }
    await volumesApi.create(data)
    ElMessage.success('Volume créé avec succès')
    createDialogVisible.value = false
    createForm.value = { name: '', driver: 'local' }
    await fetchVolumes()
  } catch (err: unknown) {
    // Gestion du conflit 409 (volume déjà existant)
    if (err && typeof err === 'object' && 'response' in err) {
      const httpErr = err as { response?: { status?: number } }
      if (httpErr.response?.status === 409) {
        ElMessage.error('Un volume avec ce nom existe déjà')
        return
      }
    }
    const message = err instanceof Error ? err.message : 'Erreur lors de la création du volume'
    ElMessage.error(message)
  } finally {
    creating.value = false
  }
}

function openDeleteConfirm(volume: VolumeResponse) {
  volumeToDelete.value = volume
  forceDelete.value = false
  deleteDialogVisible.value = true
}

async function handleDelete() {
  if (!volumeToDelete.value) return
  deleting.value = true
  try {
    await volumesApi.remove(volumeToDelete.value.name, forceDelete.value)
    ElMessage.success('Volume supprimé avec succès')
    deleteDialogVisible.value = false
    volumeToDelete.value = null
    await fetchVolumes()
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Erreur lors de la suppression du volume'
    ElMessage.error(message)
  } finally {
    deleting.value = false
  }
}

onMounted(() => {
  fetchVolumes()
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.truncated-text {
  display: inline-block;
  max-width: 300px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}
</style>
