import type { JsonObject } from '../../../shared/types/json'

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
  passthroughConfig: JsonObject
}
