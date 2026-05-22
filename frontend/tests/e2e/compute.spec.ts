import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'
import {
  mockComputeStats,
  mockComputeGlobal,
  mockTargetsList,
  mockCurrentUser,
  mockCatchAllApi,
  DEFAULT_COMPUTE_STATS,
  DEFAULT_COMPUTE_GLOBAL,
} from './helpers/api-mocks'

test.describe('Vue Compute', () => {
  test.beforeEach(async ({ page }) => {
    // ⚠️ Catch-all EN PREMIER pour intercepter les appels non mockés
    await mockCatchAllApi(page)
    await loginAsAdmin(page)
    await mockCurrentUser(page, {
      id: 'test-admin-id',
      email: 'admin@windflow.local',
      role: 'admin',
      organization_id: 'test-org-id',
    })
    await mockTargetsList(page, [
      { id: 'target-001', name: 'localhost', host: '127.0.0.1' },
      { id: 'target-002', name: 'vps-ovh', host: '192.168.1.10' },
      { id: 'target-003', name: 'pi4-home', host: '192.168.1.20' },
    ])
    await mockComputeStats(page, DEFAULT_COMPUTE_STATS)
    await mockComputeGlobal(page, DEFAULT_COMPUTE_GLOBAL)
  })

  test('redirige vers /login si non authentifié', async ({ browser }) => {
    const context = await browser.newContext()
    const page = await context.newPage()
    // Mock all API calls to return 401 so auto-login fails too
    await page.route('**/api/**', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      })
    })
    await page.goto('/compute')
    await page.waitForURL(/\/login/, { timeout: 15000 })
    expect(page.url()).toContain('/login')
    await context.close()
  })

  test('affiche le bandeau de stats et les 3 sections', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(1000)

    // Vérifie les 3 sections via leurs headers spécifiques (UPPERCASE, unambiguës)
    await expect(page.locator('.section-header', { hasText: 'STACKS WINDFLOW' })).toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'DISCOVERED' })).toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'STANDALONE' })).toBeVisible()
  })

  test('filtre par type managed', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(1000)

    // Click le bouton radio visible (pas l'input caché) pour déclencher la réactivité Vue
    await page.locator('.el-radio-button__inner', { hasText: 'Stacks WindFlow' }).click()
    await page.waitForTimeout(500)

    // Vérifier via les section-header (texte UPPERCASE unique à chaque section)
    await expect(page.locator('.section-header', { hasText: 'STACKS WINDFLOW' })).toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'DISCOVERED' })).not.toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'STANDALONE' })).not.toBeVisible()
  })

  test('filtre par type discovered', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(1000)

    await page.locator('.el-radio-button__inner', { hasText: 'Discovered' }).click()
    await page.waitForTimeout(500)

    await expect(page.locator('.section-header', { hasText: 'DISCOVERED' })).toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'STACKS WINDFLOW' })).not.toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'STANDALONE' })).not.toBeVisible()
  })

  test('filtre par type standalone', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(1000)

    await page.locator('.el-radio-button__inner', { hasText: 'Standalone' }).click()
    await page.waitForTimeout(500)

    await expect(page.locator('.section-header', { hasText: 'STANDALONE' })).toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'STACKS WINDFLOW' })).not.toBeVisible()
    await expect(page.locator('.section-header', { hasText: 'DISCOVERED' })).not.toBeVisible()
  })

  test('toggle Par machine regroupe par target', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(1000)

    // Click "Par machine" — déclenche fetchGlobalByTarget + mock retourne DEFAULT_TARGET_GROUPS
    await page.getByRole('button', { name: 'Par machine' }).click()

    // Attendre que le TargetGroupView se rende avec le collapse par target
    await expect(page.locator('.target-groups-collapse')).toBeVisible({ timeout: 8000 })

    // Les sections normales doivent avoir disparu (v-if="!groupByTarget")
    await expect(page.locator('.section-header', { hasText: 'STACKS WINDFLOW' })).not.toBeVisible()
  })

  test('recherche filtre avec debounce', async ({ page }) => {
    // Override du mock pour retourner des données filtrées selon la recherche
    await page.route('**/api/v1/compute/global**', async (route) => {
      const url = route.request().url()
      if (url.includes('search=traefik')) {
        // Retourner seulement le container traefik
        const filtered = {
          ...DEFAULT_COMPUTE_GLOBAL,
          standalone_containers: DEFAULT_COMPUTE_GLOBAL.standalone_containers.filter(
            c => c.name.includes('traefik'),
          ),
        }
        await route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(filtered) })
      } else if (!url.includes('group_by=target')) {
        await route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(DEFAULT_COMPUTE_GLOBAL),
        })
      } else {
        await route.continue()
      }
    })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 15000 })
    await page.waitForTimeout(1000)

    const searchInput = page.locator('input[placeholder="Rechercher..."]')
    await searchInput.fill('traefik')
    // Attendre debounce 300ms + délai rendu
    await page.waitForTimeout(600)

    // Après filtrage : traefik visible, pihole non
    await expect(
      page.locator('.el-table__row').filter({ hasText: 'traefik' }).first(),
    ).toBeVisible()
    await expect(page.locator('.el-table__row').filter({ hasText: 'pihole' })).not.toBeVisible()
  })
})
