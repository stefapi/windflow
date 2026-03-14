<template>
  <div class="page-container">
    <el-card class="page-header">
      <template #header>
        <div class="header-content">
          <span class="title">Audit</span>
          <span class="subtitle">Journal d'activité et logs d'audit</span>
        </div>
      </template>
      <el-empty description="Cette fonctionnalité sera disponible prochainement">
        <el-button type="primary" @click="$router.push('/')">Retour au Dashboard</el-button>
      </el-empty>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// Stub view for Audit
</script>

<style scoped>
.page-container {
  padding: 0;
}

.page-header {
  margin-bottom: 20px;
}

.header-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.title {
  font-size: 20px;
  font-weight: 600;
  color: #1f2937;
}

.subtitle {
  font-size: 14px;
  color: #6b7280;
}
</style>
