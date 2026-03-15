<template>
  <nav class="sidebar-nav" :class="{ collapsed: isCollapsed }">
    <!-- Logo -->
    <div class="sidebar-logo">
      <span class="logo-icon">🌀</span>
      <span class="logo-text" v-show="!isCollapsed">WindFlow</span>
      <!-- Toggle button (desktop only) -->
      <button
        v-if="sidebar.isDesktop.value"
        class="toggle-btn"
        @click="sidebar.toggle()"
        :title="isCollapsed ? 'Déplier la sidebar' : 'Rétracter la sidebar'"
      >
        <el-icon>
          <ArrowLeft v-if="!isCollapsed" />
          <ArrowRight v-else />
        </el-icon>
      </button>
    </div>

    <!-- Navigation Sections -->
    <div class="sidebar-content">
      <!-- Dashboard (no section title) -->
      <div class="nav-section">
        <ul class="nav-list">
          <li
            v-for="item in dashboardItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Infrastructure Section -->
      <div class="nav-section">
        <div class="section-title" v-show="!isCollapsed">INFRASTRUCTURE</div>
        <ul class="nav-list">
          <li
            v-for="item in infrastructureItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Storage & Network Section -->
      <div class="nav-section">
        <div class="section-title" v-show="!isCollapsed">STOCKAGE & RÉSEAU</div>
        <ul class="nav-list">
          <li
            v-for="item in storageNetworkItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Marketplace Section -->
      <div class="nav-section">
        <div class="section-title" v-show="!isCollapsed">MARKETPLACE</div>
        <ul class="nav-list">
          <li
            v-for="item in marketplaceItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-label">{{ item.label }}</span>
                <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Dynamic Plugin Sections -->
      <div v-if="pluginNavStore.hasPluginPages" class="nav-section plugin-section">
        <div class="section-title" v-show="!isCollapsed">PLUGINS</div>
        <ul class="nav-list">
          <li
            v-for="section in pluginNavStore.sections"
            :key="section.pluginId"
            class="nav-item plugin-title"
            disabled
            v-show="!isCollapsed"
          >
            <span class="nav-label">{{ section.title }}</span>
          </li>
          <li
            v-for="item in pluginItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Administration Section -->
      <div class="nav-section">
        <div class="section-title" v-show="!isCollapsed">ADMINISTRATION</div>
        <ul class="nav-list">
          <li
            v-for="item in administrationItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>
    </div>

    <!-- Footer: Target Selector & User -->
    <div class="sidebar-footer">
      <!-- Active Target Selector -->
      <el-tooltip
        :content="activeTargetName"
        placement="right"
        :disabled="!isCollapsed"
        :show-after="300"
      >
        <div class="target-selector" @click="openTargetSelector">
          <span class="target-indicator">{{ targetIndicator }}</span>
          <span class="target-name" v-show="!isCollapsed">{{ activeTargetName }}</span>
        </div>
      </el-tooltip>

      <!-- User Info -->
      <el-tooltip
        :content="authStore.user?.username || 'Utilisateur'"
        placement="right"
        :disabled="!isCollapsed"
        :show-after="300"
      >
        <div class="user-info">
          <el-icon class="user-icon"><User /></el-icon>
          <span class="user-name" v-show="!isCollapsed">{{ authStore.user?.username || 'Utilisateur' }}</span>
          <el-dropdown @command="handleUserCommand" v-show="!isCollapsed">
            <span class="user-menu-trigger">
              <el-icon><MoreFilled /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">Déconnexion</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-tooltip>
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTargetsStore } from '@/stores/targets'
import { usePluginNavStore } from '@/stores/pluginNav'
import { useSidebar } from '@/composables/useSidebar'
import {
  Odometer,
  Box,
  Monitor,
  Upload,
  Connection,
  FolderOpened,
  Link,
  PictureFilled,
  ShoppingCart,
  Grid,
  Setting,
  DocumentChecked,
  User,
  MoreFilled,
  ArrowLeft,
  ArrowRight,
} from '@element-plus/icons-vue'
import type { NavItem, PluginNavItem } from '@/types/navigation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const targetsStore = useTargetsStore()
const pluginNavStore = usePluginNavStore()

// Sidebar responsive state
const sidebar = useSidebar()
const isCollapsed = computed(() => {
  if (sidebar.isMobile.value) {
    return !sidebar.isMobileOpen.value // Sur mobile, collapsed = fermé
  }
  return sidebar.isCollapsed.value
})

// Dashboard items (no section title)
const dashboardItems: NavItem[] = [
  { icon: Odometer, label: 'Dashboard', path: '/' },
]

// Infrastructure section items
const infrastructureItems: NavItem[] = [
  { icon: Box, label: 'Containers', path: '/containers' },
  { icon: Monitor, label: 'VMs', path: '/vms' },
  { icon: Connection, label: 'Stacks', path: '/stacks' },
  { icon: Upload, label: 'Targets', path: '/targets' },
]

// Storage & Network section items
const storageNetworkItems: NavItem[] = [
  { icon: FolderOpened, label: 'Volumes', path: '/volumes' },
  { icon: Link, label: 'Networks', path: '/networks' },
  { icon: PictureFilled, label: 'Images', path: '/images' },
]

// Marketplace section items
const marketplaceItems: NavItem[] = [
  { icon: ShoppingCart, label: 'Marketplace', path: '/marketplace' },
  { icon: Grid, label: 'Plugins', path: '/plugins' },
]

// Administration section items
const administrationItems: NavItem[] = [
  { icon: Setting, label: 'Settings', path: '/settings' },
  { icon: DocumentChecked, label: 'Audit', path: '/audit' },
]

// Plugin items from dynamic store
const pluginItems = computed<PluginNavItem[]>(() => {
  const items: PluginNavItem[] = []
  for (const section of pluginNavStore.sections) {
    items.push(...section.items)
  }
  return items
})

// Active target info
const activeTargetName = computed(() => {
  if (targetsStore.currentTarget) {
    return `${targetsStore.currentTarget.name}`
  }
  return 'Aucun target'
})

const targetIndicator = computed(() => {
  if (targetsStore.currentTarget) {
    return '🟢'
  }
  return '⚪'
})

// Check if current path is active
function isActive(path: string): boolean {
  if (path === '/') {
    return route.path === '/'
  }
  return route.path.startsWith(path)
}

// Navigate to path
function navigate(path: string): void {
  router.push(path)
}

// Open target selector (could open a dialog/dropdown)
function openTargetSelector(): void {
  router.push('/targets')
}

// Handle user dropdown commands
function handleUserCommand(command: string): void {
  if (command === 'logout') {
    authStore.logout()
  }
}
</script>

<style scoped>
.sidebar-nav {
  display: flex;
  flex-direction: column;
  height: 100%;
  background-color: #0c0e14;
  color: #e2e5f0;
  width: 220px;
  transition: width 0.3s ease;
}

/* Collapsed state */
.sidebar-nav.collapsed {
  width: 64px;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px;
  border-bottom: 1px solid #252838;
  min-height: 64px;
}

.logo-icon {
  font-size: 24px;
  flex-shrink: 0;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
  white-space: nowrap;
  overflow: hidden;
}

/* Toggle button */
.toggle-btn {
  margin-left: auto;
  background: transparent;
  border: none;
  color: #7c8098;
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.toggle-btn:hover {
  color: #e2e5f0;
  background-color: #1c1f2b;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 10px 0;
}

.nav-section {
  margin-bottom: 8px;
}

.section-title {
  padding: 8px 20px 4px;
  font-size: 11px;
  font-weight: 600;
  color: #7c8098;
  text-transform: uppercase;
  letter-spacing: 0.5px;
  white-space: nowrap;
  overflow: hidden;
}

.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  cursor: pointer;
  transition: background-color 0.2s;
  color: #e2e5f0;
}

.nav-item:hover {
  background-color: #1c1f2b;
}

.nav-item.active {
  background-color: #1c1f2b;
  color: #4f8ff7;
}

.nav-item.plugin-title {
  font-size: 11px;
  font-weight: 500;
  color: #7c8098;
  padding: 6px 20px;
  cursor: default;
}

.nav-item.plugin-title:hover {
  background-color: transparent;
}

/* Nav item content wrapper */
.nav-item-content {
  display: flex;
  align-items: center;
  gap: 12px;
  width: 100%;
}

.nav-icon {
  font-size: 18px;
  flex-shrink: 0;
}

.nav-label {
  flex: 1;
  font-size: 14px;
  white-space: nowrap;
  overflow: hidden;
}

.nav-badge {
  background-color: #4f8ff7;
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
}

/* Collapsed state adjustments */
.sidebar-nav.collapsed .sidebar-logo {
  flex-direction: column;
  padding: 12px 8px;
  gap: 8px;
}

.sidebar-nav.collapsed .toggle-btn {
  margin-left: 0;
  width: 100%;
}

.sidebar-nav.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
}

.sidebar-nav.collapsed .nav-item-content {
  justify-content: center;
}

.sidebar-nav.collapsed .nav-label,
.sidebar-nav.collapsed .nav-badge {
  display: none;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid #252838;
  background-color: #0c0e14;
}

.target-selector {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: #151821;
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 8px;
  transition: background-color 0.2s;
}

.target-selector:hover {
  background-color: #1c1f2b;
}

.target-indicator {
  font-size: 12px;
  flex-shrink: 0;
}

.target-name {
  font-size: 13px;
  color: #e2e5f0;
  white-space: nowrap;
  overflow: hidden;
}

/* Collapsed footer */
.sidebar-nav.collapsed .sidebar-footer {
  padding: 12px 8px;
}

.sidebar-nav.collapsed .target-selector {
  justify-content: center;
  padding: 8px;
}

.sidebar-nav.collapsed .target-name {
  display: none;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background-color: #151821;
  border-radius: 8px;
}

.user-icon {
  font-size: 16px;
  color: #7c8098;
  flex-shrink: 0;
}

.user-name {
  flex: 1;
  font-size: 13px;
  color: #e2e5f0;
  white-space: nowrap;
  overflow: hidden;
}

.user-menu-trigger {
  cursor: pointer;
  padding: 4px;
  color: #7c8098;
  transition: color 0.2s;
}

.user-menu-trigger:hover {
  color: #e2e5f0;
}

/* Collapsed user info */
.sidebar-nav.collapsed .user-info {
  justify-content: center;
  padding: 8px;
}

.sidebar-nav.collapsed .user-name {
  display: none;
}

/* Responsive: Mobile overlay sidebar */
@media (max-width: 767px) {
  .sidebar-nav {
    position: fixed;
    left: 0;
    top: 0;
    height: 100vh;
    z-index: 1000;
    transform: translateX(-100%);
    width: 220px !important;
  }

  .sidebar-nav:not(.collapsed) {
    transform: translateX(0);
  }

  /* On mobile, collapsed means hidden */
  .sidebar-nav.collapsed {
    transform: translateX(-100%);
  }
}
</style>
