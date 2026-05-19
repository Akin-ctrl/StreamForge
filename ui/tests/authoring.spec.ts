import { expect, test } from '@playwright/test'

import { ensureAuthenticated, expectActionResult, uniqueEntityId } from './helpers/session'

test.describe('operator authoring workflows', () => {
  test('validates, tests, and saves a reusable Modbus TCP adapter', async ({ page }) => {
    const adapterId = uniqueEntityId('ui-adapter')
    const adapterName = `UI Adapter ${adapterId}`

    await ensureAuthenticated(page)
    await page.goto('/adapters')

    await expect(page.getByRole('heading', { name: 'Adapters' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create Adapter' })).toBeVisible()

    await page.getByLabel('Adapter ID', { exact: true }).fill(adapterId)
    await page.getByLabel('Name', { exact: true }).fill(adapterName)
    await page.getByLabel('Host', { exact: true }).fill('modbus-simulator')
    await page.getByLabel('Port', { exact: true }).fill('5020')
    await page.getByLabel('Unit ID', { exact: true }).fill('1')
    await page.getByLabel('Default Asset ID', { exact: true }).fill(`${adapterId}-asset`)

    await page.getByRole('button', { name: 'Add Point' }).click()
    const pointName = page.getByPlaceholder('Point name')
    await pointName.click()
    await pointName.pressSequentially('temperature')
    await expect(pointName).toHaveValue('temperature')
    await page.getByPlaceholder('Address').fill('0')
    await page.getByPlaceholder('Unit').fill('celsius')

    await page.getByRole('button', { name: 'Validate' }).click()
    const validationPanel = await expectActionResult(page, 'Adapter Validation')
    await expect(validationPanel).toContainText('Passed')
    await expect(validationPanel).toContainText('Validation passed for the current draft.')

    await page.getByRole('button', { name: 'Test Connection' }).click()
    const connectionPanel = await expectActionResult(page, 'Adapter Connection Test')
    await expect(connectionPanel).toContainText('Passed')
    await expect(connectionPanel).toContainText('Reached modbus-simulator:5020')

    await page.getByRole('button', { name: 'Create Adapter' }).click()
    await expect(page.locator('tr').filter({ hasText: adapterId })).toContainText(adapterName)
  })

  test('validates, tests, saves, and edits a reusable TimescaleDB sink', async ({ page }) => {
    const sinkId = uniqueEntityId('ui-sink')
    const sinkName = `UI Sink ${sinkId}`
    const updatedSinkName = `${sinkName} Updated`

    await ensureAuthenticated(page)
    await page.goto('/sinks')

    await expect(page.getByRole('heading', { name: 'Sinks' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Create Sink' })).toBeVisible()

    await page.getByLabel('Sink ID', { exact: true }).fill(sinkId)
    await page.getByLabel('Name', { exact: true }).fill(sinkName)
    await page.getByRole('textbox', { name: /Database DSN/ }).fill(
      'postgresql://streamforge:streamforge@timescaledb:5432/streamforge',
    )
    await page.getByLabel('Table', { exact: true }).fill(`telemetry_ui_${sinkId.replace(/-/g, '_')}`)

    await page.getByRole('button', { name: 'Validate' }).click()
    const validationPanel = await expectActionResult(page, 'Sink Validation')
    await expect(validationPanel).toContainText('Passed')
    await expect(validationPanel).toContainText('Validation passed for the current draft.')

    await page.getByRole('button', { name: 'Test Connection' }).click()
    const connectionPanel = await expectActionResult(page, 'Sink Connection Test')
    await expect(connectionPanel).toContainText('Passed')
    await expect(connectionPanel).toContainText('TimescaleDB connectivity check succeeded')

    await page.getByRole('button', { name: 'Create Sink' }).click()
    const sinkRow = page.locator('tr').filter({ hasText: sinkId })
    await expect(sinkRow).toContainText(sinkName)

    await sinkRow.getByRole('button', { name: 'Edit' }).click()
    await expect(page.getByRole('heading', { name: 'Edit Saved Sink' })).toBeVisible()
    await expect(page.getByRole('textbox', { name: /Database DSN/ })).toHaveAttribute(
      'placeholder',
      /Leave blank to keep current DSN/,
    )

    await page.getByLabel('Name', { exact: true }).fill(updatedSinkName)
    await page.getByRole('button', { name: 'Update Sink' }).click()
    await expect(page.locator('tr').filter({ hasText: sinkId })).toContainText(updatedSinkName)
  })
})
