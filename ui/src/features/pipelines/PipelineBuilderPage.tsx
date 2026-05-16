import { useEffect, useMemo, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

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
} from '../../shared/api/client'

type RegisterInput = {
  address: number
  param: string
  type: string
  unit: string
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

/**
 * Step-based pipeline wizard.
 * Step 1: Adapter, Step 2: Sink, Step 3: Validation, Step 4: Review.
 */
export function PipelineBuilderPage({ availableAdapters, availableSinkCatalog, availableSinks }: PipelineBuilderProps = {}) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [gateways, setGateways] = useState<GatewayItem[]>([])
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
    formState: { errors },
  } = useForm<BuilderFormValues>({
    defaultValues: {
      pipelineName: 'demo-pipeline-ui',
      gatewayId: '',
      adapter: {
        adapter_id: 'adapter-01',
        adapter_type: '',
        config_values: {},
        registers: [{ address: 40001, param: 'temperature', type: 'float32', unit: 'celsius' }],
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
    },
  })

  const { fields, append, remove } = useFieldArray({
    control,
    name: 'adapter.registers',
  })

  const adapters = availableAdapters || catalogAdapters || BUILT_IN_ADAPTERS
  const sinkCatalog = availableSinkCatalog || catalogSinks || BUILT_IN_SINKS
  const sinks = availableSinks || fetchedSinks

  const selectedAdapterType = watch('adapter.adapter_type')
  const createNewSink = watch('output.create_new_sink')
  const selectedSinkId = watch('output.sink_id')
  const selectedSinkType = watch('output.sink_type')
  const selectedRegisters = watch('adapter.registers')
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
    () => Array.from(new Set((selectedRegisters || []).map((row) => row.param).filter((value) => value?.trim()))),
    [selectedRegisters],
  )

  useEffect(() => {
    const load = async () => {
      setLoadError(null)
      try {
        const [gatewayRows, sinkRows, catalog] = await Promise.all([
          listGateways(),
          availableSinks ? Promise.resolve([] as SinkItem[]) : listSinks(),
          availableAdapters && availableSinkCatalog ? Promise.resolve(null) : getCatalog(),
        ])

        setGateways(gatewayRows)
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
    const output = {
      sink_type: values.output.sink_type,
      kafka_bootstrap: values.output.kafka_bootstrap,
      topic: values.rawTopic,
      asset_id: values.output.asset_id,
      sink_id: values.output.create_new_sink ? undefined : values.output.sink_id || undefined,
    }

    const dynamicAdapterConfig = normalizeCatalogFieldValues(selectedAdapter?.fields || [], values.adapter.config_values || {})
    const adapterConfig = selectedAdapter?.supports_registers
      ? {
          ...dynamicAdapterConfig,
          registers: values.adapter.registers.map((row) => ({
            address: Number(row.address),
            param: row.param,
            type: row.type,
            unit: row.unit,
          })),
          output,
        }
      : {
          ...dynamicAdapterConfig,
          output,
        }

    const ranges: Record<string, { min: number; max: number }> = {}
    const rateOfChange: Record<string, number> = {}
    const gapDetection: Record<string, number> = {}
    const alarmRules: Array<Record<string, string | number>> = []

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

    return {
      name: values.pipelineName,
      gateway_id: values.gatewayId,
      config: {
        adapters: [
          {
            adapter_id: values.adapter.adapter_id,
            adapter_type: values.adapter.adapter_type,
            config: adapterConfig,
          },
        ],
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
      const pipeline = await createPipeline(payload)
      if (getValues('output.create_new_sink')) {
        await createSink(buildSinkPayload(pipeline.id))
      }
      navigate('/overview', { replace: true })
    } catch (createError) {
      setSubmitError(createError instanceof Error ? createError.message : 'Failed to create pipeline')
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
        <h2>Compose Deployment</h2>
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
          <p className="muted">Build the gateway-side adapter config directly from the supported adapter catalog.</p>

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
          </div>

          <h4>Compiled Payload (Read-only)</h4>
          <pre className="json-preview">{JSON.stringify(reviewPayload, null, 2)}</pre>

          <button className="btn" onClick={() => void onConfirm()} type="button" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Deployment'}
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
