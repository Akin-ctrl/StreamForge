import type { CatalogSinkType, SinkItem } from '../../shared/api/client'
import { getCatalogStringDefault, getInternalFieldKeys } from '../../shared/config/catalog'

export type SinkFormState = {
  sinkId: string
  name: string
  sinkType: string
  status: string
  description: string
  sourceTopic: string
  kafkaBootstrap: string
  kafkaGroupId: string
  dbDsn: string
  dbDsnConfigured: boolean
  table: string
  targetBootstrap: string
  targetTopic: string
  url: string
  method: string
  routeType: string
  webhookUrl: string
  webhookUrlConfigured: boolean
  slackWebhookUrl: string
  slackWebhookUrlConfigured: boolean
  passthroughConfig: Record<string, unknown>
}

function cloneConfig<T extends Record<string, unknown>>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

export function buildDefaultSinkForm(sinkType: string, contract?: CatalogSinkType): SinkFormState {
  return {
    sinkId: 'sink-01',
    name: 'Sink 01',
    sinkType,
    status: 'active',
    description: '',
    sourceTopic:
      getCatalogStringDefault(contract, 'ingress', 'source_topic', '') ||
      (sinkType === 'alert_router' ? 'alarms.raw' : 'telemetry.clean'),
    kafkaBootstrap: getCatalogStringDefault(contract, 'ingress', 'kafka_bootstrap', 'kafka:9092'),
    kafkaGroupId: getCatalogStringDefault(contract, 'ingress', 'group_id', 'sf-sink-timescaledb'),
    dbDsn: '',
    dbDsnConfigured: false,
    table: getCatalogStringDefault(contract, 'destination', 'table', 'telemetry_clean'),
    targetBootstrap: getCatalogStringDefault(contract, 'destination', 'target_bootstrap', 'kafka:9092'),
    targetTopic: getCatalogStringDefault(contract, 'destination', 'target_topic', 'mirror.telemetry.clean'),
    url: getCatalogStringDefault(contract, 'destination', 'url', 'http://receiver:8080/ingest'),
    method: getCatalogStringDefault(contract, 'destination', 'method', 'POST'),
    routeType: getCatalogStringDefault(contract, 'destination', 'route_type', 'webhook'),
    webhookUrl: '',
    webhookUrlConfigured: false,
    slackWebhookUrl: '',
    slackWebhookUrlConfigured: false,
    passthroughConfig: {},
  }
}

export function sinkToForm(sink: SinkItem, contract?: CatalogSinkType): SinkFormState {
  const defaults = buildDefaultSinkForm(sink.sink_type, contract)
  const config = sink.config || {}
  const secretStatus = sink.secret_status || {}
  return {
    ...defaults,
    sinkId: sink.sink_id,
    name: sink.name,
    sinkType: sink.sink_type,
    status: sink.status,
    description: sink.description || '',
    sourceTopic: asString(config.source_topic || config.topic, defaults.sourceTopic),
    kafkaBootstrap: asString(config.kafka_bootstrap, defaults.kafkaBootstrap),
    kafkaGroupId: asString(config.group_id, defaults.kafkaGroupId),
    dbDsn: '',
    dbDsnConfigured:
      Boolean(secretStatus.db_dsn?.configured) ||
      (typeof config.db_dsn === 'string' && config.db_dsn.trim().length > 0),
    table: asString(config.table, defaults.table),
    targetBootstrap: asString(config.target_bootstrap, defaults.targetBootstrap),
    targetTopic: asString(config.target_topic, defaults.targetTopic),
    url: asString(config.url, defaults.url),
    method: asString(config.method, defaults.method),
    routeType: asString(config.route_type, defaults.routeType),
    webhookUrl: '',
    webhookUrlConfigured:
      Boolean(secretStatus.url?.configured) ||
      (typeof config.url === 'string' && config.url.trim().length > 0 && sink.sink_type === 'alert_router'),
    slackWebhookUrl: '',
    slackWebhookUrlConfigured:
      Boolean(secretStatus.webhook_url?.configured) ||
      (typeof config.webhook_url === 'string' && config.webhook_url.trim().length > 0),
    passthroughConfig: cloneConfig(config),
  }
}

function baseConfig(form: SinkFormState) {
  const config = cloneConfig(form.passthroughConfig)
  for (const key of [
    'source_topic',
    'topic',
    'kafka_bootstrap',
    'group_id',
    'db_dsn',
    'table',
    'target_bootstrap',
    'target_topic',
    'url',
    'method',
    'route_type',
  ]) {
    delete config[key]
  }
  return config
}

function buildConfig(form: SinkFormState): Record<string, unknown> {
  const config = baseConfig(form)

  if (form.sinkType === 'timescaledb') {
    return {
      ...config,
      kafka_bootstrap: form.kafkaBootstrap,
      topic: form.sourceTopic,
      group_id: form.kafkaGroupId,
      table: form.table,
    }
  }

  if (form.sinkType === 'kafka') {
    return {
      ...config,
      source_topic: form.sourceTopic,
      target_bootstrap: form.targetBootstrap,
      target_topic: form.targetTopic,
    }
  }

  if (form.sinkType === 'http') {
    return {
      ...config,
      source_topic: form.sourceTopic,
      url: form.url,
      method: form.method,
    }
  }

  return {
    ...config,
    source_topic: form.sourceTopic,
    route_type: form.routeType,
  }
}

function buildSecrets(form: SinkFormState): Record<string, string | null> | undefined {
  if (form.sinkType === 'timescaledb') {
    if (!form.dbDsn.trim()) {
      return undefined
    }
    return { db_dsn: form.dbDsn.trim() }
  }

  if (form.sinkType === 'alert_router') {
    if (form.routeType === 'slack') {
      if (!form.slackWebhookUrl.trim()) {
        return undefined
      }
      return { webhook_url: form.slackWebhookUrl.trim() }
    }
    if (!form.webhookUrl.trim()) {
      return undefined
    }
    return { url: form.webhookUrl.trim() }
  }

  return undefined
}

function stripInternalSinkConfig(config: Record<string, unknown>, contract?: CatalogSinkType) {
  const safeConfig = cloneConfig(config)
  for (const fieldKey of getInternalFieldKeys(contract, 'ingress')) {
    delete safeConfig[fieldKey]
  }
  return safeConfig
}

export function buildSinkConfigJson(form: SinkFormState, contract?: CatalogSinkType): string {
  return JSON.stringify(stripInternalSinkConfig(buildConfig(form), contract), null, 2)
}

export function applySinkConfigJson(form: SinkFormState, text: string, contract?: CatalogSinkType): SinkFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  const mergedConfig = {
    ...buildConfig(form),
    ...cloneConfig(parsed),
  }
  const nextForm = sinkToForm(
    {
      sink_id: form.sinkId,
      name: form.name,
      sink_type: form.sinkType,
      status: form.status,
      description: form.description || null,
      config: mergedConfig,
      secret_status: {},
      created_at: '',
      updated_at: '',
    },
    contract,
  )
  return {
    ...nextForm,
    dbDsn: '',
    dbDsnConfigured: form.dbDsnConfigured,
    webhookUrl: '',
    webhookUrlConfigured: form.webhookUrlConfigured,
    slackWebhookUrl: '',
    slackWebhookUrlConfigured: form.slackWebhookUrlConfigured,
  }
}

export function formToCreateSinkPayload(form: SinkFormState) {
  const secrets = buildSecrets(form)
  return {
    sink_id: form.sinkId.trim(),
    name: form.name.trim(),
    sink_type: form.sinkType,
    status: form.status,
    config: buildConfig(form),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}

export function formToUpdateSinkPayload(form: SinkFormState) {
  const secrets = buildSecrets(form)
  return {
    name: form.name.trim(),
    sink_type: form.sinkType,
    status: form.status,
    config: buildConfig(form),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}
