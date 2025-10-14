<template>
  <el-container class="main-layout">
    <el-aside width="200px">
      <div class="logo">
        <h2>WindFlow</h2>
      </div>
      <el-menu
        :default-active="activeMenu"
        router
        class="el-menu-vertical"
      >
        <el-menu-item index="/">
          <el-icon><Odometer /></el-icon>
          <span>Dashboard</span>
        </el-menu-item>
        <el-menu-item index="/targets">
          <el-icon><Monitor /></el-icon>
          <span>Targets</span>
        </el-menu-item>
        <el-menu-item index="/stacks">
          <el-icon><Box /></el-icon>
          <span>Stacks</span>
        </el-menu-item>
        <el-menu-item index="/deployments">
          <el-icon><Upload /></el-icon>
          <span>Deployments</span>
        </el-menu-item>
        <el-menu-item index="/workflows">
          <el-icon><Connection /></el-icon>
          <span>Workflows</span>
        </el-menu-item>
        <el-menu-item index="/marketplace">
          <el-icon><Shop /></el-icon>
          <span>Marketplace</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <div class="header-left">
          <h3>{{ pageTitle }}</h3>
        </div>
        <div class="header-right">
          <el-dropdown @command="handleCommand">
            <span class="user-dropdown">
              <el-icon><User /></el-icon>
              {{ authStore.user?.username }}
            </span>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item command="logout">Logout</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import {
  Odometer,
  Monitor,
  Box,
  Upload,
  Connection,
  Shop,
  User
} from '@element-plus/icons-vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const activeMenu = computed(() => route.path)

const pageTitle = computed(() => {
  const name = route.name?.toString() || 'Dashboard'
  return name
})

const handleCommand = async (command: string) => {
  if (command === 'logout') {
    await authStore.logout()
    router.push('/login')
  }
}
</script>

<style scoped>
.main-layout {
  height: 100vh;
}

.logo {
  padding: 20px;
  text-align: center;
  background-color: #001529;
  color: white;
}

.logo h2 {
  margin: 0;
  color: white;
}

.el-aside {
  background-color: #001529;
}

.el-menu-vertical {
  border-right: none;
  background-color: #001529;
}

.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background-color: #fff;
  border-bottom: 1px solid #e8e8e8;
  padding: 0 20px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 20px;
}

.user-dropdown {
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 8px;
}

.el-main {
  background-color: #f0f2f5;
  padding: 20px;
}
</style>
