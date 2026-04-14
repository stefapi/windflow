<template>
  <div class="targets">
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>{{ t('targets.title', 'Cibles de déploiement') }}</span>
          <el-button
            type="primary"
            @click="openCreateDialog"
          >
            <el-icon class="mr-1">
              <Plus />
            </el-icon>
            {{ t('targets.add', 'Ajouter une cible') }}
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="targetsStore.loading"
        :data="targetsStore.targets"
        :expand-row-keys="expandedRowId ? [expandedRowId] : []"
        row-key="id"
        stripe
        @expand-change="handleExpandChange"
      >
        <el-table-column type="expand">
          <template #default="{ row }">
            <div
              v-loading="loadingCapabilities.has(row.id)"
              class="panel rounded p-5 my-2.5"
            >
              <!-- Description -->
              <p
                v-if="row.description"
                class="mt-0 mb-4 text-body"
              >
                {{ row.description }}
              </p>

              <h4 class="text-heading text-base mb-4">
                {{ t('targets.capabilities', 'Capacités détectées') }}
              </h4>

              <!-- Scan info -->
              <div
                v-if="row.scan_date"
                class="flex items-center gap-3 mb-4"
              >
                <el-tag
                  v-if="row.access_profile?.access_level === 'root'"
                  type="danger"
                  size="small"
                >
                  root
                </el-tag>
                <el-tag
                  v-else-if="row.access_profile?.sudo_verified"
                  :type="row.access_profile?.sudo_passwordless ? 'success' : 'warning'"
                  size="small"
                >
                  {{ row.access_profile?.sudo_passwordless ? 'sudo (no pass)' : 'sudo' }}
                </el-tag>
                <el-tag
                  v-else-if="row.access_profile?.access_level === 'limited'"
                  type="info"
                  size="small"
                >
                  limited
                </el-tag>
                <span class="text-label">{{ formatDate(row.scan_date) }}</span>
                <el-button
                  size="small"
                  :loading="scanningTargets.has(row.id)"
                  @click="refreshCapabilities(row.id)"
                >
                  Rescan
                </el-button>
              </div>

              <!-- OS / Platform info -->
              <div
                v-if="row.os_info || row.platform_info"
                class="mb-4"
              >
                <el-descriptions
                  :column="2"
                  size="small"
                  border
                >
                  <el-descriptions-item
                    v-if="row.os_info && row.os_info['distribution']"
                    label="OS"
                  >
                    {{ row.os_info['distribution'] }}
                    {{ row.os_info['version'] || '' }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="row.platform_info && row.platform_info['architecture']"
                    label="Architecture"
                  >
                    {{ row.platform_info['architecture'] }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="row.platform_info && row.platform_info['cpu_cores']"
                    label="CPU cores"
                  >
                    {{ row.platform_info['cpu_cores'] }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="row.platform_info && row.platform_info['total_memory_gb']"
                    label="Mémoire"
                  >
                    {{ row.platform_info['total_memory_gb'] }} Go
                  </el-descriptions-item>
                </el-descriptions>
              </div>

              <!-- Capabilities table -->
              <el-table
                v-if="row.capabilities && row.capabilities.length > 0"
                :data="row.capabilities"
                stripe
              >
                <el-table-column
                  prop="capability_type"
                  :label="t('targets.capabilityType', 'Type')"
                  width="250"
                >
                  <template #default="{ row: capRow }">
                    <el-tag size="small">
                      {{ formatCapabilityType(capRow.capability_type) }}
                    </el-tag>
                  </template>
                </el-table-column>
                <el-table-column
                  prop="version"
                  label="Version"
                >
                  <template #default="{ row: capRow }">
                    {{ capRow.version || '—' }}
                  </template>
                </el-table-column>
                <el-table-column
                  prop="is_available"
                  label="Disponible"
                  width="120"
                >
                  <template #default="{ row: capRow }">
                    <el-tag
                      :type="capRow.is_available ? 'success' : 'info'"
                      size="small"
                    >
                      {{ capRow.is_available ? 'Oui' : 'Non' }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
              <div
                v-else-if="!loadingCapabilities.has(row.id)"
                class="py-5 text-center"
              >
                <el-empty :description="t('targets.noCapabilities', 'Aucune capacité détectée. Cliquez sur le bouton Scan pour détecter.')" />
              </div>
            </div>
          </template>
        </el-table-column>

        <el-table-column
          prop="name"
          label="Nom"
          min-width="140"
        />
        <el-table-column
          prop="host"
          label="Hôte"
          min-width="160"
        />
        <el-table-column
          prop="port"
          label="Port"
          width="80"
        />
        <el-table-column
          label="Connexion"
          width="130"
        >
          <template #default="{ row }">
            <div class="flex flex-col gap-1 items-start">
              <el-tag
                size="small"
                type="info"
              >
                {{ row.auth_method === 'local' ? 'Local' : row.auth_method === 'ssh_key' ? 'SSH Key' : 'Password' }}
              </el-tag>
              <span
                v-if="row.username"
                class="text-label"
              >{{ row.username }}</span>
              <el-tag
                v-if="row.access_profile?.access_level === 'root'"
                size="small"
                type="danger"
              >
                root
              </el-tag>
              <el-tag
                v-else-if="row.access_profile?.sudo_verified"
                size="small"
                type="warning"
              >
                sudo
              </el-tag>
            </div>
          </template>
        </el-table-column>
        <el-table-column
          label="Statut"
          width="120"
        >
          <template #default="{ row }">
            <StatusBadge :status="row.status" />
          </template>
        </el-table-column>
        <el-table-column
          label="Actions"
          width="200"
          align="right"
        >
          <template #default="{ row }">
            <el-button-group>
              <el-button
                size="small"
                title="Vérifier la connexion"
                :loading="targetsStore.healthCheckingIds.has(row.id)"
                @click="manualHealthCheck(row)"
              >
                <el-icon><Connection /></el-icon>
              </el-button>
              <el-button
                size="small"
                title="Scanner"
                :loading="scanningTargets.has(row.id)"
                @click="refreshCapabilities(row.id)"
              >
                <el-icon><Refresh /></el-icon>
              </el-button>
              <el-button
                size="small"
                title="Modifier"
                @click="openEditDialog(row)"
              >
                <el-icon><Edit /></el-icon>
              </el-button>
              <el-button
                size="small"
                type="danger"
                title="Supprimer"
                @click="confirmDelete(row)"
              >
                <el-icon><Delete /></el-icon>
              </el-button>
            </el-button-group>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <!-- Target Wizard (Create / Edit) -->
    <TargetWizard
      v-model="wizardVisible"
      :edit-target="editingTarget"
      @saved="onWizardSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { targetsApi } from '@/services/api'
import type { Target } from '@/types/api'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import TargetWizard from '@/components/TargetWizard.vue'

const targetsStore = useTargetsStore()
const authStore = useAuthStore()

// ─── Wizard state ─────────────────────────────────────────────
const wizardVisible = ref(false)
const editingTarget = ref<Target | null>(null)

function openCreateDialog(): void {
  editingTarget.value = null
  wizardVisible.value = true
}

function openEditDialog(target: Target): void {
  editingTarget.value = target
  wizardVisible.value = true
}

function onWizardSaved(targetId: string): void {
  wizardVisible.value = false
  editingTarget.value = null
  // Trigger a capabilities scan for the newly created/updated target
  refreshCapabilities(targetId)
}

// ─── UI state ─────────────────────────────────────────────────
const scanningTargets = ref<Set<string>>(new Set())
const expandedRowId = ref<string | null>(null)
const loadingCapabilities = ref<Set<string>>(new Set())

// ─── Helpers ──────────────────────────────────────────────────

const t = (_key: string, fallback: string) => fallback // i18n placeholder

function formatDate(date: string | null): string {
  if (!date) return '—'
  return new Date(date).toLocaleString('fr-FR')
}

function formatCapabilityType(type: string): string {
  const map: Record<string, string> = {
    docker: 'Docker',
    docker_compose: 'Docker Compose',
    docker_swarm: 'Docker Swarm',
    kubernetes: 'Kubernetes',
    kubectl: 'kubectl',
    helm: 'Helm',
    libvirt: 'Libvirt',
    virtualbox: 'VirtualBox',
    vagrant: 'Vagrant',
    proxmox: 'Proxmox',
    qemu_kvm: 'QEMU/KVM',
    podman: 'Podman',
    lxc: 'LXC',
    lxd: 'LXD',
    incus: 'Incus',
    containerd: 'containerd',
  }
  return map[type] || type
}

// ─── Delete ───────────────────────────────────────────────────

async function confirmDelete(target: Target): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Supprimer la cible "${target.name}" (${target.host}) ? Cette action est irréversible.`,
      'Confirmer la suppression',
      {
        confirmButtonText: 'Supprimer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
    await targetsStore.deleteTarget(target.id)
    ElMessage.success('Cible supprimée')
  } catch {
    // User cancelled or delete failed
  }
}

// ─── Scan / Capabilities ──────────────────────────────────────

const handleExpandChange = async (row: Target, expandedRows: Target[]): Promise<void> => {
  if (expandedRows.length === 0) {
    expandedRowId.value = null
  } else {
    expandedRowId.value = row.id
    if (!row.capabilities || row.capabilities.length === 0) {
      await loadCapabilities(row.id)
    }
  }
}

const loadCapabilities = async (targetId: string): Promise<void> => {
  loadingCapabilities.value.add(targetId)
  try {
    const response = await targetsApi.getCapabilities(targetId)
    const targetIndex = targetsStore.targets.findIndex(t => t.id === targetId)
    if (targetIndex !== -1 && targetsStore.targets[targetIndex]) {
      targetsStore.targets[targetIndex].capabilities = response.data.capabilities
    }
  } catch {
    ElMessage.error('Impossible de charger les capacités')
  } finally {
    loadingCapabilities.value.delete(targetId)
  }
}

const refreshCapabilities = async (targetId: string): Promise<void> => {
  try {
    scanningTargets.value.add(targetId)
    await targetsStore.scanTarget(targetId)
    await loadCapabilities(targetId)
    ElMessage.success('Scan terminé avec succès')
  } catch {
    ElMessage.error('Échec du scan')
  } finally {
    scanningTargets.value.delete(targetId)
  }
}

// ── Health check ────────────────────────────────────────────────

async function manualHealthCheck(target: Target): Promise<void> {
  try {
    const result = await targetsStore.healthCheckTarget(target.id)
    const ok = result.status === 'online'
    ElMessage({
      type: ok ? 'success' : 'error',
      message: ok
        ? `✓ ${target.host} est en ligne`
        : `✗ ${target.host} est injoignable — ${result.message}`,
    })
  } catch {
    ElMessage.error('Impossible de vérifier la cible')
  }
}

// ─── Init ─────────────────────────────────────────────────────

onMounted(() => {
  targetsStore.fetchTargets(authStore.organizationId || undefined).then(() => {
    targetsStore.startHealthPolling()
  })
})

onBeforeUnmount(() => {
  targetsStore.stopHealthPolling()
})
</script>

<style scoped>
.mr-1 {
  margin-right: 4px;
}
</style>
