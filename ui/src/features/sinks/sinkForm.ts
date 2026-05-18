import type { SinkItem } from '../../shared/api/client'

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
}

function asString(value: unknown, fallback = ''): string {
  return typeof value === 'string' ? value : fallback
}

export function buildDefaultSinkForm(sinkType: string): SinkFormState {
  return {
    sinkId: 'sink-01',
    name: 'Sink 01',
    sinkType,
    status: 'active',
    description: '',
    sourceTopic: sinkType === 'alert_router' ? 'alarms.raw' : 'telemetry.clean',
    kafkaBootstrap: 'kafka:9092',
    kafkaGroupId: 'sf-sink-timescaledb',
    dbDsn: '',
    dbDsnConfigured: false,
    table: 'telemetry_clean',
    targetBootstrap: 'kafka:9092',
    targetTopic: 'mirror.telemetry.clean',
    url: 'http://receiver:8080/ingest',
    method: 'POST',
    routeType: 'webhook',
    webhookUrl: '',
    webhookUrlConfigured: false,
    slackWebhookUrl: '',
    slackWebhookUrlConfigured: false,
  }
}

export function sinkToForm(sink: SinkItem): SinkFormState {
  const defaults = buildDefaultSinkForm(sink.sink_type)
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
  }
}

function buildConfig(form: SinkFormState): Record<string, unknown> {
  if (form.sinkType === 'timescaledb') {
    return {
      kafka_bootstrap: form.kafkaBootstrap,
      topic: form.sourceTopic,
      group_id: form.kafkaGroupId,
      table: form.table,
    }
  }

  if (form.sinkType === 'kafka') {
    return {
      source_topic: form.sourceTopic,
      target_bootstrap: form.targetBootstrap,
      target_topic: form.targetTopic,
    }
  }

  if (form.sinkType === 'http') {
    return {
      source_topic: form.sourceTopic,
      url: form.url,
      method: form.method,
    }
  }

  return {
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

export function buildSinkConfigJson(form: SinkFormState): string {
  return JSON.stringify(buildConfig(form), null, 2)
}

export function applySinkConfigJson(form: SinkFormState, text: string): SinkFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  const nextForm = sinkToForm({
    sink_id: form.sinkId,
    name: form.name,
    sink_type: form.sinkType,
    status: form.status,
    description: form.description || null,
    config: parsed,
    secret_status: {},
    created_at: '',
    updated_at: '',
  })
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
