import type { AdapterItem, CatalogAdapterType } from '../../../shared/api/client'
import { asBoolean, asJsonObject, asString, cloneJsonObject, toStringValue } from '../../../shared/config/json'
import { buildDefaultAdapterForm, createDefaultMonitoredItemForm, createDefaultMqttMappingForm, createDefaultMqttSubscriptionForm, createDefaultPointForm } from './defaults'
import { isAdapterPasswordConfigured } from './secrets'
import type { AdapterFormState } from './types'

/**
 * Converts persisted adapter API data into editable form state.
 * Secret fields stay write-only and are represented through configured flags.
 */
export function adapterToForm(adapter: AdapterItem, contract?: CatalogAdapterType): AdapterFormState {
  const defaults = buildDefaultAdapterForm(adapter.adapter_type, contract)
  const config = adapter.config
  const output = asJsonObject(config.output) || {}
  const advanced = asJsonObject(config.advanced) || {}
  const subscriptionConfig = asJsonObject(config.subscription) || {}
  const secretStatus = asJsonObject(adapter.secret_status) || {}
  const defaultPoint = createDefaultPointForm(contract)
  const defaultSubscription = createDefaultMqttSubscriptionForm(contract)
  const defaultMapping = createDefaultMqttMappingForm(contract)
  const defaultMonitoredItem = createDefaultMonitoredItemForm(contract)

  return {
    ...defaults,
    adapterId: adapter.adapter_id,
    name: adapter.name,
    adapterType: adapter.adapter_type,
    status: adapter.status,
    description: adapter.description || '',
    defaultAssetId: asString(output.asset_id, defaults.defaultAssetId),
    host: asString(config.host, defaults.host),
    port: toStringValue(config.port, defaults.port),
    unitId: toStringValue(config.unit_id, defaults.unitId),
    pollIntervalMs: toStringValue(config.poll_interval_ms, defaults.pollIntervalMs),
    serialPort: asString(config.serial_port, defaults.serialPort),
    baudrate: toStringValue(config.baudrate, defaults.baudrate),
    bytesize: toStringValue(config.bytesize, defaults.bytesize),
    parity: asString(config.parity, defaults.parity),
    stopbits: toStringValue(config.stopbits, defaults.stopbits),
    timeout: toStringValue(config.timeout, defaults.timeout),
    brokerHost: asString(config.broker_host, defaults.brokerHost),
    brokerPort: toStringValue(config.broker_port, defaults.brokerPort),
    clientId: asString(config.client_id, defaults.clientId),
    username: asString(config.username, defaults.username),
    password: '',
    passwordConfigured: isAdapterPasswordConfigured(secretStatus, config),
    qos: toStringValue(config.qos, defaults.qos),
    keepaliveSeconds: toStringValue(advanced.keepalive_seconds ?? config.keepalive_seconds, defaults.keepaliveSeconds),
    connectTimeoutSeconds: toStringValue(
      advanced.connect_timeout_seconds ?? config.connect_timeout_seconds,
      defaults.connectTimeoutSeconds,
    ),
    cleanStart: asBoolean(advanced.clean_start ?? config.clean_start, defaults.cleanStart),
    endpoint: asString(config.endpoint, defaults.endpoint),
    authMode: asString(config.auth_mode, defaults.authMode),
    publishingIntervalMs: toStringValue(subscriptionConfig.publishing_interval_ms, defaults.publishingIntervalMs),
    securityMode: asString(advanced.security_mode, defaults.securityMode),
    securityPolicy: asString(advanced.security_policy, defaults.securityPolicy),
    points: Array.isArray(config.points)
      ? config.points.map((point) => {
          const pointRecord = asJsonObject(point) || {}
          return {
            point_name: asString(pointRecord.point_name),
            memory_area: asString(pointRecord.memory_area, defaultPoint.memory_area),
            address: toStringValue(pointRecord.address),
            data_type: asString(pointRecord.data_type, defaultPoint.data_type),
            byte_order: asString(pointRecord.byte_order, defaultPoint.byte_order),
            word_order: asString(pointRecord.word_order, defaultPoint.word_order),
            scale: toStringValue(pointRecord.scale, defaultPoint.scale),
            offset: toStringValue(pointRecord.offset, defaultPoint.offset),
            unit: asString(pointRecord.unit),
            classification: asString(pointRecord.classification, defaultPoint.classification),
            event_type: asString(pointRecord.event_type),
          }
        })
      : defaults.points,
    subscriptions: Array.isArray(config.subscriptions)
      ? config.subscriptions.map((subscription) => {
          const subscriptionRecord = asJsonObject(subscription) || {}
          return {
            topic_filter: asString(subscriptionRecord.topic_filter),
            message_type: asString(subscriptionRecord.message_type, defaultSubscription.message_type),
            payload_format: asString(subscriptionRecord.payload_format, defaultSubscription.payload_format),
            asset_id_override: asString(subscriptionRecord.asset_id_override),
            qos: toStringValue(subscriptionRecord.qos, defaultSubscription.qos),
            mappings: Array.isArray(subscriptionRecord.mappings)
              ? subscriptionRecord.mappings.map((mapping) => {
                  const mappingRecord = asJsonObject(mapping) || {}
                  return {
                    json_field: asString(mappingRecord.json_field),
                    parameter: asString(mappingRecord.parameter),
                    unit: asString(mappingRecord.unit),
                    data_type: asString(mappingRecord.data_type, defaultMapping.data_type),
                  }
                })
              : [],
          }
        })
      : defaults.subscriptions,
    monitoredItems: Array.isArray(config.monitored_items)
      ? config.monitored_items.map((item) => {
          const itemRecord = asJsonObject(item) || {}
          return {
            node_id: asString(itemRecord.node_id),
            parameter: asString(itemRecord.parameter),
            unit: asString(itemRecord.unit),
            asset_id_override: asString(itemRecord.asset_id_override),
            sampling_interval_ms: toStringValue(itemRecord.sampling_interval_ms, defaultMonitoredItem.sampling_interval_ms),
            queue_size: toStringValue(itemRecord.queue_size, defaultMonitoredItem.queue_size),
            monitoring_mode: asString(itemRecord.monitoring_mode, defaultMonitoredItem.monitoring_mode),
          }
        })
      : defaults.monitoredItems,
    outputTopic: asString(output.topic, defaults.outputTopic),
    eventsTopic: asString(output.events_topic, defaults.eventsTopic),
    passthroughConfig: cloneJsonObject(config),
  }
}
