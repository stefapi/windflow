/**
 * useRelativeTime Composable
 *
 * Formats dates as relative time strings (e.g., "il y a 2h", "il y a 5 min")
 * Used for displaying timestamps in a user-friendly way.
 */

import { computed, ref, onMounted, onUnmounted } from 'vue'

/**
 * Format a date as relative time string
 * @param date - Date string or Date object
 * @returns Relative time string in French (e.g., "il y a 2h", "il y a 5 min")
 */
export function formatRelativeTime(date: string | Date | null | undefined): string {
  if (!date) return ''

  const now = new Date()
  const targetDate = typeof date === 'string' ? new Date(date) : date
  const diffMs = now.getTime() - targetDate.getTime()

  // Future dates
  if (diffMs < 0) {
    return 'à l\'instant'
  }

  const diffSeconds = Math.floor(diffMs / 1000)
  const diffMinutes = Math.floor(diffSeconds / 60)
  const diffHours = Math.floor(diffMinutes / 60)
  const diffDays = Math.floor(diffHours / 24)
  const diffWeeks = Math.floor(diffDays / 7)
  const diffMonths = Math.floor(diffDays / 30)
  const diffYears = Math.floor(diffDays / 365)

  if (diffSeconds < 60) {
    return 'à l\'instant'
  } else if (diffMinutes < 60) {
    return `il y a ${diffMinutes} min`
  } else if (diffHours < 24) {
    return `il y a ${diffHours}h`
  } else if (diffDays < 7) {
    return `il y a ${diffDays}j`
  } else if (diffWeeks < 4) {
    return `il y a ${diffWeeks} sem.`
  } else if (diffMonths < 12) {
    return `il y a ${diffMonths} mois`
  } else {
    return `il y a ${diffYears} an${diffYears > 1 ? 's' : ''}`
  }
}

/**
 * Composable for reactive relative time formatting
 * Automatically updates the formatted string every minute
 * @param dateRef - Ref containing the date string or Date object
 * @returns Computed ref with the formatted relative time
 */
export function useRelativeTime(dateRef: Ref<string | Date | null | undefined>) {
  // Force re-computation every minute
  const ticker = ref(0)
  let interval: number | null = null

  onMounted(() => {
    interval = window.setInterval(() => {
      ticker.value++
    }, 60000) // Update every minute
  })

  onUnmounted(() => {
    if (interval) {
      window.clearInterval(interval)
    }
  })

  return computed(() => {
    // Include ticker in dependency to trigger updates
    void ticker.value
    return formatRelativeTime(dateRef.value)
  })
}

// Type for Vue Ref
type Ref<T> = import('vue').Ref<T>
