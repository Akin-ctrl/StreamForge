import type { PipelineItem } from '../api/client'

export type DeploymentSummary = {
  adapterCount: number
  sinkCount: number
  validationEnabled: boolean
  eventsConfigured: boolean
  aggregatesConfigured: boolean
}

export type AdapterConfigValues = Record<string, string | number>

export type AdapterRegisterDraft = {
  address: number
  param: string
  type: string
  unit: string
}

export type MqttSubscriptionDraft = {
  topic: string
  message_type: string
  payload_format: string
  asset_id: string
}

export type MqttMappingDraft = {
  topic: string
  field: string
  parameter: string
  unit: string
}

export type OpcuaMonitoredItemDraft = {
  node_id: string
  parameter: string
  unit: string
  asset_id: string
}

export type AdapterDraft = {
  adapter_id: string
  adapter_type: string
  config_values: AdapterConfigValues
  registers: AdapterRegisterDraft[]
  mqtt_subscriptions: MqttSubscriptionDraft[]
  mqtt_mappings: MqttMappingDraft[]
  opcua_monitored_items: OpcuaMonitoredItemDraft[]
}

export type ConfiguredAdapter = {
  pipelineId: number
  pipelineName: string
  gatewayId: string
  adapterId: string
  adapterType: string
  summary: string
  config: Record<string, unknown>
  draft: AdapterDraft
}

export type PipelineComposerState = {
  mode: 'create' | 'edit'
  source: 'adapter-catalog' | 'adapter-duplicate' | 'adapter-edit'
  adapterDraft: AdapterDraft
  pipelineId?: number
  pipelineName?: string
  gatewayId?: string
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

function normalizeConfigValues(config: Record<string, unknown>): AdapterConfigValues {
  const next: AdapterConfigValues = {}

  for (const [key, value] of Object.entries(config)) {
    if (key === 'registers' || key === 'output' || key === 'subscriptions' || key === 'monitored_items') {
      continue
    }
    if (typeof value === 'string' || typeof value === 'number') {
      next[key] = value
    }
  }

  return next
}

export function getDeploymentAdapterCount(config: Record<string, unknown>): number {
  const adapters = config.adapters
  return Array.isArray(adapters) ? adapters.length : 0
}

export function getDeploymentValidationEnabled(config: Record<string, unknown>): boolean {
  const validation = asRecord(config.validation)
  return Boolean(validation?.enabled)
}

export function getDeploymentEventsConfigured(config: Record<string, unknown>): boolean {
  const events = asRecord(config.events)
  if (events && Object.keys(events).length > 0) {
    return true
  }

  const adapters = Array.isArray(config.adapters) ? config.adapters : []
  return adapters.some((adapter) => {
    const adapterRecord = asRecord(adapter)
    const adapterConfig = asRecord(adapterRecord?.config)
    const output = asRecord(adapterConfig?.output)
    return typeof output?.events_topic === 'string' && output.events_topic.trim().length > 0
  })
}

export function getDeploymentAggregatesConfigured(config: Record<string, unknown>): boolean {
  const aggregates = asRecord(config.aggregates)
  return Boolean(aggregates?.enabled)
}

export function summarizeDeployment(config: Record<string, unknown>, sinkCount: number): DeploymentSummary {
  return {
    adapterCount: getDeploymentAdapterCount(config),
    sinkCount,
    validationEnabled: getDeploymentValidationEnabled(config),
    eventsConfigured: getDeploymentEventsConfigured(config),
    aggregatesConfigured: getDeploymentAggregatesConfigured(config),
  }
}

export function buildAdapterDraft(config: Record<string, unknown>, adapterId: string, adapterType: string): AdapterDraft {
  const registers = Array.isArray(config.registers)
    ? config.registers
        .map((row) => {
          const record = asRecord(row)
          if (!record) {
            return null
          }
          return {
            address: asNumber(record.address, 40001),
            param: asString(record.param),
            type: asString(record.type, 'float32'),
            unit: asString(record.unit, 'unit'),
          }
        })
        .filter((row): row is AdapterRegisterDraft => Boolean(row))
    : []

  const subscriptions = Array.isArray(config.subscriptions)
    ? config.subscriptions
        .map((row) => {
          const record = asRecord(row)
          if (!record) {
            return null
          }
          return {
            topic: asString(record.topic),
            message_type: asString(record.message_type, 'telemetry'),
            payload_format: asString(record.payload_format, 'json'),
            asset_id: asString(record.asset_id),
          }
        })
        .filter((row): row is MqttSubscriptionDraft => Boolean(row))
    : []

  const mappings = Array.isArray(config.subscriptions)
    ? config.subscriptions.flatMap((row) => {
        const record = asRecord(row)
        const topic = asString(record?.topic)
        const rowMappings = Array.isArray(record?.mappings) ? record.mappings : []
        return rowMappings
          .map((mapping) => {
            const mappingRecord = asRecord(mapping)
            if (!mappingRecord) {
              return null
            }
            return {
              topic,
              field: asString(mappingRecord.field),
              parameter: asString(mappingRecord.parameter),
              unit: asString(mappingRecord.unit),
            }
          })
          .filter((mapping): mapping is MqttMappingDraft => Boolean(mapping))
      })
    : []

  const monitoredItems = Array.isArray(config.monitored_items)
    ? config.monitored_items
        .map((row) => {
          const record = asRecord(row)
          if (!record) {
            return null
          }
          return {
            node_id: asString(record.node_id),
            parameter: asString(record.parameter),
            unit: asString(record.unit),
            asset_id: asString(record.asset_id),
          }
        })
        .filter((row): row is OpcuaMonitoredItemDraft => Boolean(row))
    : []

  return {
    adapter_id: adapterId,
    adapter_type: adapterType,
    config_values: normalizeConfigValues(config),
    registers,
    mqtt_subscriptions: subscriptions,
    mqtt_mappings: mappings,
    opcua_monitored_items: monitoredItems,
  }
}

export function summarizeAdapterConfig(adapterType: string, config: Record<string, unknown>): string {
  if (adapterType === 'modbus_tcp') {
    const host = asString(config.host, 'unknown-host')
    const port = asNumber(config.port, 0)
    const registers = Array.isArray(config.registers) ? config.registers.length : 0
    return `${host}:${port} · ${registers} mapped register${registers === 1 ? '' : 's'}`
  }

  if (adapterType === 'modbus_rtu') {
    const port = asString(config.port, '/dev/ttyUSB0')
    const baudrate = asNumber(config.baudrate, 9600)
    const registers = Array.isArray(config.registers) ? config.registers.length : 0
    return `${port} @ ${baudrate} baud · ${registers} mapped register${registers === 1 ? '' : 's'}`
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

  return 'Configured through deployment JSON'
}

export function extractConfiguredAdapters(pipelines: PipelineItem[]): ConfiguredAdapter[] {
  const rows: ConfiguredAdapter[] = []

  for (const pipeline of pipelines) {
    const adapters = Array.isArray(pipeline.config.adapters) ? pipeline.config.adapters : []
    for (const adapter of adapters) {
      const record = asRecord(adapter)
      if (!record) {
        continue
      }
      const adapterType = asString(record.adapter_type, 'unknown')
      const adapterId = asString(record.adapter_id, 'unknown-adapter')
      const config = asRecord(record.config) || {}
      rows.push({
        pipelineId: pipeline.id,
        pipelineName: pipeline.name,
        gatewayId: pipeline.gateway_id,
        adapterId,
        adapterType,
        summary: summarizeAdapterConfig(adapterType, config),
        config,
        draft: buildAdapterDraft(config, adapterId, adapterType),
      })
    }
  }

  return rows
}
