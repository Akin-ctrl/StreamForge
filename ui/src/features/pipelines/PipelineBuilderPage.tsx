import { useEffect, useMemo, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { useLocation, useNavigate } from 'react-router-dom'

import {
  CatalogAdapterType,
  CatalogSinkType,
  GatewayItem,
  SinkItem,
  createPipeline,
  createSink,
  getCatalog,
  listGateways,
  listSinks,
  listPipelines,
  PipelineItem,
  updatePipeline,
} from '../../shared/api/client'
import { PipelineComposerState } from '../../shared/config/deployments'

type RegisterInput = {
  address: number
  param: string
  type: string
  unit: string
}

type MqttSubscriptionInput = {
  topic: string
  message_type: string
  payload_format: string
  asset_id: string
}

type MqttMappingInput = {
  topic: string
  field: string
  parameter: string
  unit: string
}

type OpcuaMonitoredItemInput = {
  node_id: string
  parameter: string
  unit: string
  asset_id: string
}

type ValidationPerParam = {
  min: number
  max: number
  rate_of_change: number
  gap_detection: number
  alarm_enabled: boolean
  alarm_threshold: number
  alarm_severity: string
}

type BuilderFormValues = {
  pipelineName: string
  gatewayId: string
  adapter: {
    adapter_id: string
    adapter_type: string
    config_values: Record<string, string | number>
    registers: RegisterInput[]
    mqtt_subscriptions: MqttSubscriptionInput[]
    mqtt_mappings: MqttMappingInput[]
    opcua_monitored_items: OpcuaMonitoredItemInput[]
  }
  output: {
    create_new_sink: boolean
    sink_id: string
    sink_type: string
    sink_status: string
    kafka_bootstrap: string
    topic: string
    asset_id: string
    group_id: string
    db_dsn: string
    table: string
  }
  validationEnabled: boolean
  rawTopic: string
  cleanTopic: string
  dlqTopic: string
  validationByParam: Record<string, ValidationPerParam>
}

type PipelineBuilderProps = {
  availableAdapters?: CatalogAdapterType[]
  availableSinkCatalog?: CatalogSinkType[]
  availableSinks?: SinkItem[]
}

const DEFAULT_PARAM_RULES: ValidationPerParam = {
  min: -50,
  max: 500,
  rate_of_change: 20,
  gap_detection: 5,
  alarm_enabled: false,
  alarm_threshold: 100,
  alarm_severity: 'HIGH',
}

const BUILT_IN_ADAPTERS: CatalogAdapterType[] = [
  {
    adapter_type: 'modbus_tcp',
    label: 'Modbus TCP',
    supports_registers: true,
    fields: [
      { key: 'host', label: 'Host', input_type: 'text', required: true, default: 'modbus-simulator' },
      { key: 'port', label: 'Port', input_type: 'number', required: true, default: 5020 },
      { key: 'unit_id', label: 'Unit ID', input_type: 'number', required: true, default: 1 },
      { key: 'poll_interval_ms', label: 'Poll Interval (ms)', input_type: 'number', required: true, default: 1000 },
    ],
  },
  {
    adapter_type: 'modbus_rtu',
    label: 'Modbus RTU',
    supports_registers: true,
    fields: [
      { key: 'port', label: 'Serial Port', input_type: 'text', required: true, default: '/dev/ttyUSB0' },
      { key: 'baudrate', label: 'Baud Rate', input_type: 'number', required: true, default: 9600 },
      { key: 'bytesize', label: 'Data Bits', input_type: 'number', required: true, default: 8 },
      { key: 'parity', label: 'Parity', input_type: 'text', required: true, default: 'N' },
      { key: 'stopbits', label: 'Stop Bits', input_type: 'number', required: true, default: 1 },
      { key: 'timeout', label: 'Timeout (s)', input_type: 'number', required: true, default: 1 },
      { key: 'unit_id', label: 'Unit ID', input_type: 'number', required: true, default: 1 },
      { key: 'poll_interval_ms', label: 'Poll Interval (ms)', input_type: 'number', required: true, default: 1000 },
    ],
  },
  {
    adapter_type: 'mqtt',
    label: 'MQTT',
    supports_registers: false,
    fields: [
      { key: 'broker_host', label: 'Broker Host', input_type: 'text', required: true, default: 'mqtt-broker' },
      { key: 'broker_port', label: 'Broker Port', input_type: 'number', required: true, default: 1883 },
      { key: 'client_id', label: 'Client ID', input_type: 'text', required: true, default: 'streamforge-mqtt' },
      { key: 'qos', label: 'QoS', input_type: 'number', required: true, default: 1 },
      { key: 'keepalive_seconds', label: 'Keepalive (s)', input_type: 'number', required: true, default: 60 },
      { key: 'poll_interval_ms', label: 'Throttle Interval Hint (ms)', input_type: 'number', required: true, default: 1000 },
    ],
  },
  {
    adapter_type: 'opcua',
    label: 'OPC UA',
    supports_registers: false,
    fields: [
      { key: 'endpoint', label: 'Endpoint', input_type: 'text', required: true, default: 'opc.tcp://opcua-server:4840' },
      { key: 'security_mode', label: 'Security Mode', input_type: 'text', required: true, default: 'None' },
      { key: 'security_policy', label: 'Security Policy', input_type: 'text', required: true, default: 'None' },
      { key: 'username', label: 'Username', input_type: 'text', required: false, default: '' },
      { key: 'password', label: 'Password', input_type: 'text', required: false, default: '' },
      { key: 'subscription_interval_ms', label: 'Subscription Interval (ms)', input_type: 'number', required: true, default: 1000 },
      { key: 'poll_interval_ms', label: 'Throttle Interval Hint (ms)', input_type: 'number', required: true, default: 1000 },
    ],
  },
]
const BUILT_IN_SINKS: CatalogSinkType[] = [
  {
    sink_type: 'timescaledb',
    label: 'TimescaleDB',
    fields: [
      { key: 'kafka_bootstrap', label: 'Kafka Bootstrap', input_type: 'text', required: true, default: 'kafka:9092' },
      { key: 'topic', label: 'Topic', input_type: 'text', required: true, default: 'telemetry.clean' },
      { key: 'group_id', label: 'Consumer Group', input_type: 'text', required: true, default: 'sf-sink-timescaledb' },
      { key: 'db_dsn', label: 'Database DSN', input_type: 'text', required: true, default: 'postgresql://streamforge:streamforge@timescaledb:5432/streamforge' },
      { key: 'table', label: 'Table', input_type: 'text', required: true, default: 'telemetry_clean' },
    ],
  },
]

function normalizeCatalogFieldValues(
  fields: Array<{ key: string; input_type: string; default?: string | number | boolean | null }>,
  values: Record<string, string | number>,
): Record<string, string | number> {
  const next: Record<string, string | number> = {}

  for (const field of fields) {
    const rawValue = values[field.key]
    const fallback = typeof field.default === 'string' || typeof field.default === 'number' ? field.default : undefined

    if (field.input_type === 'number') {
      const candidate = rawValue === '' || rawValue === undefined || rawValue === null ? fallback : rawValue
      const numericValue = typeof candidate === 'number' ? candidate : Number(candidate)
      if (Number.isFinite(numericValue)) {
        next[field.key] = numericValue
      } else if (typeof fallback === 'number') {
        next[field.key] = fallback
      }
      continue
    }

    const textValue = rawValue === undefined || rawValue === null || rawValue === '' ? fallback : rawValue
    if (typeof textValue === 'string' || typeof textValue === 'number') {
      next[field.key] = textValue
    }
  }

  return next
}

function registerWidth(type: string): number {
  return type === 'float32' ? 2 : 1
}

function nextRegisterAddress(registers: RegisterInput[]): number {
  if (registers.length === 0) {
    return 40001
  }

  const highestEnd = registers.reduce((highest, register) => {
    const width = registerWidth(register.type)
    return Math.max(highest, Number(register.address) + width - 1)
  }, 40000)

  return highestEnd + 1
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }
  return value as Record<string, unknown>
}

function defaultBuilderValues(): BuilderFormValues {
  return {
    pipelineName: 'demo-pipeline-ui',
    gatewayId: '',
    adapter: {
      adapter_id: 'adapter-01',
      adapter_type: '',
      config_values: {},
      registers: [{ address: 40001, param: 'temperature', type: 'float32', unit: 'celsius' }],
      mqtt_subscriptions: [{ topic: 'factory/line1/telemetry', message_type: 'telemetry', payload_format: 'json', asset_id: 'asset-01' }],
      mqtt_mappings: [{ topic: 'factory/line1/telemetry', field: 'temperature', parameter: 'temperature', unit: 'celsius' }],
      opcua_monitored_items: [{ node_id: 'ns=2;s=Line1.Temperature', parameter: 'temperature', unit: 'celsius', asset_id: 'asset-01' }],
    },
    output: {
      create_new_sink: true,
      sink_id: '',
      sink_type: 'timescaledb',
      sink_status: 'active',
      kafka_bootstrap: 'kafka:9092',
      topic: 'telemetry.raw',
      asset_id: 'asset-01',
      group_id: 'sf-sink-timescaledb',
      db_dsn: 'postgresql://streamforge:streamforge@timescaledb:5432/streamforge',
      table: 'telemetry_clean',
    },
    validationEnabled: true,
    rawTopic: 'telemetry.raw',
    cleanTopic: 'telemetry.clean',
    dlqTopic: 'dlq.telemetry',
    validationByParam: {},
  }
}

/**
 * Step-based pipeline wizard.
 * Step 1: Adapter, Step 2: Sink, Step 3: Validation, Step 4: Review.
 */
export function PipelineBuilderPage({ availableAdapters, availableSinkCatalog, availableSinks }: PipelineBuilderProps = {}) {
  const navigate = useNavigate()
  const location = useLocation()
  const composerState = location.state as PipelineComposerState | null
  const [step, setStep] = useState(1)
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [catalogAdapters, setCatalogAdapters] = useState<CatalogAdapterType[]>([])
  const [catalogSinks, setCatalogSinks] = useState<CatalogSinkType[]>([])
  const [fetchedSinks, setFetchedSinks] = useState<SinkItem[]>([])
  const [loadError, setLoadError] = useState<string | null>(null)
  const [stepError, setStepError] = useState<string | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register,
    control,
    watch,
    setValue,
    getValues,
    reset,
    formState: { errors },
  } = useForm<BuilderFormValues>({
    defaultValues: defaultBuilderValues(),
  })

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'adapter.registers',
  })
  const { fields: mqttSubscriptionFields, append: appendMqttSubscription, remove: removeMqttSubscription } = useFieldArray({
    control,
    name: 'adapter.mqtt_subscriptions',
  })
  const { fields: mqttMappingFields, append: appendMqttMapping, remove: removeMqttMapping } = useFieldArray({
    control,
    name: 'adapter.mqtt_mappings',
  })
  const { fields: opcuaItemFields, append: appendOpcuaItem, remove: removeOpcuaItem } = useFieldArray({
    control,
    name: 'adapter.opcua_monitored_items',
  })

  const adapters = availableAdapters || catalogAdapters || BUILT_IN_ADAPTERS
  const sinkCatalog = availableSinkCatalog || catalogSinks || BUILT_IN_SINKS
  const sinks = availableSinks || fetchedSinks

  const selectedAdapterType = watch('adapter.adapter_type')
  const createNewSink = watch('output.create_new_sink')
  const selectedSinkId = watch('output.sink_id')
  const selectedSinkType = watch('output.sink_type')
  const selectedRegisters = watch('adapter.registers')
  const selectedMqttMappings = watch('adapter.mqtt_mappings')
  const selectedOpcuaItems = watch('adapter.opcua_monitored_items')
  const formSnapshot = watch()

  const selectedAdapter = useMemo(
    () => adapters.find((item) => item.adapter_type === selectedAdapterType) || null,
    [adapters, selectedAdapterType],
  )

  const selectedSink = useMemo(
    () => sinks.find((item) => String(item.id) === selectedSinkId) || null,
    [sinks, selectedSinkId],
  )

  const sinkTypeOptions = useMemo(
    () => Array.from(new Set([...sinkCatalog.map((item) => item.sink_type), ...sinks.map((item) => item.sink_type).filter((value) => value.trim())])),
    [sinkCatalog, sinks],
  )

  const selectedSinkCatalog = useMemo(
    () => sinkCatalog.find((item) => item.sink_type === selectedSinkType) || null,
    [selectedSinkType, sinkCatalog],
  )

  const parameterNames = useMemo(
    () =>
      Array.from(
        new Set(
          [
            ...(selectedRegisters || []).map((row) => row.param),
            ...(selectedMqttMappings || []).map((row) => row.parameter),
            ...(selectedOpcuaItems || []).map((row) => row.parameter),
          ].filter((value) => value?.trim()),
        ),
      ),
    [selectedRegisters, selectedMqttMappings, selectedOpcuaItems],
  )

  useEffect(() => {
    const load = async () => {
      setLoadError(null)
      try {
        const [gatewayRows, sinkRows, pipelineRows, catalog] = await Promise.all([
          listGateways(),
          availableSinks ? Promise.resolve([] as SinkItem[]) : listSinks(),
          listPipelines(),
          availableAdapters && availableSinkCatalog ? Promise.resolve(null) : getCatalog(),
        ])

        setGateways(gatewayRows)
        setPipelines(pipelineRows)
        if (!availableSinks) {
          setFetchedSinks(sinkRows)
        }
        if (catalog) {
          setCatalogAdapters(catalog.adapters)
          setCatalogSinks(catalog.sinks)
        }

        if (gatewayRows.length > 0) {
          setValue('gatewayId', gatewayRows[0].gateway_id)
        }
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : 'Failed to load wizard data')
      }
    }

    void load()
  }, [availableAdapters, availableSinkCatalog, availableSinks, setValue])

  useEffect(() => {
    if (!composerState) {
      return
    }

    const next = defaultBuilderValues()
    const editPipeline = composerState.pipelineId ? pipelines.find((pipeline) => pipeline.id === composerState.pipelineId) : undefined
    const pipelineConfig = editPipeline?.config || {}
    const validation = asRecord(pipelineConfig.validation)
    const firstSink = composerState.pipelineId ? sinks.find((sink) => sink.pipeline_id === composerState.pipelineId) : undefined

    if (composerState.mode === 'edit' && editPipeline) {
      next.pipelineName = editPipeline.name
      next.gatewayId = editPipeline.gateway_id
    } else {
      next.pipelineName = composerState.pipelineName || next.pipelineName
      next.gatewayId = composerState.gatewayId || next.gatewayId
    }

    next.adapter = {
      adapter_id: composerState.adapterDraft.adapter_id || next.adapter.adapter_id,
      adapter_type: composerState.adapterDraft.adapter_type || next.adapter.adapter_type,
      config_values: composerState.adapterDraft.config_values || {},
      registers: composerState.adapterDraft.registers.length > 0 ? composerState.adapterDraft.registers : next.adapter.registers,
      mqtt_subscriptions:
        composerState.adapterDraft.mqtt_subscriptions.length > 0 ? composerState.adapterDraft.mqtt_subscriptions : next.adapter.mqtt_subscriptions,
      mqtt_mappings: composerState.adapterDraft.mqtt_mappings.length > 0 ? composerState.adapterDraft.mqtt_mappings : next.adapter.mqtt_mappings,
      opcua_monitored_items:
        composerState.adapterDraft.opcua_monitored_items.length > 0
          ? composerState.adapterDraft.opcua_monitored_items
          : next.adapter.opcua_monitored_items,
    }

    if (validation) {
      next.validationEnabled = Boolean(validation.enabled)
      next.rawTopic = typeof validation.raw_topic === 'string' ? validation.raw_topic : next.rawTopic
      next.cleanTopic = typeof validation.clean_topic === 'string' ? validation.clean_topic : next.cleanTopic
      next.dlqTopic = typeof validation.dlq_topic === 'string' ? validation.dlq_topic : next.dlqTopic
      const ranges = asRecord(validation.ranges) || {}
      const rateOfChange = asRecord(validation.rate_of_change) || {}
      const gapDetection = asRecord(validation.gap_detection) || {}
      const rules: Record<string, ValidationPerParam> = {}
      for (const parameter of [
        ...new Set([
          ...Object.keys(ranges),
          ...Object.keys(rateOfChange),
          ...Object.keys(gapDetection),
          ...next.adapter.registers.map((row) => row.param),
          ...next.adapter.mqtt_mappings.map((row) => row.parameter),
          ...next.adapter.opcua_monitored_items.map((row) => row.parameter),
        ]),
      ]) {
        const range = asRecord(ranges[parameter]) || {}
        rules[parameter] = {
          ...DEFAULT_PARAM_RULES,
          min: typeof range.min === 'number' ? range.min : DEFAULT_PARAM_RULES.min,
          max: typeof range.max === 'number' ? range.max : DEFAULT_PARAM_RULES.max,
          rate_of_change: typeof rateOfChange[parameter] === 'number' ? Number(rateOfChange[parameter]) : DEFAULT_PARAM_RULES.rate_of_change,
          gap_detection: typeof gapDetection[parameter] === 'number' ? Number(gapDetection[parameter]) : DEFAULT_PARAM_RULES.gap_detection,
        }
      }
      next.validationByParam = rules
    }

    if (firstSink) {
      const sinkConfig = firstSink.config as Record<string, unknown>
      next.output.create_new_sink = false
      next.output.sink_id = String(firstSink.id)
      next.output.sink_type = firstSink.sink_type
      next.output.sink_status = firstSink.status
      next.output.kafka_bootstrap = typeof sinkConfig.kafka_bootstrap === 'string' ? sinkConfig.kafka_bootstrap : next.output.kafka_bootstrap
      next.output.group_id = typeof sinkConfig.group_id === 'string' ? sinkConfig.group_id : next.output.group_id
      next.output.db_dsn = typeof sinkConfig.db_dsn === 'string' ? sinkConfig.db_dsn : next.output.db_dsn
      next.output.table = typeof sinkConfig.table === 'string' ? sinkConfig.table : next.output.table
      next.output.asset_id = typeof sinkConfig.asset_id === 'string' ? sinkConfig.asset_id : next.output.asset_id
      next.cleanTopic = typeof sinkConfig.topic === 'string' ? sinkConfig.topic : next.cleanTopic
    }

    if (!next.gatewayId && gateways.length > 0) {
      next.gatewayId = gateways[0].gateway_id
    }

    reset(next)
    setStep(1)
    setStepError(null)
    setSubmitError(null)
  }, [composerState, gateways, pipelines, reset, sinks])

  useEffect(() => {
    if (!selectedSink) {
      return
    }

    const sinkConfig = selectedSink.config as Record<string, unknown>
    const kafkaBootstrap = typeof sinkConfig.kafka_bootstrap === 'string' ? sinkConfig.kafka_bootstrap : ''
    const topic = typeof sinkConfig.topic === 'string' ? sinkConfig.topic : ''
    const assetId = typeof sinkConfig.asset_id === 'string' ? sinkConfig.asset_id : `sink-${selectedSink.id}`

    setValue('output.kafka_bootstrap', kafkaBootstrap)
    setValue('output.topic', topic)
    if (topic) {
      setValue('cleanTopic', topic)
    }
    setValue('output.asset_id', assetId)
    setValue('output.sink_type', selectedSink.sink_type)
    setValue('output.group_id', typeof sinkConfig.group_id === 'string' ? sinkConfig.group_id : 'sf-sink-timescaledb')
    setValue('output.db_dsn', typeof sinkConfig.db_dsn === 'string' ? sinkConfig.db_dsn : '')
    setValue('output.table', typeof sinkConfig.table === 'string' ? sinkConfig.table : 'telemetry_clean')
    setValue('output.sink_status', typeof selectedSink.status === 'string' ? selectedSink.status : 'active')
  }, [selectedSink, setValue])

  useEffect(() => {
    if (!createNewSink || selectedSink) {
      return
    }
    if (selectedSinkCatalog) {
      const currentOutput = getValues('output') as Record<string, unknown>
      for (const field of selectedSinkCatalog.fields) {
        const currentValue = currentOutput[field.key]
        if (currentValue === '' || currentValue === undefined) {
          setValue(`output.${field.key as keyof BuilderFormValues['output']}` as never, field.default as never)
        }
      }
    }
  }, [createNewSink, getValues, selectedSink, selectedSinkCatalog, setValue])

  useEffect(() => {
    const existing = getValues('validationByParam') || {}
    const next: Record<string, ValidationPerParam> = {}

    for (const param of parameterNames) {
      next[param] = {
        ...DEFAULT_PARAM_RULES,
        ...(existing[param] || {}),
      }
    }

    setValue('validationByParam', next)
  }, [getValues, parameterNames, setValue])

  useEffect(() => {
    if (!selectedAdapter) {
      return
    }

    const current = getValues('adapter.config_values') || {}
    const next: Record<string, string | number> = {}

    for (const field of selectedAdapter.fields) {
      if (current[field.key] !== undefined) {
        next[field.key] = current[field.key]
      } else {
        if (typeof field.default === 'number' || typeof field.default === 'string') {
          next[field.key] = field.default
        } else {
          next[field.key] = field.input_type === 'number' ? 0 : ''
        }
      }
    }

    setValue('adapter.config_values', next)
  }, [getValues, selectedAdapter, setValue])

  const buildPayload = () => {
    const values = getValues()
    const existingPipeline = composerState?.mode === 'edit' && composerState.pipelineId
      ? pipelines.find((pipeline) => pipeline.id === composerState.pipelineId)
      : undefined
    const existingConfig = existingPipeline?.config || {}
    const existingValidation = asRecord(existingConfig.validation) || {}
    const output = {
      sink_type: values.output.sink_type,
      kafka_bootstrap: values.output.kafka_bootstrap,
      topic: values.rawTopic,
      asset_id: values.output.asset_id,
      sink_id: values.output.create_new_sink ? undefined : values.output.sink_id || undefined,
    }

    const dynamicAdapterConfig = normalizeCatalogFieldValues(selectedAdapter?.fields || [], values.adapter.config_values || {})
    let adapterConfig: Record<string, unknown> = {
      ...dynamicAdapterConfig,
      output,
    }

    if (selectedAdapter?.supports_registers) {
      adapterConfig = {
        ...adapterConfig,
        registers: values.adapter.registers.map((row) => ({
          address: Number(row.address),
          param: row.param,
          type: row.type,
          unit: row.unit,
        })),
      }
    }

    if (values.adapter.adapter_type === 'mqtt') {
      const mappingsByTopic = values.adapter.mqtt_mappings.reduce<Record<string, Array<Record<string, string>>>>((groups, mapping) => {
        const topic = mapping.topic.trim()
        if (!topic) {
          return groups
        }
        groups[topic] = groups[topic] || []
        groups[topic].push({
          field: mapping.field,
          parameter: mapping.parameter,
          unit: mapping.unit,
        })
        return groups
      }, {})

      adapterConfig = {
        ...adapterConfig,
        subscriptions: values.adapter.mqtt_subscriptions.map((subscription) => ({
          topic: subscription.topic,
          message_type: subscription.message_type,
          payload_format: subscription.payload_format,
          asset_id: subscription.asset_id,
          mappings: mappingsByTopic[subscription.topic] || [],
        })),
      }
    }

    if (values.adapter.adapter_type === 'opcua') {
      adapterConfig = {
        ...adapterConfig,
        monitored_items: values.adapter.opcua_monitored_items.map((item) => ({
          node_id: item.node_id,
          parameter: item.parameter,
          unit: item.unit,
          asset_id: item.asset_id,
        })),
      }
    }

    const ranges = { ...((asRecord(existingValidation.ranges) || {}) as Record<string, { min: number; max: number }>) }
    const rateOfChange = { ...((asRecord(existingValidation.rate_of_change) || {}) as Record<string, number>) }
    const gapDetection = { ...((asRecord(existingValidation.gap_detection) || {}) as Record<string, number>) }
    const existingAlarmRules = Array.isArray(existingValidation.alarm_rules) ? existingValidation.alarm_rules : []
    const untouchedAlarmRules = existingAlarmRules.filter((rule) => {
      const record = asRecord(rule)
      const parameter = typeof record?.parameter === 'string' ? record.parameter : ''
      return !Object.prototype.hasOwnProperty.call(values.validationByParam || {}, parameter)
    })
    const alarmRules: Array<Record<string, string | number>> = untouchedAlarmRules
      .map((rule) => asRecord(rule))
      .filter((rule): rule is Record<string, string | number> => Boolean(rule))

    for (const param of Object.keys(values.validationByParam || {})) {
      const rules = values.validationByParam[param]
      ranges[param] = { min: Number(rules.min), max: Number(rules.max) }
      rateOfChange[param] = Number(rules.rate_of_change)
      gapDetection[param] = Number(rules.gap_detection)
      if (rules.alarm_enabled) {
        const threshold = Number(rules.alarm_threshold)
        alarmRules.push({
          parameter: param,
          type: `${param}_threshold`,
          severity: rules.alarm_severity || 'HIGH',
          operator: '>',
          threshold,
          condition: `value > ${threshold}`,
          message: `${param} exceeded configured threshold`,
          clear_message: `${param} returned to normal range`,
        })
      }
    }

    const currentAdapter = {
      adapter_id: values.adapter.adapter_id,
      adapter_type: values.adapter.adapter_type,
      config: adapterConfig,
    }

    const existingAdapters = Array.isArray(existingConfig.adapters) ? existingConfig.adapters : []
    const preservedAdapters =
      composerState?.mode === 'edit'
        ? existingAdapters.filter((adapter) => {
            const record = asRecord(adapter)
            return record?.adapter_id !== composerState.adapterDraft.adapter_id
          })
        : []

    return {
      name: values.pipelineName,
      gateway_id: values.gatewayId,
      config: {
        adapters: [...preservedAdapters, currentAdapter],
        validation: {
          enabled: Boolean(values.validationEnabled),
          raw_topic: values.rawTopic,
          clean_topic: values.cleanTopic,
          dlq_topic: values.dlqTopic,
          alarm_topic: 'alarms.raw',
          alarm_rules: alarmRules,
          ranges,
          rate_of_change: rateOfChange,
          gap_detection: gapDetection,
        },
        events: asRecord(existingConfig.events) || {},
        aggregates: asRecord(existingConfig.aggregates) || {},
      },
    }
  }

  const buildSinkPayload = (pipelineId: number) => {
    const values = getValues()
    return {
      pipeline_id: pipelineId,
      sink_type: values.output.sink_type,
      status: values.output.sink_status,
      config: {
        kafka_bootstrap: values.output.kafka_bootstrap,
        topic: values.cleanTopic,
        group_id: values.output.group_id,
        db_dsn: values.output.db_dsn,
        table: values.output.table,
        asset_id: values.output.asset_id,
      },
    }
  }

  const goNext = () => {
    setStepError(null)

    if (step === 1) {
      const values = getValues()
      if (!values.adapter.adapter_type) {
        setStepError('Select an adapter type to continue.')
        return
      }
      if (!values.adapter.adapter_id.trim()) {
        setStepError('Adapter ID is required.')
        return
      }
      if (!values.pipelineName.trim() || !values.gatewayId.trim()) {
        setStepError('Pipeline name and gateway are required.')
        return
      }

      if (selectedAdapter?.supports_registers && values.adapter.registers.length === 0) {
        setStepError('Add at least one register to continue.')
        return
      }
      if (values.adapter.adapter_type === 'mqtt') {
        if (values.adapter.mqtt_subscriptions.length === 0) {
          setStepError('Add at least one MQTT subscription to continue.')
          return
        }
        if (values.adapter.mqtt_mappings.length === 0) {
          setStepError('Add at least one MQTT field mapping to continue.')
          return
        }
      }
      if (values.adapter.adapter_type === 'opcua' && values.adapter.opcua_monitored_items.length === 0) {
        setStepError('Add at least one OPC UA monitored item to continue.')
        return
      }
    }

    if (step === 2) {
      const values = getValues()
      if (!values.output.sink_type) {
        setStepError('Select a sink type to continue.')
        return
      }
      if (!values.output.create_new_sink && !values.output.sink_id) {
        setStepError('Select an existing sink or create a new one.')
        return
      }
      if (values.output.create_new_sink) {
        if (!values.output.db_dsn.trim() || !values.output.table.trim() || !values.output.group_id.trim()) {
          setStepError('DB DSN, sink table, and consumer group are required when creating a sink.')
          return
        }
      }
    }

    if (step === 3) {
      if (parameterNames.length === 0) {
        setStepError('Add at least one parameter in Step 1 before continuing.')
        return
      }
    }

    setStep((current) => Math.min(current + 1, 4))
  }

  const goBack = () => {
    setStepError(null)
    setStep((current) => Math.max(current - 1, 1))
  }

  const onConfirm = async () => {
    setSubmitError(null)
    setIsSubmitting(true)
    try {
      const payload = buildPayload()
      if (composerState?.mode === 'edit' && composerState.pipelineId) {
        await updatePipeline(composerState.pipelineId, {
          name: payload.name,
          config: payload.config,
        })
        if (getValues('output.create_new_sink')) {
          await createSink(buildSinkPayload(composerState.pipelineId))
        }
      } else {
        const pipeline = await createPipeline(payload)
        if (getValues('output.create_new_sink')) {
          await createSink(buildSinkPayload(pipeline.id))
        }
      }
      navigate('/overview', { replace: true })
    } catch (createError) {
      setSubmitError(createError instanceof Error ? createError.message : `Failed to ${composerState?.mode === 'edit' ? 'update' : 'create'} deployment`)
    } finally {
      setIsSubmitting(false)
    }
  }

  const reviewPayload = useMemo(
    () => ({
      pipeline: buildPayload(),
      sink: getValues('output.create_new_sink') ? buildSinkPayload(0) : { reuse_sink_id: selectedSinkId || null },
    }),
    [formSnapshot, getValues, selectedSinkId, selectedAdapter],
  )

  return (
    <section>
      <div className="page-header">
        <h2>{composerState?.mode === 'edit' ? 'Edit Deployment Adapter' : 'Compose Deployment'}</h2>
        <span className="muted">Step {step} of 4</span>
      </div>
      <p className="muted">
        This composer builds a gateway deployment configuration. In the current control-plane model it writes one
        pipeline record plus sink attachments; fuller multi-adapter and multi-sink composition is the next UI phase.
      </p>

      <div className="wizard-steps">
        <span className={step >= 1 ? 'wizard-step active' : 'wizard-step'}>1. Adapter</span>
        <span className={step >= 2 ? 'wizard-step active' : 'wizard-step'}>2. Sink</span>
        <span className={step >= 3 ? 'wizard-step active' : 'wizard-step'}>3. Validation</span>
        <span className={step >= 4 ? 'wizard-step active' : 'wizard-step'}>4. Review</span>
      </div>

      {loadError && <p className="error">{loadError}</p>}
      {stepError && <p className="error">{stepError}</p>}
      {submitError && <p className="error">{submitError}</p>}

      {step === 1 && (
        <article className="card builder-section">
          <h3>Step 1: Source Adapter</h3>
          <p className="muted">
            Build the gateway-side adapter config directly from the supported adapter catalog. This is the protocol-aware
            part of the deployment, so the form changes shape based on the adapter type you select.
          </p>

          <div className="inline-grid">
            <label>
              Deployment Name
              <input {...register('pipelineName', { required: true })} />
              {errors.pipelineName && <span className="error">Required</span>}
            </label>
            <label>
              Gateway
              <select {...register('gatewayId', { required: true })}>
                {gateways.map((gateway) => (
                  <option key={gateway.gateway_id} value={gateway.gateway_id}>
                    {gateway.gateway_id}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Adapter ID
              <input {...register('adapter.adapter_id', { required: true })} />
            </label>
            <label>
              Adapter Type
              <select {...register('adapter.adapter_type')}>
                <option value="">Select adapter</option>
                {adapters.map((adapter) => (
                  <option key={adapter.adapter_type} value={adapter.adapter_type}>
                    {adapter.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {selectedAdapter && (
            <>
              <h4>Adapter Configuration</h4>
              <div className="inline-grid">
                {selectedAdapter.fields.map((field) => (
                  <label key={field.key}>
                    {field.label}
                    <input
                      type={field.input_type === 'number' ? 'number' : 'text'}
                      {...register(`adapter.config_values.${field.key}` as const)}
                    />
                  </label>
                ))}
              </div>
            </>
          )}

          {selectedAdapter?.supports_registers && (
            <>
              <h4>Parameter Mapping</h4>
              <p className="muted">Add one row per PLC/SCADA parameter you want the gateway to collect.</p>
              {fields.map((field, index) => (
                <div className="inline-grid" key={field.id}>
                  <label>
                    Address
                    <input
                      type="number"
                      {...register(`adapter.registers.${index}.address` as const, { valueAsNumber: true })}
                    />
                  </label>
                  <label>
                    Parameter
                    <input {...register(`adapter.registers.${index}.param` as const)} />
                  </label>
                  <label>
                    Type
                    <input {...register(`adapter.registers.${index}.type` as const)} />
                  </label>
                  <label>
                    Unit
                    <input {...register(`adapter.registers.${index}.unit` as const)} />
                  </label>
                  <button className="btn btn-secondary" onClick={() => remove(index)} type="button">
                    Remove
                  </button>
                </div>
              ))}
              <button
                className="btn"
                onClick={() =>
                  append({
                    address: nextRegisterAddress(getValues('adapter.registers') || []),
                    param: '',
                    type: 'float32',
                    unit: 'unit',
                  })
                }
                type="button"
              >
                Add Register
              </button>
            </>
          )}

          {selectedAdapterType === 'mqtt' && (
            <>
              <h4>MQTT Subscriptions</h4>
              <p className="muted">Define the topics this adapter subscribes to and how incoming JSON payloads should be classified.</p>
              {mqttSubscriptionFields.map((field, index) => (
                <div className="inline-grid" key={field.id}>
                  <label>
                    Topic
                    <input {...register(`adapter.mqtt_subscriptions.${index}.topic` as const)} />
                  </label>
                  <label>
                    Message Type
                    <select {...register(`adapter.mqtt_subscriptions.${index}.message_type` as const)}>
                      <option value="telemetry">telemetry</option>
                      <option value="event">event</option>
                    </select>
                  </label>
                  <label>
                    Payload Format
                    <select {...register(`adapter.mqtt_subscriptions.${index}.payload_format` as const)}>
                      <option value="json">json</option>
                    </select>
                  </label>
                  <label>
                    Asset ID
                    <input {...register(`adapter.mqtt_subscriptions.${index}.asset_id` as const)} />
                  </label>
                  <button className="btn btn-secondary" onClick={() => removeMqttSubscription(index)} type="button">
                    Remove
                  </button>
                </div>
              ))}
              <button
                className="btn"
                onClick={() =>
                  appendMqttSubscription({
                    topic: '',
                    message_type: 'telemetry',
                    payload_format: 'json',
                    asset_id: getValues('output.asset_id') || 'asset-01',
                  })
                }
                type="button"
              >
                Add MQTT Subscription
              </button>

              <h4>MQTT Field Mappings</h4>
              <p className="muted">Map JSON fields from subscribed topics into normalized parameters.</p>
              {mqttMappingFields.map((field, index) => (
                <div className="inline-grid" key={field.id}>
                  <label>
                    Topic
                    <input list="mqtt-topic-options" {...register(`adapter.mqtt_mappings.${index}.topic` as const)} />
                    <datalist id="mqtt-topic-options">
                      {(watch('adapter.mqtt_subscriptions') || []).map((subscription, subscriptionIndex) => (
                        <option key={`${subscription.topic || 'subscription'}-${subscriptionIndex}`} value={subscription.topic} />
                      ))}
                    </datalist>
                  </label>
                  <label>
                    JSON Field
                    <input {...register(`adapter.mqtt_mappings.${index}.field` as const)} />
                  </label>
                  <label>
                    Parameter
                    <input {...register(`adapter.mqtt_mappings.${index}.parameter` as const)} />
                  </label>
                  <label>
                    Unit
                    <input {...register(`adapter.mqtt_mappings.${index}.unit` as const)} />
                  </label>
                  <button className="btn btn-secondary" onClick={() => removeMqttMapping(index)} type="button">
                    Remove
                  </button>
                </div>
              ))}
              <button
                className="btn"
                onClick={() =>
                  appendMqttMapping({
                    topic: getValues('adapter.mqtt_subscriptions.0.topic') || '',
                    field: '',
                    parameter: '',
                    unit: '',
                  })
                }
                type="button"
              >
                Add MQTT Mapping
              </button>
            </>
          )}

          {selectedAdapterType === 'opcua' && (
            <>
              <h4>OPC UA Monitored Items</h4>
              <p className="muted">Map monitored OPC UA node changes into normalized parameters.</p>
              {opcuaItemFields.map((field, index) => (
                <div className="inline-grid" key={field.id}>
                  <label>
                    Node ID
                    <input {...register(`adapter.opcua_monitored_items.${index}.node_id` as const)} />
                  </label>
                  <label>
                    Parameter
                    <input {...register(`adapter.opcua_monitored_items.${index}.parameter` as const)} />
                  </label>
                  <label>
                    Unit
                    <input {...register(`adapter.opcua_monitored_items.${index}.unit` as const)} />
                  </label>
                  <label>
                    Asset ID
                    <input {...register(`adapter.opcua_monitored_items.${index}.asset_id` as const)} />
                  </label>
                  <button className="btn btn-secondary" onClick={() => removeOpcuaItem(index)} type="button">
                    Remove
                  </button>
                </div>
              ))}
              <button
                className="btn"
                onClick={() =>
                  appendOpcuaItem({
                    node_id: '',
                    parameter: '',
                    unit: '',
                    asset_id: getValues('output.asset_id') || 'asset-01',
                  })
                }
                type="button"
              >
                Add OPC UA Monitored Item
              </button>
            </>
          )}
        </article>
      )}

      {step === 2 && (
        <article className="card builder-section">
          <h3>Step 2: Destination Sink</h3>
          <p className="muted">Create a new sink as part of this workflow or attach the deployment to an existing sink instance.</p>

          <div className="inline-grid">
            <label className="toggle-label">
              <input type="checkbox" {...register('output.create_new_sink')} />
              Create new sink
            </label>

            <label>
              Sink Type
              <input list="sink-type-options" placeholder="e.g. timescaledb" {...register('output.sink_type')} />
              <datalist id="sink-type-options">
                {sinkTypeOptions.map((sinkType) => (
                  <option key={sinkType} value={sinkType} />
                ))}
              </datalist>
            </label>

            <label>
              Existing Sink Instance
              <select {...register('output.sink_id')} disabled={createNewSink}>
                <option value="">None</option>
                {sinks.map((sink) => (
                  <option key={sink.id} value={sink.id}>
                    {sink.id} - {sink.sink_type} ({sink.status})
                  </option>
                ))}
              </select>
            </label>
          </div>

          {sinkTypeOptions.length === 0 && <p className="muted">No sink types discovered yet.</p>}

          <div className="inline-grid">
            <label>
              Kafka Bootstrap
              <input {...register('output.kafka_bootstrap')} />
            </label>
            <label>
              Topic
              <input {...register('cleanTopic')} />
            </label>
            <label>
              Asset ID
              <input {...register('output.asset_id')} />
            </label>
          </div>

          {createNewSink && (
            <div className="inline-grid">
              <label>
                Sink Status
                <select {...register('output.sink_status')}>
                  <option value="active">active</option>
                  <option value="paused">paused</option>
                </select>
              </label>
              <label>
                Consumer Group
                <input {...register('output.group_id')} />
              </label>
              {selectedSinkCatalog?.fields
                .filter((field) => !['kafka_bootstrap', 'topic', 'group_id'].includes(field.key))
                .map((field) => (
                  <label key={field.key}>
                    {field.label}
                    <input
                      type={field.input_type === 'number' ? 'number' : 'text'}
                      {...register(`output.${field.key as keyof BuilderFormValues['output']}` as never)}
                    />
                  </label>
                ))}
            </div>
          )}
        </article>
      )}

      {step === 3 && (
        <article className="card builder-section">
          <h3>Step 3: Validation Rules</h3>
          <p className="muted">Rules are generated from parameters entered in Step 1.</p>

          <div className="inline-grid">
            <label className="toggle-label">
              <input type="checkbox" {...register('validationEnabled')} />
              Enable Validation
            </label>
            <label>
              Raw Topic
              <input {...register('rawTopic')} />
            </label>
            <label>
              Clean Topic
              <input {...register('cleanTopic')} />
            </label>
            <label>
              DLQ Topic
              <input {...register('dlqTopic')} />
            </label>
          </div>

          {parameterNames.length === 0 && <p className="muted">No parameters available yet. Go back to Step 1.</p>}

          {parameterNames.map((param) => (
            <div className="card nested-card" key={param}>
              <h4>{param}</h4>
              <div className="inline-grid">
                <label>
                  Min
                  <input
                    type="number"
                    {...register(`validationByParam.${param}.min` as const, { valueAsNumber: true })}
                  />
                </label>
                <label>
                  Max
                  <input
                    type="number"
                    {...register(`validationByParam.${param}.max` as const, { valueAsNumber: true })}
                  />
                </label>
                <label>
                  Rate of Change
                  <input
                    type="number"
                    {...register(`validationByParam.${param}.rate_of_change` as const, { valueAsNumber: true })}
                  />
                </label>
                <label>
                  Gap Detection
                  <input
                    type="number"
                    {...register(`validationByParam.${param}.gap_detection` as const, { valueAsNumber: true })}
                  />
                </label>
                <label className="toggle-label">
                  <input type="checkbox" {...register(`validationByParam.${param}.alarm_enabled` as const)} />
                  Enable Alarm
                </label>
                <label>
                  Alarm Threshold
                  <input
                    type="number"
                    {...register(`validationByParam.${param}.alarm_threshold` as const, { valueAsNumber: true })}
                  />
                </label>
                <label>
                  Alarm Severity
                  <select {...register(`validationByParam.${param}.alarm_severity` as const)}>
                    <option value="CRITICAL">CRITICAL</option>
                    <option value="HIGH">HIGH</option>
                    <option value="MEDIUM">MEDIUM</option>
                    <option value="LOW">LOW</option>
                    <option value="INFO">INFO</option>
                  </select>
                </label>
              </div>
            </div>
          ))}
        </article>
      )}

      {step === 4 && (
        <article className="card builder-section">
          <h3>Step 4: Review & Confirm</h3>
          <p className="muted">Review the gateway deployment bundle before it is written into the current control-plane pipeline model.</p>

          <div className="review-grid">
            <p>
              <strong>Deployment:</strong> {getValues('pipelineName')}
            </p>
            <p>
              <strong>Gateway:</strong> {getValues('gatewayId')}
            </p>
            <p>
              <strong>Adapter:</strong> {selectedAdapter?.label || getValues('adapter.adapter_type')}
            </p>
            <p>
              <strong>Sink:</strong> {selectedSinkType || 'None'}
            </p>
            <p>
              <strong>Validation Parameters:</strong> {parameterNames.join(', ') || 'None'}
            </p>
            <p>
              <strong>Sink Provisioning:</strong> {createNewSink ? 'Create new sink' : `Reuse sink ${selectedSinkId || 'None'}`}
            </p>
            <p>
              <strong>Mode:</strong> {composerState?.mode === 'edit' ? 'Edit existing deployment' : 'Create new deployment'}
            </p>
          </div>

          <h4>Compiled Payload (Read-only)</h4>
          <pre className="json-preview">{JSON.stringify(reviewPayload, null, 2)}</pre>

          <button className="btn" onClick={() => void onConfirm()} type="button" disabled={isSubmitting}>
            {isSubmitting ? (composerState?.mode === 'edit' ? 'Updating...' : 'Creating...') : composerState?.mode === 'edit' ? 'Update Deployment' : 'Create Deployment'}
          </button>
        </article>
      )}

      <div className="wizard-actions">
        <button className="btn btn-secondary" disabled={step === 1} onClick={goBack} type="button">
          Back
        </button>
        <button className="btn" disabled={step === 4} onClick={goNext} type="button">
          Next
        </button>
      </div>
    </section>
  )
}
