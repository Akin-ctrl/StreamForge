import type { AdapterItem, DeploymentItem, SinkItem } from '../api/client'

export type DeploymentSummary = {
  adapterCount: number
  sinkCount: number
  validationEnabled: boolean
  eventsConfigured: boolean
  aggregatesConfigured: boolean
}

export type AdapterUsage = {
  adapter: AdapterItem
  deploymentIds: string[]
  gatewayIds: string[]
}

export type SinkUsage = {
  sink: SinkItem
  deploymentIds: string[]
  gatewayIds: string[]
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

function asNumber(value: unknown, fallback = 0): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : fallback
}

export function summarizeDeployment(deployment: DeploymentItem): DeploymentSummary {
  return {
    adapterCount: deployment.adapter_ids.length,
    sinkCount: deployment.sink_ids.length,
    validationEnabled: Boolean(asRecord(deployment.validation_config)?.enabled),
    eventsConfigured: Boolean(asRecord(deployment.events_config)?.enabled || Object.keys(deployment.events_config || {}).length > 0),
    aggregatesConfigured: Boolean(asRecord(deployment.aggregates_config)?.enabled || Object.keys(deployment.aggregates_config || {}).length > 0),
  }
}

export function summarizeAdapterConfig(adapterType: string, config: Record<string, unknown>): string {
  if (adapterType === 'modbus_tcp') {
    const host = asString(config.host, 'unknown-host')
    const port = asNumber(config.port, 502)
    const points = Array.isArray(config.points) ? config.points.length : 0
    return `${host}:${port} · ${points} point${points === 1 ? '' : 's'}`
  }

  if (adapterType === 'modbus_rtu') {
    const port = asString(config.serial_port || config.port, '/dev/ttyUSB0')
    const baudrate = asNumber(config.baudrate, 9600)
    const points = Array.isArray(config.points) ? config.points.length : 0
    return `${port} @ ${baudrate} baud · ${points} point${points === 1 ? '' : 's'}`
  }

  if (adapterType === 'mqtt') {
    const host = asString(config.broker_host, 'mqtt-broker')
    const port = asNumber(config.broker_port, 1883)
    const subscriptions = Array.isArray(config.subscriptions) ? config.subscriptions.length : 0
    return `${host}:${port} · ${subscriptions} subscription${subscriptions === 1 ? '' : 's'}`
  }

  if (adapterType === 'opcua') {
    const endpoint = asString(config.endpoint, 'opc.tcp://opcua-server:4840')
    const monitoredItems = Array.isArray(config.monitored_items) ? config.monitored_items.length : 0
    return `${endpoint} · ${monitoredItems} monitored item${monitoredItems === 1 ? '' : 's'}`
  }

  return 'Configured adapter'
}

export function buildAdapterUsage(adapters: AdapterItem[], deployments: DeploymentItem[]): AdapterUsage[] {
  return adapters.map((adapter) => {
    const matchingDeployments = deployments.filter((deployment) => deployment.adapter_ids.includes(adapter.adapter_id))
    return {
      adapter,
      deploymentIds: matchingDeployments.map((deployment) => deployment.deployment_id),
      gatewayIds: Array.from(new Set(matchingDeployments.map((deployment) => deployment.gateway_id))),
    }
  })
}

export function summarizeSinkConfig(sinkType: string, config: Record<string, unknown>): string {
  if (sinkType === 'timescaledb') {
    const table = asString(config.table, 'telemetry_clean')
    const topic = asString(config.topic, 'telemetry.clean')
    return `${table} ← ${topic}`
  }

  if (sinkType === 'kafka') {
    const topic = asString(config.target_topic, 'telemetry.outbound')
    const bootstrap = asString(config.target_bootstrap, 'kafka:9092')
    return `${bootstrap} → ${topic}`
  }

  if (sinkType === 'http') {
    const method = asString(config.method, 'POST')
    const url = asString(config.url, 'http://example.local/telemetry')
    return `${method} ${url}`
  }

  if (sinkType === 'alert_router') {
    const routeType = asString(config.route_type, 'webhook')
    const destination = asString(config.url || config.webhook_url)
    return destination ? `${routeType} → ${destination}` : `${routeType} configured`
  }

  return 'Configured sink'
}

export function buildSinkUsage(sinks: SinkItem[], deployments: DeploymentItem[]): SinkUsage[] {
  return sinks.map((sink) => {
    const matchingDeployments = deployments.filter((deployment) => deployment.sink_ids.includes(sink.sink_id))
    return {
      sink,
      deploymentIds: matchingDeployments.map((deployment) => deployment.deployment_id),
      gatewayIds: Array.from(new Set(matchingDeployments.map((deployment) => deployment.gateway_id))),
    }
  })
}
