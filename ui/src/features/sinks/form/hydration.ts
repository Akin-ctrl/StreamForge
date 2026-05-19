import type { CatalogSinkType, SinkItem } from '../../../shared/api/client'
import { asString, cloneJsonObject } from '../../../shared/config/json'
import { buildDefaultSinkForm } from './defaults'
import type { SinkFormState } from './types'

/**
 * Rehydrates sink API state into the editor model without round-tripping write-only secrets.
 */
export function sinkToForm(sink: SinkItem, contract?: CatalogSinkType): SinkFormState {
  const defaults = buildDefaultSinkForm(sink.sink_type, contract)
  const config = sink.config
  const secretStatus = sink.secret_status

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
    passthroughConfig: cloneJsonObject(config),
  }
}
