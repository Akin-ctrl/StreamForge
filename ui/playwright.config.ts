import { defineConfig } from '@playwright/test'

const wsEndpoint = process.env.PLAYWRIGHT_WS_ENDPOINT

export default defineConfig({
  testDir: './tests',
  fullyParallel: false,
  workers: 1,
  timeout: 300_000,
  expect: {
    timeout: 15_000,
  },
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://127.0.0.1:5000',
    connectOptions: wsEndpoint ? { wsEndpoint } : undefined,
    headless: true,
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
})
