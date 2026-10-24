/**
 * Tests du module ws-reconnect — politique de reconnexion unifiée (STORY-164.3).
 *
 * Source aléatoire injectée → délais déterministes ; aucun timer réel :
 * la machine à états retourne des délais, le consommateur programme.
 */
import { describe, it, expect, vi } from 'vitest'
import {
  AUTH_CLOSE_REASONS,
  WS_RECONNECT_DEFAULTS,
  WS_RECONNECT_PRESETS,
  computeReconnectDelay,
  createReconnectPolicy,
} from '@/services/ws-reconnect'

/** random() = 0.5 → jitter nul (centre de la borne). */
const noJitter = () => 0.5
/** random() = 1 → jitter maximal positif (+ratio × délai). */
const maxJitter = () => 1
/** random() = 0 → jitter maximal négatif (−ratio × délai). */
const minJitter = () => 0

describe('computeReconnectDelay', () => {
  it('suit le backoff exponentiel 1s → 2s → 4s (jitter nul)', () => {
    expect(computeReconnectDelay(0, { random: noJitter })).toBe(1000)
    expect(computeReconnectDelay(1, { random: noJitter })).toBe(2000)
    expect(computeReconnectDelay(2, { random: noJitter })).toBe(4000)
  })

  it('plafonne le délai au maximum (8 s par défaut)', () => {
    expect(computeReconnectDelay(10, { random: noJitter })).toBe(8000)
    expect(computeReconnectDelay(50, { random: noJitter })).toBe(8000)
  })

  it('borne le jitter à ±25 % du délai calculé', () => {
    // attempt 0 → base 1000 ; +25 % = 1250, −25 % = 750
    expect(computeReconnectDelay(0, { random: maxJitter })).toBe(1250)
    expect(computeReconnectDelay(0, { random: minJitter })).toBe(750)
    // attempt 2 → 4000 ; +25 % = 5000, −25 % = 3000
    expect(computeReconnectDelay(2, { random: maxJitter })).toBe(5000)
    expect(computeReconnectDelay(2, { random: minJitter })).toBe(3000)
  })

  it('applique le jitter sur le délai plafonné, pas sur le brut', () => {
    // attempt 10 → brut 1024000, plafonné 8000 ; +25 % = 10000
    expect(computeReconnectDelay(10, { random: maxJitter })).toBe(10000)
  })

  it('respecte les surcharges (base, factor, max, ratio)', () => {
    expect(
      computeReconnectDelay(1, { baseDelayMs: 500, factor: 3, maxDelayMs: 10000, random: noJitter })
    ).toBe(1500)
  })
})

describe('createReconnectPolicy — machine à états', () => {
  it('transitions idle → connecting → open', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    expect(policy.getState()).toBe('idle')

    policy.recordConnecting()
    expect(policy.getState()).toBe('connecting')

    policy.recordOpen()
    expect(policy.getState()).toBe('open')
    expect(policy.getAttempts()).toBe(0)
  })

  it('open ⇄ reconnecting : coupure réseau → délai de retry, retour à open', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.recordConnecting()
    policy.recordOpen()

    const delay = policy.recordClose(1006, 'Abnormal closure')
    expect(delay).toBe(1000)
    expect(policy.getState()).toBe('reconnecting')
    expect(policy.getAttempts()).toBe(1)

    policy.recordConnecting()
    policy.recordOpen()
    expect(policy.getState()).toBe('open')
    expect(policy.getAttempts()).toBe(0)
  })

  it('backoff croissant sur tentatives successives (1s → 2s → 4s)', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.recordConnecting()
    policy.recordOpen()

    expect(policy.recordClose(1006)).toBe(1000)
    expect(policy.recordClose(1006)).toBe(2000)
    expect(policy.recordClose(1006)).toBe(4000)
  })

  it('stop() est idempotent et bloque tout retry ultérieur', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.stop()
    policy.stop() // pas d'erreur

    expect(policy.getState()).toBe('stopped')
    expect(policy.recordClose(1006)).toBeNull()

    policy.recordConnecting() // ignoré, avec warning
    expect(policy.getState()).toBe('stopped')
  })

  it('reset() repart de zéro pour une reconnexion manuelle', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.stop()
    policy.reset()
    expect(policy.getState()).toBe('idle')

    policy.recordConnecting()
    policy.recordOpen()
    expect(policy.getState()).toBe('open')
  })
})

describe('createReconnectPolicy — fermetures sans retry', () => {
  it('1008 (policy violation / auth) → aucun retry, état stopped, onAuthError invoqué', () => {
    const onAuthError = vi.fn()
    const policy = createReconnectPolicy({ random: noJitter, onAuthError })
    policy.recordConnecting()
    policy.recordOpen()

    const delay = policy.recordClose(1008, 'Authentication required')
    expect(delay).toBeNull()
    expect(policy.getState()).toBe('stopped')
    expect(onAuthError).toHaveBeenCalledWith(1008, 'Authentication required')
  })

  it('1003 (unsupported data) → aucun retry', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.recordConnecting()
    policy.recordOpen()
    expect(policy.recordClose(1003, '')).toBeNull()
    expect(policy.getState()).toBe('stopped')
  })

  it('raison d\'auth (« Invalid token ») sans code 1008/1003 → aucun retry', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.recordConnecting()
    policy.recordOpen()
    const delay = policy.recordClose(1000, 'Invalid token')
    expect(delay).toBeNull()
    expect(policy.getState()).toBe('stopped')
  })

  it('toutes les raisons d\'auth historiques sont reconnues', () => {
    for (const reason of AUTH_CLOSE_REASONS) {
      const policy = createReconnectPolicy({ random: noJitter })
      policy.recordConnecting()
      policy.recordOpen()
      expect(policy.recordClose(1000, reason)).toBeNull()
    }
  })

  it('fermetures 1000/1006 → retry autorisé (codes paramétrables)', () => {
    const policy = createReconnectPolicy({ random: noJitter })
    policy.recordConnecting()
    policy.recordOpen()
    expect(policy.recordClose(1000)).toBe(1000)
    expect(policy.getState()).toBe('reconnecting')
  })

  it('paramétrage par canal : canaux dédiés excluent aussi 1000', () => {
    const policy = createReconnectPolicy({ random: noJitter, noRetryCodes: [1008, 1003, 1000] })
    policy.recordConnecting()
    policy.recordOpen()
    expect(policy.recordClose(1000, '')).toBeNull()
    expect(policy.getState()).toBe('stopped')
  })
})

describe('createReconnectPolicy — épuisement et callbacks', () => {
  it('épuisement des tentatives → onExhausted, état stopped', () => {
    const onExhausted = vi.fn()
    const policy = createReconnectPolicy({ random: noJitter, maxAttempts: 2, onExhausted })
    policy.recordConnecting()
    policy.recordOpen()

    expect(policy.recordClose(1006)).toBe(1000) // tentative 1
    expect(policy.recordClose(1006)).toBe(2000) // tentative 2
    const delay = policy.recordClose(1006) // épuisement
    expect(delay).toBeNull()
    expect(policy.getState()).toBe('stopped')
    expect(onExhausted).toHaveBeenCalledTimes(1)
  })

  it('onResubscribe invoqué à CHAQUE ouverture réussie', () => {
    const onResubscribe = vi.fn()
    const policy = createReconnectPolicy({ random: noJitter, onResubscribe })
    policy.recordConnecting()
    policy.recordOpen()
    expect(onResubscribe).toHaveBeenCalledTimes(1)

    policy.recordClose(1006)
    policy.recordConnecting()
    policy.recordOpen()
    expect(onResubscribe).toHaveBeenCalledTimes(2)
  })

  it('onResync invoqué UNIQUEMENT après une coupure (pas à la première ouverture)', () => {
    const onResync = vi.fn()
    const policy = createReconnectPolicy({ random: noJitter, onResync })
    policy.recordConnecting()
    policy.recordOpen() // première connexion → pas de resync
    expect(onResync).not.toHaveBeenCalled()

    policy.recordClose(1006)
    policy.recordConnecting()
    policy.recordOpen() // reconnexion → resync GET
    expect(onResync).toHaveBeenCalledTimes(1)
  })
})

describe('constant centralisées (décision 9)', () => {
  it('presets : canal général 3 tentatives, canal dédié 5', () => {
    expect(WS_RECONNECT_PRESETS.generalChannel.maxAttempts).toBe(3)
    expect(WS_RECONNECT_PRESETS.dedicatedChannel.maxAttempts).toBe(5)
  })

  it('défauts : base 1 s, facteur 2, plafond 8 s, jitter ±25 %, auth 1008/1003', () => {
    expect(WS_RECONNECT_DEFAULTS.baseDelayMs).toBe(1000)
    expect(WS_RECONNECT_DEFAULTS.factor).toBe(2)
    expect(WS_RECONNECT_DEFAULTS.maxDelayMs).toBe(8000)
    expect(WS_RECONNECT_DEFAULTS.jitterRatio).toBe(0.25)
    expect(WS_RECONNECT_DEFAULTS.authCodes).toEqual([1008, 1003])
    expect(WS_RECONNECT_DEFAULTS.noRetryCodes).toEqual([])
  })
})
