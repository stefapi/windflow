/**
 * Context Menu Type Definitions — Mode App
 *
 * Defines the structure of the canonical `[⋯ Plus]` context menu
 * used across the App family (list, dashboard, detail).
 *
 * The menu has 3 ordered sections:
 *   1. Primary actions (Open, Start/Stop, Restart)
 *   2. Tools (Logs, Console, Config)
 *   3. Advanced (Technical details, Delete) — only zone where technical vocabulary leaks in Mode App
 *
 * @see docs/general_specs/11b-workload-families-and-adapters.md §2.4
 */

/** A single item inside a context menu section */
export interface ContextMenuItem {
  /** Action identifier (e.g. 'open', 'start', 'stop', 'restart', 'logs', 'console', 'config', 'details', 'delete') */
  action: string
  /** Display label (translated per mode) */
  label: string
  /** Element Plus icon name */
  icon: string
  /** Whether the item is disabled */
  disabled?: boolean
  /** Whether the item is a dangerous action (red styling) */
  danger?: boolean
  /** Whether the item should be shown (default: true) */
  visible?: boolean
}

/** A section of the context menu (e.g. "Actions principales", "Outils", "Avancé") */
export interface ContextMenuSection {
  /** Section key identifier */
  key: ContextMenuSectionKey
  /** Section title displayed as a non-clickable header */
  label: string
  /** Items in this section */
  items: ContextMenuItem[]
}

/** The 3 canonical section keys, in display order */
export type ContextMenuSectionKey = 'primary' | 'tools' | 'advanced'

/** Props required by AppContextMenu component */
export interface AppContextMenuProps {
  /** Container ID */
  containerId: string
  /** Container display name */
  containerName: string
  /** Container status (running, stopped, paused, etc.) */
  containerStatus: string
  /** Optional domain URL for the "Open" action */
  domain?: string
  /** Optional container labels (for vocabulary detection) */
  labels?: Record<string, string>
  /** Button size */
  size?: 'small' | 'default' | 'large'
}

/** All possible action identifiers for the context menu */
export type ContextMenuAction =
  | 'open'
  | 'start'
  | 'stop'
  | 'restart'
  | 'logs'
  | 'console'
  | 'config'
  | 'details'
  | 'delete'

/** Canonical section keys in display order */
export const CONTEXT_MENU_SECTION_KEYS: ContextMenuSectionKey[] = [
  'primary',
  'tools',
  'advanced',
]

/** Section labels in Mode App (non-technical) */
export const CONTEXT_MENU_SECTION_LABELS_APP: Record<ContextMenuSectionKey, string> = {
  primary: 'Actions',
  tools: 'Outils',
  advanced: 'Avancé',
}

/** Section labels in Mode Infra (technical) */
export const CONTEXT_MENU_SECTION_LABELS_INFRA: Record<ContextMenuSectionKey, string> = {
  primary: 'Actions',
  tools: 'Outils',
  advanced: 'Avancé',
}

/** Icon mapping for each context menu action */
export const CONTEXT_MENU_ACTION_ICONS: Record<ContextMenuAction, string> = {
  open: 'Link',
  start: 'VideoPlay',
  stop: 'VideoPause',
  restart: 'RefreshRight',
  logs: 'Document',
  console: 'Monitor',
  config: 'Setting',
  details: 'InfoFilled',
  delete: 'Delete',
}

/** Action labels in Mode App (non-technical vocabulary) */
export const CONTEXT_MENU_ACTION_LABELS_APP: Record<ContextMenuAction, string> = {
  open: 'Ouvrir',
  start: 'Démarrer',
  stop: 'Arrêter',
  restart: 'Redémarrer',
  logs: 'Logs',
  console: 'Console',
  config: 'Config',
  details: 'Détails techniques',
  delete: 'Supprimer',
}

/** Action labels in Mode Infra (technical vocabulary) */
export const CONTEXT_MENU_ACTION_LABELS_INFRA: Record<ContextMenuAction, string> = {
  open: 'Ouvrir',
  start: 'Démarrer',
  stop: 'Arrêter',
  restart: 'Redémarrer',
  logs: 'Logs',
  console: 'Console',
  config: 'Configuration',
  details: 'Inspecter le container',
  delete: 'Supprimer le container',
}
