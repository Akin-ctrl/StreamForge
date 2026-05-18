import type { AdapterItem } from '../../shared/api/client'

export type ModbusPointForm = {
  point_name: string
  memory_area: string
  address: string
  data_type: string
  byte_order: string
  word_order: string
  scale: string
  offset: string
  unit: string
  classification: string
  event_type: string
}

export type MqttMappingForm = {
  json_field: string
  parameter: string
  unit: string
  data_type: string
}

export type MqttSubscriptionForm = {
  topic_filter: string
  message_type: string
  payload_format: string
  asset_id_override: string
  qos: string
  mappings: MqttMappingForm[]
}

export type OpcuaMonitoredItemForm = {
  node_id: string
  parameter: string
  unit: string
  asset_id_override: string
  sampling_interval_ms: string
  queue_size: string
  monitoring_mode: string
}

export type AdapterFormState = {
  adapterId: string
  name: string
  adapterType: string
  status: string
  description: string
  defaultAssetId: string
  host: string
  port: string
  unitId: string
  pollIntervalMs: string
  serialPort: string
  baudrate: string
  bytesize: string
  parity: string
  stopbits: string
  timeout: string
  brokerHost: string
  brokerPort: string
  clientId: string
  username: string
  password: string
  passwordConfigured: boolean
  qos: string
  keepaliveSeconds: string
  connectTimeoutSeconds: string
  cleanStart: boolean
  endpoint: string
  authMode: string
  publishingIntervalMs: string
  securityMode: string
  securityPolicy: string
  points: ModbusPointForm[]
  subscriptions: MqttSubscriptionForm[]
  monitoredItems: OpcuaMonitoredItemForm[]
  outputTopic: string
  eventsTopic: string
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

function toStringValue(value: unknown, fallback = ''): string {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return String(value)
  }
  return asString(value, fallback)
}

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function parseNumber(value: string, fallback?: number) {
  if (!value.trim()) {
    return fallback
  }
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : fallback
}

function createDefaultPoint(): ModbusPointForm {
  return {
    point_name: '',
    memory_area: 'holding_register',
    address: '',
    data_type: 'float32',
    byte_order: 'big',
    word_order: 'big',
    scale: '1',
    offset: '0',
    unit: '',
    classification: 'telemetry',
    event_type: '',
  }
}

function createDefaultMqttMapping(): MqttMappingForm {
  return {
    json_field: '',
    parameter: '',
    unit: '',
    data_type: 'float32',
  }
}

function createDefaultMqttSubscription(): MqttSubscriptionForm {
  return {
    topic_filter: '',
    message_type: 'telemetry',
    payload_format: 'json',
    asset_id_override: '',
    qos: '1',
    mappings: [createDefaultMqttMapping()],
  }
}

function createDefaultMonitoredItem(): OpcuaMonitoredItemForm {
  return {
    node_id: '',
    parameter: '',
    unit: '',
    asset_id_override: '',
    sampling_interval_ms: '1000',
    queue_size: '1',
    monitoring_mode: 'reporting',
  }
}

export function buildDefaultAdapterForm(adapterType: string): AdapterFormState {
  return {
    adapterId: 'adapter-01',
    name: 'Adapter 01',
    adapterType,
    status: 'active',
    description: '',
    defaultAssetId: 'asset-01',
    host: 'modbus-simulator',
    port: '502',
    unitId: '1',
    pollIntervalMs: '1000',
    serialPort: '/dev/ttyUSB0',
    baudrate: '9600',
    bytesize: '8',
    parity: 'N',
    stopbits: '1',
    timeout: '1',
    brokerHost: 'mqtt-broker',
    brokerPort: '1883',
    clientId: 'streamforge-mqtt',
    username: '',
    password: '',
    passwordConfigured: false,
    qos: '1',
    keepaliveSeconds: '60',
    connectTimeoutSeconds: '5',
    cleanStart: true,
    endpoint: 'opc.tcp://opcua-server:4840',
    authMode: 'anonymous',
    publishingIntervalMs: '1000',
    securityMode: 'None',
    securityPolicy: 'None',
    points: [],
    subscriptions: [],
    monitoredItems: [],
    outputTopic: 'telemetry.raw',
    eventsTopic: 'events.raw',
  }
}

export function adapterToForm(adapter: AdapterItem): AdapterFormState {
  const defaults = buildDefaultAdapterForm(adapter.adapter_type)
  const config = adapter.config || {}
  const output = asRecord(config.output) || {}
  const advanced = asRecord(config.advanced) || {}
  const subscriptionConfig = asRecord(config.subscription) || {}
  const secretStatus = asRecord(adapter.secret_status) || {}
  const passwordStatus = asRecord(secretStatus.password)

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
    serialPort: asString(config.serial_port || config.port, defaults.serialPort),
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
    passwordConfigured:
      asBoolean(passwordStatus?.configured, false) ||
      (typeof config.password === 'string' && config.password.trim().length > 0),
    qos: toStringValue(config.qos, defaults.qos),
    keepaliveSeconds: toStringValue(advanced.keepalive_seconds ?? config.keepalive_seconds, defaults.keepaliveSeconds),
    connectTimeoutSeconds: toStringValue(advanced.connect_timeout_seconds ?? config.connect_timeout_seconds, defaults.connectTimeoutSeconds),
    cleanStart: asBoolean(advanced.clean_start ?? config.clean_start, defaults.cleanStart),
    endpoint: asString(config.endpoint, defaults.endpoint),
    authMode: asString(config.auth_mode, defaults.authMode),
    publishingIntervalMs: toStringValue(subscriptionConfig.publishing_interval_ms, defaults.publishingIntervalMs),
    securityMode: asString(advanced.security_mode ?? config.security_mode, defaults.securityMode),
    securityPolicy: asString(advanced.security_policy ?? config.security_policy, defaults.securityPolicy),
    points: Array.isArray(config.points)
      ? config.points.map((point) => {
          const pointRecord = asRecord(point) || {}
          return {
            point_name: asString(pointRecord.point_name),
            memory_area: asString(pointRecord.memory_area, 'holding_register'),
            address: toStringValue(pointRecord.address),
            data_type: asString(pointRecord.data_type, 'float32'),
            byte_order: asString(pointRecord.byte_order, 'big'),
            word_order: asString(pointRecord.word_order, 'big'),
            scale: toStringValue(pointRecord.scale, '1'),
            offset: toStringValue(pointRecord.offset, '0'),
            unit: asString(pointRecord.unit),
            classification: asString(pointRecord.classification, 'telemetry'),
            event_type: asString(pointRecord.event_type),
          }
        })
      : defaults.points,
    subscriptions: Array.isArray(config.subscriptions)
      ? config.subscriptions.map((subscription) => {
          const subscriptionRecord = asRecord(subscription) || {}
          return {
            topic_filter: asString(subscriptionRecord.topic_filter),
            message_type: asString(subscriptionRecord.message_type, 'telemetry'),
            payload_format: asString(subscriptionRecord.payload_format, 'json'),
            asset_id_override: asString(subscriptionRecord.asset_id_override),
            qos: toStringValue(subscriptionRecord.qos, '1'),
            mappings: Array.isArray(subscriptionRecord.mappings)
              ? subscriptionRecord.mappings.map((mapping) => {
                  const mappingRecord = asRecord(mapping) || {}
                  return {
                    json_field: asString(mappingRecord.json_field),
                    parameter: asString(mappingRecord.parameter),
                    unit: asString(mappingRecord.unit),
                    data_type: asString(mappingRecord.data_type, 'float32'),
                  }
                })
              : [],
          }
        })
      : defaults.subscriptions,
    monitoredItems: Array.isArray(config.monitored_items)
      ? config.monitored_items.map((item) => {
          const itemRecord = asRecord(item) || {}
          return {
            node_id: asString(itemRecord.node_id),
            parameter: asString(itemRecord.parameter),
            unit: asString(itemRecord.unit),
            asset_id_override: asString(itemRecord.asset_id_override),
            sampling_interval_ms: toStringValue(itemRecord.sampling_interval_ms, '1000'),
            queue_size: toStringValue(itemRecord.queue_size, '1'),
            monitoring_mode: asString(itemRecord.monitoring_mode, 'reporting'),
          }
        })
      : defaults.monitoredItems,
    outputTopic: asString(output.topic, defaults.outputTopic),
    eventsTopic: asString(output.events_topic, defaults.eventsTopic),
  }
}

function serializePoint(point: ModbusPointForm) {
  return {
    point_name: point.point_name,
    memory_area: point.memory_area,
    ...(parseNumber(point.address) !== undefined ? { address: parseNumber(point.address) } : {}),
    data_type: point.data_type,
    byte_order: point.byte_order,
    word_order: point.word_order,
    ...(parseNumber(point.scale, 1) !== undefined ? { scale: parseNumber(point.scale, 1) } : {}),
    ...(parseNumber(point.offset, 0) !== undefined ? { offset: parseNumber(point.offset, 0) } : {}),
    unit: point.unit,
    classification: point.classification,
    ...(point.event_type.trim() ? { event_type: point.event_type.trim() } : {}),
  }
}

function buildConfig(form: AdapterFormState): Record<string, unknown> {
  if (form.adapterType === 'modbus_tcp') {
    return {
      host: form.host,
      port: parseNumber(form.port, 502),
      unit_id: parseNumber(form.unitId, 1),
      poll_interval_ms: parseNumber(form.pollIntervalMs, 1000),
      points: form.points.filter((point) => point.point_name.trim()).map(serializePoint),
      output: {
        asset_id: form.defaultAssetId,
        topic: form.outputTopic,
        events_topic: form.eventsTopic,
      },
    }
  }

  if (form.adapterType === 'modbus_rtu') {
    return {
      serial_port: form.serialPort,
      baudrate: parseNumber(form.baudrate, 9600),
      bytesize: parseNumber(form.bytesize, 8),
      parity: form.parity,
      stopbits: parseNumber(form.stopbits, 1),
      timeout: parseNumber(form.timeout, 1),
      unit_id: parseNumber(form.unitId, 1),
      poll_interval_ms: parseNumber(form.pollIntervalMs, 1000),
      points: form.points.filter((point) => point.point_name.trim()).map(serializePoint),
      output: {
        asset_id: form.defaultAssetId,
        topic: form.outputTopic,
        events_topic: form.eventsTopic,
      },
    }
  }

  if (form.adapterType === 'mqtt') {
    return {
      broker_host: form.brokerHost,
      broker_port: parseNumber(form.brokerPort, 1883),
      client_id: form.clientId,
      username: form.username,
      qos: parseNumber(form.qos, 1),
      subscriptions: form.subscriptions
        .filter((subscription) => subscription.topic_filter.trim())
        .map((subscription) => ({
          topic_filter: subscription.topic_filter,
          message_type: subscription.message_type,
          payload_format: subscription.payload_format,
          ...(subscription.asset_id_override.trim() ? { asset_id_override: subscription.asset_id_override } : {}),
          qos: parseNumber(subscription.qos, 1),
          mappings: subscription.mappings
            .filter((mapping) => mapping.json_field.trim() && mapping.parameter.trim())
            .map((mapping) => ({
              json_field: mapping.json_field,
              parameter: mapping.parameter,
              unit: mapping.unit,
              data_type: mapping.data_type,
            })),
        })),
      output: {
        asset_id: form.defaultAssetId,
        topic: form.outputTopic,
        events_topic: form.eventsTopic,
      },
      advanced: {
        keepalive_seconds: parseNumber(form.keepaliveSeconds, 60),
        connect_timeout_seconds: parseNumber(form.connectTimeoutSeconds, 5),
        clean_start: form.cleanStart,
      },
    }
  }

  return {
    endpoint: form.endpoint,
    auth_mode: form.authMode,
    ...(form.username.trim() ? { username: form.username } : {}),
    subscription: {
      publishing_interval_ms: parseNumber(form.publishingIntervalMs, 1000),
    },
    monitored_items: form.monitoredItems
      .filter((item) => item.node_id.trim() && item.parameter.trim())
      .map((item) => ({
        node_id: item.node_id,
        parameter: item.parameter,
        unit: item.unit,
        ...(item.asset_id_override.trim() ? { asset_id_override: item.asset_id_override } : {}),
        sampling_interval_ms: parseNumber(item.sampling_interval_ms, 1000),
        queue_size: parseNumber(item.queue_size, 1),
        monitoring_mode: item.monitoring_mode,
      })),
    output: {
      asset_id: form.defaultAssetId,
      topic: form.outputTopic,
    },
    advanced: {
      security_mode: form.securityMode,
      security_policy: form.securityPolicy,
    },
  }
}

function buildSecrets(form: AdapterFormState): Record<string, string | null> | undefined {
  if (form.adapterType !== 'mqtt' && form.adapterType !== 'opcua') {
    return undefined
  }

  if (!form.password.trim()) {
    return undefined
  }

  return { password: form.password.trim() }
}

export function buildAdapterConfigJson(form: AdapterFormState): string {
  return JSON.stringify(buildConfig(form), null, 2)
}

export function applyAdapterConfigJson(form: AdapterFormState, text: string): AdapterFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  const nextForm = adapterToForm({
    adapter_id: form.adapterId,
    name: form.name,
    adapter_type: form.adapterType,
    status: form.status,
    description: form.description || null,
    config: parsed,
    secret_status: {},
    created_at: '',
    updated_at: '',
  })
  return {
    ...nextForm,
    password: '',
    passwordConfigured: form.passwordConfigured,
  }
}

export function formToCreateAdapterPayload(form: AdapterFormState) {
  const secrets = buildSecrets(form)
  return {
    adapter_id: form.adapterId.trim(),
    name: form.name.trim(),
    adapter_type: form.adapterType,
    status: form.status,
    config: buildConfig(form),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}

export function formToUpdateAdapterPayload(form: AdapterFormState) {
  const secrets = buildSecrets(form)
  return {
    name: form.name.trim(),
    status: form.status,
    config: buildConfig(form),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}

export function createDefaultPointForm() {
  return createDefaultPoint()
}

export function createDefaultMqttSubscriptionForm() {
  return createDefaultMqttSubscription()
}

export function createDefaultMqttMappingForm() {
  return createDefaultMqttMapping()
}

export function createDefaultMonitoredItemForm() {
  return createDefaultMonitoredItem()
}
