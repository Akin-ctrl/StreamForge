import { expect, test } from '@playwright/test'

import { ensureAuthenticated, expectActionResult, uniqueEntityId } from './helpers/session'

test.describe('deployment composer and repeatable-row regressions', () => {
  test('keeps typed validation and alarm rule values stable, then preflights and saves a paused deployment', async ({
    page,
  }) => {
    const deploymentId = uniqueEntityId('ui-deployment')
    const deploymentName = `UI Deployment ${deploymentId}`

    await ensureAuthenticated(page)
    await page.goto('/create-pipeline')

    await expect(page.getByRole('heading', { name: 'Compose Deployment' })).toBeVisible()

    const assignmentCard = page.locator('article.card').filter({
      has: page.getByRole('heading', { name: 'Gateway Assignment' }),
    })

    await assignmentCard.getByRole('textbox', { name: 'Deployment ID' }).fill(deploymentId)
    await assignmentCard.getByRole('textbox', { name: 'Name', exact: true }).fill(deploymentName)
    await assignmentCard.getByRole('combobox', { name: 'Status' }).selectOption('disabled')

    await page.locator('label.selection-card').filter({ hasText: 'modbus-demo-01' }).getByRole('checkbox').check()
    await page.locator('label.selection-card').filter({ hasText: 'timescaledb-primary' }).getByRole('checkbox').check()

    await page.getByRole('button', { name: 'Add Range' }).click()
    const rangeParameter = page.getByPlaceholder('Parameter').first()
    await rangeParameter.click()
    await rangeParameter.pressSequentially('temperature')
    await expect(rangeParameter).toHaveValue('temperature')
    await page.getByPlaceholder('Min').fill('-20')
    await page.getByPlaceholder('Max').fill('150')

    await page.getByRole('button', { name: 'Add Alarm' }).click()
    const alarmParameter = page.getByPlaceholder('Parameter').nth(1)
    await alarmParameter.click()
    await alarmParameter.pressSequentially('temperature')
    await expect(alarmParameter).toHaveValue('temperature')

    const alarmType = page.getByPlaceholder('Alarm type')
    await alarmType.click()
    await alarmType.pressSequentially('temperature_high')
    await expect(alarmType).toHaveValue('temperature_high')
    await page.getByPlaceholder('Threshold').fill('100')

    await page.getByRole('button', { name: 'Preflight Deployment' }).click()
    const preflightPanel = await expectActionResult(page, 'Deployment Preflight')
    await expect(preflightPanel).toContainText('Passed')
    await expect(preflightPanel).toContainText('Deployment is structurally ready to save and apply.')

    await page.getByRole('button', { name: 'Create Deployment' }).click()
    await expect(page).toHaveURL(/\/pipelines$/)
    await expect(page.locator('tr').filter({ hasText: deploymentId })).toContainText('disabled')
  })

  test('preserves typed MQTT subscription and mapping values', async ({ page }) => {
    await ensureAuthenticated(page)
    await page.goto('/adapters')

    await expect(page.getByRole('heading', { name: 'Adapters' })).toBeVisible()
    await page.getByLabel('Type', { exact: true }).selectOption('mqtt')

    await page.getByRole('button', { name: 'Add Subscription' }).click()
    const topicFilter = page.getByPlaceholder('Topic filter')
    await topicFilter.click()
    await topicFilter.pressSequentially('factory/line-1/telemetry')
    await expect(topicFilter).toHaveValue('factory/line-1/telemetry')

    const jsonField = page.getByPlaceholder('JSON field')
    await jsonField.click()
    await jsonField.pressSequentially('temperature')
    await expect(jsonField).toHaveValue('temperature')

    const parameterField = page.getByPlaceholder('Parameter')
    await parameterField.click()
    await parameterField.pressSequentially('temperature')
    await expect(parameterField).toHaveValue('temperature')
  })

  test('preserves typed OPC UA monitored item values', async ({ page }) => {
    await ensureAuthenticated(page)
    await page.goto('/adapters')

    await expect(page.getByRole('heading', { name: 'Adapters' })).toBeVisible()
    await page.getByLabel('Type', { exact: true }).selectOption('opcua')

    await page.getByRole('button', { name: 'Add Item' }).click()
    const nodeId = page.getByPlaceholder('Node ID')
    await nodeId.click()
    await nodeId.pressSequentially('ns=2;s=Machine/Temperature')
    await expect(nodeId).toHaveValue('ns=2;s=Machine/Temperature')

    const parameter = page.getByPlaceholder('Parameter')
    await parameter.click()
    await parameter.pressSequentially('temperature')
    await expect(parameter).toHaveValue('temperature')
  })
})
