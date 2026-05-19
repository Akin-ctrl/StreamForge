import type { AdapterItem, CatalogAdapterType } from '../../shared/api/client'
import { getCatalogBooleanDefault, getCatalogStringDefault, getInternalFieldKeys } from '../../shared/config/catalog'

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
  passthroughConfig: Record<string, unknown>
}

function cloneConfig<T extends Record<string, unknown>>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
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

function createDefaultPoint(contract?: CatalogAdapterType): ModbusPointForm {
  return {
    point_name: '',
    memory_area: getCatalogStringDefault(contract, 'points', 'memory_area', 'holding_register'),
    address: '',
    data_type: getCatalogStringDefault(contract, 'points', 'data_type', 'float32'),
    byte_order: getCatalogStringDefault(contract, 'points', 'byte_order', 'big'),
    word_order: getCatalogStringDefault(contract, 'points', 'word_order', 'big'),
    scale: getCatalogStringDefault(contract, 'points', 'scale', '1'),
    offset: getCatalogStringDefault(contract, 'points', 'offset', '0'),
    unit: '',
    classification: getCatalogStringDefault(contract, 'points', 'classification', 'telemetry'),
    event_type: '',
  }
}

function createDefaultMqttMapping(contract?: CatalogAdapterType): MqttMappingForm {
  return {
    json_field: '',
    parameter: '',
    unit: '',
    data_type: getCatalogStringDefault(contract, 'subscriptions', 'data_type', 'float32'),
  }
}

function createDefaultMqttSubscription(contract?: CatalogAdapterType): MqttSubscriptionForm {
  return {
    topic_filter: '',
    message_type: getCatalogStringDefault(contract, 'subscriptions', 'message_type', 'telemetry'),
    payload_format: getCatalogStringDefault(contract, 'subscriptions', 'payload_format', 'json'),
    asset_id_override: '',
    qos: getCatalogStringDefault(contract, 'subscriptions', 'qos', '1'),
    mappings: [createDefaultMqttMapping(contract)],
  }
}

function createDefaultMonitoredItem(contract?: CatalogAdapterType): OpcuaMonitoredItemForm {
  return {
    node_id: '',
    parameter: '',
    unit: '',
    asset_id_override: '',
    sampling_interval_ms: getCatalogStringDefault(contract, 'monitored_items', 'sampling_interval_ms', '1000'),
    queue_size: getCatalogStringDefault(contract, 'monitored_items', 'queue_size', '1'),
    monitoring_mode: getCatalogStringDefault(contract, 'monitored_items', 'monitoring_mode', 'reporting'),
  }
}

export function buildDefaultAdapterForm(adapterType: string, contract?: CatalogAdapterType): AdapterFormState {
  return {
    adapterId: 'adapter-01',
    name: 'Adapter 01',
    adapterType,
    status: 'active',
    description: '',
    defaultAssetId: getCatalogStringDefault(contract, 'output', 'asset_id', 'asset-01'),
    host: getCatalogStringDefault(contract, 'connection', 'host', 'modbus-simulator'),
    port: getCatalogStringDefault(contract, 'connection', 'port', '502'),
    unitId: getCatalogStringDefault(contract, 'connection', 'unit_id', '1'),
    pollIntervalMs: getCatalogStringDefault(contract, 'connection', 'poll_interval_ms', '1000'),
    serialPort: getCatalogStringDefault(contract, 'connection', 'serial_port', '/dev/ttyUSB0'),
    baudrate: getCatalogStringDefault(contract, 'connection', 'baudrate', '9600'),
    bytesize: getCatalogStringDefault(contract, 'connection', 'bytesize', '8'),
    parity: getCatalogStringDefault(contract, 'connection', 'parity', 'N'),
    stopbits: getCatalogStringDefault(contract, 'connection', 'stopbits', '1'),
    timeout: getCatalogStringDefault(contract, 'connection', 'timeout', '1'),
    brokerHost: getCatalogStringDefault(contract, 'connection', 'broker_host', 'mqtt-broker'),
    brokerPort: getCatalogStringDefault(contract, 'connection', 'broker_port', '1883'),
    clientId: getCatalogStringDefault(contract, 'connection', 'client_id', 'streamforge-mqtt'),
    username: getCatalogStringDefault(contract, 'connection', 'username', ''),
    password: '',
    passwordConfigured: false,
    qos: getCatalogStringDefault(contract, 'subscriptions', 'qos', '1'),
    keepaliveSeconds: getCatalogStringDefault(contract, 'advanced', 'keepalive_seconds', '60'),
    connectTimeoutSeconds: getCatalogStringDefault(contract, 'advanced', 'connect_timeout_seconds', '5'),
    cleanStart: getCatalogBooleanDefault(contract, 'advanced', 'clean_start', true),
    endpoint: getCatalogStringDefault(contract, 'connection', 'endpoint', 'opc.tcp://opcua-server:4840'),
    authMode: getCatalogStringDefault(contract, 'connection', 'auth_mode', 'anonymous'),
    publishingIntervalMs: getCatalogStringDefault(contract, 'subscription', 'publishing_interval_ms', '1000'),
    securityMode: getCatalogStringDefault(contract, 'advanced', 'security_mode', 'None'),
    securityPolicy: getCatalogStringDefault(contract, 'advanced', 'security_policy', 'None'),
    points: [],
    subscriptions: [],
    monitoredItems: [],
    outputTopic: getCatalogStringDefault(contract, 'output', 'topic', 'telemetry.raw'),
    eventsTopic: getCatalogStringDefault(contract, 'output', 'events_topic', 'events.raw'),
    passthroughConfig: {},
  }
}

export function adapterToForm(adapter: AdapterItem, contract?: CatalogAdapterType): AdapterFormState {
  const defaults = buildDefaultAdapterForm(adapter.adapter_type, contract)
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
    securityMode: asString(advanced.security_mode, defaults.securityMode),
    securityPolicy: asString(advanced.security_policy, defaults.securityPolicy),
    points: Array.isArray(config.points)
      ? config.points.map((point) => {
          const pointRecord = asRecord(point) || {}
          return {
            point_name: asString(pointRecord.point_name),
            memory_area: asString(pointRecord.memory_area, createDefaultPoint(contract).memory_area),
            address: toStringValue(pointRecord.address),
            data_type: asString(pointRecord.data_type, createDefaultPoint(contract).data_type),
            byte_order: asString(pointRecord.byte_order, createDefaultPoint(contract).byte_order),
            word_order: asString(pointRecord.word_order, createDefaultPoint(contract).word_order),
            scale: toStringValue(pointRecord.scale, createDefaultPoint(contract).scale),
            offset: toStringValue(pointRecord.offset, createDefaultPoint(contract).offset),
            unit: asString(pointRecord.unit),
            classification: asString(pointRecord.classification, createDefaultPoint(contract).classification),
            event_type: asString(pointRecord.event_type),
          }
        })
      : defaults.points,
    subscriptions: Array.isArray(config.subscriptions)
      ? config.subscriptions.map((subscription) => {
          const subscriptionRecord = asRecord(subscription) || {}
          return {
            topic_filter: asString(subscriptionRecord.topic_filter),
            message_type: asString(subscriptionRecord.message_type, createDefaultMqttSubscription(contract).message_type),
            payload_format: asString(subscriptionRecord.payload_format, createDefaultMqttSubscription(contract).payload_format),
            asset_id_override: asString(subscriptionRecord.asset_id_override),
            qos: toStringValue(subscriptionRecord.qos, createDefaultMqttSubscription(contract).qos),
            mappings: Array.isArray(subscriptionRecord.mappings)
              ? subscriptionRecord.mappings.map((mapping) => {
                  const mappingRecord = asRecord(mapping) || {}
                  return {
                    json_field: asString(mappingRecord.json_field),
                    parameter: asString(mappingRecord.parameter),
                    unit: asString(mappingRecord.unit),
                    data_type: asString(mappingRecord.data_type, createDefaultMqttMapping(contract).data_type),
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
            sampling_interval_ms: toStringValue(itemRecord.sampling_interval_ms, createDefaultMonitoredItem(contract).sampling_interval_ms),
            queue_size: toStringValue(itemRecord.queue_size, createDefaultMonitoredItem(contract).queue_size),
            monitoring_mode: asString(itemRecord.monitoring_mode, createDefaultMonitoredItem(contract).monitoring_mode),
          }
        })
      : defaults.monitoredItems,
    outputTopic: asString(output.topic, defaults.outputTopic),
    eventsTopic: asString(output.events_topic, defaults.eventsTopic),
    passthroughConfig: cloneConfig(config),
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

function baseConfig(form: AdapterFormState) {
  const config = cloneConfig(form.passthroughConfig)
  for (const key of [
    'host',
    'port',
    'unit_id',
    'poll_interval_ms',
    'serial_port',
    'baudrate',
    'bytesize',
    'parity',
    'stopbits',
    'timeout',
    'broker_host',
    'broker_port',
    'client_id',
    'username',
    'qos',
    'endpoint',
    'auth_mode',
    'points',
    'registers',
    'coils',
    'subscriptions',
    'subscription',
    'monitored_items',
    'output',
    'advanced',
  ]) {
    delete config[key]
  }
  return config
}

function buildOutput(form: AdapterFormState, contract?: CatalogAdapterType) {
  const existingOutput = asRecord(form.passthroughConfig.output) || {}
  const output: Record<string, unknown> = {
    ...cloneConfig(existingOutput),
    asset_id: form.defaultAssetId,
    kafka_bootstrap: asString(existingOutput.kafka_bootstrap, getCatalogStringDefault(contract, 'output', 'kafka_bootstrap', 'kafka:9092')),
    topic: form.outputTopic,
  }

  if (form.eventsTopic.trim()) {
    output.events_topic = form.eventsTopic
  } else {
    delete output.events_topic
  }

  return output
}

function buildConfig(form: AdapterFormState, contract?: CatalogAdapterType): Record<string, unknown> {
  const config = baseConfig(form)

  if (form.adapterType === 'modbus_tcp') {
    return {
      ...config,
      host: form.host,
      port: parseNumber(form.port, 502),
      unit_id: parseNumber(form.unitId, 1),
      poll_interval_ms: parseNumber(form.pollIntervalMs, 1000),
      points: form.points.filter((point) => point.point_name.trim()).map(serializePoint),
      output: buildOutput(form, contract),
    }
  }

  if (form.adapterType === 'modbus_rtu') {
    return {
      ...config,
      serial_port: form.serialPort,
      baudrate: parseNumber(form.baudrate, 9600),
      bytesize: parseNumber(form.bytesize, 8),
      parity: form.parity,
      stopbits: parseNumber(form.stopbits, 1),
      timeout: parseNumber(form.timeout, 1),
      unit_id: parseNumber(form.unitId, 1),
      poll_interval_ms: parseNumber(form.pollIntervalMs, 1000),
      points: form.points.filter((point) => point.point_name.trim()).map(serializePoint),
      output: buildOutput(form, contract),
    }
  }

  if (form.adapterType === 'mqtt') {
    const existingAdvanced = asRecord(form.passthroughConfig.advanced) || {}
    return {
      ...config,
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
      output: buildOutput(form, contract),
      advanced: {
        ...cloneConfig(existingAdvanced),
        keepalive_seconds: parseNumber(form.keepaliveSeconds, 60),
        connect_timeout_seconds: parseNumber(form.connectTimeoutSeconds, 5),
        clean_start: form.cleanStart,
      },
    }
  }

  const existingAdvanced = asRecord(form.passthroughConfig.advanced) || {}
  const existingSubscription = asRecord(form.passthroughConfig.subscription) || {}
  return {
    ...config,
    endpoint: form.endpoint,
    auth_mode: form.authMode,
    ...(form.username.trim() ? { username: form.username } : {}),
    subscription: {
      ...cloneConfig(existingSubscription),
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
    output: buildOutput(form, contract),
    advanced: {
      ...cloneConfig(existingAdvanced),
      security_mode: form.securityMode,
      security_policy: form.securityPolicy,
    },
  }
}

function stripInternalAdapterConfig(config: Record<string, unknown>, contract?: CatalogAdapterType) {
  const safeConfig = cloneConfig(config)
  const output = asRecord(safeConfig.output)
  if (output) {
    for (const fieldKey of getInternalFieldKeys(contract, 'output')) {
      delete output[fieldKey]
    }
  }
  return safeConfig
}

function mergeAdapterConfigJson(
  adapterType: string,
  currentFullConfig: Record<string, unknown>,
  parsed: Record<string, unknown>,
): Record<string, unknown> {
  const merged = cloneConfig(currentFullConfig)
  const currentOutput = asRecord(currentFullConfig.output) || {}
  const parsedOutput = asRecord(parsed.output)
  merged.output = parsedOutput ? { ...cloneConfig(currentOutput), ...cloneConfig(parsedOutput) } : cloneConfig(currentOutput)

  if (adapterType === 'mqtt') {
    const currentAdvanced = asRecord(currentFullConfig.advanced) || {}
    const parsedAdvanced = asRecord(parsed.advanced)
    merged.advanced = parsedAdvanced ? { ...cloneConfig(currentAdvanced), ...cloneConfig(parsedAdvanced) } : cloneConfig(currentAdvanced)
  } else if (adapterType === 'opcua') {
    const currentAdvanced = asRecord(currentFullConfig.advanced) || {}
    const parsedAdvanced = asRecord(parsed.advanced)
    const currentSubscription = asRecord(currentFullConfig.subscription) || {}
    const parsedSubscription = asRecord(parsed.subscription)
    merged.advanced = parsedAdvanced ? { ...cloneConfig(currentAdvanced), ...cloneConfig(parsedAdvanced) } : cloneConfig(currentAdvanced)
    merged.subscription = parsedSubscription
      ? { ...cloneConfig(currentSubscription), ...cloneConfig(parsedSubscription) }
      : cloneConfig(currentSubscription)
  }

  return {
    ...merged,
    ...cloneConfig(parsed),
    output: merged.output,
    ...(adapterType === 'mqtt' ? { advanced: merged.advanced } : {}),
    ...(adapterType === 'opcua' ? { advanced: merged.advanced, subscription: merged.subscription } : {}),
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

export function buildAdapterConfigJson(form: AdapterFormState, contract?: CatalogAdapterType): string {
  return JSON.stringify(stripInternalAdapterConfig(buildConfig(form, contract), contract), null, 2)
}

export function applyAdapterConfigJson(
  form: AdapterFormState,
  text: string,
  contract?: CatalogAdapterType,
): AdapterFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  const mergedConfig = mergeAdapterConfigJson(form.adapterType, buildConfig(form, contract), parsed)
  const nextForm = adapterToForm(
    {
      adapter_id: form.adapterId,
      name: form.name,
      adapter_type: form.adapterType,
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
    password: '',
    passwordConfigured: form.passwordConfigured,
  }
}

export function formToCreateAdapterPayload(form: AdapterFormState, contract?: CatalogAdapterType) {
  const secrets = buildSecrets(form)
  return {
    adapter_id: form.adapterId.trim(),
    name: form.name.trim(),
    adapter_type: form.adapterType,
    status: form.status,
    config: buildConfig(form, contract),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}

export function formToUpdateAdapterPayload(form: AdapterFormState, contract?: CatalogAdapterType) {
  const secrets = buildSecrets(form)
  return {
    name: form.name.trim(),
    status: form.status,
    config: buildConfig(form, contract),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}

export function createDefaultPointForm(contract?: CatalogAdapterType) {
  return createDefaultPoint(contract)
}

export function createDefaultMqttSubscriptionForm(contract?: CatalogAdapterType) {
  return createDefaultMqttSubscription(contract)
}

export function createDefaultMqttMappingForm(contract?: CatalogAdapterType) {
  return createDefaultMqttMapping(contract)
}

export function createDefaultMonitoredItemForm(contract?: CatalogAdapterType) {
  return createDefaultMonitoredItem(contract)
}
