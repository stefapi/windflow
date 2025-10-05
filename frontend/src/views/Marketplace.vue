<template>
  <div class="marketplace">
    <el-card>
      <template #header>
        <div class="card-header">
          <span>Template Marketplace</span>
          <el-input v-model="searchQuery" placeholder="Search templates..." style="width: 300px" clearable>
            <template #prefix>
              <el-icon><icon-ep-search /></el-icon>
            </template>
          </el-input>
        </div>
      </template>
      
      <el-row :gutter="20" style="margin-bottom: 20px">
        <el-col :span="6">
          <el-select v-model="selectedCategory" placeholder="All Categories" style="width: 100%" clearable>
            <el-option label="All Categories" value="" />
            <el-option v-for="cat in marketplaceStore.categories" :key="cat" :label="cat" :value="cat" />
          </el-select>
        </el-col>
      </el-row>

      <el-row :gutter="20">
        <el-col :span="6" v-for="template in filteredTemplates" :key="template.id">
          <el-card class="template-card" shadow="hover">
            <h3>{{ template.name }}</h3>
            <p>{{ template.description }}</p>
            <div class="template-meta">
              <el-tag size="small">{{ template.category }}</el-tag>
              <el-rate v-model="template.rating" disabled show-score />
            </div>
            <div class="template-actions">
              <el-button type="primary" size="small" @click="downloadTemplate(template.id)">
                Download
              </el-button>
              <el-button size="small" @click="viewTemplate(template)">
                Details
              </el-button>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useMarketplaceStore } from '@/stores'
import { ElMessage } from 'element-plus'

const marketplaceStore = useMarketplaceStore()
const searchQuery = ref('')
const selectedCategory = ref('')

const filteredTemplates = computed(() => {
  let templates = marketplaceStore.templates
  
  if (selectedCategory.value) {
    templates = templates.filter(t => t.category === selectedCategory.value)
  }
  
  if (searchQuery.value) {
    const query = searchQuery.value.toLowerCase()
    templates = templates.filter(t => 
      t.name.toLowerCase().includes(query) || 
      t.description?.toLowerCase().includes(query)
    )
  }
  
  return templates
})

const downloadTemplate = async (id: string) => {
  try {
    const stackId = await marketplaceStore.downloadTemplate(id)
    ElMessage.success(`Template downloaded as stack: ${stackId}`)
  } catch (error) {
    ElMessage.error('Failed to download template')
  }
}

const viewTemplate = (template: any) => {
  ElMessage.info(`Viewing template: ${template.name}`)
}

onMounted(async () => {
  await Promise.all([
    marketplaceStore.fetchTemplates(),
    marketplaceStore.fetchCategories(),
    marketplaceStore.fetchPopularTemplates(),
  ])
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.template-card {
  margin-bottom: 20px;
  height: 280px;
  display: flex;
  flex-direction: column;
}

.template-card h3 {
  margin-top: 0;
  font-size: 16px;
}

.template-card p {
  flex: 1;
  font-size: 14px;
  color: #666;
}

.template-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.template-actions {
  display: flex;
  gap: 10px;
}
</style>
