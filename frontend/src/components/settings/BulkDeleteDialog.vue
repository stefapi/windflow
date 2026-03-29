<template>
  <el-dialog
    :model-value="visible"
    title="Confirmer la suppression groupée"
    width="500px"
    @update:model-value="$emit('update:visible', $event)"
  >
    <el-alert
      type="warning"
      :closable="false"
      show-icon
      class="bulk-delete-alert"
    >
      <template #title>
        Vous êtes sur le point de supprimer <strong>{{ items.length }}</strong> {{ itemLabel }}{{ items.length > 1 ? pluralSuffix : '' }}.
      </template>
    </el-alert>
    <div class="bulk-delete-list">
      <p>{{ listLabel }} :</p>
      <ul>
        <li
          v-for="(item, index) in displayedItems"
          :key="getItemKey(item, index)"
        >
          {{ getItemLabel(item) }}
        </li>
        <li
          v-if="items.length > maxDisplayed"
          class="more-items"
        >
          ... et {{ items.length - maxDisplayed }} autre{{ items.length - maxDisplayed > 1 ? 's' : '' }}
        </li>
      </ul>
    </div>
    <template #footer>
      <el-button @click="$emit('update:visible', false)">
        Annuler
      </el-button>
      <el-button
        type="danger"
        :loading="loading"
        @click="handleConfirm"
      >
        Supprimer {{ items.length }} {{ itemLabel }}{{ items.length > 1 ? pluralSuffix : '' }}
      </el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts" generic="T">
import { computed } from 'vue'

interface Props {
  visible: boolean
  items: T[]
  itemLabel: string
  pluralSuffix?: string
  listLabel?: string
  maxDisplayed?: number
  loading?: boolean
  getItemLabel: (item: T) => string
  getItemKey?: (item: T, index: number) => string | number
}

const props = withDefaults(defineProps<Props>(), {
  pluralSuffix: 's',
  listLabel: 'Éléments concernés',
  maxDisplayed: 5,
  loading: false,
  getItemKey: (_item: T, index: number) => index,
})

const emit = defineEmits<{
  'update:visible': [value: boolean]
  'confirm': []
}>()

const displayedItems = computed(() => props.items.slice(0, props.maxDisplayed))

function handleConfirm() {
  emit('confirm')
}
</script>

<script lang="ts">
export default {
  name: 'BulkDeleteDialog',
}
</script>

<style scoped>
.bulk-delete-alert {
  margin-bottom: 16px;
}

.bulk-delete-list {
  margin-bottom: 16px;
}

.bulk-delete-list p {
  font-weight: 500;
  margin-bottom: 8px;
}

.bulk-delete-list ul {
  overflow-y: auto;
  max-height: 150px;
  padding-left: 20px;
  margin: 0;
}

.bulk-delete-list li {
  margin-bottom: 4px;
}

.bulk-delete-list .more-items {
  font-style: italic;
  color: var(--el-text-color-secondary);
}
</style>
