/**
 * useAppVocabulary Composable
 *
 * Centralizes the translation of technical terms (container, stack, target, etc.)
 * into user-facing "Mode App" vocabulary. This is the foundation composable used
 * by all components of EPIC-010 to ensure consistent terminology.
 *
 * In the future "Mode Infra", simply not applying this vocabulary will restore
 * the technical terms.
 *
 * @see docs/general_specs/11b-workload-families-and-adapters.md
 */

import {
  VOCABULARY_MAP,
  APP_STATUS_MAP,
  APP_ACTIONS,
  HIDDEN_TERMS,
  type TechnicalTerm,
  type AppStatusMapping,
  type AppActionMapping,
} from '@/types/vocabulary'

/**
 * Translate a single technical term to its Mode App equivalent.
 * Returns empty string for hidden terms.
 */
export function translateTerm(technicalTerm: TechnicalTerm): string {
  const entry = VOCABULARY_MAP[technicalTerm]
  if (!entry) return ''
  return entry.visible ? entry.app : ''
}

/**
 * Replace all technical terms in a label string with their Mode App equivalents.
 * Hidden terms are removed from the label.
 *
 * @example translateLabel("Container Status") → "Statut de l'app"
 * @example translateLabel("Container network") → "App "
 */
export function translateLabel(label: string): string {
  let result = label

  // Sort terms by length descending to avoid partial replacements
  const terms = Object.keys(VOCABULARY_MAP) as TechnicalTerm[]
  const sortedTerms = [...terms].sort((a, b) => b.length - a.length)

  for (const term of sortedTerms) {
    const entry = VOCABULARY_MAP[term]
    const regex = new RegExp(term, 'gi')
    result = result.replace(regex, (match: string) => {
      if (!entry.visible) return ''
      // Preserve the case of the original term
      const firstChar = match.charAt(0)
      if (firstChar === firstChar.toUpperCase()) {
        return entry.app.charAt(0).toUpperCase() + entry.app.slice(1)
      }
      return entry.app
    })
  }

  return result
}

/**
 * Get the Mode App status mapping for a technical Docker status.
 * Falls back to the technical status with 'info' color if not found.
 */
export function getAppStatus(technicalStatus: string): AppStatusMapping {
  const mapping = APP_STATUS_MAP.find(
    (s) => s.technical.toLowerCase() === technicalStatus.toLowerCase()
  )

  if (mapping) return mapping

  return {
    technical: technicalStatus,
    app: technicalStatus,
    color: 'info',
  }
}

/**
 * Get the list of canonical Mode App actions.
 */
export function getAppActions(): AppActionMapping[] {
  return APP_ACTIONS
}

/**
 * Get the display name for an app from container data.
 * Priority: com.docker.compose.service label > org.windflow.app.name label >
 * cleaned container name.
 */
export function getAppDisplayName(container: {
  name?: string
  labels?: Record<string, string>
}): string {
  // Priority 1: Docker Compose service label
  if (container.labels?.['com.docker.compose.service']) {
    return container.labels['com.docker.compose.service']
  }

  // Priority 2: WindFlow app name label
  if (container.labels?.['org.windflow.app.name']) {
    return container.labels['org.windflow.app.name']
  }

  // Fallback: clean container name (remove leading slash and numeric prefixes)
  if (container.name) {
    return container.name.replace(/^\//, '').replace(/^[a-f0-9]{2,}-/, '')
  }

  return 'Inconnu'
}

/**
 * Check if a technical term is hidden in Mode App.
 */
export function isHiddenTerm(term: TechnicalTerm): boolean {
  return HIDDEN_TERMS.includes(term)
}

/**
 * Composable for Mode App vocabulary translation.
 * Exposes all translation functions for use in <script setup>.
 */
export function useAppVocabulary() {
  return {
    translateTerm,
    translateLabel,
    getAppStatus,
    getAppActions,
    getAppDisplayName,
    isHiddenTerm,
  }
}
