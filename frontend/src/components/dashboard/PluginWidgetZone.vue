<template>
  <div
    v-if="pluginWidgetStore.hasWidgets"
    class="plugin-widget-zone"
    data-testid="plugin-widget-zone"
  >
    <h2 class="plugin-widget-zone__title">
      <el-icon><Grid /></el-icon>
      <span>Plugin Widgets</span>
    </h2>
    <div class="plugin-widget-zone__grid">
      <el-card
        v-for="widget in pluginWidgetStore.sortedWidgets"
        :key="widget.id"
        class="plugin-widget-card"
        :data-testid="`plugin-widget-${widget.id}`"
      >
        <template
          v-if="widget.title"
          #header
        >
          <span class="plugin-widget-card__title">{{ widget.title }}</span>
        </template>
        <component
          :is="widget.component"
          v-bind="widget.props"
        />
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * PluginWidgetZone Component
 *
 * Displays widgets registered by plugins in a responsive grid.
 * Only renders if at least one widget is registered.
 *
 * @example
 * <PluginWidgetZone />
 */

import { Grid } from '@element-plus/icons-vue'
import { usePluginWidgetStore } from '@/stores/pluginWidget'

const pluginWidgetStore = usePluginWidgetStore()
</script>

<style scoped>
.plugin-widget-zone {
  margin-top: 20px;
}

.plugin-widget-zone__title {
  display: flex;
  align-items: center;
  margin-bottom: 1rem;
  font-size: var(--text-lg, 1.125rem);
  color: var(--color-text-primary);
  gap: 0.5rem;
  font-weight: 600;
}

.plugin-widget-zone__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 1rem;
}

/* Tablet: 1 column */
@media (width <= 768px) {
  .plugin-widget-zone__grid {
    grid-template-columns: 1fr;
  }
}

.plugin-widget-card {
  width: 100%;
}

.plugin-widget-card__title {
  font-weight: 600;
  color: var(--color-text-primary);
}
</style>
