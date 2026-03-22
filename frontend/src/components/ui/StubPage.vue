<template>
  <div class="stub-page">
    <el-card class="stub-card">
      <div class="stub-content">
        <div class="stub-icon">
          <el-icon :size="64">
            <component :is="rawIcon" />
          </el-icon>
        </div>
        <h1 class="stub-title">
          {{ title }}
        </h1>
        <p class="stub-description">
          {{ description }}
        </p>
        <el-tag
          class="stub-badge"
          type="info"
          effect="plain"
        >
          Prévu pour {{ version }}
        </el-tag>
        <el-button
          class="stub-button"
          type="primary"
          @click="$router.push('/')"
        >
          Retour au Dashboard
        </el-button>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { markRaw, type Component } from 'vue'

/**
 * StubPage - Reusable placeholder page component
 * Used for features that are planned but not yet implemented
 */

interface Props {
  title: string
  description: string
  icon: Component
  version?: string
}

const props = withDefaults(defineProps<Props>(), {
  version: 'v1.1 — Phase 2',
})

// Mark icon as raw to prevent Vue from making it reactive
const rawIcon = markRaw(props.icon)
</script>

<style scoped>
.stub-page {
  display: flex;
  justify-content: center;
  align-items: flex-start;
  padding: 40px 20px;
}

.stub-card {
  max-width: 480px;
  width: 100%;
  background-color: var(--color-bg-card);
  border-color: var(--color-border);
}

.stub-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 20px;
}

.stub-icon {
  color: var(--color-text-muted);
  margin-bottom: 24px;
  opacity: 0.6;
}

.stub-title {
  font-size: var(--text-2xl);
  font-weight: var(--font-semibold);
  color: var(--color-text-primary);
  margin: 0 0 12px 0;
}

.stub-description {
  font-size: var(--text-base);
  color: var(--color-text-secondary);
  margin: 0 0 20px 0;
  max-width: 320px;
  line-height: var(--leading-relaxed);
}

.stub-badge {
  margin-bottom: 24px;
}

.stub-button {
  min-width: 160px;
}
</style>
