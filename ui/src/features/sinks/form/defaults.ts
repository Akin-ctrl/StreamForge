import type { CatalogSinkType } from '../../../shared/api/client'
import { getCatalogStringDefault } from '../../../shared/config/catalog'
import type { SinkFormState } from './types'

/**
 * Sink form defaults live separately from hydration/serialization so the page can
 * stay focused on workflow and leave contract shaping here.
 */
export function buildDefaultSinkForm(sinkType: string, contract?: CatalogSinkType): SinkFormState {
  return {
    sinkId: 'sink-01',
    name: 'Sink 01',
    sinkType,
    status: 'active',
    description: '',
    sourceTopic:
      getCatalogStringDefault(contract, 'ingress', 'source_topic', '') ||
      getCatalogStringDefault(contract, 'ingress', 'topic', '') ||
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
