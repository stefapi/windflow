<template>
  <el-card
    class="stack-card cursor-pointer hover:shadow-lg transition-shadow"
    :body-style="{ padding: '0' }"
    @click="$emit('select', stack)"
  >
    <!-- Image/Icône -->
    <div class="stack-header relative h-40 bg-gradient-to-br from-primary-50 to-primary-100 flex items-center justify-center">
      <img
        v-if="stack.icon_url"
        :src="stack.icon_url"
        :alt="stack.name"
        class="h-20 w-20 object-contain"
        @error="onImageError"
      >
      <el-icon v-else class="text-6xl text-primary-400">
        <Box />
      </el-icon>

      <!-- Badge catégorie -->
      <div v-if="stack.category" class="absolute top-2 right-2">
        <el-tag :type="getCategoryType(stack.category)" size="small">
          {{ stack.category }}
        </el-tag>
      </div>
    </div>

    <!-- Contenu -->
    <div class="p-4">
      <!-- Titre et version -->
      <div class="mb-2">
        <h3 class="text-lg font-semibold text-gray-900 truncate">
          {{ stack.name }}
        </h3>
        <p class="text-sm text-gray-500">
          v{{ stack.version }}
          <span v-if="stack.author" class="ml-2">• {{ stack.author }}</span>
        </p>
      </div>

      <!-- Description -->
      <p class="text-sm text-gray-600 line-clamp-2 mb-3 min-h-10">
        {{ stack.description || 'Aucune description disponible' }}
      </p>

      <!-- Tags -->
      <div class="flex flex-wrap gap-1 mb-3 min-h-6">
        <el-tag
          v-for="tag in stack.tags.slice(0, 3)"
          :key="tag"
          size="small"
          effect="plain"
          class="text-xs"
        >
          {{ tag }}
        </el-tag>
        <el-tag
          v-if="stack.tags.length > 3"
          size="small"
          effect="plain"
          class="text-xs"
        >
          +{{ stack.tags.length - 3 }}
        </el-tag>
      </div>

      <!-- Stats -->
      <div class="flex items-center justify-between text-sm text-gray-500 border-t pt-3">
        <div class="flex items-center gap-4">
          <!-- Téléchargements -->
          <div class="flex items-center gap-1">
            <el-icon><Download /></el-icon>
            <span>{{ formatNumber(stack.downloads) }}</span>
          </div>

          <!-- Note -->
          <div v-if="stack.rating > 0" class="flex items-center gap-1">
            <el-icon class="text-yellow-500"><StarFilled /></el-icon>
            <span>{{ stack.rating.toFixed(1) }}</span>
          </div>
        </div>

        <!-- Licence -->
        <div v-if="stack.license" class="text-xs text-gray-400">
          {{ stack.license }}
        </div>
      </div>
    </div>
  </el-card>
</template>

<script setup lang="ts">
import { Box, Download, StarFilled } from '@element-plus/icons-vue'
import type { MarketplaceStack } from '@/types/marketplace'

interface Props {
  stack: MarketplaceStack
}

interface Emits {
  select: [stack: MarketplaceStack]
}

defineProps<Props>()
defineEmits<Emits>()

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

function formatNumber(num: number): string {
  if (num >= 1000) {
    return `${(num / 1000).toFixed(1)}k`
  }
  return num.toString()
}

function onImageError(event: Event) {
  // Cacher l'image si elle ne charge pas
  const img = event.target as HTMLImageElement
  img.style.display = 'none'
}
</script>

<style scoped>
.stack-card {
  height: 100%;
  display: flex;
  flex-direction: column;
}

.line-clamp-2 {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.min-h-10 {
  min-height: 2.5rem;
}

.min-h-6 {
  min-height: 1.5rem;
}
</style>
