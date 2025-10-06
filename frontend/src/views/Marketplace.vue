<template>
  <div class="marketplace-view p-6">
    <!-- En-tête -->
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900 mb-2">
        Marketplace WindFlow
      </h1>
      <p class="text-gray-600">
        Déployez des applications populaires en quelques clics
      </p>
    </div>

    <!-- Barre de recherche et filtres -->
    <div class="flex flex-col md:flex-row gap-4 mb-6">
      <!-- Recherche -->
      <el-input
        v-model="store.searchQuery"
        placeholder="Rechercher un stack..."
        :prefix-icon="Search"
        clearable
        class="flex-1"
        @input="onSearchChange"
      />

      <!-- Filtre catégorie -->
      <el-select
        v-model="store.selectedCategory"
        placeholder="Toutes les catégories"
        clearable
        class="w-full md:w-64"
        @change="onCategoryChange"
      >
        <el-option label="Toutes les catégories" value="" />
        <el-option
          v-for="category in store.categories"
          :key="category"
          :label="category"
          :value="category"
        />
      </el-select>

      <!-- Bouton rafraîchir -->
      <el-button :icon="Refresh" @click="refresh">
        Rafraîchir
      </el-button>
    </div>

    <!-- Sections populaires et récents -->
    <div v-if="!store.searchQuery && !store.selectedCategory" class="mb-8">
      <!-- Stacks populaires -->
      <div v-if="popularStacks.length > 0" class="mb-8">
        <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
          <el-icon><TrendCharts /></el-icon>
          Les plus populaires
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <StackCard
            v-for="stack in popularStacks.slice(0, 4)"
            :key="stack.id"
            :stack="stack"
            @select="showStackDetails"
          />
        </div>
      </div>

      <!-- Stacks récents -->
      <div v-if="recentStacks.length > 0" class="mb-8">
        <h2 class="text-xl font-semibold mb-4 flex items-center gap-2">
          <el-icon><Clock /></el-icon>
          Récemment ajoutés
        </h2>
        <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
          <StackCard
            v-for="stack in recentStacks.slice(0, 4)"
            :key="stack.id"
            :stack="stack"
            @select="showStackDetails"
          />
        </div>
      </div>

      <el-divider />
    </div>

    <!-- Grille de stacks -->
    <div v-loading="store.loading">
      <!-- Nombre de résultats -->
      <div class="mb-4 text-sm text-gray-600">
        {{ store.totalStacks }} stack{{ store.totalStacks > 1 ? 's' : '' }} trouvé{{ store.totalStacks > 1 ? 's' : '' }}
      </div>

      <!-- Grille -->
      <div
        v-if="store.stacks.length > 0"
        class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4"
      >
        <StackCard
          v-for="stack in store.stacks"
          :key="stack.id"
          :stack="stack"
          @select="showStackDetails"
        />
      </div>

      <!-- Message vide -->
      <el-empty
        v-else-if="!store.loading"
        description="Aucun stack trouvé"
        :image-size="200"
      >
        <el-button type="primary" @click="clearFilters">
          Réinitialiser les filtres
        </el-button>
      </el-empty>

      <!-- Bouton charger plus -->
      <div v-if="store.hasMoreStacks" class="text-center mt-6">
        <el-button
          type="primary"
          :loading="store.loading"
          @click="store.loadMore"
        >
          Charger plus de stacks
        </el-button>
      </div>
    </div>

    <!-- Modal détails du stack -->
    <StackDetailsModal
      v-if="selectedStack"
      v-model:visible="detailsVisible"
      :stack-id="selectedStack.id"
      @deploy="showDeploymentWizard"
    />

    <!-- Wizard de déploiement -->
    <DeploymentWizard
      v-if="stackToDeploy"
      v-model:visible="wizardVisible"
      :stack="stackToDeploy"
      @deployed="onDeployed"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { Search, Refresh, TrendCharts, Clock } from '@element-plus/icons-vue'
import { useMarketplaceStore } from '@/stores/marketplace'
import StackCard from '@/components/marketplace/StackCard.vue'
import StackDetailsModal from '@/components/marketplace/StackDetailsModal.vue'
import DeploymentWizard from '@/components/marketplace/DeploymentWizard.vue'
import type { MarketplaceStack, StackDetails } from '@/types/marketplace'
import { ElMessage } from 'element-plus'
import { useRouter } from 'vue-router'

const store = useMarketplaceStore()
const router = useRouter()

// État local
const selectedStack = ref<MarketplaceStack | null>(null)
const stackToDeploy = ref<StackDetails | null>(null)
const detailsVisible = ref(false)
const wizardVisible = ref(false)
const popularStacks = ref<MarketplaceStack[]>([])
const recentStacks = ref<MarketplaceStack[]>([])

// Debounce pour la recherche
let searchTimeout: NodeJS.Timeout

function onSearchChange() {
  clearTimeout(searchTimeout)
  searchTimeout = setTimeout(() => {
    store.setSearch(store.searchQuery)
  }, 500)
}

function onCategoryChange() {
  store.setCategory(store.selectedCategory)
}

function clearFilters() {
  store.clearFilters()
}

async function refresh() {
  await Promise.all([
    store.fetchStacks({ reset: true }),
    loadPopularAndRecent()
  ])
  ElMessage.success('Marketplace actualisée')
}

async function loadPopularAndRecent() {
  try {
    const [popular, recent] = await Promise.all([
      store.fetchStacks({ reset: true }),
      // TODO: Appeler les endpoints populaires et récents
      // marketplaceService.getPopularStacks(),
      // marketplaceService.getRecentStacks()
    ])
    // popularStacks.value = popular
    // recentStacks.value = recent
  } catch (err) {
    console.error('Erreur chargement stacks populaires/récents:', err)
  }
}

function showStackDetails(stack: MarketplaceStack) {
  selectedStack.value = stack
  detailsVisible.value = true
}

function showDeploymentWizard(stack: StackDetails) {
  stackToDeploy.value = stack
  wizardVisible.value = true
}

function onDeployed(deploymentId: string) {
  wizardVisible.value = false
  ElMessage.success('Déploiement lancé !')

  // Rediriger vers la page des déploiements
  router.push(`/deployments/${deploymentId}`)
}

onMounted(async () => {
  // Charger les catégories et stacks initiaux
  await Promise.all([
    store.fetchCategories(),
    store.fetchStacks({ reset: true }),
    loadPopularAndRecent()
  ])
})
</script>

<style scoped>
.marketplace-view {
  max-width: 1400px;
  margin: 0 auto;
}
</style>
