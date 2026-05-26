/**
 * useAppContextMenu Composable
 *
 * Generates the 3 canonical sections of the `[⋯ Plus]` context menu
 * based on container status and UI mode (App/Infra).
 *
 * Sections:
 *   1. Primary — Open (if domain), Start/Stop (per status), Restart
 *   2. Tools — Logs, Console, Config
 *   3. Advanced — Technical details, Delete (danger)
 *
 * In Mode App, labels use non-technical vocabulary except in the Advanced section
 * where technical terms are allowed (controlled leak per spec 11b §2.4).
 *
 * @see docs/general_specs/11b-workload-families-and-adapters.md §2.4
 */

import { computed, type ComputedRef } from 'vue'
import { useModeStore } from '@/stores/mode'
import {
  type ContextMenuItem,
  type ContextMenuSection,
  type ContextMenuSectionKey,
  type ContextMenuAction,
  type AppContextMenuProps,
  CONTEXT_MENU_SECTION_LABELS_APP,
  CONTEXT_MENU_SECTION_LABELS_INFRA,
  CONTEXT_MENU_ACTION_ICONS,
  CONTEXT_MENU_ACTION_LABELS_APP,
  CONTEXT_MENU_ACTION_LABELS_INFRA,
} from '@/types/context-menu'

/** Statuses where the container is considered "running" */
const RUNNING_STATUSES = ['running', 'restarting']

/** Statuses where the container is considered "stopped" */
const STOPPED_STATUSES = ['stopped', 'exited', 'dead', 'created']

/**
 * Build the "Primary" section items based on container state.
 */
function buildPrimaryItems(
  containerStatus: string,
  domain: string | undefined,
  isAppMode: boolean,
): ContextMenuItem[] {
  const labels = isAppMode ? CONTEXT_MENU_ACTION_LABELS_APP : CONTEXT_MENU_ACTION_LABELS_INFRA
  const icons = CONTEXT_MENU_ACTION_ICONS
  const items: ContextMenuItem[] = []
  const isRunning = RUNNING_STATUSES.includes(containerStatus.toLowerCase())
  const isStopped = STOPPED_STATUSES.includes(containerStatus.toLowerCase())

  // Open — only if domain is available
  if (domain) {
    items.push({
      action: 'open',
      label: labels.open,
      icon: icons.open,
    })
  }

  // Start — only if stopped
  if (isStopped) {
    items.push({
      action: 'start',
      label: labels.start,
      icon: icons.start,
    })
  }

  // Stop — only if running
  if (isRunning) {
    items.push({
      action: 'stop',
      label: labels.stop,
      icon: icons.stop,
    })
  }

  // Restart — only if running
  if (isRunning) {
    items.push({
      action: 'restart',
      label: labels.restart,
      icon: icons.restart,
    })
  }

  return items
}

/**
 * Build the "Tools" section items (always the same).
 */
function buildToolsItems(isAppMode: boolean): ContextMenuItem[] {
  const labels = isAppMode ? CONTEXT_MENU_ACTION_LABELS_APP : CONTEXT_MENU_ACTION_LABELS_INFRA
  const icons = CONTEXT_MENU_ACTION_ICONS

  return [
    {
      action: 'logs',
      label: labels.logs,
      icon: icons.logs,
    },
    {
      action: 'console',
      label: labels.console,
      icon: icons.console,
    },
    {
      action: 'config',
      label: labels.config,
      icon: icons.config,
    },
  ]
}

/**
 * Build the "Advanced" section items.
 * This is the only section where technical vocabulary is allowed in Mode App.
 */
function buildAdvancedItems(isAppMode: boolean): ContextMenuItem[] {
  const labels = isAppMode ? CONTEXT_MENU_ACTION_LABELS_APP : CONTEXT_MENU_ACTION_LABELS_INFRA
  const icons = CONTEXT_MENU_ACTION_ICONS

  return [
    {
      action: 'details',
      label: labels.details,
      icon: icons.details,
    },
    {
      action: 'delete',
      label: labels.delete,
      icon: icons.delete,
      danger: true,
    },
  ]
}

/**
 * Composable that generates the canonical context menu sections.
 *
 * @param props - Container data needed to build the menu
 * @returns Reactive sections, visibility flag, and action handler factory
 */
export function useAppContextMenu(props: AppContextMenuProps): {
  /** The 3 canonical menu sections, computed reactively */
  sections: ComputedRef<ContextMenuSection[]>
  /** Whether the menu has at least one visible action */
  isMenuVisible: ComputedRef<boolean>
  /** Get a handler function for a given action that emits the appropriate event */
  getActionHandler: (action: string) => () => void
} {
  const modeStore = useModeStore()

  /**
   * Build all 3 sections reactively based on props and mode.
   */
  const sections = computed<ContextMenuSection[]>(() => {
    const isAppMode = modeStore.isAppMode
    const sectionLabels = isAppMode ? CONTEXT_MENU_SECTION_LABELS_APP : CONTEXT_MENU_SECTION_LABELS_INFRA

    const primaryItems = buildPrimaryItems(
      props.containerStatus,
      props.domain,
      isAppMode,
    )
    const toolsItems = buildToolsItems(isAppMode)
    const advancedItems = buildAdvancedItems(isAppMode)

    return [
      {
        key: 'primary' as ContextMenuSectionKey,
        label: sectionLabels.primary,
        items: primaryItems,
      },
      {
        key: 'tools' as ContextMenuSectionKey,
        label: sectionLabels.tools,
        items: toolsItems,
      },
      {
        key: 'advanced' as ContextMenuSectionKey,
        label: sectionLabels.advanced,
        items: advancedItems,
      },
    ]
  })

  /**
   * Whether the menu has at least one visible item across all sections.
   */
  const isMenuVisible = computed<boolean>(() => {
    return sections.value.some(
      (section) => section.items.length > 0,
    )
  })

  /**
   * Create a handler function for a given action.
   * The returned function is a no-op placeholder — the actual emission
   * is handled by the component via the `action` event.
   *
   * This is useful for programmatic usage or testing.
   */
  function getActionHandler(action: string): () => void {
    return () => {
      // The actual action emission is handled by the component's emit.
      // This function serves as a bridge for programmatic usage.
      // eslint-disable-next-line no-console
      console.debug(`[AppContextMenu] Action triggered: ${action} on container ${props.containerId}`)
    }
  }

  return {
    sections,
    isMenuVisible,
    getActionHandler,
  }
}

/**
 * Get the list of all possible context menu actions.
 * Useful for validation or testing.
 */
export function getContextMenuActions(): ContextMenuAction[] {
  return ['open', 'start', 'stop', 'restart', 'logs', 'console', 'config', 'details', 'delete']
}

/**
 * Check if an action is a dangerous action.
 */
export function isDangerousAction(action: string): boolean {
  return action === 'delete'
}
