/**
 * Serialization helpers for adapter authoring.
 *
 * The form keeps a passthrough JSON fragment so we can preserve catalog-driven
 * advanced fields that are not rendered directly in the current editor. These
 * helpers rebuild the canonical editable sections, then merge back the safe
 * passthrough state without reintroducing secrets or internal-only defaults.
 */
import type { AdapterCreatePayload, AdapterItem, AdapterUpdatePayload, CatalogAdapterType } from '../../../shared/api/client'
import { getCatalogStringDefault, getInternalFieldKeys } from '../../../shared/config/catalog'
import { asJsonObject, asString, cloneJsonObject, parseNumberInput } from '../../../shared/config/json'
import type { JsonObject } from '../../../shared/types/json'
import { buildAdapterSecrets, preserveAdapterSecretState } from './secrets'
import { adapterToForm } from './hydration'
import type { AdapterFormState, ModbusPointForm } from './types'

function serializePoint(point: ModbusPointForm): JsonObject {
  return {
    point_name: point.point_name,
    memory_area: point.memory_area,
    ...(parseNumberInput(point.address) !== undefined ? { address: parseNumberInput(point.address) } : {}),
    data_type: point.data_type,
    byte_order: point.byte_order,
    word_order: point.word_order,
    ...(parseNumberInput(point.scale, 1) !== undefined ? { scale: parseNumberInput(point.scale, 1) } : {}),
    ...(parseNumberInput(point.offset, 0) !== undefined ? { offset: parseNumberInput(point.offset, 0) } : {}),
    unit: point.unit,
    classification: point.classification,
    ...(point.event_type.trim() ? { event_type: point.event_type.trim() } : {}),
  }
}

function baseConfig(form: AdapterFormState): JsonObject {
  const config = cloneJsonObject(form.passthroughConfig)
  // These keys are rebuilt from explicit form state so stale passthrough values
  // do not win during edits or JSON fallback application.
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

function buildOutput(form: AdapterFormState, contract?: CatalogAdapterType): JsonObject {
  const existingOutput = asJsonObject(form.passthroughConfig.output) || {}
  const output: JsonObject = {
    ...cloneJsonObject(existingOutput),
    asset_id: form.defaultAssetId,
    kafka_bootstrap: asString(
      existingOutput.kafka_bootstrap,
      getCatalogStringDefault(contract, 'output', 'kafka_bootstrap', 'kafka:9092'),
    ),
    topic: form.outputTopic,
  }

  if (form.eventsTopic.trim()) {
    output.events_topic = form.eventsTopic
  } else {
    delete output.events_topic
  }

  return output
}

function buildConfig(form: AdapterFormState, contract?: CatalogAdapterType): JsonObject {
  const config = baseConfig(form)

  if (form.adapterType === 'modbus_tcp') {
    return {
      ...config,
      host: form.host,
      port: parseNumberInput(form.port, 502) ?? 502,
      unit_id: parseNumberInput(form.unitId, 1) ?? 1,
      poll_interval_ms: parseNumberInput(form.pollIntervalMs, 1000) ?? 1000,
      points: form.points.filter((point) => point.point_name.trim()).map(serializePoint),
      output: buildOutput(form, contract),
    }
  }

  if (form.adapterType === 'modbus_rtu') {
    return {
      ...config,
      serial_port: form.serialPort,
      baudrate: parseNumberInput(form.baudrate, 9600) ?? 9600,
      bytesize: parseNumberInput(form.bytesize, 8) ?? 8,
      parity: form.parity,
      stopbits: parseNumberInput(form.stopbits, 1) ?? 1,
      timeout: parseNumberInput(form.timeout, 1) ?? 1,
      unit_id: parseNumberInput(form.unitId, 1) ?? 1,
      poll_interval_ms: parseNumberInput(form.pollIntervalMs, 1000) ?? 1000,
      points: form.points.filter((point) => point.point_name.trim()).map(serializePoint),
      output: buildOutput(form, contract),
    }
  }

  if (form.adapterType === 'mqtt') {
    const existingAdvanced = asJsonObject(form.passthroughConfig.advanced) || {}
    return {
      ...config,
      broker_host: form.brokerHost,
      broker_port: parseNumberInput(form.brokerPort, 1883) ?? 1883,
      client_id: form.clientId,
      username: form.username,
      qos: parseNumberInput(form.qos, 1) ?? 1,
      subscriptions: form.subscriptions
        .filter((subscription) => subscription.topic_filter.trim())
        .map((subscription) => ({
          topic_filter: subscription.topic_filter,
          message_type: subscription.message_type,
          payload_format: subscription.payload_format,
          ...(subscription.asset_id_override.trim() ? { asset_id_override: subscription.asset_id_override } : {}),
          qos: parseNumberInput(subscription.qos, 1) ?? 1,
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
        ...cloneJsonObject(existingAdvanced),
        keepalive_seconds: parseNumberInput(form.keepaliveSeconds, 60) ?? 60,
        connect_timeout_seconds: parseNumberInput(form.connectTimeoutSeconds, 5) ?? 5,
        clean_start: form.cleanStart,
      },
    }
  }

  const existingAdvanced = asJsonObject(form.passthroughConfig.advanced) || {}
  const existingSubscription = asJsonObject(form.passthroughConfig.subscription) || {}
  return {
    ...config,
    endpoint: form.endpoint,
    auth_mode: form.authMode,
    ...(form.username.trim() ? { username: form.username } : {}),
    subscription: {
      ...cloneJsonObject(existingSubscription),
      publishing_interval_ms: parseNumberInput(form.publishingIntervalMs, 1000) ?? 1000,
    },
    monitored_items: form.monitoredItems
      .filter((item) => item.node_id.trim() && item.parameter.trim())
      .map((item) => ({
        node_id: item.node_id,
        parameter: item.parameter,
        unit: item.unit,
        ...(item.asset_id_override.trim() ? { asset_id_override: item.asset_id_override } : {}),
        sampling_interval_ms: parseNumberInput(item.sampling_interval_ms, 1000) ?? 1000,
        queue_size: parseNumberInput(item.queue_size, 1) ?? 1,
        monitoring_mode: item.monitoring_mode,
      })),
    output: buildOutput(form, contract),
    advanced: {
      ...cloneJsonObject(existingAdvanced),
      security_mode: form.securityMode,
      security_policy: form.securityPolicy,
    },
  }
}

function stripInternalAdapterConfig(config: JsonObject, contract?: CatalogAdapterType): JsonObject {
  const safeConfig = cloneJsonObject(config)
  const output = asJsonObject(safeConfig.output)
  if (output) {
    for (const fieldKey of getInternalFieldKeys(contract, 'output')) {
      delete output[fieldKey]
    }
  }

  return safeConfig
}

function mergeConfigSection(current: JsonObject, parsedSection: unknown): JsonObject {
  const parsedRecord = asJsonObject(parsedSection)
  return parsedRecord ? { ...cloneJsonObject(current), ...cloneJsonObject(parsedRecord) } : cloneJsonObject(current)
}

function mergeAdapterConfigJson(adapterType: string, currentFullConfig: JsonObject, parsed: JsonObject): JsonObject {
  const merged = cloneJsonObject(currentFullConfig)
  const currentOutput = asJsonObject(currentFullConfig.output) || {}
  merged.output = mergeConfigSection(currentOutput, parsed.output)

  // MQTT and OPC UA carry nested advanced sections that are not fully surfaced
  // in the default editor. Merge them explicitly so advanced JSON edits do not
  // wipe unrelated nested settings.
  if (adapterType === 'mqtt') {
    const currentAdvanced = asJsonObject(currentFullConfig.advanced) || {}
    merged.advanced = mergeConfigSection(currentAdvanced, parsed.advanced)
  } else if (adapterType === 'opcua') {
    const currentAdvanced = asJsonObject(currentFullConfig.advanced) || {}
    const currentSubscription = asJsonObject(currentFullConfig.subscription) || {}
    merged.advanced = mergeConfigSection(currentAdvanced, parsed.advanced)
    merged.subscription = mergeConfigSection(currentSubscription, parsed.subscription)
  }

  return {
    ...merged,
    ...cloneJsonObject(parsed),
    output: merged.output,
    ...(adapterType === 'mqtt' ? { advanced: merged.advanced } : {}),
    ...(adapterType === 'opcua' ? { advanced: merged.advanced, subscription: merged.subscription } : {}),
  }
}

export function buildAdapterConfigJson(form: AdapterFormState, contract?: CatalogAdapterType): string {
  return JSON.stringify(stripInternalAdapterConfig(buildConfig(form, contract), contract), null, 2)
}

export function applyAdapterConfigJson(
  form: AdapterFormState,
  text: string,
  contract?: CatalogAdapterType,
): AdapterFormState {
  const parsed = JSON.parse(text) as JsonObject
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
    } satisfies AdapterItem,
    contract,
  )

  return preserveAdapterSecretState(form, nextForm)
}

export function formToCreateAdapterPayload(form: AdapterFormState, contract?: CatalogAdapterType): AdapterCreatePayload {
  const secrets = buildAdapterSecrets(form)
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

export function formToUpdateAdapterPayload(form: AdapterFormState, contract?: CatalogAdapterType): AdapterUpdatePayload {
  const secrets = buildAdapterSecrets(form)
  return {
    name: form.name.trim(),
    status: form.status,
    config: buildConfig(form, contract),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}
