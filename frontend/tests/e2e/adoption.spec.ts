import { test, expect } from '@playwright/test'
import { loginAsAdmin } from './helpers/auth'
import {
  mockComputeGlobal,
  mockComputeStats,
  mockAdoptionData,
  mockAdoptPost,
  mockTargetsList,
  mockCurrentUser,
  mockCatchAllApi,
  DEFAULT_COMPUTE_STATS,
} from './helpers/api-mocks'
import { EL_DIALOG, EL_MESSAGE_SUCCESS } from './helpers/selectors'

test.describe('Wizard d\'adoption', () => {
  const adoptableItem = {
    id: 'disc-001',
    name: 'orphan-monitoring',
    type: 'composition' as const,
    technology: 'compose',
    source_path: '/home/user/monitoring/docker-compose.yml',
    target_id: 'target-002',
    target_name: 'vps-ovh',
    services_total: 2,
    services_running: 2,
    detected_at: '2026-05-20T10:00:00Z',
    adoptable: true,
    services: [
      { id: 'dsvc-001', name: 'node-exporter', image: 'prom/node-exporter:latest', status: 'running', cpu_percent: 0.5, memory_usage: '20M' },
      { id: 'dsvc-002', name: 'cadvisor', image: 'gcr.io/cadvisor/cadvisor:latest', status: 'running', cpu_percent: 1.8, memory_usage: '60M' },
    ],
  }

  const nonAdoptableItem = {
    id: 'disc-002',
    name: 'legacy-db',
    type: 'container' as const,
    technology: 'docker',
    target_id: 'target-001',
    target_name: 'localhost',
    services_total: 1,
    services_running: 1,
    detected_at: '2026-05-19T08:00:00Z',
    adoptable: false,
    services: [
      { id: 'dsvc-003', name: 'legacy-db-svc', image: 'mysql:5.7', status: 'running', cpu_percent: 3.2, memory_usage: '450M' },
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
      { id: 'target-002', name: 'vps-ovh', host: '192.168.1.10' },
    ])
    await mockComputeStats(page, DEFAULT_COMPUTE_STATS)
    await mockComputeGlobal(page, {
      managed_stacks: [],
      discovered_items: [adoptableItem, nonAdoptableItem],
      standalone_containers: [],
    })
  })

  test('ouvre le wizard depuis un item découvert', async ({ page }) => {
    await mockAdoptionData(page, adoptableItem.id, 'composition')

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    // Cliquer sur le bouton "↗ Adopter" dans la section discovered (dans le header du collapse)
    await page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' }).click()

    // Le dialog du wizard s'ouvre
    await expect(page.locator(EL_DIALOG)).toBeVisible()
    await expect(page.locator('.el-dialog__title')).toContainText('orphan-monitoring')
  })

  test('affiche l\'inventaire des services à l\'étape 1', async ({ page }) => {
    await mockAdoptionData(page, adoptableItem.id, 'composition')

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Vérifie la table des services — scopé dans le dialog pour éviter les matches extérieurs
    const dialog = page.locator(EL_DIALOG)
    await expect(dialog.getByText('node-exporter', { exact: true }).first()).toBeVisible()
    await expect(dialog.getByText('cadvisor', { exact: true }).first()).toBeVisible()
    await expect(dialog.getByText('prom/node-exporter:latest').first()).toBeVisible()
  })

  test('passe à l\'étape 2 et pré-remplit le nom', async ({ page }) => {
    await mockAdoptionData(page, adoptableItem.id, 'composition')

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Clique sur Suivant
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()

    // Vérifie l'étape 2 : formulaire avec nom pré-rempli
    const nameInput = page.locator(EL_DIALOG).locator('input').first()
    await expect(nameInput).toHaveValue(/orphan-monitoring/)
  })

  test('passe à l\'étape 3 et affiche le récapitulatif', async ({ page }) => {
    await mockAdoptionData(page, adoptableItem.id, 'composition')

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Étape 1 → 2
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()
    await page.waitForTimeout(200)

    // Étape 2 → 3
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()
    await page.waitForTimeout(200)

    // Vérifie le récapitulatif — scopé dans le dialog pour éviter les matches extérieurs
    const dialog = page.locator(EL_DIALOG)
    await expect(dialog.getByText('vps-ovh').first()).toBeVisible()
  })

  test('confirme l\'adoption avec succès', async ({ page }) => {
    await mockAdoptionData(page, adoptableItem.id, 'composition')
    await mockAdoptPost(page, { success: true, message: 'Stack adoptée avec succès', stack_id: 'stack-adopted-001' })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Avance jusqu'à l'étape 3
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()
    await page.waitForTimeout(200)
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()
    await page.waitForTimeout(200)

    // Confirme l'adoption (BaseWizard confirm button — el-button--success)
    await page.locator(EL_DIALOG).locator('button[class*="el-button--success"]').click()

    // Vérifie le message de succès
    await expect(page.locator(EL_MESSAGE_SUCCESS)).toContainText('adoptée', { timeout: 5000 })

    // Le BaseWizard reste ouvert avec état "completed" — cliquer Fermer pour clore
    // OU simplement vérifier que le bouton Fermer/close apparaît
    // Le dialog peut rester ouvert, vérifions juste le toast
  })

  test('affiche une erreur si l\'adoption échoue', async ({ page }) => {
    await mockAdoptionData(page, adoptableItem.id, 'composition')
    await mockAdoptPost(page, { success: false, message: 'Erreur lors de l\'adoption' })

    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    await page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' }).click()

    await expect(page.locator(EL_DIALOG)).toBeVisible()

    // Avance jusqu'à l'étape 3
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()
    await page.waitForTimeout(200)
    await page.locator(EL_DIALOG).getByRole('button', { name: 'Suivant' }).click()
    await page.waitForTimeout(200)

    // Confirme l'adoption avec erreur attendue
    await page.locator(EL_DIALOG).locator('button[class*="el-button--success"]').click()

    // Vérifie le message d'erreur — prendre le premier des deux
    await expect(
      page.locator('.el-alert--error').or(page.locator('.el-message--error')).first(),
    ).toBeVisible({ timeout: 5000 })
  })

  test('bouton Adopter masqué si non adoptable', async ({ page }) => {
    await page.goto('/compute')
    await expect(page.locator('.compute-view')).toBeVisible({ timeout: 10000 })

    // Le bouton Adopter est dans le HEADER du collapse (toujours visible sans expansion)
    // Pour l'item non-adoptable (legacy-db), v-if="item.adoptable" = false → bouton absent
    // Vérifier que SEUL l'item orphan-monitoring a un bouton Adopter (1 seul en tout)
    const adoptButtons = page.locator('.discovered-collapse .el-button--primary', { hasText: 'Adopter' })
    await expect(adoptButtons).toHaveCount(1)

    // Vérifier que le bouton Adopter n'est pas dans le collapse header correspondant à legacy-db
    const legacyHeader = page.locator('.el-collapse-item__header', { hasText: 'legacy-db' }).first()
    await expect(legacyHeader.locator('.el-button--primary', { hasText: 'Adopter' })).not.toBeVisible()
  })
})
