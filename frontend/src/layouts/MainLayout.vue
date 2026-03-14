<template>
  <el-container class="main-layout">
    <el-aside width="220px" class="sidebar-aside">
      <SidebarNav />
    </el-aside>
    <el-container>
      <el-main class="main-content">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import SidebarNav from '@/components/SidebarNav.vue'
</script>

<style scoped>
.main-layout {
  height: 100vh;
  overflow: hidden;
}

.sidebar-aside {
  background-color: #0c0e14;
  height: 100vh;
  overflow: hidden;
}

.main-content {
  background-color: #f0f2f5;
  padding: 20px;
  overflow-y: auto;
  height: 100vh;
}
</style>
