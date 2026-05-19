import { expect, test } from '@playwright/test'

import { ensureAuthenticated } from './helpers/session'

test.describe('operator views and navigation regressions', () => {
  test('keeps the logs level filter stable through URL sync and refresh', async ({ page }) => {
    await ensureAuthenticated(page)
    await page.goto('/logs')

    await expect(page.getByRole('heading', { name: 'Logs' })).toBeVisible()

    await page.getByLabel('Gateway ID').fill('gateway-demo-01')
    await page.getByLabel('Level').selectOption('ERROR')
    await expect(page).toHaveURL(/gateway=gateway-demo-01/)
    await expect(page).toHaveURL(/level=ERROR/)
    await expect(page.getByLabel('Level')).toHaveValue('ERROR')

    await page.getByRole('button', { name: 'Refresh' }).click()
    await expect(page.getByLabel('Level')).toHaveValue('ERROR')

    const rows = page.locator('tbody tr')
    if ((await rows.count()) > 0 && !((await rows.first().innerText()).includes('No recent runtime logs match'))) {
      await rows.first().click()
      await expect(page.getByRole('heading', { name: 'Log Detail' })).toBeVisible()
      await page.getByRole('link', { name: 'gateway-demo-01' }).click()
      await expect(page).toHaveURL(/\/fleet\?gateway=gateway-demo-01$/)
      await expect(page.getByRole('heading', { name: 'Fleet' })).toBeVisible()
    }
  })

  test('loads fleet, aggregate, and event surfaces honestly', async ({ page }) => {
    await ensureAuthenticated(page)

    await page.goto('/fleet?gateway=gateway-demo-01')
    await expect(page.getByRole('heading', { name: 'Fleet' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Gateway Inventory' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Active Topology' })).toBeVisible()

    await page.goto('/aggregates')
    await expect(page.getByRole('heading', { name: 'Aggregates' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Aggregate Inventory' })).toBeVisible()

    const aggregateRows = page.locator('tbody tr')
    if ((await aggregateRows.count()) > 0 && !((await aggregateRows.first().innerText()).includes('No aggregate records match'))) {
      await aggregateRows.first().click()
      await expect(page.getByRole('heading', { name: 'Aggregate Detail' })).toBeVisible()
    }

    await page.goto('/events')
    await expect(page.getByRole('heading', { name: 'Events' })).toBeVisible()
    await expect(page.getByRole('heading', { name: 'Event Inventory' })).toBeVisible()

    const eventRows = page.locator('tbody tr')
    if ((await eventRows.count()) > 0 && !((await eventRows.first().innerText()).includes('No event records match'))) {
      await eventRows.first().click()
      await expect(page.getByRole('heading', { name: 'Event Detail' })).toBeVisible()
    } else {
      await expect(page.getByText('No event records match the current filters.')).toBeVisible()
    }
  })
})
