/**
 * Vocabulary Type Definitions — Mode App
 *
 * Centralizes the mapping of technical terms (container, stack, target, etc.)
 * to user-facing "Mode App" vocabulary. Used by useAppVocabulary composable.
 *
 * @see docs/general_specs/11b-workload-families-and-adapters.md
 */

/** Technical terms that can be translated to Mode App vocabulary */
export type TechnicalTerm =
  | 'container'
  | 'stack'
  | 'target'
  | 'compose'
  | 'image'
  | 'volume'
  | 'network'
  | 'deployment'

/** A single vocabulary mapping entry */
export interface AppVocabularyTerm {
  /** The technical term (e.g. "container") */
  technical: TechnicalTerm
  /** The Mode App display term (e.g. "app"), or empty string if hidden */
  app: string
  /** Whether this term should be visible in Mode App UI */
  visible: boolean
}

/** Status mapping from technical Docker status to Mode App label + color */
export interface AppStatusMapping {
  /** Technical Docker status string */
  technical: string
  /** User-facing Mode App status label */
  app: string
  /** Element Plus color token for status badge */
  color: string
}

/** Action mapping from technical action to Mode App label + icon */
export interface AppActionMapping {
  /** Technical action identifier */
  technical: string
  /** User-facing Mode App action label */
  app: string
  /** Element Plus / icon name for the action */
  icon: string
}

/** Terms that are hidden (never displayed) in Mode App */
export const HIDDEN_TERMS: TechnicalTerm[] = [
  'compose',
  'image',
  'volume',
  'network',
  'deployment',
]

/** Complete vocabulary mapping table */
export const VOCABULARY_MAP: Record<TechnicalTerm, AppVocabularyTerm> = {
  container: { technical: 'container', app: 'app', visible: true },
  stack: { technical: 'stack', app: 'app', visible: true },
  target: { technical: 'target', app: 'serveur', visible: true },
  compose: { technical: 'compose', app: '', visible: false },
  image: { technical: 'image', app: '', visible: false },
  volume: { technical: 'volume', app: '', visible: false },
  network: { technical: 'network', app: '', visible: false },
  deployment: { technical: 'deployment', app: '', visible: false },
}

/** Status mapping: technical Docker status → Mode App label + color */
export const APP_STATUS_MAP: AppStatusMapping[] = [
  { technical: 'running', app: 'En cours', color: 'success' },
  { technical: 'stopped', app: 'Arrêté', color: 'danger' },
  { technical: 'paused', app: 'En pause', color: 'warning' },
  { technical: 'restarting', app: 'Redémarrage', color: 'warning' },
  { technical: 'created', app: 'Créé', color: 'info' },
  { technical: 'exited', app: 'Terminé', color: 'info' },
  { technical: 'dead', app: 'Erreur', color: 'danger' },
]

/** Canonical Mode App actions (from spec 11b — Action Bar Apps) */
export const APP_ACTIONS: AppActionMapping[] = [
  { technical: 'open', app: 'Ouvrir', icon: 'Link' },
  { technical: 'lifecycle', app: 'Lifecycle', icon: 'VideoPlay' },
  { technical: 'logs', app: 'Logs', icon: 'Document' },
  { technical: 'console', app: 'Console', icon: 'Monitor' },
  { technical: 'config', app: 'Config', icon: 'Setting' },
  { technical: 'restart', app: 'Redémarrer', icon: 'RefreshRight' },
  { technical: 'delete', app: 'Supprimer', icon: 'Delete' },
  { technical: 'details', app: 'Détails techniques', icon: 'InfoFilled' },
]
