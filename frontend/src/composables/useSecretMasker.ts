/**
 * useSecretMasker Composable
 *
 * Provides utilities for masking and revealing sensitive environment variables
 * based on key patterns (PASSWORD, SECRET, KEY, TOKEN, etc.)
 */

import { ref } from 'vue'

// Patterns that indicate a secret/sensitive variable
const SECRET_PATTERNS = [
  /password/i,
  /passwd/i,
  /secret/i,
  /api[_-]?key/i,
  /apikey/i,
  /auth[_-]?key/i,
  /access[_-]?key/i,
  /private[_-]?key/i,
  /token/i,
  /credential/i,
  /jwt/i,
  /session[_-]?key/i,
  /encryption[_-]?key/i,
  /salt/i,
  /hash/i,
]

/**
 * Check if a variable key indicates a secret/sensitive value
 */
export function isSecretKey(key: string): boolean {
  return SECRET_PATTERNS.some(pattern => pattern.test(key))
}

/**
 * Mask a value with asterisks
 */
export function maskValue(value: string): string {
  if (!value || value.length === 0) return ''
  if (value.length <= 4) return '****'
  // Show first 2 and last 2 characters
  return `${value.substring(0, 2)}${'*'.repeat(Math.min(value.length - 4, 10))}${value.substring(value.length - 2)}`
}

/**
 * Parse environment variables from Docker container format
 * Docker returns env as array of "KEY=value" strings
 */
export function parseEnvVars(envArray: string[] | undefined): { key: string; value: string }[] {
  if (!envArray || !Array.isArray(envArray)) return []

  return envArray.map(env => {
    const equalIndex = env.indexOf('=')
    if (equalIndex === -1) {
      return { key: env, value: '' }
    }
    return {
      key: env.substring(0, equalIndex),
      value: env.substring(equalIndex + 1),
    }
  })
}

/**
 * Composable for managing secret masking state
 */
export function useSecretMasker() {
  // Set of keys that are currently revealed
  const revealedKeys = ref<Set<string>>(new Set())

  /**
   * Toggle the reveal state of a secret
   */
  function toggleSecret(key: string): void {
    if (revealedKeys.value.has(key)) {
      revealedKeys.value.delete(key)
    } else {
      revealedKeys.value.add(key)
    }
    // Force reactivity update
    revealedKeys.value = new Set(revealedKeys.value)
  }

  /**
   * Check if a key is currently revealed
   */
  function isRevealed(key: string): boolean {
    return revealedKeys.value.has(key)
  }

  /**
   * Get display value for a variable (masked or not)
   */
  function getDisplayValue(key: string, value: string): string {
    if (!isSecretKey(key)) {
      return value
    }
    if (isRevealed(key)) {
      return value
    }
    return maskValue(value)
  }

  /**
   * Reveal all secrets
   */
  function revealAll(keys: string[]): void {
    keys.forEach(key => revealedKeys.value.add(key))
    revealedKeys.value = new Set(revealedKeys.value)
  }

  /**
   * Hide all secrets
   */
  function hideAll(): void {
    revealedKeys.value = new Set()
  }

  return {
    revealedKeys,
    isSecretKey,
    maskValue,
    toggleSecret,
    isRevealed,
    getDisplayValue,
    revealAll,
    hideAll,
    parseEnvVars,
  }
}

export default useSecretMasker
