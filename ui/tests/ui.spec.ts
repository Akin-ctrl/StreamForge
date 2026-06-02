import { execFileSync } from 'node:child_process'

import { expect, test } from '@playwright/test'

const ADMIN_USERNAME = 'ui_admin'
const ADMIN_PASSWORD = 'StreamForge1234'
const SECONDARY_USER_PASSWORD = 'StreamForge5678'
const RUN_ID = Date.now()
const SECONDARY_USERNAME = `ui_user_${RUN_ID}`
const CREATED_GATEWAY_ID = 'gateway-demo-01'
const CREATED_GATEWAY_HOSTNAME = 'gateway-demo-01.local'
const JSON_PIPELINE_NAME = `ui-json-pipeline-${RUN_ID}`
const WIZARD_PIPELINE_NAME = `ui-wizard-pipeline-${RUN_ID}`

type ContainerInfo = {
  name: string
  status: string
}

function listContainers(includeStopped = false): ContainerInfo[] {
  const args = includeStopped ? ['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Status}}'] : ['docker', 'ps', '--format', '{{.Names}}\t{{.Status}}']
  return runCommand(args)
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [name, ...statusParts] = line.split('\t')
      return {
        name,
        status: statusParts.join('\t'),
      }
    })
}

function findContainerName(description: string, matcher: (name: string) => boolean): string {
  const match = listContainers().find((container) => !container.status.startsWith('Restarting') && matcher(container.name))
  if (!match) {
    throw new Error(`Unable to find running container for ${description}`)
  }
  return match.name
}

function waitForContainerName(description: string, matcher: (name: string) => boolean, timeoutMs = 60_000): string {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const match = listContainers().find((container) => !container.status.startsWith('Restarting') && matcher(container.name))
    if (match) {
      return match.name
    }
    execFileSync('python3', ['-c', 'import time; time.sleep(1)'], { stdio: 'ignore' })
  }
  throw new Error(`Unable to find running container for ${description}`)
}

function runCommand(args: string[]): string {
  return execFileSync(args[0], args.slice(1), {
    encoding: 'utf8',
    stdio: ['ignore', 'pipe', 'pipe'],
  }).trim()
}

function runSql(sql: string): string {
  const postgresContainer = findContainerName('postgres', (name) => name.endsWith('-postgres-1'))
  return runCommand([
    'docker',
    'exec',
    postgresContainer,
    'psql',
    '-U',
    'streamforge',
    '-d',
    'streamforge',
    '-At',
    '-c',
    sql,
  ])
}

function runTimescaleSql(sql: string): string {
  const timescaledbContainer = findContainerName('timescaledb', (name) => name.endsWith('-timescaledb-1'))
  return runCommand([
    'docker',
    'exec',
    timescaledbContainer,
    'psql',
    '-U',
    'streamforge',
    '-d',
    'streamforge',
    '-At',
    '-c',
    sql,
  ])
}

async function waitForSqlContains(sql: string, expectedText: string, timeout = 90_000) {
  await expect
    .poll(() => runSql(sql), { timeout })
    .toContain(expectedText)
}

async function waitForTimescaleContains(sql: string, expectedText: string, timeout = 90_000) {
  await expect
    .poll(() => runTimescaleSql(sql), { timeout })
    .toContain(expectedText)
}

async function waitForSqlCount(sql: string, minimum: number, timeout = 90_000) {
  await expect
    .poll(() => Number(runSql(sql) || '0'), { timeout })
    .toBeGreaterThanOrEqual(minimum)
}

function writeModbusValues(temperature: number, pressure = 15.5, humidity = 40): void {
  const adapterContainer = findContainerName('managed adapter', (name) => name.startsWith('sf-adapter-'))
  const script = `
import struct
from pymodbus.client import ModbusTcpClient

client = ModbusTcpClient('modbus-simulator', port=5020)
assert client.connect()
values = [(0, ${temperature}), (2, ${pressure}), (4, ${humidity})]
for address, value in values:
    registers = list(struct.unpack('>HH', struct.pack('>f', float(value))))
    result = client.write_registers(address, registers)
    assert not result.isError(), result
client.close()
print("ok")
`
  runCommand(['docker', 'exec', adapterContainer, 'python', '-c', script])
}

function removeManagedContainers(): void {
  const managed = listContainers(true)
    .map((container) => container.name)
    .filter((name) => name.startsWith('sf-adapter-') || name.startsWith('sf-sink-'))

  if (managed.length === 0) {
    return
  }

  runCommand(['docker', 'rm', '-f', ...managed])
}

function resetGatewayRuntimeState(): void {
  const gatewayRuntimeContainer = findContainerName('gateway runtime', (name) => name.endsWith('-gateway_runtime-1'))
  runCommand(['docker', 'exec', gatewayRuntimeContainer, 'rm', '-f', '/data/config/gateway.json', '/data/schemas.cache.json'])
  runCommand(['docker', 'restart', gatewayRuntimeContainer])
}

function resetControlPlaneState(): void {
  runSql('DELETE FROM sinks;')
  runSql('DELETE FROM pipelines;')
  runSql('DELETE FROM alarms;')
  runSql('DELETE FROM dlq_messages;')
  runSql('DELETE FROM gateways;')
  runSql('DELETE FROM users;')
}

async function login(page, username: string, password: string) {
  await page.goto('/login')
  await expect(page.getByRole('heading', { name: 'Control Plane Login' })).toBeVisible()
  await page.getByLabel('Username', { exact: true }).fill(username)
  await page.getByLabel('Password', { exact: true }).fill(password)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await expect(page).toHaveURL(/\/overview$/)
}

async function refreshUntilContains(page, expectedText: string) {
  await expect
    .poll(
      async () => {
        await page.getByRole('button', { name: 'Refresh' }).click()
        return page.locator('body').innerText()
      },
      { timeout: 30_000 },
    )
    .toContain(expectedText)
}

async function refreshTableUntilContains(page, expectedText: string, timeout = 45_000) {
  await expect
    .poll(
      async () => {
        await page.getByRole('button', { name: 'Refresh' }).click()
        return page.locator('tbody').innerText()
      },
      { timeout },
    )
    .toContain(expectedText)
}

test.describe.configure({ mode: 'serial' })

test('covers bootstrap, authentication, every route, and key UI actions', async ({ page }) => {
  const jsonPipelineConfig = JSON.stringify(
    {
      adapters: [
        {
          adapter_id: `json-adapter-${RUN_ID}`,
          adapter_type: 'modbus_tcp',
          config: {
            host: 'modbus-simulator',
            port: 5020,
            unit_id: 1,
            poll_interval_ms: 1000,
            registers: [
              {
                address: 40001,
                param: 'temperature',
                type: 'float32',
                unit: 'celsius',
              },
            ],
            output: {
              kafka_bootstrap: 'kafka:9092',
              topic: 'telemetry.raw',
              asset_id: `json-sensor-${RUN_ID}`,
            },
          },
        },
      ],
      validation: {
        enabled: true,
        raw_topic: 'telemetry.raw',
        clean_topic: 'telemetry.clean',
        dlq_topic: 'dlq.telemetry',
        ranges: {
          temperature: { min: -50, max: 500 },
        },
        rate_of_change: { temperature: 20 },
        gap_detection: { temperature: 5 },
      },
    },
    null,
    2,
  )

  await test.step('bootstrap the first admin through the UI', async () => {
    resetControlPlaneState()
    removeManagedContainers()
    resetGatewayRuntimeState()

    await page.goto('/')
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Create First Admin' })).toBeVisible()

    await page.getByLabel('Username', { exact: true }).fill(ADMIN_USERNAME)
    await page.getByLabel('Password', { exact: true }).fill(ADMIN_PASSWORD)
    await page.getByLabel('Confirm Password', { exact: true }).fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: 'Create Admin Account' }).click()

    await expect(page).toHaveURL(/\/overview$/)
    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
  })

  await test.step('exercise logout, failed login, and successful login', async () => {
    await page.getByRole('button', { name: 'Logout' }).click()
    await expect(page).toHaveURL(/\/login$/)
    await expect(page.getByRole('heading', { name: 'Control Plane Login' })).toBeVisible()

    await page.getByLabel('Username', { exact: true }).fill(ADMIN_USERNAME)
    await page.getByLabel('Password', { exact: true }).fill(`${ADMIN_PASSWORD}-wrong`)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page.getByText(/invalid|login failed/i)).toBeVisible()

    await page.getByLabel('Password', { exact: true }).fill(ADMIN_PASSWORD)
    await page.getByRole('button', { name: 'Sign in' }).click()
    await expect(page).toHaveURL(/\/overview$/)

    await page.goto('/')
    await expect(page).toHaveURL(/\/overview$/)
  })

  await test.step('verify overview route and timezone preference persistence', async () => {
    await page.goto('/overview')
    await expect(page.getByRole('heading', { name: 'Overview' })).toBeVisible()
    await expect(page.getByText('Gateway Health')).toBeVisible()

    const timezoneSelect = page.locator('.app-sidebar select')
    await timezoneSelect.selectOption('UTC')
    await expect.poll(() => page.evaluate(() => window.localStorage.getItem('sf-timezone'))).toBe('UTC')

    await page.reload()
    await expect(timezoneSelect).toHaveValue('UTC')
  })

  await test.step('exercise gateway creation page', async () => {
    await page.goto('/gateways')
    await expect(page.getByRole('heading', { name: 'Gateways' })).toBeVisible()

    await page.getByLabel('Gateway ID', { exact: true }).fill(CREATED_GATEWAY_ID)
    await page.getByLabel('Hostname', { exact: true }).fill(CREATED_GATEWAY_HOSTNAME)
    await page.getByRole('button', { name: 'Create Gateway' }).click()

    await refreshUntilContains(page, CREATED_GATEWAY_ID)
    const gatewayRow = page.locator('tbody tr', { hasText: CREATED_GATEWAY_HOSTNAME }).first()
    await expect(gatewayRow).toBeVisible()
  })

  let jsonPipelineId = 0

  await test.step('exercise JSON pipeline management page', async () => {
    await page.goto('/pipelines')
    await expect(page.getByRole('heading', { name: 'Pipelines' })).toBeVisible()
    const pipelineForm = page.locator('form.card').first()

    await pipelineForm.getByLabel('Name', { exact: true }).fill(JSON_PIPELINE_NAME)
    await expect(pipelineForm.getByRole('combobox', { name: 'Gateway' })).toHaveValue('gateway-demo-01')
    await pipelineForm.locator('textarea').fill(jsonPipelineConfig)
    await pipelineForm.getByRole('button', { name: 'Create Pipeline' }).click()

    const pipelineRow = page.locator('tbody tr', { hasText: JSON_PIPELINE_NAME }).first()
    await expect(pipelineRow).toBeVisible()
    jsonPipelineId = Number((await pipelineRow.locator('td').nth(0).textContent()) || '0')
    expect(jsonPipelineId).toBeGreaterThan(0)
  })

  await test.step('exercise sink management page', async () => {
    await page.goto('/sinks')
    await expect(page.getByRole('heading', { name: 'Sinks' })).toBeVisible()
    const sinkForm = page.locator('form.card').first()

    await sinkForm.getByRole('combobox', { name: 'Pipeline' }).selectOption(String(jsonPipelineId))
    await sinkForm.getByRole('button', { name: 'Create Sink' }).click()

    const sinkRow = page.locator('tbody tr', { hasText: String(jsonPipelineId) }).first()
    await expect(sinkRow).toBeVisible()
    await sinkRow.getByRole('button', { name: 'Delete' }).click()
    await expect(sinkRow).toHaveCount(0)
  })

  await test.step('exercise pipeline wizard route and creation flow', async () => {
    await page.goto('/create-pipeline')
    await expect(page.getByRole('heading', { name: 'Create Pipeline Wizard' })).toBeVisible()

    await page.getByLabel('Pipeline Name', { exact: true }).fill(WIZARD_PIPELINE_NAME)
    await page.getByRole('combobox', { name: 'Gateway' }).selectOption('gateway-demo-01')
    await page.getByRole('combobox', { name: 'Adapter Type' }).selectOption({ label: 'Modbus TCP' })
    await page.getByRole('button', { name: 'Add Register' }).click()

    await page.locator('input[name="adapter.registers.1.param"]').fill('pressure')
    await page.locator('input[name="adapter.registers.1.unit"]').fill('bar')

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByRole('heading', { name: 'Step 2: Destination Sink' })).toBeVisible()
    await page.getByLabel('Topic', { exact: true }).fill('telemetry.clean')

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByRole('heading', { name: 'Step 3: Validation Rules' })).toBeVisible()
    await page.locator('input[name="validationByParam.temperature.alarm_enabled"]').check()
    await page.locator('input[name="validationByParam.temperature.alarm_threshold"]').fill('100')
    await page.locator('select[name="validationByParam.temperature.alarm_severity"]').selectOption('HIGH')

    await page.getByRole('button', { name: 'Next' }).click()
    await expect(page.getByRole('heading', { name: 'Step 4: Review & Confirm' })).toBeVisible()
    await page.getByRole('button', { name: 'Create Pipeline' }).click()

    await expect(page).toHaveURL(/\/overview$/)
    await expect(page.getByText(WIZARD_PIPELINE_NAME)).toBeVisible()
  })

  await test.step('exercise health route', async () => {
    await page.goto('/health')
    await expect(page.getByRole('heading', { name: 'Health', exact: true })).toBeVisible()
    await expect(page.getByText('CPU')).toBeVisible()
    await expect(page.getByText('Network RX')).toBeVisible()
    await expect(page.getByRole('heading', { name: CREATED_GATEWAY_ID, exact: true })).toBeVisible()
  })

  await test.step('exercise users page create and delete flows', async () => {
    await page.goto('/users')
    await expect(page.getByRole('heading', { name: 'Users' })).toBeVisible()
    const userForm = page.locator('form.card').first()

    await userForm.getByLabel('Username', { exact: true }).fill(SECONDARY_USERNAME)
    await userForm.getByLabel('Password', { exact: true }).fill(SECONDARY_USER_PASSWORD)
    await userForm.getByLabel('Confirm Password', { exact: true }).fill(SECONDARY_USER_PASSWORD)
    await userForm.getByRole('button', { name: 'Create User' }).click()

    const userRow = page.locator('tbody tr', { hasText: SECONDARY_USERNAME }).first()
    await expect(userRow).toBeVisible()
    await userRow.getByRole('button', { name: 'Delete' }).click()
    await expect(userRow).toHaveCount(0)
  })

  await test.step('exercise alarms page acknowledge and suppress flows', async () => {
    waitForContainerName('managed adapter', (name) => name.startsWith('sf-adapter-'))
    waitForContainerName('managed sink', (name) => name.startsWith('sf-sink-'))
    writeModbusValues(80)
    await waitForTimescaleContains(
      "select coalesce((select asset_id || '|' || parameter from telemetry_clean where asset_id = 'asset-01' order by gateway_time desc limit 1), '')",
      'asset-01|temperature',
      120_000,
    )
    writeModbusValues(120)

    await waitForSqlContains(
      "select coalesce((select alarm_id || '|' || state from alarms order by raised_at desc limit 1), '')",
      '|ACTIVE',
      120_000,
    )
    const alarmId = runSql("select alarm_id from alarms where state = 'ACTIVE' order by raised_at desc limit 1")
    expect(alarmId).not.toBe('')

    await page.goto('/alarms')
    await expect(page.getByRole('heading', { name: 'Alarms' })).toBeVisible()
    await refreshTableUntilContains(page, alarmId, 90_000)
    const trackedAlarmRow = page.locator('tbody tr', { hasText: alarmId }).first()
    await expect(trackedAlarmRow).toContainText('ACTIVE')

    await trackedAlarmRow.getByRole('button', { name: 'Acknowledge' }).click()
    await expect(trackedAlarmRow).toContainText('ACKNOWLEDGED')

    await trackedAlarmRow.getByRole('button', { name: 'Suppress' }).click()
    await expect(trackedAlarmRow).toContainText('SUPPRESSED')

    writeModbusValues(80)
    await page.getByRole('button', { name: 'Refresh' }).click()
  })

  await test.step('exercise DLQ page single and bulk actions', async () => {
    writeModbusValues(600)
    await waitForSqlCount("select count(*) from dlq_messages where status = 'PENDING'", 2, 120_000)

    await page.goto('/dlq')
    await expect(page.getByRole('heading', { name: 'DLQ', exact: true })).toBeVisible()
    await refreshTableUntilContains(page, 'range_above_max:temperature')

    const rows = page.locator('tbody tr')
    await expect
      .poll(async () => await rows.count(), { timeout: 30_000 })
      .toBeGreaterThanOrEqual(2)
    await expect(rows.first()).toBeVisible()

    await rows.nth(0).locator('input[type="checkbox"]').check()
    await rows.nth(1).locator('input[type="checkbox"]').check()
    await page.getByRole('button', { name: /Reprocess Selected/ }).click()

    await expect
      .poll(async () => page.locator('tbody').innerText(), { timeout: 30_000 })
      .toMatch(/REPROCESS_REQUESTED|REPROCESSED/)

    const discardRow = page.locator('tbody tr', { hasText: 'PENDING' }).first()
    await expect(discardRow).toBeVisible()
    await discardRow.getByRole('button', { name: 'Discard' }).click()

    await expect
      .poll(async () => page.locator('tbody').innerText(), { timeout: 30_000 })
      .toMatch(/DISCARD_REQUESTED|DISCARDED/)

    writeModbusValues(80)
  })

  await test.step('delete created JSON pipeline after sink cleanup', async () => {
    await page.goto('/pipelines')
    const pipelineRow = page.locator('tbody tr', { hasText: JSON_PIPELINE_NAME }).first()
    await expect(pipelineRow).toBeVisible()
    await pipelineRow.getByRole('button', { name: 'Delete' }).click()
    await expect(pipelineRow).toHaveCount(0)
  })
})
