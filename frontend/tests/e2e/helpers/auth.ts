/**
 * Helpers d'authentification pour les tests E2E Playwright
 */

import type { Page } from '@playwright/test'
import { EL_BUTTON_PRIMARY } from './selectors'

export interface UserCredentials {
  username: string
  password: string
}

/** Credentials prédéfinis pour les rôles */
export const CREDENTIALS = {
  admin: { username: 'admin@windflow.local', password: 'admin123' },
  operator: { username: 'operator@windflow.local', password: 'operator123' },
  viewer: { username: 'viewer@windflow.local', password: 'viewer123' },
} as const

/**
 * Génère un JWT dummy valide structurellement pour les tests.
 * Le payload contient un user admin/opérateur.
 */
export function generateDummyJWT(role: 'admin' | 'operator' | 'viewer' = 'admin'): string {
  const header = btoa(JSON.stringify({ alg: 'none', typ: 'JWT' }))
  const payload = btoa(JSON.stringify({
    sub: `test-${role}-id`,
    email: CREDENTIALS[role].username,
    role,
    organization_id: 'test-org-id',
    exp: Math.floor(Date.now() / 1000) + 3600,
  }))
  return `${header}.${payload}.`
}

/**
 * Injecte un token JWT et un objet user dans le localStorage (mode rapide).
 * Le store auth lit `access_token` et `user` au démarrage (initFromStorage).
 */
export async function setAuthToken(page: Page, token: string, role: 'admin' | 'operator' | 'viewer' = 'admin'): Promise<void> {
  const user = {
    id: `test-${role}-id`,
    email: CREDENTIALS[role].username,
    username: CREDENTIALS[role].username,
    role,
    organization_id: 'test-org-id',
    is_superuser: role === 'admin',
    is_active: true,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
  }
  await page.addInitScript((data: { token: string; userStr: string }) => {
    localStorage.setItem('access_token', data.token)
    localStorage.setItem('user', data.userStr)
  }, { token, userStr: JSON.stringify(user) })
}

/**
 * Authentification rapide par injection de token JWT dans le localStorage.
 * À utiliser dans test.beforeEach pour éviter le login via formulaire à chaque test.
 */
export async function loginAsUser(page: Page, creds: UserCredentials): Promise<void> {
  await page.goto('/login')
  await page.waitForSelector('.el-form')

  const inputs = await page.locator('.el-input__inner').all()
  if (inputs.length >= 2) {
    await inputs[0].fill(creds.username)
    await inputs[1].fill(creds.password)
  }

  await page.locator(EL_BUTTON_PRIMARY).first().click()
  await page.waitForURL(/\/(?!login)/, { timeout: 10000 })
}

/**
 * Login rapide en injectant un token JWT admin.
 */
export async function loginAsAdmin(page: Page): Promise<void> {
  const token = generateDummyJWT('admin')
  await setAuthToken(page, token, 'admin')
}

/**
 * Login rapide en injectant un token JWT operator.
 */
export async function loginAsOperator(page: Page): Promise<void> {
  const token = generateDummyJWT('operator')
  await setAuthToken(page, token, 'operator')
}

/**
 * Login rapide en injectant un token JWT viewer.
 */
export async function loginAsViewer(page: Page): Promise<void> {
  const token = generateDummyJWT('viewer')
  await setAuthToken(page, token, 'viewer')
}
