import { expect, type Locator, type Page } from '@playwright/test'

const ADMIN_USERNAME = process.env.PLAYWRIGHT_ADMIN_USERNAME || 'streamforge_admin'
const ADMIN_PASSWORD = process.env.PLAYWRIGHT_ADMIN_PASSWORD || 'LocalAdminBootstrap42'

async function locatorIsVisible(locator: Locator, timeout = 3_000): Promise<boolean> {
  try {
    await locator.waitFor({ state: 'visible', timeout })
    return true
  } catch {
    return false
  }
}

export function uniqueEntityId(prefix: string): string {
  return `${prefix}-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
}

export async function ensureAuthenticated(page: Page): Promise<void> {
  await page.goto('/login')

  const bootstrapHeading = page.getByRole('heading', { name: 'Create First Admin' })
  if (await locatorIsVisible(bootstrapHeading)) {
    await page.getByLabel('Username', { exact: true }).fill(ADMIN_USERNAME)
    await page.getByLabel('Password', { exact: true }).fill(ADMIN_PASSWORD)
    await page.getByLabel('Confirm Password', { exact: true }).fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: 'Create Admin Account' }).click()
  } else {
    await expect(page.getByRole('heading', { name: 'Control Plane Login' })).toBeVisible()
    await page.getByLabel('Username', { exact: true }).fill(ADMIN_USERNAME)
    await page.getByLabel('Password', { exact: true }).fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: 'Sign in' }).click()
  }

  await expect(page).toHaveURL(/\/overview$/)
}

export async function expectActionResult(page: Page, title: string): Promise<Locator> {
  const panel = page.locator('article.action-result').filter({
    has: page.getByRole('heading', { name: title }),
  })
  await expect(panel).toBeVisible()
  return panel
}
