<template>
  <el-container class="main-layout">
    <!-- Mobile overlay -->
    <div
      v-if="sidebar.isMobile.value && sidebar.isMobileOpen.value"
      class="sidebar-overlay"
      @click="sidebar.closeMobile()"
    />

    <!-- Sidebar -->
    <el-aside
      :width="sidebarWidth"
      class="sidebar-aside"
      :class="{ 'mobile-open': sidebar.isMobileOpen.value }"
    >
      <SidebarNav />
    </el-aside>

    <el-container>
      <!-- Mobile header with hamburger -->
      <el-header
        v-if="sidebar.isMobile.value"
        class="mobile-header"
        height="56px"
      >
        <button
          class="hamburger-btn"
          @click="sidebar.toggleMobile()"
        >
          <el-icon :size="24">
            <Close v-if="sidebar.isMobileOpen.value" />
            <Menu v-else />
          </el-icon>
        </button>
        <span class="mobile-title">WindFlow</span>
        <div class="mobile-header-actions">
          <ThemeToggle />
        </div>
      </el-header>

      <el-main class="main-content">
        <div class="content-header">
          <Breadcrumb />
          <ThemeToggle v-if="!sidebar.isMobile.value" />
        </div>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import SidebarNav from '@/components/SidebarNav.vue'
import Breadcrumb from '@/components/Breadcrumb.vue'
import ThemeToggle from '@/components/ThemeToggle.vue'
import { useSidebar } from '@/composables/useSidebar'
import { Menu, Close } from '@element-plus/icons-vue'

const sidebar = useSidebar()

// Compute sidebar width based on state
const sidebarWidth = computed(() => {
  if (sidebar.isMobile.value) {
    return '0px' // Hidden on mobile (shown via overlay)
  }
  return `${sidebar.sidebarWidth.value}px`
})
</script>

<style scoped>
.main-layout {
  height: 100vh;
  overflow: hidden;
}

.sidebar-aside {
  background-color: var(--color-bg-primary);
  height: 100vh;
  overflow: hidden;
  transition: width 0.3s ease;
}

/* Mobile overlay */
.sidebar-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background-color: rgba(0, 0, 0, 0.5);
  z-index: 999;
}

/* Mobile header */
.mobile-header {
  display: flex;
  align-items: center;
  padding: 0 16px;
  background-color: var(--color-bg-primary);
  border-bottom: 1px solid var(--color-border);
}

.hamburger-btn {
  background: transparent;
  border: none;
  color: var(--color-text-primary);
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: background-color 0.2s;
}

.hamburger-btn:hover {
  background-color: var(--color-bg-hover);
}

.mobile-title {
  margin-left: 12px;
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text-primary);
}

.mobile-header-actions {
  margin-left: auto;
}

.main-content {
  background-color: var(--color-bg-secondary);
  padding: 20px;
  overflow-y: auto;
  height: 100vh;
}

.content-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

/* Responsive adjustments */
@media (max-width: 767px) {
  .main-content {
    padding: 16px;
  }

  .sidebar-aside {
    position: fixed;
    left: 0;
    top: 0;
    height: 100vh;
    z-index: 1000;
    width: 0 !important;
    overflow: hidden;
  }

  .sidebar-aside.mobile-open {
    width: 220px !important;
  }
}

/* Tablet: collapsed sidebar */
@media (min-width: 768px) and (max-width: 1023px) {
  .sidebar-aside {
    width: 64px !important;
  }
}
</style>
