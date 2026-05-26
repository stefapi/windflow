/**
 * useSidebarNav Composable
 *
 * Centralizes sidebar navigation items based on the current UI mode (App/Infra).
 * Returns computed NavSection arrays that SidebarNav.vue iterates over.
 *
 * @see docs/general_specs/11b-workload-families-and-adapters.md
 */

import { computed } from 'vue'
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
  DataAnalysis,
  InfoFilled,
} from '@element-plus/icons-vue'
import { useModeStore } from '@/stores/mode'
import type { NavSection } from '@/types/navigation'

/**
 * Navigation items for Mode App (simplified, non-technical vocabulary).
 * Structure: Dashboard → Workloads (Apps, Marketplace, Plugins) → Settings
 */
const appModeSections: NavSection[] = [
  {
    // Dashboard — no section title
    items: [
      { icon: Odometer, label: 'Dashboard', path: '/' },
    ],
  },
  {
    title: 'WORKLOADS',
    items: [
      { icon: Connection, label: 'Apps', path: '/compute' },
      { icon: ShoppingCart, label: 'Marketplace', path: '/marketplace', badge: 'Bientôt' },
      { icon: Grid, label: 'Plugins', path: '/plugins', badge: 'Bientôt' },
    ],
  },
  {
    items: [
      { icon: Setting, label: 'Settings', path: '/settings' },
    ],
  },
]

/**
 * Navigation items for Mode Infra (technical vocabulary, current behavior).
 * Structure: Dashboard → Infrastructure → Storage & Network → Marketplace → Administration
 */
const infraModeSections: NavSection[] = [
  {
    // Dashboard — no section title
    items: [
      { icon: Odometer, label: 'Dashboard', path: '/' },
    ],
  },
  {
    title: 'INFRASTRUCTURE',
    items: [
      { icon: Monitor, label: 'VMs', path: '/vms', badge: 'Bientôt' },
      { icon: Connection, label: 'Stacks', path: '/stacks' },
      { icon: DataAnalysis, label: 'Compute', path: '/compute' },
      { icon: Upload, label: 'Targets', path: '/targets' },
    ],
  },
  {
    title: 'STOCKAGE & RÉSEAU',
    items: [
      { icon: FolderOpened, label: 'Volumes', path: '/volumes', badge: 'Bientôt' },
      { icon: Link, label: 'Networks', path: '/networks', badge: 'Bientôt' },
      { icon: PictureFilled, label: 'Images', path: '/images', badge: 'Bientôt' },
    ],
  },
  {
    title: 'MARKETPLACE',
    items: [
      { icon: ShoppingCart, label: 'Marketplace', path: '/marketplace', badge: 'Bientôt' },
      { icon: Grid, label: 'Plugins', path: '/plugins', badge: 'Bientôt' },
    ],
  },
  {
    title: 'ADMINISTRATION',
    items: [
      { icon: Setting, label: 'Settings', path: '/settings' },
      { icon: InfoFilled, label: 'System Info', path: '/system-info' },
      { icon: DocumentChecked, label: 'Audit', path: '/audit', badge: 'Bientôt' },
    ],
  },
]

/**
 * Composable that provides navigation sections based on the current UI mode.
 */
export function useSidebarNav() {
  const modeStore = useModeStore()

  /**
   * Navigation sections computed from the current mode.
   * Returns appModeSections or infraModeSections.
   */
  const navSections = computed<NavSection[]>(() => {
    return modeStore.isAppMode ? appModeSections : infraModeSections
  })

  /**
   * Shortcut to check if we're in App mode
   */
  const isAppMode = computed(() => modeStore.isAppMode)

  return {
    navSections,
    isAppMode,
  }
}
