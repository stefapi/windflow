<template>
  <nav class="sidebar-nav">
    <!-- Logo -->
    <div class="sidebar-logo">
      <span class="logo-icon">🌀</span>
      <span class="logo-text">WindFlow</span>
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
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
      </div>

      <!-- Infrastructure Section -->
      <div class="nav-section">
        <div class="section-title">INFRASTRUCTURE</div>
        <ul class="nav-list">
          <li
            v-for="item in infrastructureItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
      </div>

      <!-- Storage & Network Section -->
      <div class="nav-section">
        <div class="section-title">STOCKAGE & RÉSEAU</div>
        <ul class="nav-list">
          <li
            v-for="item in storageNetworkItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
      </div>

      <!-- Marketplace Section -->
      <div class="nav-section">
        <div class="section-title">MARKETPLACE</div>
        <ul class="nav-list">
          <li
            v-for="item in marketplaceItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
            <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
          </li>
        </ul>
      </div>

      <!-- Dynamic Plugin Sections -->
      <div v-if="pluginNavStore.hasPluginPages" class="nav-section plugin-section">
        <div class="section-title">PLUGINS</div>
        <ul class="nav-list">
          <li
            v-for="section in pluginNavStore.sections"
            :key="section.pluginId"
            class="nav-item plugin-title"
            disabled
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
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
      </div>

      <!-- Administration Section -->
      <div class="nav-section">
        <div class="section-title">ADMINISTRATION</div>
        <ul class="nav-list">
          <li
            v-for="item in administrationItems"
            :key="item.path"
            class="nav-item"
            :class="{ active: isActive(item.path) }"
            @click="navigate(item.path)"
          >
            <el-icon class="nav-icon"><component :is="item.icon" /></el-icon>
            <span class="nav-label">{{ item.label }}</span>
          </li>
        </ul>
      </div>
    </div>

    <!-- Footer: Target Selector & User -->
    <div class="sidebar-footer">
      <!-- Active Target Selector -->
      <div class="target-selector" @click="openTargetSelector">
        <span class="target-indicator">{{ targetIndicator }}</span>
        <span class="target-name">{{ activeTargetName }}</span>
      </div>

      <!-- User Info -->
      <div class="user-info">
        <el-icon class="user-icon"><User /></el-icon>
        <span class="user-name">{{ authStore.user?.username || 'Utilisateur' }}</span>
        <el-dropdown @command="handleUserCommand">
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
    </div>
  </nav>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useTargetsStore } from '@/stores/targets'
import { usePluginNavStore } from '@/stores/pluginNav'
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
} from '@element-plus/icons-vue'
import type { NavItem, PluginNavItem } from '@/types/navigation'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const targetsStore = useTargetsStore()
const pluginNavStore = usePluginNavStore()

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
}

.sidebar-logo {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 20px;
  border-bottom: 1px solid #252838;
}

.logo-icon {
  font-size: 24px;
}

.logo-text {
  font-size: 18px;
  font-weight: 600;
  color: #fff;
}

.sidebar-content {
  flex: 1;
  overflow-y: auto;
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
}

.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
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

.nav-icon {
  font-size: 18px;
}

.nav-label {
  flex: 1;
  font-size: 14px;
}

.nav-badge {
  background-color: #4f8ff7;
  color: #fff;
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 10px;
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
}

.target-name {
  font-size: 13px;
  color: #e2e5f0;
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
}

.user-name {
  flex: 1;
  font-size: 13px;
  color: #e2e5f0;
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
</style>
