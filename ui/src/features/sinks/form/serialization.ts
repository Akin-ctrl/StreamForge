import type { CatalogSinkType, SinkCreatePayload, SinkItem, SinkUpdatePayload } from '../../../shared/api/client'
import { getInternalFieldKeys } from '../../../shared/config/catalog'
import { cloneJsonObject } from '../../../shared/config/json'
import type { JsonObject } from '../../../shared/types/json'
import { sinkToForm } from './hydration'
import { buildSinkSecrets, preserveSinkSecretState } from './secrets'
import type { SinkFormState } from './types'

function baseConfig(form: SinkFormState): JsonObject {
  const config = cloneJsonObject(form.passthroughConfig)
  for (const key of [
    'source_topic',
    'topic',
    'kafka_bootstrap',
    'group_id',
    'db_dsn',
    'table',
    'target_bootstrap',
    'target_topic',
    'url',
    'method',
    'route_type',
  ]) {
    delete config[key]
  }

  return config
}

function buildConfig(form: SinkFormState): JsonObject {
  const config = baseConfig(form)

  if (form.sinkType === 'timescaledb') {
    return {
      ...config,
      kafka_bootstrap: form.kafkaBootstrap,
      topic: form.sourceTopic,
      group_id: form.kafkaGroupId,
      table: form.table,
    }
  }

  if (form.sinkType === 'kafka') {
    return {
      ...config,
      source_topic: form.sourceTopic,
      target_bootstrap: form.targetBootstrap,
      target_topic: form.targetTopic,
    }
  }

  if (form.sinkType === 'http') {
    return {
      ...config,
      source_topic: form.sourceTopic,
      url: form.url,
      method: form.method,
    }
  }

  return {
    ...config,
    source_topic: form.sourceTopic,
    route_type: form.routeType,
  }
}

function stripInternalSinkConfig(config: JsonObject, contract?: CatalogSinkType): JsonObject {
  const safeConfig = cloneJsonObject(config)
  for (const fieldKey of getInternalFieldKeys(contract, 'ingress')) {
    delete safeConfig[fieldKey]
  }

  return safeConfig
}

export function buildSinkConfigJson(form: SinkFormState, contract?: CatalogSinkType): string {
  return JSON.stringify(stripInternalSinkConfig(buildConfig(form), contract), null, 2)
}

export function applySinkConfigJson(form: SinkFormState, text: string, contract?: CatalogSinkType): SinkFormState {
  const parsed = JSON.parse(text) as JsonObject
  const mergedConfig = {
    ...buildConfig(form),
    ...cloneJsonObject(parsed),
  }
  const nextForm = sinkToForm(
    {
      sink_id: form.sinkId,
      name: form.name,
      sink_type: form.sinkType,
      status: form.status,
      description: form.description || null,
      config: mergedConfig,
      secret_status: {},
      created_at: '',
      updated_at: '',
    } satisfies SinkItem,
    contract,
  )

  return preserveSinkSecretState(form, nextForm)
}

export function formToCreateSinkPayload(form: SinkFormState): SinkCreatePayload {
  const secrets = buildSinkSecrets(form)
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

export function formToUpdateSinkPayload(form: SinkFormState): SinkUpdatePayload {
  const secrets = buildSinkSecrets(form)
  return {
    name: form.name.trim(),
    sink_type: form.sinkType,
    status: form.status,
    config: buildConfig(form),
    ...(secrets ? { secrets } : {}),
    description: form.description.trim() || null,
  }
}
