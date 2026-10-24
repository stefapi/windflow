/**
 * ws-reconnect — politique de reconnexion WebSocket unifiée (STORY-164.3).
 *
 * Un seul algorithme partagé par le service du canal général
 * (`services/websocket.ts`) et les composables dédiés
 * (`useContainerLogs`, `useContainerStats`, …) :
 *
 * - backoff exponentiel (base × factor^n) **plafonné** à `maxDelayMs` ;
 * - **jitter borné** (± `jitterRatio` du délai calculé) pour éviter les
 *   tempêtes de reconnexion — source aléatoire **injectable** pour des tests
 *   déterministes ;
 * - **aucun retry** sur les fermetures d'authentification (codes 1008/1003 ou
 *   raison d'auth) → état `stopped` immédiat (généralisation du comportement
 *   historiquement correct du canal général) ;
 * - **re-souscription automatique** (callback `onResubscribe` à chaque
 *   ouverture) et **resynchronisation d'état** (callback `onResync` après une
 *   coupure) — le consommateur refait un `GET` de la ressource suivie.
 *
 * Le contrôleur ne possède ni WebSocket ni timers : le consommateur ouvre la
 * connexion, appelle `recordConnecting()` / `recordOpen()` / `recordClose()`
 * et programme lui-même le `setTimeout` avec le délai retourné.
 *
 * Contrat serveur associé (STORY-164.1) : le serveur expire une connexion
 * muette au bout de ~2 intervalles de heartbeat (`ws_heartbeat_*`) et
 * re-diffuse les messages critiques non acquittés (TTL `ws_ack_ttl_seconds`).
 */

export type ReconnectState = 'idle' | 'connecting' | 'open' | 'reconnecting' | 'stopped'

export interface ReconnectPolicyOptions {
  /** Nombre maximal de tentatives de reconnexion avant `onExhausted`. */
  maxAttempts?: number
  /** Délai de la première tentative (ms). */
  baseDelayMs?: number
  /** Facteur multiplicatif du backoff exponentiel. */
  factor?: number
  /** Plafond du délai calculé (ms), appliqué avant le jitter. */
  maxDelayMs?: number
  /** Borne du jitter : ± `jitterRatio` × délai calculé (ex. 0.25 = ±25 %). */
  jitterRatio?: number
  /** Source aléatoire injectable (tests déterministes). Défaut : `Math.random`. */
  random?: () => number
  /** Codes de fermeture d'authentification → stop + `onAuthError`. Défaut : 1008, 1003. */
  authCodes?: readonly number[]
  /** Fragments de raison d'authentification → stop + `onAuthError`. Défaut : `AUTH_CLOSE_REASONS`. */
  authReasons?: readonly string[]
  /** Codes de fermeture additionnels sans retry (arrêt **silencieux**, ex. 1000 fin de stream). */
  noRetryCodes?: readonly number[]
  /** Invoqué sur fermeture d'authentification (aucun retry). */
  onAuthError?: (code: number, reason: string) => void
  /** Invoqué sur épuisement des tentatives (ex. logout du canal général). */
  onExhausted?: () => void
  /** Invoqué à chaque ouverture réussie (rétablir les abonnements). */
  onResubscribe?: () => void
  /** Invoqué à l'ouverture réussie **après une coupure** (resynchronisation GET). */
  onResync?: () => void
}

export interface ReconnectController {
  /** État courant de la machine à états. */
  getState(): ReconnectState
  /** Nombre de tentatives consommées depuis la dernière ouverture réussie. */
  getAttempts(): number
  /** À appeler au lancement d'une tentative de connexion. */
  recordConnecting(): void
  /** À appeler à l'ouverture réussie de la connexion. */
  recordOpen(): void
  /**
   * À appeler sur fermeture de la connexion.
   * Retourne le délai (ms) à attendre avant la prochaine tentative, ou
   * `null` s'il ne faut PAS retenter (fermeture d'auth, épuisement, arrêt).
   */
  recordClose(code: number, reason?: string): number | null
  /** Arrête définitivement la politique (déconnexion volontaire). Idempotent. */
  stop(): void
  /** Remet à zéro (retour à `idle`) pour une reconnexion manuelle. */
  reset(): void
}

/** Raisons de fermeture synonymes d'échec d'authentification (canal général). */
export const AUTH_CLOSE_REASONS: readonly string[] = [
  'User not found or inactive',
  'Invalid token',
  'Authentication required',
  'Authentication timeout',
]

/** Constantes centralisées de la politique de reconnexion (décision 9). */
export const WS_RECONNECT_DEFAULTS = {
  maxAttempts: 3,
  baseDelayMs: 1000,
  factor: 2,
  maxDelayMs: 8000,
  jitterRatio: 0.25,
  authCodes: [1008, 1003],
  noRetryCodes: [] as readonly number[],
} as const

/** Préréglages par famille de canal. */
export const WS_RECONNECT_PRESETS = {
  /**
   * Canal général : 3 tentatives puis abandon — le service déclenche le
   * logout sur épuisement (comportement historique préservé, arbitrage STORY-164.3).
   */
  generalChannel: { maxAttempts: 3 },
  /** Canaux dédiés (logs/stats/…) : tolérance réseau plus longue. */
  dedicatedChannel: { maxAttempts: 5 },
} as const

interface ResolvedReconnectOptions {
  maxAttempts: number
  baseDelayMs: number
  factor: number
  maxDelayMs: number
  jitterRatio: number
  random: () => number
  authCodes: readonly number[]
  authReasons: readonly string[]
  noRetryCodes: readonly number[]
  onAuthError?: (code: number, reason: string) => void
  onExhausted?: () => void
  onResubscribe?: () => void
  onResync?: () => void
}

/**
 * Calcule le délai de reconnexion pour la tentative `attempt` (index 0 = première
 * tentative après une coupure) : `min(base × factor^attempt, maxDelayMs)` puis
 * jitter borné à ± `jitterRatio` du délai plafonné.
 */
export function computeReconnectDelay(
  attempt: number,
  overrides?: Partial<
    Pick<ResolvedReconnectOptions, 'baseDelayMs' | 'factor' | 'maxDelayMs' | 'jitterRatio'> & {
      random: () => number
    }
  >,
): number {
  const opts = { ...WS_RECONNECT_DEFAULTS, random: Math.random, ...overrides }
  const safeAttempt = Math.max(0, Math.floor(attempt))
  const raw = opts.baseDelayMs * Math.pow(opts.factor, safeAttempt)
  const capped = Math.min(raw, opts.maxDelayMs)
  const jitter = capped * opts.jitterRatio * (2 * opts.random() - 1)
  return Math.round(capped + jitter)
}

/**
 * Crée une politique de reconnexion (machine à états + calcul de délai).
 * Voir `ReconnectController` pour le contrat d'usage.
 */
export function createReconnectPolicy(options: ReconnectPolicyOptions = {}): ReconnectController {
  const opts: ResolvedReconnectOptions = {
    ...WS_RECONNECT_DEFAULTS,
    random: Math.random,
    authReasons: AUTH_CLOSE_REASONS,
    ...options,
  }

  let state: ReconnectState = 'idle'
  let attempts = 0
  let hasDropped = false

  /** Fermeture d'authentification : stop + `onAuthError`. */
  function isAuthFailure(code: number, reason: string): boolean {
    return opts.authCodes.includes(code) || opts.authReasons.some((fragment) => reason.includes(fragment))
  }

  return {
    getState: () => state,
    getAttempts: () => attempts,

    recordConnecting() {
      if (state === 'stopped') {
        console.warn('[ws-reconnect] recordConnecting ignoré : politique arrêtée')
        return
      }
      state = 'connecting'
    },

    recordOpen() {
      if (state === 'stopped') {
        console.warn('[ws-reconnect] recordOpen ignoré : politique arrêtée')
        return
      }
      const dropped = hasDropped
      state = 'open'
      attempts = 0
      hasDropped = false
      // Resynchronisation uniquement après une coupure (pas à la première ouverture)
      if (dropped) {
        opts.onResync?.()
      }
      opts.onResubscribe?.()
    },

    recordClose(code: number, reason = ''): number | null {
      if (state === 'stopped') {
        return null
      }

      // Fermeture d'auth (1008/1003 ou raison d'auth) → stop + onAuthError ;
      // codes no-retry additionnels (ex. 1000 fin de stream propre) → stop
      // silencieux, sans callback d'erreur.
      if (isAuthFailure(code, reason) || opts.noRetryCodes.includes(code)) {
        state = 'stopped'
        attempts = 0
        hasDropped = false
        if (isAuthFailure(code, reason)) {
          opts.onAuthError?.(code, reason)
        }
        return null
      }

      if (attempts >= opts.maxAttempts) {
        state = 'stopped'
        attempts = 0
        hasDropped = false
        opts.onExhausted?.()
        return null
      }

      const delay = computeReconnectDelay(attempts, opts)
      attempts++
      hasDropped = true
      state = 'reconnecting'
      return delay
    },

    stop() {
      state = 'stopped'
    },

    reset() {
      state = 'idle'
      attempts = 0
      hasDropped = false
    },
  }
}
