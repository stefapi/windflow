import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'
import {
  mockComputeGlobal,
  mockComputeStats,
  mockStackStart,
  mockStackStop,
  mockStackRedeploy,
  mockStackExport,
  mockStackImport,
  mockTargetsList,
  mockCurrentUser,
  mockStacksList,
  mockCatchAllApi,
  DEFAULT_COMPUTE_STATS,
} from './helpers/api-mocks'
import { EL_MESSAGE_SUCCESS, EL_DIALOG } from './helpers/selectors'

test.describe('Actions de stack + Import/Export', () => {
  const stoppedStack = {
    id: 'stack-002',
    name: 'web-apps',
    technology: 'compose',
    target_id: 'target-001',
    target_name: 'localhost',
    services_total: 2,
    services_running: 0,
    status: 'stopped' as const,
    services: [],
  }

  const runningStack = {
    id: 'stack-001',
    name: 'monitoring',
    technology: 'compose',
    target_id: 'target-001',
    target_name: 'localhost',
    services_total: 3,
    services_running: 3,
    status: 'running' as const,
    services: [
      { id: 'svc-001', name: 'grafana', image: 'grafana/grafana:latest', status: 'running', cpu_percent: 2.5, memory_usage: '120M' },
      { id: 'svc-002', name: 'prometheus', image: 'prom/prometheus:latest', status: 'running', cpu_percent: 5.1, memory_usage: '340M' },
      { id: 'svc-003', name: 'loki', image: 'grafana/loki:latest', status: 'running', cpu_percent: 1.2, memory_usage: '80M' },
    ],
  }

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
    await mockTargetsList(page, [
      { id: 'target-001', name: 'localhost', host: '127.0.0.1' },
    ])
    await mockComputeStats(page, DEFAULT_COMPUTE_STATS)
    await mockComputeGlobal(page, {
      managed_stacks: [runningStack, stoppedStack],
      discovered_items: [],
      standalone_containers: [],
    })
  })

  test('démarre une stack arrêtée', async ({ page }) => {
    await mockStackStart(page, stoppedStack.id, { success: true, message: 'Stack démarrée avec succès' })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    // Expand la section de la stack arrêtée — utilise exact pour éviter la strict mode violation
    await page.locator('.el-collapse-item__header', { hasText: 'web-apps' }).first().click()
    await page.waitForTimeout(300)

    // Scope the button search to the active (expanded) item
    const activeItem = page.locator('.el-collapse-item.is-active')
    const startBtn = activeItem.getByRole('button', { name: 'Démarrer' })
    await expect(startBtn).toBeEnabled()
    await startBtn.click()

    // Confirme le dialog
    await page.locator('.el-message-box__btns .el-button--primary').click()

    // Vérifie le toast de succès
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('démarrée', { timeout: 5000 })
  })

  test('arrête une stack en cours', async ({ page }) => {
    await mockStackStop(page, runningStack.id, { success: true, message: 'Stack arrêtée avec succès' })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    // Expand la section de la stack running
    await page.locator('.el-collapse-item__header', { hasText: 'monitoring' }).first().click()
    await page.waitForTimeout(300)

    // Scope to active item
    const activeItem = page.locator('.el-collapse-item.is-active')
    const stopBtn = activeItem.getByRole('button', { name: 'Arrêter' })
    await expect(stopBtn).toBeEnabled()
    await stopBtn.click()

    // Confirme le dialog
    await page.locator('.el-message-box__btns .el-button--primary').click()

    // Vérifie le toast de succès
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('arrêtée', { timeout: 5000 })
  })

  test('redéploie une stack avec stratégie stop-start', async ({ page }) => {
    await mockStackRedeploy(page, runningStack.id, { success: true, message: 'Stack redéployée avec succès' })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    // Expand la section
    await page.locator('.el-collapse-item__header', { hasText: 'monitoring' }).first().click()
    await page.waitForTimeout(300)

    // Scope to active item
    const activeItem = page.locator('.el-collapse-item.is-active')
    await activeItem.getByRole('button', { name: 'Redéployer' }).click()

    // Le dialog de stratégie s'ouvre
    await expect(page.locator(EL_DIALOG)).toBeVisible()
    await expect(page.getByText('Arrêt puis démarrage')).toBeVisible()

    // Confirme le redéploiement
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Redéployer' }).click()

    // Vérifie le toast de succès
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('redéployée', { timeout: 5000 })
  })

  test('redéploie une stack avec stratégie rolling', async ({ page }) => {
    await mockStackRedeploy(page, runningStack.id, { success: true, message: 'Stack redéployée avec succès' })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.el-collapse-item__header', { hasText: 'monitoring' }).first().click()
    await page.waitForTimeout(300)

    const activeItem = page.locator('.el-collapse-item.is-active')
    await activeItem.getByRole('button', { name: 'Redéployer' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Sélectionne la stratégie rolling
    await page.getByText('Rolling (séquentiel)').click()

    await page.locator(EL_DIALOG).getByRole('button', { name: 'Redéployer' }).click()

    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('redéployée', { timeout: 5000 })
  })

  test('bouton Démarrer désactivé si tous les services running', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.el-collapse-item__header', { hasText: 'monitoring' }).first().click()
    await page.waitForTimeout(300)

    const activeItem = page.locator('.el-collapse-item.is-active')
    const startBtn = activeItem.getByRole('button', { name: 'Démarrer' })
    await expect(startBtn).toBeDisabled()
  })

  test('bouton Arrêter désactivé si tous les services arrêtés', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.el-collapse-item__header', { hasText: 'web-apps' }).first().click()
    await page.waitForTimeout(300)

    const activeItem = page.locator('.el-collapse-item.is-active')
    const stopBtn = activeItem.getByRole('button', { name: 'Arrêter' })
    await expect(stopBtn).toBeDisabled()
  })

  test('exporte une stack en JSON', async ({ page }) => {
    await mockStackExport(page, runningStack.id, {
      version: '1.0',
      stack: {
        name: 'monitoring',
        version: '1.0.0',
        tags: ['observability'],
        template: 'version: "3.8"\nservices:\n  grafana:\n    image: grafana/grafana',
        variables: {},
        license: 'MIT',
        screenshots: [],
      },
    })
    await mockStacksList(page, [
      { id: runningStack.id, name: runningStack.name, status: 'running' },
    ])

    await page.goto('/stacks')
    // Attend que la table soit chargée
    await expect(page.getByText('monitoring', { exact: true })).toBeVisible({ timeout: 10000 })

    // Attend le téléchargement et clique sur le bouton export (icône cercle dans ActionButtons)
    const downloadPromise = page.waitForEvent('download', { timeout: 10000 })
    await page.locator('.action-buttons__btn--export').first().click()

    // Vérifie que le téléchargement est déclenché
    const download = await downloadPromise
    expect(download.suggestedFilename()).toContain('monitoring')
  })

  test('importe une stack depuis un fichier JSON valide', async ({ page }) => {
    await mockStackImport(page, { message: 'Stack imported', stack_id: 'stack-imported-001', name: 'imported-stack' })
    await mockStacksList(page, [
      { id: 'stack-imported-001', name: 'imported-stack', status: 'draft' },
    ])

    await page.goto('/stacks')
    await expect(page.locator('.el-card')).toBeVisible({ timeout: 10000 })

    // Ouvre le dialog d'import
    await page.getByRole('button', { name: 'Import' }).click()

    // Upload un fichier JSON
    const fileContent = JSON.stringify({
      version: '1.0',
      stack: {
        name: 'imported-stack',
        template: 'version: "3.8"\nservices:\n  web:\n    image: nginx',
        tags: [],
        variables: {},
        license: 'MIT',
        screenshots: [],
      },
    })
    const buffer = Buffer.from(fileContent)
    await page.locator('input[type="file"]').setInputFiles({
      name: 'stack.json',
      mimeType: 'application/json',
      buffer,
    })

    // Clique sur Import
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Import' }).click()

    // Vérifie le toast de succès
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('imported', { timeout: 5000 })

    // Vérifie que la nouvelle stack apparaît
    await expect(page.getByText('imported-stack')).toBeVisible()
  })

  test('importe une stack avec un JSON invalide', async ({ page }) => {
    await page.goto('/stacks')
    await expect(page.locator('.el-card')).toBeVisible({ timeout: 10000 })

    await page.getByRole('button', { name: 'Import' }).click()

    // Upload un fichier JSON invalide
    const fileContent = JSON.stringify({ invalid: true })
    const buffer = Buffer.from(fileContent)
    await page.locator('input[type="file"]').setInputFiles({
      name: 'invalid.json',
      mimeType: 'application/json',
      buffer,
    })

    // L'erreur doit s'afficher dans le dialog
    await expect(page.getByText('Invalid format')).toBeVisible()
  })
})
