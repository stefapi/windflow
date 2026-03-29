<template>
  <nav
    class="sidebar-nav"
    :class="{ collapsed: isCollapsed }"
  >
    <!-- Logo -->
    <div class="sidebar-logo">
      <WindFlowLogo
        size="small"
        :show-text="!isCollapsed"
        variant="auto"
      />
      <!-- Toggle button (desktop only) -->
      <button
        v-if="sidebar.isDesktop.value"
        class="toggle-btn"
        :title="isCollapsed ? 'Déplier la sidebar' : 'Rétracter la sidebar'"
        @click="sidebar.toggle()"
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
                <el-icon class="nav-icon">
                  <component :is="item.icon" />
                </el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Infrastructure Section -->
      <div class="nav-section">
        <div
          v-show="!isCollapsed"
          class="section-title"
        >
          INFRASTRUCTURE
        </div>
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
                <el-icon class="nav-icon">
                  <component :is="item.icon" />
                </el-icon>
                <span class="nav-label">{{ item.label }}</span>
                <span
                  v-if="item.badge"
                  class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl"
                >{{ item.badge }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Storage & Network Section -->
      <div class="nav-section">
        <div
          v-show="!isCollapsed"
          class="section-title"
        >
          STOCKAGE & RÉSEAU
        </div>
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
                <el-icon class="nav-icon">
                  <component :is="item.icon" />
                </el-icon>
                <span class="nav-label">{{ item.label }}</span>
                <span
                  v-if="item.badge"
                  class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl"
                >{{ item.badge }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Marketplace Section -->
      <div class="nav-section">
        <div
          v-show="!isCollapsed"
          class="section-title"
        >
          MARKETPLACE
        </div>
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
                <el-icon class="nav-icon">
                  <component :is="item.icon" />
                </el-icon>
                <span class="nav-label">{{ item.label }}</span>
                <span
                  v-if="item.badge"
                  class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl"
                >{{ item.badge }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Dynamic Plugin Sections -->
      <div
        v-if="pluginNavStore.hasPluginPages"
        class="nav-section plugin-section"
      >
        <div
          v-show="!isCollapsed"
          class="section-title"
        >
          PLUGINS
        </div>
        <ul class="nav-list">
          <li
            v-for="section in pluginNavStore.sections"
            v-show="!isCollapsed"
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
            <el-tooltip
              :content="item.label"
              placement="right"
              :disabled="!isCollapsed"
              :show-after="300"
            >
              <div class="nav-item-content">
                <el-icon class="nav-icon">
                  <component :is="item.icon" />
                </el-icon>
                <span class="nav-label">{{ item.label }}</span>
              </div>
            </el-tooltip>
          </li>
        </ul>
      </div>

      <!-- Administration Section -->
      <div class="nav-section">
        <div
          v-show="!isCollapsed"
          class="section-title"
        >
          ADMINISTRATION
        </div>
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
                <el-icon class="nav-icon">
                  <component :is="item.icon" />
                </el-icon>
                <span class="nav-label">{{ item.label }}</span>
                <span
                  v-if="item.badge"
                  class="bg-[var(--color-accent)] text-white text-[11px] px-1.5 py-0.5 rounded-xl"
                >{{ item.badge }}</span>
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
        <div
          class="target-selector"
          @click="openTargetSelector"
        >
          <span class="target-indicator">{{ targetIndicator }}</span>
          <span
            v-show="!isCollapsed"
            class="target-name"
          >{{ activeTargetName }}</span>
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
          <el-icon class="user-icon">
            <User />
          </el-icon>
          <span
            v-show="!isCollapsed"
            class="user-name"
          >{{ authStore.user?.username || 'Utilisateur' }}</span>
          <el-dropdown
            v-show="!isCollapsed"
            @command="handleUserCommand"
          >
            <span class="user-menu-trigger">
              <el-icon><MoreFilled /></el-icon>
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">
                  Déconnexion
                </el-dropdown-item>
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
import WindFlowLogo from '@/components/WindFlowLogo.vue'
import {
  Odometer,
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
  DataAnalysis,
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
  { icon: Monitor, label: 'VMs', path: '/vms', badge: 'Bientôt' },
  { icon: Connection, label: 'Stacks', path: '/stacks' },
  { icon: DataAnalysis, label: 'Compute', path: '/compute' },
  { icon: Upload, label: 'Targets', path: '/targets' },
]

// Storage & Network section items
const storageNetworkItems: NavItem[] = [
  { icon: FolderOpened, label: 'Volumes', path: '/volumes', badge: 'Bientôt' },
  { icon: Link, label: 'Networks', path: '/networks', badge: 'Bientôt' },
  { icon: PictureFilled, label: 'Images', path: '/images', badge: 'Bientôt' },
]

// Marketplace section items
const marketplaceItems: NavItem[] = [
  { icon: ShoppingCart, label: 'Marketplace', path: '/marketplace', badge: 'Bientôt' },
  { icon: Grid, label: 'Plugins', path: '/plugins', badge: 'Bientôt' },
]

// Administration section items
const administrationItems: NavItem[] = [
  { icon: Setting, label: 'Settings', path: '/settings' },
  { icon: DocumentChecked, label: 'Audit', path: '/audit', badge: 'Bientôt' },
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
  width: 220px;
  height: 100%;
  color: var(--color-text-primary);
  background-color: var(--color-bg-primary);
  transition: width 0.3s ease;
  flex-direction: column;
}

/* Collapsed state */
.sidebar-nav.collapsed {
  width: 64px;
}

.sidebar-logo {
  display: flex;
  align-items: center;
  min-height: 64px;
  padding: 20px;
  gap: 10px;
  border-bottom: 1px solid var(--color-border);
}

/* Toggle button */
.toggle-btn {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 4px;
  margin-left: auto;
  color: var(--color-text-secondary);
  background: transparent;
  border: none;
  border-radius: 4px;
  transition: all 0.2s;
  cursor: pointer;
}

.toggle-btn:hover {
  color: var(--color-text-primary);
  background-color: var(--color-bg-elevated);
}

.sidebar-content {
  overflow: hidden auto;
  padding: 10px 0;
  flex: 1;
}

.nav-section {
  margin-bottom: 8px;
}

.section-title {
  overflow: hidden;
  padding: 8px 20px 4px;
  font-size: 11px;
  white-space: nowrap;
  color: var(--color-text-secondary);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-list {
  padding: 0;
  margin: 0;
  list-style: none;
}

.nav-item {
  display: flex;
  align-items: center;
  padding: 10px 20px;
  color: var(--color-text-primary);
  transition: background-color 0.2s;
  cursor: pointer;
}

.nav-item:hover {
  background-color: var(--color-bg-elevated);
}

.nav-item.active {
  color: var(--color-accent);
  background-color: var(--color-bg-elevated);
}

.nav-item.plugin-title {
  padding: 6px 20px;
  font-size: 11px;
  color: var(--color-text-secondary);
  font-weight: 500;
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
  flex-shrink: 0;
  font-size: 18px;
}

.nav-label {
  overflow: hidden;
  font-size: 14px;
  white-space: nowrap;
  flex: 1;
}

/* Collapsed state adjustments */
.sidebar-nav.collapsed .sidebar-logo {
  flex-direction: column;
  padding: 12px 8px;
  gap: 8px;
}

.sidebar-nav.collapsed .toggle-btn {
  width: 100%;
  margin-left: 0;
}

.sidebar-nav.collapsed .nav-item {
  justify-content: center;
  padding: 10px;
}

.sidebar-nav.collapsed .nav-item-content {
  justify-content: center;
}

.sidebar-nav.collapsed .nav-label {
  display: none;
}

.sidebar-footer {
  padding: 12px 16px;
  border-top: 1px solid var(--color-border);
  background-color: var(--color-bg-primary);
}

.target-selector {
  display: flex;
  align-items: center;
  padding: 8px 12px;
  margin-bottom: 8px;
  background-color: var(--color-bg-secondary);
  border-radius: 8px;
  transition: background-color 0.2s;
  gap: 8px;
  cursor: pointer;
}

.target-selector:hover {
  background-color: var(--color-bg-elevated);
}

.target-indicator {
  flex-shrink: 0;
  font-size: 12px;
}

.target-name {
  overflow: hidden;
  font-size: 13px;
  white-space: nowrap;
  color: var(--color-text-primary);
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
  background-color: var(--color-bg-secondary);
  border-radius: 8px;
}

.user-icon {
  flex-shrink: 0;
  font-size: 16px;
  color: var(--color-text-secondary);
}

.user-name {
  overflow: hidden;
  font-size: 13px;
  white-space: nowrap;
  color: var(--color-text-primary);
  flex: 1;
}

.user-menu-trigger {
  cursor: pointer;
  padding: 4px;
  color: var(--color-text-secondary);
  transition: color 0.2s;
}

.user-menu-trigger:hover {
  color: var(--color-text-primary);
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
@media (width <= 767px) {
  .sidebar-nav {
    position: fixed;
    top: 0;
    left: 0;
    z-index: 1000;
    width: 220px !important;
    height: 100vh;
    transform: translateX(-100%);
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
