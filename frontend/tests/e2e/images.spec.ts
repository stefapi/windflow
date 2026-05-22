import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'
import {
  mockImagesList,
  mockImagePull,
  mockImageRemove,
  mockCurrentUser,
  mockCatchAllApi,
  DEFAULT_IMAGES,
} from './helpers/api-mocks'
import { EL_MESSAGE_SUCCESS, EL_DIALOG } from './helpers/selectors'

test.describe('Gestion des images Docker', () => {
  test.beforeEach(async ({ page }) => {
    // ⚠️ Catch-all EN PREMIER — les mocks spécifiques (enregistrés après) auront la priorité
    await mockCatchAllApi(page)
    await loginAsAdmin(page)
    await mockCurrentUser(page, {
      id: 'test-admin-id',
      email: 'admin@windflow.local',
      role: 'admin',
      organization_id: 'test-org-id',
    })
    await mockImagesList(page, DEFAULT_IMAGES)
  })

  test('affiche la liste des images avec tags et taille', async ({ page }) => {
    await page.goto('/images')

    // Attend que la table soit rendue
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    // Vérifie les tags
    await expect(page.getByText('nginx:latest')).toBeVisible()
    await expect(page.getByText('redis:7-alpine')).toBeVisible()

    // Vérifie la taille formatée via formatBytes(187_000_000) = 178.3 MB (binaire 1024)
    // et formatBytes(45_000_000) = 42.9 MB
    await expect(page.getByText('178.3 MB')).toBeVisible()
    await expect(page.getByText('42.9 MB')).toBeVisible()

    // Vérifie l'utilisation — "✓ Utilisée (2)" pour inUse:true
    // Scopé dans .el-tag pour éviter le match des options du sélecteur de filtre
    await expect(page.locator('.el-tag__content', { hasText: '✓ Utilisée' })).toBeVisible()
    await expect(page.locator('.el-tag__content', { hasText: 'Non utilisée' })).toBeVisible()
  })

  test('pull une image avec nom et tag', async ({ page }) => {
    await mockImagePull(page, { status: 'Downloaded newer image for nginx:latest' })

    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    // Ouvre le dialog de pull
    await page.getByRole('button', { name: 'Pull image' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Remplit le formulaire via les inputs El Plus dans le dialog
    await page.locator(EL_DIALOG).locator('.el-input__inner, input').first().fill('nginx')
    await page.locator(EL_DIALOG).locator('.el-input__inner, input').nth(1).fill('latest')

    // Soumet
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Pull' }).click()

    // Vérifie le toast de succès (message contient le status retourné par le mock)
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toBeVisible({ timeout: 5000 })
  })

  test('pull une image sans nom affiche une erreur', async ({ page }) => {
    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    await page.getByRole('button', { name: 'Pull image' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Laisse le nom vide et clique Pull
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Pull' }).click()

    // Vérifie le message de validation — handlePull montre ElMessage.warning (pas error)
    await expect(page.locator('.el-message--warning')).toContainText('nom', { timeout: 5000 })
  })

  test('supprime une image avec confirmation', async ({ page }) => {
    const imageId = 'sha256:xyz789uvw012'
    await mockImageRemove(page, imageId, true)

    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    // Trouve le bouton de suppression (danger) dans la table
    const deleteBtn = page.locator('.el-button--danger').first()
    await deleteBtn.click()

    // Confirme le dialog ElMessageBox via le bouton primary (indépendant du texte i18n)
    await page.locator('.el-message-box__btns .el-button--primary').click()

    // Vérifie le toast de succès — handleDelete: ElMessage.success('Image supprimée avec succès')
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('supprimée', { timeout: 5000 })
  })

  test('filtre les images par utilisation used', async ({ page }) => {
    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    // Ouvre le dropdown de filtre et sélectionne l'option
    await page.locator('.el-select').first().click()
    // Attendre que le dropdown soit ouvert — Element Plus utilise .el-select-dropdown__item
    await page.waitForSelector('.el-select-dropdown', { state: 'visible' })
    // Cliquer sur l'item "Utilisées" (class spécifique Element Plus v2)
    await page.locator('.el-select-dropdown__item').filter({ hasText: /^Utilisées$/ }).click()
    await page.waitForTimeout(200)

    // Seule l'image utilisée doit être visible
    await expect(page.getByText('nginx:latest')).toBeVisible()
    await expect(page.getByText('redis:7-alpine')).not.toBeVisible()
  })

  test('filtre les images par utilisation unused', async ({ page }) => {
    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    // Ouvre le dropdown et sélectionne "Non utilisées"
    await page.locator('.el-select').first().click()
    await page.waitForSelector('.el-select-dropdown', { state: 'visible' })
    await page.locator('.el-select-dropdown__item').filter({ hasText: /^Non utilisées$/ }).click()
    await page.waitForTimeout(200)

    // Seule l'image non utilisée doit être visible
    await expect(page.getByText('redis:7-alpine')).toBeVisible()
    await expect(page.getByText('nginx:latest')).not.toBeVisible()
  })

  test('recherche par tag filtre la liste', async ({ page }) => {
    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    const searchInput = page.locator('input[placeholder*="Rechercher"], input[placeholder*="tag"]').first()
    await searchInput.fill('redis')
    await page.waitForTimeout(300)

    await expect(page.getByText('redis:7-alpine')).toBeVisible()
    await expect(page.getByText('nginx:latest')).not.toBeVisible()
  })

  test('recherche par ID filtre la liste', async ({ page }) => {
    await page.goto('/images')
    await expect(page.locator('.el-table')).toBeVisible({ timeout: 10000 })

    const searchInput = page.locator('input[placeholder*="Rechercher"], input[placeholder*="tag"]').first()
    await searchInput.fill('abc123')
    await page.waitForTimeout(300)

    await expect(page.getByText('nginx:latest')).toBeVisible()
    await expect(page.getByText('redis:7-alpine')).not.toBeVisible()
  })
})
