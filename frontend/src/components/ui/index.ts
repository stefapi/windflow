/**
 * UI Components - Base Components Library
 *
 * This module exports all base UI components for the WindFlow application.
 * Each component uses design system tokens for consistent styling.
 *
 * @example
 * import { StatusBadge, ResourceBar, ActionButtons, CounterCard } from '@/components/ui'
 */

// Components
export { default as StatusBadge } from './StatusBadge.vue'
export { default as ResourceBar } from './ResourceBar.vue'
export { default as ActionButtons } from './ActionButtons.vue'
export { default as CounterCard } from './CounterCard.vue'

// Types
export type { StatusType, StatusBadgeProps } from './StatusBadge.vue'
export type { ResourceBarProps } from './ResourceBar.vue'
export type { ActionType, ActionConfig, ActionConfigObject, ActionButtonsProps } from './ActionButtons.vue'
export type { CounterCardProps } from './CounterCard.vue'
