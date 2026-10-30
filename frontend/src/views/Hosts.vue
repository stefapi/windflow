<template>
  <div class="hosts">
    <el-card>
      <template #header>
        <div class="flex justify-between items-center">
          <span>{{ t('hosts.title', 'Hôtes de déploiement') }}</span>
          <el-button
            v-if="authStore.isSuperuser"
            type="primary"
            @click="openCreateDialog"
          >
            <el-icon class="mr-1">
              <Plus />
            </el-icon>
            {{ t('hosts.add', 'Ajouter un hôte') }}
          </el-button>
        </div>
      </template>

      <el-table
        v-loading="hostsStore.loading"
        :data="hostsStore.hosts"
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
                {{ t('hosts.capabilities', 'Capacités détectées') }}
              </h4>

              <!-- Scan info -->
              <div
                v-if="row.last_scan_at"
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
                <span class="text-label">{{ formatDate(row.last_scan_at) }}</span>
                <el-button
                  v-if="authStore.isSuperuser"
                  size="small"
                  :loading="scanningHosts.has(row.id)"
                  @click="refreshCapabilities(row.id)"
                >
                  Rescan
                </el-button>
              </div>

              <!-- OS / Hardware info (canonique STORY-166.6 : hardware_info d'abord, echo legacy platform_info) -->
              <div
                v-if="row.os_info || row.hardware_info || row.platform_info"
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
                    v-if="hwValue(row, 'architecture')"
                    label="Architecture"
                  >
                    {{ hwValue(row, 'architecture') }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="hwValue(row, 'cpu_cores')"
                    label="CPU cores"
                  >
                    {{ hwValue(row, 'cpu_cores') }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="hwValue(row, 'total_memory_gb')"
                    label="Mémoire"
                  >
                    {{ hwValue(row, 'total_memory_gb') }} Go
                  </el-descriptions-item>
                </el-descriptions>
              </div>

              <!-- Installed engines (canonique spec 06 — STORY-166) -->
              <div
                v-if="row.installed_engines && row.installed_engines.length > 0"
                class="mb-4 flex flex-wrap gap-1"
              >
                <el-tag
                  v-for="engine in row.installed_engines"
                  :key="String(engine['capability_type'] ?? engine)"
                  size="small"
                  type="info"
                  class="mr-1"
                >
                  {{ formatCapabilityType(String(engine['capability_type'] ?? engine)) }}
                  <template v-if="engine['version']">
                    · {{ String(engine['version']) }}
                  </template>
                </el-tag>
              </div>

              <!-- Capabilities table -->
              <el-table
                v-if="row.capabilities && row.capabilities.length > 0"
                :data="row.capabilities"
                stripe
              >
                <el-table-column
                  prop="capability_type"
                  :label="t('hosts.capabilityType', 'Type')"
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
                <el-empty :description="t('hosts.noCapabilities', 'Aucune capacité détectée. Cliquez sur le bouton Scan pour détecter.')" />
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
          label="Profil"
          width="170"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.profile === 'host_remote_docker' ? 'warning' : row.profile === 'host_proxmox' ? 'success' : 'info'"
            >
              {{ formatProfile(row.profile) }}
            </el-tag>
          </template>
        </el-table-column>
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
          v-if="authStore.isSuperuser"
          label="Actions"
          width="200"
          align="right"
        >
          <template #default="{ row }">
            <el-button-group>
              <el-button
                size="small"
                title="Vérifier la connexion"
                :loading="hostsStore.healthCheckingIds.has(row.id)"
                @click="manualHealthCheck(row)"
              >
                <el-icon><Connection /></el-icon>
              </el-button>
              <el-button
                size="small"
                title="Scanner"
                :loading="scanningHosts.has(row.id)"
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

    <!-- Host Wizard (Create / Edit) -->
    <HostWizard
      v-model="wizardVisible"
      :edit-host="editingHost"
      @saved="onWizardSaved"
    />
  </div>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useHostsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection, Delete, Edit, Plus, Refresh } from '@element-plus/icons-vue'
import { hostsApi } from '@/services/api'
import type { Host } from '@/types/api'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import HostWizard from '@/components/HostWizard.vue'

const hostsStore = useHostsStore()
const authStore = useAuthStore()

// ─── Wizard state ─────────────────────────────────────────────
const wizardVisible = ref(false)
const editingHost = ref<Host | null>(null)

function openCreateDialog(): void {
  editingHost.value = null
  wizardVisible.value = true
}

function openEditDialog(host: Host): void {
  editingHost.value = host
  wizardVisible.value = true
}

function onWizardSaved(hostId: string): void {
  wizardVisible.value = false
  editingHost.value = null
  // Trigger a capabilities scan for the newly created/updated host
  refreshCapabilities(hostId)
}

/** Valeur hardware affichable (string/number) pour une clé donnée, sinon vide. */
function hwValue(host: Host, key: string): string | number | undefined {
  const info = host.hardware_info ?? host.platform_info ?? null
  const raw = info?.[key]
  if (raw === null || raw === undefined) return undefined
  return typeof raw === 'string' || typeof raw === 'number' ? raw : undefined
}

// ─── UI state ─────────────────────────────────────────────────
const scanningHosts = ref<Set<string>>(new Set())
const expandedRowId = ref<string | null>(null)
const loadingCapabilities = ref<Set<string>>(new Set())

// ─── Helpers ──────────────────────────────────────────────────

const t = (_key: string, fallback: string) => fallback // i18n placeholder

function formatDate(date: string | null): string {
  if (!date) return '—'
  return new Date(date).toLocaleString('fr-FR')
}

function formatProfile(profile: string): string {
  const map: Record<string, string> = {
    host_baremetal: 'Bare Metal',
    host_proxmox: 'Proxmox',
    host_remote_docker: 'Docker distant',
  }
  return map[profile] || profile
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

async function confirmDelete(host: Host): Promise<void> {
  try {
    await ElMessageBox.confirm(
      `Supprimer l'hôte "${host.name}" (${host.host}) ? Cette action est irréversible.`,
      'Confirmer la suppression',
      {
        confirmButtonText: 'Supprimer',
        cancelButtonText: 'Annuler',
        type: 'warning',
      },
    )
    await hostsStore.deleteHost(host.id)
    ElMessage.success('Hôte supprimé')
  } catch {
    // User cancelled or delete failed
  }
}

// ─── Scan / Capabilities ──────────────────────────────────────

const handleExpandChange = async (row: Host, expandedRows: Host[]): Promise<void> => {
  if (expandedRows.length === 0) {
    expandedRowId.value = null
  } else {
    expandedRowId.value = row.id
    if (!row.capabilities || row.capabilities.length === 0) {
      await loadCapabilities(row.id)
    }
  }
}

const loadCapabilities = async (hostId: string): Promise<void> => {
  loadingCapabilities.value.add(hostId)
  try {
    const response = await hostsApi.getCapabilities(hostId)
    const hostIndex = hostsStore.hosts.findIndex(h => h.id === hostId)
    if (hostIndex !== -1 && hostsStore.hosts[hostIndex]) {
      hostsStore.hosts[hostIndex]!.capabilities = response.data.capabilities
    }
  } catch {
    ElMessage.error('Impossible de charger les capacités')
  } finally {
    loadingCapabilities.value.delete(hostId)
  }
}

const refreshCapabilities = async (hostId: string): Promise<void> => {
  try {
    scanningHosts.value.add(hostId)
    await hostsStore.scanHost(hostId)
    await loadCapabilities(hostId)
    ElMessage.success('Scan terminé avec succès')
  } catch {
    ElMessage.error('Échec du scan')
  } finally {
    scanningHosts.value.delete(hostId)
  }
}

// ── Health check ────────────────────────────────────────────────

async function manualHealthCheck(host: Host): Promise<void> {
  try {
    const result = await hostsStore.healthCheckHost(host.id)
    const ok = result.status === 'online'
    ElMessage({
      type: ok ? 'success' : 'error',
      message: ok
        ? `✓ ${host.host} est en ligne`
        : `✗ ${host.host} est injoignable — ${result.message}`,
    })
  } catch {
    ElMessage.error("Impossible de vérifier l'hôte")
  }
}

// ─── Init ─────────────────────────────────────────────────────

onMounted(() => {
  hostsStore.fetchHosts(authStore.organizationId || undefined).then(() => {
    hostsStore.startHealthPolling()
  })
})

onBeforeUnmount(() => {
  hostsStore.stopHealthPolling()
})
</script>

<style scoped>
.mr-1 {
  margin-right: 4px;
}
</style>
