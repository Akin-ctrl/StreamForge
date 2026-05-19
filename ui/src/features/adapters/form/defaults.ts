import type { CatalogAdapterType } from '../../../shared/api/client'
import { getCatalogBooleanDefault, getCatalogStringDefault } from '../../../shared/config/catalog'
import type {
  AdapterFormState,
  ModbusPointForm,
  MqttMappingForm,
  MqttSubscriptionForm,
  OpcuaMonitoredItemForm,
} from './types'

export function createDefaultPointForm(contract?: CatalogAdapterType): ModbusPointForm {
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

export function createDefaultMqttMappingForm(contract?: CatalogAdapterType): MqttMappingForm {
  return {
    json_field: '',
    parameter: '',
    unit: '',
    data_type: getCatalogStringDefault(contract, 'subscriptions', 'data_type', 'float32'),
  }
}

export function createDefaultMqttSubscriptionForm(contract?: CatalogAdapterType): MqttSubscriptionForm {
  return {
    topic_filter: '',
    message_type: getCatalogStringDefault(contract, 'subscriptions', 'message_type', 'telemetry'),
    payload_format: getCatalogStringDefault(contract, 'subscriptions', 'payload_format', 'json'),
    asset_id_override: '',
    qos: getCatalogStringDefault(contract, 'subscriptions', 'qos', '1'),
    mappings: [createDefaultMqttMappingForm(contract)],
  }
}

export function createDefaultMonitoredItemForm(contract?: CatalogAdapterType): OpcuaMonitoredItemForm {
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

/**
 * Builds the editable adapter draft state from catalog defaults.
 * The page layer owns orchestration; protocol defaults stay here.
 */
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
