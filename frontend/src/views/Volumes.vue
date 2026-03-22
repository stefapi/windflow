<template>
  <StubPage
    title="Volumes"
    description="Gestion des volumes Docker pour le stockage persistant de vos conteneurs."
    :icon="FolderOpened"
  />
</template>

<script setup lang="ts">
import StubPage from '@/components/ui/StubPage.vue'
import { FolderOpened } from '@element-plus/icons-vue'
</script>
