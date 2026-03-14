<template>
  <el-breadcrumb separator="/" class="breadcrumb">
    <el-breadcrumb-item v-for="(item, index) in breadcrumbs" :key="index" :to="item.path ?? undefined">
      {{ item.label }}
    </el-breadcrumb-item>
  </el-breadcrumb>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'

interface BreadcrumbItem {
  label: string
  path?: string
}

// Mapping des noms de routes vers des labels lisibles en français
const routeLabels: Record<string, string> = {
  Dashboard: 'Dashboard',
  Containers: 'Containers',
  VMs: 'Machines Virtuelles',
  Targets: 'Targets',
  Stacks: 'Stacks',
  Deployments: 'Déploiements',
  DeploymentDetail: 'Détail Déploiement',
  Workflows: 'Workflows',
  WorkflowEditor: 'Éditeur Workflow',
  Schedules: 'Planifications',
  Terminal: 'Terminal',
  Volumes: 'Volumes',
  Networks: 'Réseaux',
  Images: 'Images',
  Marketplace: 'Marketplace',
  Plugins: 'Plugins',
  Settings: 'Paramètres',
  Audit: 'Audit',
}

const route = useRoute()

const breadcrumbs = computed<BreadcrumbItem[]>(() => {
  const items: BreadcrumbItem[] = []

  // Toujours commencer par Dashboard
  items.push({ label: 'Dashboard', path: '/' })

  // Si on est sur le dashboard, pas besoin d'aller plus loin
  if (route.path === '/') {
    return items
  }

  // Récupérer le nom de la route actuelle
  const routeName = route.name as string | undefined

  if (routeName && routeLabels[routeName as keyof typeof routeLabels]) {
    const label = routeLabels[routeName as keyof typeof routeLabels] as string
    // Pour les routes avec paramètres (détails), ajouter d'abord la liste parente
    if (isDetailRoute(routeName)) {
      const parentRoute = getParentRoute(routeName)
      if (parentRoute) {
        const parentLabel = routeLabels[parentRoute as keyof typeof routeLabels] as string
        items.push({ label: parentLabel, path: `/${parentRoute.toLowerCase()}` })
      }
      items.push({ label })
    } else {
      items.push({ label, path: route.path })
    }
  } else {
    // Fallback: utiliser les segments du path
    const segments = route.path.split('/').filter(Boolean)
    segments.forEach((segment, index) => {
      const capitalizedSegment = capitalize(segment)
      const label = routeLabels[capitalizedSegment] ?? capitalizedSegment
      const path = index === segments.length - 1 ? undefined : `/${segments.slice(0, index + 1).join('/')}`
      items.push({ label, path })
    })
  }

  return items
})

function isDetailRoute(routeName: string): boolean {
  const detailRoutes = ['DeploymentDetail', 'WorkflowEditor', 'Terminal']
  return detailRoutes.includes(routeName)
}

function getParentRoute(routeName: string): string | null {
  const parents: Record<string, string> = {
    DeploymentDetail: 'Deployments',
    WorkflowEditor: 'Workflows',
    Terminal: 'Containers',
  }
  return parents[routeName] || null
}

function capitalize(str: string): string {
  return str.charAt(0).toUpperCase() + str.slice(1)
}
</script>

<style scoped>
.breadcrumb {
  padding: 12px 0;
  margin-bottom: 16px;
  background-color: transparent;
}
</style>
