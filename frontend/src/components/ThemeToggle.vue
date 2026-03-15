<template>
  <el-tooltip :content="themeStore.isDark() ? 'Passer au thème clair' : 'Passer au thème sombre'" placement="bottom">
    <el-button
      class="theme-toggle"
      circle
      @click="themeStore.toggleTheme()"
    >
      <el-icon>
        <Sunny v-if="themeStore.isDark()" />
        <Moon v-else />
      </el-icon>
    </el-button>
  </el-tooltip>
</template>

<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'
import { Moon, Sunny } from '@element-plus/icons-vue'

const themeStore = useThemeStore()
</script>

<style scoped>
.theme-toggle {
  background-color: var(--color-bg-elevated);
  border-color: var(--color-border);
  color: var(--color-text-secondary);
}

.theme-toggle:hover {
  background-color: var(--color-bg-hover);
  color: var(--color-accent);
}
</style>
