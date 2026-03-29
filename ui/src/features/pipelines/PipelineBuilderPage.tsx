import { useEffect, useMemo, useState } from 'react'
import { useFieldArray, useForm } from 'react-hook-form'
import { useNavigate } from 'react-router-dom'

import {
  GatewayItem,
  PipelineItem,
  SinkItem,
  createPipeline,
  listGateways,
  listPipelines,
  listSinks,
} from '../../shared/api/client'

type AdapterField = {
  key: string
  label: string
  type: 'text' | 'number'
}

type AdapterOption = {
  adapter_type: string
  label: string
  supports_registers: boolean
  fields: AdapterField[]
}

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
    sink_id: string
    sink_type: string
    kafka_bootstrap: string
    topic: string
    asset_id: string
  }
  validationEnabled: boolean
  rawTopic: string
  cleanTopic: string
  dlqTopic: string
  validationByParam: Record<string, ValidationPerParam>
}

type PipelineBuilderProps = {
  availableAdapters?: AdapterOption[]
  availableSinks?: SinkItem[]
}

const DEFAULT_PARAM_RULES: ValidationPerParam = {
  min: -50,
  max: 500,
  rate_of_change: 20,
  gap_detection: 5,
}

function formatLabel(value: string) {
  return value
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (char) => char.toUpperCase())
}

function normalizeAdapterOptions(rows: PipelineItem[]): AdapterOption[] {
  const map = new Map<string, AdapterOption>()

  for (const pipeline of rows) {
    const config = pipeline.config as Record<string, unknown>
    const adapters = Array.isArray(config.adapters)
      ? (config.adapters as Array<Record<string, unknown>>)
      : []

    for (const adapter of adapters) {
      const adapterType = String(adapter.adapter_type || '').trim()
      if (!adapterType) {
        continue
      }

      const adapterConfig = (adapter.config as Record<string, unknown>) || {}
      const supportsRegisters = Array.isArray(adapterConfig.registers)
      const fields: AdapterField[] = Object.entries(adapterConfig)
        .filter(([key]) => key !== 'registers' && key !== 'output')
        .map(([key, value]) => ({
          key,
          label: formatLabel(key),
          type: typeof value === 'number' ? 'number' : 'text',
        }))

      const existing = map.get(adapterType)
      if (!existing) {
        map.set(adapterType, {
          adapter_type: adapterType,
          label: formatLabel(adapterType),
          supports_registers: supportsRegisters,
          fields,
        })
        continue
      }

      const mergedFieldMap = new Map(existing.fields.map((field) => [field.key, field]))
      for (const field of fields) {
        if (!mergedFieldMap.has(field.key)) {
          mergedFieldMap.set(field.key, field)
        }
      }

      map.set(adapterType, {
        ...existing,
        supports_registers: existing.supports_registers || supportsRegisters,
        fields: Array.from(mergedFieldMap.values()),
      })
    }
  }

  return Array.from(map.values())
}

/**
 * Step-based pipeline wizard.
 * Step 1: Adapter, Step 2: Sink, Step 3: Validation, Step 4: Review.
 */
export function PipelineBuilderPage({ availableAdapters, availableSinks }: PipelineBuilderProps = {}) {
  const navigate = useNavigate()
  const [step, setStep] = useState(1)
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [fetchedAdapters, setFetchedAdapters] = useState<AdapterOption[]>([])
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
        sink_id: '',
        sink_type: '',
        kafka_bootstrap: 'kafka:9092',
        topic: 'telemetry.raw',
        asset_id: 'asset-01',
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

  const adapters = availableAdapters || fetchedAdapters
  const sinks = availableSinks || fetchedSinks

  const selectedAdapterType = watch('adapter.adapter_type')
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
    () => Array.from(new Set(sinks.map((item) => item.sink_type).filter((value) => value.trim()))),
    [sinks],
  )

  const parameterNames = useMemo(
    () => Array.from(new Set((selectedRegisters || []).map((row) => row.param).filter((value) => value?.trim()))),
    [selectedRegisters],
  )

  useEffect(() => {
    const load = async () => {
      setLoadError(null)
      try {
        const [gatewayRows, sinkRows, pipelineRows] = await Promise.all([
          listGateways(),
          availableSinks ? Promise.resolve([] as SinkItem[]) : listSinks(),
          availableAdapters ? Promise.resolve([] as PipelineItem[]) : listPipelines(),
        ])

        setGateways(gatewayRows)
        if (!availableSinks) {
          setFetchedSinks(sinkRows)
        }
        if (!availableAdapters) {
          setFetchedAdapters(normalizeAdapterOptions(pipelineRows))
        }

        if (gatewayRows.length > 0) {
          setValue('gatewayId', gatewayRows[0].gateway_id)
        }
      } catch (error) {
        setLoadError(error instanceof Error ? error.message : 'Failed to load wizard data')
      }
    }

    void load()
  }, [availableAdapters, availableSinks, setValue])

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
    setValue('output.asset_id', assetId)
    setValue('output.sink_type', selectedSink.sink_type)
  }, [selectedSink, setValue])

  useEffect(() => {
    const existing = getValues('validationByParam') || {}
    const next: Record<string, ValidationPerParam> = {}

    for (const param of parameterNames) {
      next[param] = existing[param] || DEFAULT_PARAM_RULES
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
        next[field.key] = field.type === 'number' ? 0 : ''
      }
    }

    setValue('adapter.config_values', next)
  }, [getValues, selectedAdapter, setValue])

  const buildPayload = () => {
    const values = getValues()
    const output = {
      sink_type: values.output.sink_type,
      kafka_bootstrap: values.output.kafka_bootstrap,
      topic: values.output.topic,
      asset_id: values.output.asset_id,
      sink_id: values.output.sink_id || undefined,
    }

    const dynamicAdapterConfig = { ...values.adapter.config_values }
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

    for (const param of Object.keys(values.validationByParam || {})) {
      const rules = values.validationByParam[param]
      ranges[param] = { min: Number(rules.min), max: Number(rules.max) }
      rateOfChange[param] = Number(rules.rate_of_change)
      gapDetection[param] = Number(rules.gap_detection)
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
          ranges,
          rate_of_change: rateOfChange,
          gap_detection: gapDetection,
        },
      },
    }
  }

  const goNext = () => {
    setStepError(null)

    if (step === 1) {
      const values = getValues()
      if (adapters.length === 0) {
        setStepError('No registered adapters found yet. Create at least one pipeline/adapter first.')
        return
      }
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
      await createPipeline(payload)
      navigate('/overview', { replace: true })
    } catch (createError) {
      setSubmitError(createError instanceof Error ? createError.message : 'Failed to create pipeline')
    } finally {
      setIsSubmitting(false)
    }
  }

  const reviewPayload = useMemo(() => buildPayload(), [formSnapshot, selectedAdapter])

  return (
    <section>
      <div className="page-header">
        <h2>Create Pipeline Wizard</h2>
        <span className="muted">Step {step} of 4</span>
      </div>

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

          <div className="inline-grid">
            <label>
              Pipeline Name
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

          {adapters.length === 0 && (
            <p className="error">No adapter types are registered yet. Add one from an existing pipeline first.</p>
          )}

          {selectedAdapter && (
            <>
              <h4>Adapter Configuration</h4>
              <div className="inline-grid">
                {selectedAdapter.fields.map((field) => (
                  <label key={field.key}>
                    {field.label}
                    <input
                      type={field.type === 'number' ? 'number' : 'text'}
                      {...register(`adapter.config_values.${field.key}` as const)}
                    />
                  </label>
                ))}
              </div>
            </>
          )}

          {selectedAdapter?.supports_registers && (
            <>
              <h4>Registers</h4>
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
                    address: 40001,
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
          <p className="muted">Select a sink type from the runtime registry, then tune output routing.</p>

          <div className="inline-grid">
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
              Existing Sink Instance (optional)
              <select {...register('output.sink_id')}>
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
              <input {...register('output.topic')} />
            </label>
            <label>
              Asset ID
              <input {...register('output.asset_id')} />
            </label>
          </div>
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
              </div>
            </div>
          ))}
        </article>
      )}

      {step === 4 && (
        <article className="card builder-section">
          <h3>Step 4: Review & Confirm</h3>

          <div className="review-grid">
            <p>
              <strong>Pipeline:</strong> {getValues('pipelineName')}
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
          </div>

          <h4>Compiled Payload (Read-only)</h4>
          <pre className="json-preview">{JSON.stringify(reviewPayload, null, 2)}</pre>

          <button className="btn" onClick={() => void onConfirm()} type="button" disabled={isSubmitting}>
            {isSubmitting ? 'Creating...' : 'Create Pipeline'}
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
