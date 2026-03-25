<template>
  <div class="compute-view p-6">
    <!-- A. Header -->
    <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
      <div>
        <h1 class="text-2xl font-bold text-gray-800 dark:text-gray-100">
          Containers — vue globale
        </h1>
        <p class="text-sm text-gray-500 mt-1">
          {{ computeStore.stats?.targets_count ?? 0 }} targets
          · {{ techCount }} technologies
        </p>
      </div>
      <div class="flex items-center gap-2">
        <el-button
          :type="!groupByTarget ? 'primary' : 'default'"
          size="small"
          @click="groupByTarget = false"
        >
          Tout
        </el-button>
        <el-button
          :type="groupByTarget ? 'primary' : 'default'"
          size="small"
          @click="groupByTarget = true"
        >
          Par machine
        </el-button>
        <el-button
          size="small"
          disabled
        >
          + Déployer
        </el-button>
      </div>
    </div>

    <!-- B. Barre de filtres -->
    <div class="filter-bar mb-6 flex flex-col gap-3">
      <!-- Ligne 1 : Type + Technologie -->
      <div class="flex flex-wrap items-center gap-3">
        <el-radio-group
          v-model="filterType"
          size="small"
        >
          <el-radio-button value="all">
            Tout
          </el-radio-button>
          <el-radio-button value="managed">
            ● Stacks WindFlow
          </el-radio-button>
          <el-radio-button value="discovered">
            ● Discovered
          </el-radio-button>
          <el-radio-button value="standalone">
            ● Standalone
          </el-radio-button>
        </el-radio-group>

        <span class="text-gray-300">|</span>

        <el-input
          v-model="filterSearch"
          size="small"
          placeholder="Rechercher..."
          clearable
          style="width: 200px"
        />
      </div>

      <!-- Ligne 2 : Pills technologie + pills target -->
      <div class="flex flex-wrap items-center gap-2">
        <span class="text-xs text-gray-500 font-semibold">Tech :</span>
        <span
          v-for="tech in availableTechnologies"
          :key="tech"
          class="pill"
          :class="activeTechnologies.includes(tech) ? 'pill-selected' : 'pill-default'"
          @click="toggleTechnology(tech)"
        >
          {{ tech }}
        </span>

        <span class="text-xs text-gray-500 font-semibold ml-2">Target :</span>
        <span
          v-for="target in targetsStore.targets"
          :key="target.id"
          class="pill"
          :class="activeTargets.includes(target.id) ? 'pill-selected' : 'pill-default'"
          @click="toggleTarget(target.id)"
        >
          {{ target.name }}
        </span>
      </div>
    </div>

    <!-- C. Bandeau métriques -->
    <div class="mb-6">
      <ComputeStatsBanner
        :stats="computeStore.stats"
        :loading="computeStore.statsLoading"
      />
    </div>

    <!-- Mode normal (D + E + F) -->
    <template v-if="!groupByTarget">
      <!-- D. Section STACKS WINDFLOW -->
      <div
        v-if="filterType === 'all' || filterType === 'managed'"
        class="section mb-6"
      >
        <div class="section-header mb-3 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded-sm bg-blue-600" />
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
            STACKS WINDFLOW
            <span class="text-gray-400 font-normal">(managées, source of truth dans WindFlow)</span>
          </span>
        </div>

        <div
          v-if="computeStore.loading"
          class="flex justify-center py-8"
        >
          <el-icon
            class="is-loading text-2xl text-blue-500"
          >
            <Loading />
          </el-icon>
        </div>

        <el-empty
          v-else-if="visibleManagedStacks.length === 0"
          description="Aucune stack WindFlow avec des instances actives"
        />

        <el-collapse
          v-else
          class="stacks-collapse"
        >
          <el-collapse-item
            v-for="stack in visibleManagedStacks"
            :key="stack.id"
            :name="stack.id"
          >
            <template #title>
              <div class="flex flex-wrap items-center gap-2 w-full pr-4">
                <span class="font-semibold text-sm">{{ stack.name }}</span>
                <el-tag
                  type="primary"
                  size="small"
                >
                  stack WindFlow
                </el-tag>
                <el-tag size="small">
                  {{ stack.technology }}
                </el-tag>
                <el-tag
                  size="small"
                  type="info"
                >
                  ● {{ stack.target_name }}
                </el-tag>
                <span
                  class="text-xs font-semibold"
                  :class="servicesRunningClass(stack)"
                >
                  {{ stack.services_running }}/{{ stack.services_total }} running
                </span>
                <div class="ml-auto flex items-center gap-1">
                  <el-button
                    size="small"
                    text
                    title="Copier ID"
                    @click.stop="copyToClipboard(stack.id)"
                  >
                    📄
                  </el-button>
                  <el-button
                    size="small"
                    text
                    title="Rafraîchir"
                    @click.stop="refreshGlobal"
                  >
                    🔄
                  </el-button>
                  <el-button
                    size="small"
                    type="primary"
                    @click.stop
                  >
                    Éditer stack
                  </el-button>
                </div>
              </div>
            </template>

            <el-table
              :data="stack.services"
              size="small"
              stripe
            >
              <el-table-column
                label="Service"
                min-width="160"
              >
                <template #default="{ row }">
                  <span
                    class="mr-1"
                    :class="row.status === 'running' ? 'text-green-500' : 'text-red-400'"
                  >●</span>
                  {{ row.name }}
                </template>
              </el-table-column>
              <el-table-column
                prop="image"
                label="Image"
                min-width="180"
              />
              <el-table-column
                label="Statut"
                width="100"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === 'running' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="CPU"
                width="120"
              >
                <template #default="{ row }">
                  <div class="flex items-center gap-1">
                    <div class="flex-1 bg-gray-200 rounded h-2">
                      <div
                        class="h-2 rounded bg-blue-500"
                        :style="{ width: Math.min(row.cpu_percent, 100) + '%' }"
                      />
                    </div>
                    <span class="text-xs text-gray-500">{{ row.cpu_percent.toFixed(1) }}%</span>
                  </div>
                </template>
              </el-table-column>
              <el-table-column
                label="Mémoire"
                width="80"
              >
                <template #default="{ row }">
                  {{ row.memory_usage }}
                </template>
              </el-table-column>
              <el-table-column
                label="Actions"
                width="80"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    text
                    title="Copier ID"
                    @click="copyToClipboard(row.id)"
                  >
                    📄
                  </el-button>
                  <el-button
                    size="small"
                    text
                    title="Terminal"
                    @click="openTerminal(row.id)"
                  >
                    >_
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- E. Section DISCOVERED -->
      <div
        v-if="filterType === 'all' || filterType === 'discovered'"
        class="section mb-6"
      >
        <div class="section-header mb-3 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded-sm bg-orange-500" />
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
            DISCOVERED — NON MANAGÉS
            <span class="text-gray-400 font-normal">(détectés sur la machine, WindFlow n'en est pas l'auteur)</span>
          </span>
        </div>

        <el-empty
          v-if="!computeStore.loading && visibleDiscoveredItems.length === 0"
          description="Aucun objet découvert avec des instances actives"
        />

        <el-collapse
          v-else-if="visibleDiscoveredItems.length > 0"
          class="discovered-collapse"
        >
          <el-collapse-item
            v-for="item in visibleDiscoveredItems"
            :key="item.id"
            :name="item.id"
          >
            <template #title>
              <div class="flex flex-wrap items-center gap-2 w-full pr-4">
                <span class="font-semibold text-sm">{{ item.name }}</span>
                <el-tag
                  type="warning"
                  size="small"
                >
                  discovered
                </el-tag>
                <el-tag size="small">
                  {{ item.technology }}
                </el-tag>
                <el-tag
                  size="small"
                  type="info"
                >
                  ● {{ item.target_name }}
                </el-tag>
                <span class="text-xs text-gray-500">
                  {{ item.services_running }}/{{ item.services_total }} running
                </span>
                <span class="ml-auto flex items-center gap-1">
                  👁
                  <el-button
                    v-if="item.adoptable"
                    size="small"
                    type="warning"
                    @click.stop
                  >
                    ↗ Adopter
                  </el-button>
                </span>
              </div>
            </template>

            <el-alert
              v-if="item.source_path"
              type="warning"
              :closable="false"
              class="mb-3"
            >
              ⚠ Détecté via {{ item.source_path }} — lecture seule. Adoptez pour gérer depuis WindFlow.
            </el-alert>

            <el-table
              :data="item.services ?? []"
              size="small"
              stripe
            >
              <el-table-column
                label="Service"
                min-width="160"
              >
                <template #default="{ row }">
                  <span
                    class="mr-1"
                    :class="row.status === 'running' ? 'text-green-500' : 'text-red-400'"
                  >●</span>
                  {{ row.name }}
                  <span class="text-xs text-gray-400 ml-1">(read-only)</span>
                </template>
              </el-table-column>
              <el-table-column
                prop="image"
                label="Image"
                min-width="180"
              />
              <el-table-column
                label="Statut"
                width="100"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === 'running' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                label="CPU"
                width="80"
              >
                <template #default="{ row }">
                  {{ row.cpu_percent.toFixed(1) }}%
                </template>
              </el-table-column>
              <el-table-column
                label="Actions"
                width="60"
              >
                <template #default>
                  👁
                </template>
              </el-table-column>
            </el-table>
          </el-collapse-item>
        </el-collapse>
      </div>

      <!-- F. Section STANDALONE -->
      <div
        v-if="filterType === 'all' || filterType === 'standalone'"
        class="section mb-6"
      >
        <div class="section-header mb-3 flex items-center gap-2">
          <span class="inline-block w-3 h-3 rounded-sm bg-gray-400" />
          <span class="text-sm font-semibold text-gray-700 dark:text-gray-200">
            STANDALONE
            <span class="text-gray-400 font-normal">(containers individuels sans composition, créés directement)</span>
          </span>
        </div>

        <el-empty
          v-if="!computeStore.loading && computeStore.standaloneContainers.length === 0"
          description="Aucun container standalone"
        />

        <template v-else-if="computeStore.standaloneContainers.length > 0">
          <!-- Bulk Actions Bar for Standalone -->
          <transition name="slide-down">
            <div
              v-if="selectedStandaloneIds.length > 0"
              class="flex justify-between items-center px-4 py-3 mb-4 bg-[var(--color-accent-light)] border border-[var(--color-accent)] rounded-lg"
            >
              <div class="flex items-center gap-3">
                <el-tag
                  type="primary"
                  effect="dark"
                >
                  {{ selectedStandaloneIds.length }} sélectionné{{ selectedStandaloneIds.length > 1 ? 's' : '' }}
                </el-tag>
                <el-button
                  text
                  size="small"
                  @click="clearStandaloneSelection"
                >
                  Annuler la sélection
                </el-button>
              </div>
              <div class="flex items-center gap-2">
                <el-button
                  size="small"
                  :loading="standaloneBulkActionLoading === 'start'"
                  @click="handleStandaloneBulkAction('start')"
                >
                  <el-icon class="el-icon--left">
                    <VideoPlay />
                  </el-icon>
                  Démarrer
                </el-button>
                <el-button
                  size="small"
                  :loading="standaloneBulkActionLoading === 'stop'"
                  @click="handleStandaloneBulkAction('stop')"
                >
                  <el-icon class="el-icon--left">
                    <VideoPause />
                  </el-icon>
                  Arrêter
                </el-button>
                <el-button
                  size="small"
                  :loading="standaloneBulkActionLoading === 'restart'"
                  @click="handleStandaloneBulkAction('restart')"
                >
                  <el-icon class="el-icon--left">
                    <RefreshRight />
                  </el-icon>
                  Redémarrer
                </el-button>
                <el-button
                  type="danger"
                  size="small"
                  :loading="standaloneBulkActionLoading === 'delete'"
                  @click="showStandaloneBulkDeleteDialog"
                >
                  <el-icon class="el-icon--left">
                    <Delete />
                  </el-icon>
                  Supprimer
                </el-button>
              </div>
            </div>
          </transition>

          <el-table
            ref="standaloneTableRef"
            :data="computeStore.standaloneContainers"
            size="small"
            stripe
            class="w-full"
            @selection-change="handleStandaloneSelectionChange"
          >
            <el-table-column
              type="selection"
              width="55"
            />

            <el-table-column
              label="Nom"
              min-width="160"
            >
              <template #default="{ row }">
                <router-link
                  :to="`/containers/${row.id}`"
                  class="text-[var(--color-accent)] no-underline font-medium hover:underline"
                >
                  <span
                    class="mr-1"
                    :class="getContainerStatusColor(row)"
                  >●</span>
                  {{ row.name }}
                </router-link>
              </template>
            </el-table-column>
            <el-table-column
              prop="image"
              label="Image"
              min-width="180"
            />
            <el-table-column
              label="Target"
              width="100"
            >
              <template #default="{ row }">
                <el-tag size="small">
                  {{ row.target_name }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="Statut"
              width="110"
            >
              <template #default="{ row }">
                <el-tag
                  :type="getContainerStatusType(row)"
                  size="small"
                >
                  {{ getContainerStatusLabel(row) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="Uptime"
              width="120"
            >
              <template #default="{ row }">
                <span
                  v-if="row.uptime"
                  class="text-xs text-gray-600"
                >
                  {{ row.uptime }}
                </span>
                <span
                  v-else
                  class="text-xs text-gray-400"
                >-</span>
              </template>
            </el-table-column>
            <el-table-column
              label="Ports"
              min-width="140"
            >
              <template #default="{ row }">
                <div
                  v-if="row.ports && row.ports.length > 0"
                  class="flex flex-wrap gap-1"
                >
                  <el-tag
                    v-for="(port, index) in row.ports.slice(0, 3)"
                    :key="index"
                    size="small"
                    class="font-mono text-[11px]"
                  >
                    {{ formatPort(port) }}
                  </el-tag>
                  <el-tag
                    v-if="row.ports.length > 3"
                    size="small"
                    type="info"
                  >
                    +{{ row.ports.length - 3 }}
                  </el-tag>
                </div>
                <span
                  v-else
                  class="text-xs text-gray-400"
                >-</span>
              </template>
            </el-table-column>
            <el-table-column
              label="CPU / Mém."
              width="110"
            >
              <template #default="{ row }">
                {{ row.cpu_percent.toFixed(1) }}% / {{ row.memory_usage }}
              </template>
            </el-table-column>
            <el-table-column
              label="Actions"
              width="140"
              fixed="right"
            >
              <template #default="{ row }">
                <ActionButtons
                  :actions="getStandaloneActions(row)"
                  @action="handleStandaloneAction($event, row)"
                />
              </template>
            </el-table-column>
          </el-table>
        </template>
      </div>
    </template>

    <!-- G. Mode "Par machine" -->
    <template v-if="groupByTarget">
      <div
        v-if="computeStore.loading"
        class="flex justify-center py-8"
      >
        <el-icon class="is-loading text-2xl text-blue-500">
          <Loading />
        </el-icon>
      </div>

      <el-empty
        v-else-if="computeStore.targetGroups.length === 0"
        description="Aucun groupe de machines trouvé"
      />

      <el-collapse
        v-else
        class="target-groups-collapse"
      >
        <el-collapse-item
          v-for="group in filteredTargetGroups"
          :key="group.target_id"
          :name="group.target_id"
        >
          <template #title>
            <div class="flex flex-wrap items-center gap-2 w-full pr-4">
              <span class="font-semibold">{{ group.target_name }}</span>
              <el-tag size="small">
                {{ group.technology }}
              </el-tag>
              <span class="text-xs text-gray-500">
                CPU: {{ group.metrics.cpu_total_percent }}% |
                RAM: {{ group.metrics.memory_used }}/{{ group.metrics.memory_total }}
              </span>
            </div>
          </template>

          <!-- Stacks du groupe -->
          <template v-if="group.stacks.length > 0">
            <div class="text-xs font-semibold text-blue-600 mb-2 mt-2">
              Stacks ({{ group.stacks.length }})
            </div>
            <el-table
              :data="group.stacks"
              size="small"
              stripe
              class="mb-4"
            >
              <el-table-column
                prop="name"
                label="Nom"
              />
              <el-table-column
                prop="technology"
                label="Tech"
                width="80"
              />
              <el-table-column
                label="Services"
                width="100"
              >
                <template #default="{ row }">
                  <span :class="servicesRunningClass(row)">
                    {{ row.services_running }}/{{ row.services_total }}
                  </span>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <!-- Discovered du groupe -->
          <template v-if="group.discovered.length > 0">
            <div class="text-xs font-semibold text-orange-500 mb-2">
              Discovered ({{ group.discovered.length }})
            </div>
            <el-table
              :data="group.discovered"
              size="small"
              stripe
              class="mb-4"
            >
              <el-table-column
                prop="name"
                label="Nom"
              />
              <el-table-column
                prop="technology"
                label="Tech"
                width="80"
              />
              <el-table-column
                label="Adoptable"
                width="90"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.adoptable ? 'warning' : 'info'"
                    size="small"
                  >
                    {{ row.adoptable ? 'Oui' : 'Non' }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <!-- Standalone du groupe -->
          <template v-if="group.standalone.length > 0">
            <div class="text-xs font-semibold text-gray-500 mb-2">
              Standalone ({{ group.standalone.length }})
            </div>
            <el-table
              :data="group.standalone"
              size="small"
              stripe
            >
              <el-table-column
                prop="name"
                label="Nom"
              />
              <el-table-column
                prop="image"
                label="Image"
              />
              <el-table-column
                label="Statut"
                width="100"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === 'running' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </template>

          <el-empty
            v-if="group.stacks.length === 0 && group.discovered.length === 0 && group.standalone.length === 0"
            description="Aucune ressource sur cette machine"
          />
        </el-collapse-item>
      </el-collapse>
    </template>

    <!-- H. Légende -->
    <div class="flex flex-wrap gap-6 mt-8 text-sm text-gray-500 border-t pt-4">
      <span>
        <span class="inline-block w-3 h-3 rounded-sm bg-blue-600 mr-1" />
        Stack WindFlow — géré, éditable
      </span>
      <span>
        <span class="inline-block w-3 h-3 rounded-sm bg-orange-500 mr-1" />
        Discovered — observé, adoptable
      </span>
      <span>
        <span class="inline-block w-3 h-3 rounded-sm bg-gray-400 mr-1" />
        Standalone — container individuel géré
      </span>
    </div>

    <!-- Bulk Delete Confirmation Dialog for Standalone -->
    <el-dialog
      v-model="standaloneBulkDeleteDialogVisible"
      title="Confirmer la suppression groupée"
      width="500px"
    >
      <el-alert
        type="warning"
        :closable="false"
        show-icon
        class="bulk-delete-alert"
      >
        <template #title>
          Vous êtes sur le point de supprimer <strong>{{ selectedStandaloneIds.length }}</strong> container{{ selectedStandaloneIds.length > 1 ? 's' : '' }}.
        </template>
      </el-alert>
      <div class="bulk-delete-list">
        <p>Containers concernés :</p>
        <ul>
          <li
            v-for="id in selectedStandaloneIds.slice(0, 5)"
            :key="id"
          >
            {{ getStandaloneContainerName(id) }}
          </li>
          <li
            v-if="selectedStandaloneIds.length > 5"
            class="more-items"
          >
            ... et {{ selectedStandaloneIds.length - 5 }} autre{{ selectedStandaloneIds.length - 5 > 1 ? 's' : '' }}
          </li>
        </ul>
      </div>
      <el-checkbox v-model="standaloneBulkForceDelete">
        Forcer la suppression
      </el-checkbox>
      <template #footer>
        <el-button @click="standaloneBulkDeleteDialogVisible = false">
          Annuler
        </el-button>
        <el-button
          type="danger"
          :loading="standaloneBulkDeleting"
          @click="confirmStandaloneBulkDelete"
        >
          Supprimer {{ selectedStandaloneIds.length }} container{{ selectedStandaloneIds.length > 1 ? 's' : '' }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Loading, VideoPlay, VideoPause, RefreshRight, Delete } from '@element-plus/icons-vue'
import { useComputeStore, useTargetsStore } from '@/stores'
import { useAuthStore } from '@/stores/auth'
import { containersApi } from '@/services/api'
import ComputeStatsBanner from '@/components/ComputeStatsBanner.vue'
import ActionButtons, { type ActionType } from '@/components/ui/ActionButtons.vue'
import type { ControlLevel, StackWithServices, StandaloneContainer, StandaloneContainerPortMapping } from '@/types/api'

const router = useRouter()
const computeStore = useComputeStore()
const targetsStore = useTargetsStore()
const authStore = useAuthStore()

// Filtres
const groupByTarget = ref(false)
const filterType = ref<ControlLevel | 'all'>('all')
const activeTechnologies = ref<string[]>([])
const activeTargets = ref<string[]>([])
const filterSearch = ref('')

// Debounce manuel 300ms sur filterSearch
const debouncedSearch = ref('')
let debounceTimer: number | undefined

watch(filterSearch, (val) => {
  if (debounceTimer !== undefined) {
    window.clearTimeout(debounceTimer)
  }
  debounceTimer = window.setTimeout(() => {
    debouncedSearch.value = val
  }, 300)
})

// Standalone selection state
const standaloneTableRef = ref()
const selectedStandaloneContainers = ref<StandaloneContainer[]>([])
const selectedStandaloneIds = computed(() => selectedStandaloneContainers.value.map(c => c.id))

// Standalone bulk action state
const standaloneBulkActionLoading = ref<string | null>(null)
const standaloneBulkDeleteDialogVisible = ref(false)
const standaloneBulkForceDelete = ref(false)
const standaloneBulkDeleting = ref(false)

// Technologies disponibles (dynamiques depuis les données chargées)
const availableTechnologies = computed<string[]>(() => {
  const techs = new Set<string>()
  computeStore.managedStacks.forEach(s => techs.add(s.technology))
  computeStore.discoveredItems.forEach(d => techs.add(d.technology))
  return Array.from(techs)
})

// Nombre de technologies distinctes pour sous-titre
const techCount = computed(() => availableTechnologies.value.length)

// Stacks managées avec au moins une instance (services_total > 0)
const visibleManagedStacks = computed(() =>
  computeStore.managedStacks.filter(stack => stack.services_total > 0)
)

// Items découverts avec au moins une instance (services_total > 0)
const visibleDiscoveredItems = computed(() =>
  computeStore.discoveredItems.filter(item => item.services_total > 0)
)

// Groupes par machine avec stacks et discovered filtrés (sans les stacks vides)
const filteredTargetGroups = computed(() =>
  computeStore.targetGroups.map(group => ({
    ...group,
    stacks: group.stacks.filter(stack => stack.services_total > 0),
    discovered: group.discovered.filter(item => item.services_total > 0)
  }))
)

// Paramètres de filtre calculés
const filterParams = computed(() => ({
  type: filterType.value !== 'all' ? (filterType.value as ControlLevel) : undefined,
  technology: activeTechnologies.value.length > 0 ? activeTechnologies.value[0] : undefined,
  target_id: activeTargets.value.length > 0 ? activeTargets.value[0] : undefined,
  search: debouncedSearch.value || undefined,
}))

// Helpers de toggle pills
function toggleTechnology(tech: string): void {
  const idx = activeTechnologies.value.indexOf(tech)
  if (idx === -1) {
    activeTechnologies.value.push(tech)
  } else {
    activeTechnologies.value.splice(idx, 1)
  }
}

function toggleTarget(targetId: string): void {
  const idx = activeTargets.value.indexOf(targetId)
  if (idx === -1) {
    activeTargets.value.push(targetId)
  } else {
    activeTargets.value.splice(idx, 1)
  }
}

// Couleur des services running
function servicesRunningClass(stack: StackWithServices): string {
  if (stack.services_running === stack.services_total) return 'text-green-600'
  if (stack.services_running === 0) return 'text-red-500'
  return 'text-orange-500'
}

// Helpers actions
function copyToClipboard(text: string): void {
  window.navigator.clipboard.writeText(text).then(() => {
    ElMessage.success('ID copié dans le presse-papiers')
  })
}

function openTerminal(containerId: string): void {
  router.push(`/terminal/${containerId}`)
}

function refreshGlobal(): void {
  const orgId = authStore.organizationId ?? undefined
  if (groupByTarget.value) {
    computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: orgId })
  } else {
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  }
}

async function handleStartContainer(id: string): Promise<void> {
  try {
    await containersApi.start(id)
    ElMessage.success('Container démarré')
    refreshGlobal()
  } catch {
    ElMessage.error('Erreur lors du démarrage du container')
  }
}

async function handleRemoveContainer(id: string): Promise<void> {
  try {
    await ElMessageBox.confirm(
      'Supprimer ce container ? Cette action est irréversible.',
      'Confirmation',
      { confirmButtonText: 'Supprimer', cancelButtonText: 'Annuler', type: 'warning' }
    )
    await containersApi.remove(id)
    ElMessage.success('Container supprimé')
    refreshGlobal()
  } catch (err) {
    // Annulation par l'utilisateur = pas d'erreur
    if (err !== 'cancel') {
      ElMessage.error('Erreur lors de la suppression du container')
    }
  }
}

// Helpers pour les containers standalone
function getContainerStatusColor(container: StandaloneContainer): string {
  if (container.health_status === 'healthy') return 'text-green-500'
  if (container.health_status === 'unhealthy') return 'text-orange-500'
  if (container.status === 'running') return 'text-green-500'
  return 'text-red-400'
}

function getContainerStatusType(container: StandaloneContainer): 'success' | 'warning' | 'danger' | 'info' {
  if (container.health_status === 'healthy') return 'success'
  if (container.health_status === 'unhealthy') return 'warning'
  if (container.status === 'running') return 'success'
  if (container.status === 'exited') return 'danger'
  return 'info'
}

function getContainerStatusLabel(container: StandaloneContainer): string {
  if (container.health_status === 'healthy') return 'healthy'
  if (container.health_status === 'unhealthy') return 'unhealthy'
  if (container.health_status === 'starting') return 'starting'
  return container.status
}

function formatPort(port: StandaloneContainerPortMapping): string {
  return `${port.host_ip}:${port.host_port}->${port.container_port}/${port.protocol}`
}

function getStandaloneActions(container: StandaloneContainer) {
  const isRunning = container.status === 'running'
  const isStopped = container.status === 'exited' || container.status === 'created'

  return [
    { type: 'start' as ActionType, disabled: !isStopped },
    { type: 'stop' as ActionType, disabled: !isRunning },
    { type: 'restart' as ActionType, disabled: !isRunning },
    { type: 'logs' as ActionType },
    { type: 'delete' as ActionType },
  ]
}

async function handleStandaloneAction(action: ActionType, container: StandaloneContainer): Promise<void> {
  switch (action) {
    case 'start':
      await handleStartContainer(container.id)
      break
    case 'stop':
      try {
        await containersApi.stop(container.id)
        ElMessage.success(`Container "${container.name}" arrêté`)
        refreshGlobal()
      } catch {
        ElMessage.error('Erreur lors de l\'arrêt du container')
      }
      break
    case 'restart':
      try {
        await containersApi.restart(container.id)
        ElMessage.success(`Container "${container.name}" redémarré`)
        refreshGlobal()
      } catch {
        ElMessage.error('Erreur lors du redémarrage du container')
      }
      break
    case 'logs':
      router.push(`/containers/${container.id}`)
      break
    case 'delete':
      await handleRemoveContainer(container.id)
      break
  }
}

// Standalone selection handlers
function handleStandaloneSelectionChange(selection: StandaloneContainer[]): void {
  selectedStandaloneContainers.value = selection
}

function clearStandaloneSelection(): void {
  standaloneTableRef.value?.clearSelection()
  selectedStandaloneContainers.value = []
}

function getStandaloneContainerName(id: string): string {
  const container = computeStore.standaloneContainers.find(c => c.id === id)
  return container?.name || id
}

// Standalone bulk actions
async function handleStandaloneBulkAction(action: 'start' | 'stop' | 'restart' | 'delete'): Promise<void> {
  if (action === 'delete') {
    showStandaloneBulkDeleteDialog()
    return
  }

  standaloneBulkActionLoading.value = action

  try {
    const ids = selectedStandaloneIds.value
    let successCount = 0
    let failCount = 0

    for (const id of ids) {
      try {
        switch (action) {
          case 'start':
            await containersApi.start(id)
            break
          case 'stop':
            await containersApi.stop(id)
            break
          case 'restart':
            await containersApi.restart(id)
            break
        }
        successCount++
      } catch {
        failCount++
      }
    }

    // Show result message
    if (failCount === 0) {
      ElMessage.success(`${successCount} container${successCount > 1 ? 's' : ''} ${getActionPastParticiple(action)}`)
    } else if (successCount === 0) {
      ElMessage.error(`Échec de l'action sur ${failCount} container${failCount > 1 ? 's' : ''}`)
    } else {
      ElMessage.warning(`${successCount} réussi${successCount > 1 ? 's' : ''}, ${failCount} échoué${failCount > 1 ? 's' : ''}`)
    }

    clearStandaloneSelection()
    refreshGlobal()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de l\'action groupée'
    ElMessage.error(message)
  } finally {
    standaloneBulkActionLoading.value = null
  }
}

function getActionPastParticiple(action: 'start' | 'stop' | 'restart'): string {
  const map: Record<string, string> = {
    start: 'démarré(s)',
    stop: 'arrêté(s)',
    restart: 'redémarré(s)',
  }
  return map[action] || action
}

function showStandaloneBulkDeleteDialog(): void {
  standaloneBulkForceDelete.value = false
  standaloneBulkDeleteDialogVisible.value = true
}

async function confirmStandaloneBulkDelete(): Promise<void> {
  standaloneBulkDeleting.value = true

  try {
    const ids = selectedStandaloneIds.value
    let successCount = 0
    let failCount = 0

    for (const id of ids) {
      try {
        await containersApi.remove(id, standaloneBulkForceDelete.value)
        successCount++
      } catch {
        failCount++
      }
    }

    if (failCount === 0) {
      ElMessage.success(`${successCount} container${successCount > 1 ? 's' : ''} supprimé${successCount > 1 ? 's' : ''}`)
    } else if (successCount === 0) {
      ElMessage.error(`Échec de la suppression de ${failCount} container${failCount > 1 ? 's' : ''}`)
    } else {
      ElMessage.warning(`${successCount} supprimé${successCount > 1 ? 's' : ''}, ${failCount} échoué${failCount > 1 ? 's' : ''}`)
    }

    standaloneBulkDeleteDialogVisible.value = false
    clearStandaloneSelection()
    refreshGlobal()
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Erreur lors de la suppression groupée'
    ElMessage.error(message)
  } finally {
    standaloneBulkDeleting.value = false
  }
}

// Watcher sur les filtres
watch(filterParams, () => {
  const orgId = authStore.organizationId ?? undefined
  if (!groupByTarget.value) {
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  } else {
    computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: orgId })
  }
})

// Watcher sur le toggle par machine
watch(groupByTarget, (val) => {
  const orgId = authStore.organizationId ?? undefined
  if (val) {
    computeStore.fetchGlobalByTarget({ ...filterParams.value, organization_id: orgId })
  } else {
    computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  }
})

// Chargement initial
onMounted(() => {
  const orgId = authStore.organizationId ?? undefined
  computeStore.fetchStats(orgId)
  computeStore.fetchGlobal({ ...filterParams.value, organization_id: orgId })
  targetsStore.fetchTargets(orgId)
})
</script>

<style scoped>
.compute-view {
  max-width: 1400px;
  margin: 0 auto;
}

.section-header {
  padding: 8px 0;
  border-bottom: 1px solid var(--color-border, #e5e7eb);
}

.filter-bar :deep(.el-radio-button__inner) {
  padding: 5px 12px;
  font-size: 13px;
}

.pill {
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: 999px;
  font-size: 12px;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all 0.2s;
  user-select: none;
}

.pill-default {
  background-color: var(--color-bg-secondary, #f3f4f6);
  color: var(--color-text-secondary, #6b7280);
  border-color: var(--color-border, #e5e7eb);
}

.pill-default:hover {
  background-color: var(--color-bg-elevated, #e9ecef);
}

.pill-selected {
  background-color: var(--el-color-primary-light-8, #ecf5ff);
  color: var(--el-color-primary, #409eff);
  border-color: var(--el-color-primary, #409eff);
}

.stacks-collapse :deep(.el-collapse-item__header),
.discovered-collapse :deep(.el-collapse-item__header),
.target-groups-collapse :deep(.el-collapse-item__header) {
  height: auto;
  min-height: 44px;
  padding: 8px 16px;
}

/* Slide down transition */
.slide-down-enter-active,
.slide-down-leave-active {
  transition: all 0.3s ease;
}

.slide-down-enter-from,
.slide-down-leave-to {
  opacity: 0;
  transform: translateY(-10px);
}

/* Bulk Delete Dialog */
.bulk-delete-alert {
  margin-bottom: 16px;
}

.bulk-delete-list {
  margin-bottom: 16px;
}

.bulk-delete-list p {
  font-weight: 500;
  margin-bottom: 8px;
  color: var(--color-text-primary);
}

.bulk-delete-list ul {
  margin: 0;
  padding-left: 20px;
  max-height: 150px;
  overflow-y: auto;
}

.bulk-delete-list li {
  margin-bottom: 4px;
  color: var(--color-text-primary);
}

.bulk-delete-list .more-items {
  font-style: italic;
  color: var(--color-text-secondary);
}

/* Fix padding icônes dans boutons standalone bulk actions */
.compute-view :deep(.el-icon--left) {
  margin-right: 6px;
}
</style>
