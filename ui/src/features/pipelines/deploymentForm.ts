import type { DeploymentItem } from '../../shared/api/client'

export type RangeRuleForm = {
  parameter: string
  min: string
  max: string
}

export type RateRuleForm = {
  parameter: string
  limit: string
}

export type GapRuleForm = {
  parameter: string
  seconds: string
}

export type AlarmRuleForm = {
  parameter: string
  type: string
  severity: string
  operator: string
  threshold: string
  message: string
  clearMessage: string
}

export type DeploymentFormState = {
  deploymentId: string
  name: string
  gatewayId: string
  status: string
  adapterIds: string[]
  sinkIds: string[]
  validationEnabled: boolean
  validationRawTopic: string
  validationCleanTopic: string
  validationDlqTopic: string
  validationAlarmTopic: string
  rangeRules: RangeRuleForm[]
  rateRules: RateRuleForm[]
  gapRules: GapRuleForm[]
  alarmRules: AlarmRuleForm[]
  eventsEnabled: boolean
  eventsRawTopic: string
  eventsCleanTopic: string
  eventsDlqTopic: string
  aggregatesEnabled: boolean
  aggregatesSourceTopic: string
  aggregate1sEnabled: boolean
  aggregate1sTopic: string
  aggregate1sWindowSeconds: string
  aggregate1minEnabled: boolean
  aggregate1minTopic: string
  aggregate1minWindowSeconds: string
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

function asBoolean(value: unknown, fallback = false): boolean {
  return typeof value === 'boolean' ? value : fallback
}

function asNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function toNumberString(value: unknown, fallback = ''): string {
  const numeric = asNumber(value)
  return numeric === null ? fallback : String(numeric)
}

function mapRulesObject(
  value: unknown,
  mapper: (parameter: string, config: unknown) => Record<string, string> | null,
): Record<string, string>[] {
  const record = asRecord(value)
  if (!record) {
    return []
  }

  return Object.entries(record)
    .map(([parameter, config]) => mapper(parameter, config))
    .filter((entry): entry is Record<string, string> => Boolean(entry))
}

export function buildDefaultDeploymentForm(): DeploymentFormState {
  return {
    deploymentId: 'deployment-demo-01',
    name: 'Demo Deployment',
    gatewayId: 'gateway-demo-01',
    status: 'active',
    adapterIds: [],
    sinkIds: [],
    validationEnabled: true,
    validationRawTopic: 'telemetry.raw',
    validationCleanTopic: 'telemetry.clean',
    validationDlqTopic: 'dlq.telemetry',
    validationAlarmTopic: 'alarms.raw',
    rangeRules: [],
    rateRules: [],
    gapRules: [],
    alarmRules: [],
    eventsEnabled: true,
    eventsRawTopic: 'events.raw',
    eventsCleanTopic: 'events.clean',
    eventsDlqTopic: 'dlq.events',
    aggregatesEnabled: true,
    aggregatesSourceTopic: 'telemetry.clean',
    aggregate1sEnabled: true,
    aggregate1sTopic: 'telemetry.1s',
    aggregate1sWindowSeconds: '1',
    aggregate1minEnabled: true,
    aggregate1minTopic: 'telemetry.1min',
    aggregate1minWindowSeconds: '60',
  }
}

export function deploymentToForm(deployment: DeploymentItem): DeploymentFormState {
  const defaults = buildDefaultDeploymentForm()
  const validation = asRecord(deployment.validation_config) || {}
  const events = asRecord(deployment.events_config) || {}
  const aggregates = asRecord(deployment.aggregates_config) || {}
  const resolutions = asRecord(aggregates.resolutions) || {}
  const aggregate1s = asRecord(resolutions['1s']) || {}
  const aggregate1min = asRecord(resolutions['1min']) || {}

  return {
    deploymentId: deployment.deployment_id,
    name: deployment.name,
    gatewayId: deployment.gateway_id,
    status: deployment.status,
    adapterIds: [...deployment.adapter_ids],
    sinkIds: [...deployment.sink_ids],
    validationEnabled: asBoolean(validation.enabled, defaults.validationEnabled),
    validationRawTopic: asString(validation.raw_topic, defaults.validationRawTopic),
    validationCleanTopic: asString(validation.clean_topic, defaults.validationCleanTopic),
    validationDlqTopic: asString(validation.dlq_topic, defaults.validationDlqTopic),
    validationAlarmTopic: asString(validation.alarm_topic, defaults.validationAlarmTopic),
    rangeRules: mapRulesObject(validation.ranges, (parameter, config) => {
      const range = asRecord(config)
      if (!range) {
        return null
      }
      return {
        parameter,
        min: toNumberString(range.min),
        max: toNumberString(range.max),
      }
    }) as RangeRuleForm[],
    rateRules: mapRulesObject(validation.rate_of_change, (parameter, config) => ({
      parameter,
      limit: toNumberString(config),
    })) as RateRuleForm[],
    gapRules: mapRulesObject(validation.gap_detection, (parameter, config) => ({
      parameter,
      seconds: toNumberString(config),
    })) as GapRuleForm[],
    alarmRules: Array.isArray(validation.alarm_rules)
      ? validation.alarm_rules.map((rule) => {
          const alarmRule = asRecord(rule) || {}
          return {
            parameter: asString(alarmRule.parameter),
            type: asString(alarmRule.type),
            severity: asString(alarmRule.severity, 'HIGH'),
            operator: asString(alarmRule.operator, '>'),
            threshold: toNumberString(alarmRule.threshold),
            message: asString(alarmRule.message),
            clearMessage: asString(alarmRule.clear_message),
          }
        })
      : [],
    eventsEnabled: asBoolean(events.enabled, defaults.eventsEnabled),
    eventsRawTopic: asString(events.raw_topic, defaults.eventsRawTopic),
    eventsCleanTopic: asString(events.clean_topic, defaults.eventsCleanTopic),
    eventsDlqTopic: asString(events.dlq_topic, defaults.eventsDlqTopic),
    aggregatesEnabled: asBoolean(aggregates.enabled, defaults.aggregatesEnabled),
    aggregatesSourceTopic: asString(aggregates.source_topic, defaults.aggregatesSourceTopic),
    aggregate1sEnabled: asBoolean(aggregate1s.enabled, defaults.aggregate1sEnabled),
    aggregate1sTopic: asString(aggregate1s.topic, defaults.aggregate1sTopic),
    aggregate1sWindowSeconds: toNumberString(aggregate1s.window_seconds, defaults.aggregate1sWindowSeconds),
    aggregate1minEnabled: asBoolean(aggregate1min.enabled, defaults.aggregate1minEnabled),
    aggregate1minTopic: asString(aggregate1min.topic, defaults.aggregate1minTopic),
    aggregate1minWindowSeconds: toNumberString(aggregate1min.window_seconds, defaults.aggregate1minWindowSeconds),
  }
}

function toOptionalNumber(value: string): number | null {
  if (!value.trim()) {
    return null
  }

  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function buildValidationConfig(form: DeploymentFormState): Record<string, unknown> {
  const ranges = Object.fromEntries(
    form.rangeRules
      .filter((rule) => rule.parameter.trim())
      .map((rule) => [
        rule.parameter.trim(),
        {
          ...(toOptionalNumber(rule.min) !== null ? { min: toOptionalNumber(rule.min) } : {}),
          ...(toOptionalNumber(rule.max) !== null ? { max: toOptionalNumber(rule.max) } : {}),
        },
      ]),
  )

  const rateOfChange = Object.fromEntries(
    form.rateRules
      .filter((rule) => rule.parameter.trim() && toOptionalNumber(rule.limit) !== null)
      .map((rule) => [rule.parameter.trim(), toOptionalNumber(rule.limit)]),
  )

  const gapDetection = Object.fromEntries(
    form.gapRules
      .filter((rule) => rule.parameter.trim() && toOptionalNumber(rule.seconds) !== null)
      .map((rule) => [rule.parameter.trim(), toOptionalNumber(rule.seconds)]),
  )

  const alarmRules = form.alarmRules
    .filter((rule) => rule.parameter.trim() && rule.type.trim())
    .map((rule) => ({
      parameter: rule.parameter.trim(),
      type: rule.type.trim(),
      severity: rule.severity,
      operator: rule.operator,
      ...(toOptionalNumber(rule.threshold) !== null ? { threshold: toOptionalNumber(rule.threshold) } : {}),
      ...(rule.message.trim() ? { message: rule.message.trim() } : {}),
      ...(rule.clearMessage.trim() ? { clear_message: rule.clearMessage.trim() } : {}),
    }))

  return {
    enabled: form.validationEnabled,
    raw_topic: form.validationRawTopic,
    clean_topic: form.validationCleanTopic,
    dlq_topic: form.validationDlqTopic,
    alarm_topic: form.validationAlarmTopic,
    ranges,
    rate_of_change: rateOfChange,
    gap_detection: gapDetection,
    alarm_rules: alarmRules,
  }
}

function buildEventsConfig(form: DeploymentFormState): Record<string, unknown> {
  return {
    enabled: form.eventsEnabled,
    raw_topic: form.eventsRawTopic,
    clean_topic: form.eventsCleanTopic,
    dlq_topic: form.eventsDlqTopic,
  }
}

function buildAggregatesConfig(form: DeploymentFormState): Record<string, unknown> {
  return {
    enabled: form.aggregatesEnabled,
    source_topic: form.aggregatesSourceTopic,
    resolutions: {
      '1s': {
        enabled: form.aggregate1sEnabled,
        topic: form.aggregate1sTopic,
        window_seconds: toOptionalNumber(form.aggregate1sWindowSeconds) ?? 1,
      },
      '1min': {
        enabled: form.aggregate1minEnabled,
        topic: form.aggregate1minTopic,
        window_seconds: toOptionalNumber(form.aggregate1minWindowSeconds) ?? 60,
      },
    },
  }
}

export function formToCreatePayload(form: DeploymentFormState) {
  return {
    deployment_id: form.deploymentId.trim(),
    name: form.name.trim(),
    gateway_id: form.gatewayId,
    status: form.status,
    adapter_ids: form.adapterIds,
    sink_ids: form.sinkIds,
    validation_config: buildValidationConfig(form),
    events_config: buildEventsConfig(form),
    aggregates_config: buildAggregatesConfig(form),
  }
}

export function formToUpdatePayload(form: DeploymentFormState) {
  return {
    name: form.name.trim(),
    status: form.status,
    adapter_ids: form.adapterIds,
    sink_ids: form.sinkIds,
    validation_config: buildValidationConfig(form),
    events_config: buildEventsConfig(form),
    aggregates_config: buildAggregatesConfig(form),
  }
}

export function buildValidationJson(form: DeploymentFormState): string {
  return JSON.stringify(buildValidationConfig(form), null, 2)
}

export function buildEventsJson(form: DeploymentFormState): string {
  return JSON.stringify(buildEventsConfig(form), null, 2)
}

export function buildAggregatesJson(form: DeploymentFormState): string {
  return JSON.stringify(buildAggregatesConfig(form), null, 2)
}

export function applyValidationJson(form: DeploymentFormState, text: string): DeploymentFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  return {
    ...form,
    ...deploymentToForm({
      deployment_id: form.deploymentId,
      name: form.name,
      gateway_id: form.gatewayId,
      status: form.status,
      adapter_ids: form.adapterIds,
      sink_ids: form.sinkIds,
      validation_config: parsed,
      events_config: buildEventsConfig(form),
      aggregates_config: buildAggregatesConfig(form),
      created_at: '',
      updated_at: '',
    }),
  }
}

export function applyEventsJson(form: DeploymentFormState, text: string): DeploymentFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  return {
    ...form,
    ...deploymentToForm({
      deployment_id: form.deploymentId,
      name: form.name,
      gateway_id: form.gatewayId,
      status: form.status,
      adapter_ids: form.adapterIds,
      sink_ids: form.sinkIds,
      validation_config: buildValidationConfig(form),
      events_config: parsed,
      aggregates_config: buildAggregatesConfig(form),
      created_at: '',
      updated_at: '',
    }),
  }
}

export function applyAggregatesJson(form: DeploymentFormState, text: string): DeploymentFormState {
  const parsed = JSON.parse(text) as Record<string, unknown>
  return {
    ...form,
    ...deploymentToForm({
      deployment_id: form.deploymentId,
      name: form.name,
      gateway_id: form.gatewayId,
      status: form.status,
      adapter_ids: form.adapterIds,
      sink_ids: form.sinkIds,
      validation_config: buildValidationConfig(form),
      events_config: buildEventsConfig(form),
      aggregates_config: parsed,
      created_at: '',
      updated_at: '',
    }),
  }
}
