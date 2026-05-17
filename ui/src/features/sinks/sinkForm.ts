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
  table: string
  targetBootstrap: string
  targetTopic: string
  url: string
  method: string
  routeType: string
  webhookUrl: string
  slackWebhookUrl: string
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
    dbDsn: 'postgresql://streamforge:streamforge@timescaledb:5432/streamforge',
    table: 'telemetry_clean',
    targetBootstrap: 'kafka:9092',
    targetTopic: 'mirror.telemetry.clean',
    url: 'http://receiver:8080/ingest',
    method: 'POST',
    routeType: 'webhook',
    webhookUrl: 'http://example.local/alerts',
    slackWebhookUrl: '',
  }
}

export function sinkToForm(sink: SinkItem): SinkFormState {
  const defaults = buildDefaultSinkForm(sink.sink_type)
  const config = sink.config || {}
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
    dbDsn: asString(config.db_dsn, defaults.dbDsn),
    table: asString(config.table, defaults.table),
    targetBootstrap: asString(config.target_bootstrap, defaults.targetBootstrap),
    targetTopic: asString(config.target_topic, defaults.targetTopic),
    url: asString(config.url, defaults.url),
    method: asString(config.method, defaults.method),
    routeType: asString(config.route_type, defaults.routeType),
    webhookUrl: asString(config.url, defaults.webhookUrl),
    slackWebhookUrl: asString(config.webhook_url, defaults.slackWebhookUrl),
  }
}

function buildConfig(form: SinkFormState): Record<string, unknown> {
  if (form.sinkType === 'timescaledb') {
    return {
      kafka_bootstrap: form.kafkaBootstrap,
      topic: form.sourceTopic,
      group_id: form.kafkaGroupId,
      db_dsn: form.dbDsn,
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
    ...(form.routeType === 'slack'
      ? { webhook_url: form.slackWebhookUrl }
      : { url: form.webhookUrl }),
  }
}

export function buildSinkConfigJson(form: SinkFormState): string {
  return JSON.stringify(buildConfig(form), null, 2)
}

export function applySinkConfigJson(form: SinkFormState, text: string): SinkFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  return sinkToForm({
    sink_id: form.sinkId,
    name: form.name,
    sink_type: form.sinkType,
    status: form.status,
    description: form.description || null,
    config: parsed,
    created_at: '',
    updated_at: '',
  })
}

export function formToCreateSinkPayload(form: SinkFormState) {
  return {
    sink_id: form.sinkId.trim(),
    name: form.name.trim(),
    sink_type: form.sinkType,
    status: form.status,
    config: buildConfig(form),
    description: form.description.trim() || null,
  }
}

export function formToUpdateSinkPayload(form: SinkFormState) {
  return {
    name: form.name.trim(),
    sink_type: form.sinkType,
    status: form.status,
    config: buildConfig(form),
    description: form.description.trim() || null,
  }
}
