import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import {
  type AdapterItem,
  type DeploymentPreflightResult,
  type GatewayItem,
  type SinkItem,
  createDeployment,
  getDeployment,
  listAdapters,
  listGateways,
  listSinks,
  preflightDeployment,
  updateDeployment,
} from '../../shared/api/client'
import { ActionResultPanel } from '../../shared/forms/ActionResultPanel'
import { preflightToViewModel, type ActionResultViewModel } from '../../shared/forms/validationIssues'
import {
  buildDefaultDeploymentForm,
  deploymentToForm,
  formToCreatePayload,
  formToUpdatePayload,
  type DeploymentFormState,
} from './deploymentForm'
import { AdapterSelectionSection } from './components/AdapterSelectionSection'
import { AggregatesConfigSection } from './components/AggregatesConfigSection'
import { DeploymentBasicsSection } from './components/DeploymentBasicsSection'
import { DeploymentReviewPanel } from './components/DeploymentReviewPanel'
import { EventsConfigSection } from './components/EventsConfigSection'
import { SinkSelectionSection } from './components/SinkSelectionSection'
import { ValidationConfigSection } from './components/ValidationConfigSection'

export function PipelineBuilderPage() {
  const navigate = useNavigate()
  const { deploymentId: routeDeploymentId } = useParams()
  const editing = Boolean(routeDeploymentId)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [adapters, setAdapters] = useState<AdapterItem[]>([])
  const [sinks, setSinks] = useState<SinkItem[]>([])
  const [form, setForm] = useState<DeploymentFormState>(buildDefaultDeploymentForm())
  const [preflightResult, setPreflightResult] = useState<DeploymentPreflightResult | null>(null)
  const [preflighting, setPreflighting] = useState(false)

  useEffect(() => {
    let cancelled = false

    const load = async () => {
      setLoading(true)
      setError(null)
      try {
        const [gatewayRows, adapterRows, sinkRows, deployment] = await Promise.all([
          listGateways(),
          listAdapters(),
          listSinks(),
          routeDeploymentId ? getDeployment(routeDeploymentId) : Promise.resolve(null),
        ])

        if (cancelled) {
          return
        }

        setGateways(gatewayRows)
        setAdapters(adapterRows)
        setSinks(sinkRows)
        setPreflightResult(null)

        if (deployment) {
          setForm(deploymentToForm(deployment))
        } else {
          const defaults = buildDefaultDeploymentForm()
          setForm({
            ...defaults,
            gatewayId: gatewayRows[0]?.gateway_id || defaults.gatewayId,
          })
        }
      } catch (loadError) {
        if (!cancelled) {
          setError(loadError instanceof Error ? loadError.message : 'Failed to load deployment composer')
        }
      } finally {
        if (!cancelled) {
          setLoading(false)
        }
      }
    }

    void load()

    return () => {
      cancelled = true
    }
  }, [routeDeploymentId])

  const selectedAdapters = useMemo(
    () => adapters.filter((adapter) => form.adapterIds.includes(adapter.adapter_id)),
    [adapters, form.adapterIds],
  )
  const selectedSinks = useMemo(() => sinks.filter((sink) => form.sinkIds.includes(sink.sink_id)), [form.sinkIds, sinks])

  const toggleAdapter = (adapterId: string) => {
    setForm((current) => ({
      ...current,
      adapterIds: current.adapterIds.includes(adapterId)
        ? current.adapterIds.filter((value) => value !== adapterId)
        : [...current.adapterIds, adapterId],
    }))
  }

  const toggleSink = (sinkId: string) => {
    setForm((current) => ({
      ...current,
      sinkIds: current.sinkIds.includes(sinkId)
        ? current.sinkIds.filter((value) => value !== sinkId)
        : [...current.sinkIds, sinkId],
    }))
  }

  const onSubmit = async () => {
    setError(null)

    if (!form.deploymentId.trim()) {
      setError('Deployment ID is required.')
      return
    }

    if (!form.name.trim()) {
      setError('Deployment name is required.')
      return
    }

    if (!form.gatewayId) {
      setError('Select a gateway for this deployment.')
      return
    }

    if (form.adapterIds.length === 0) {
      setError('Select at least one adapter.')
      return
    }

    if (form.sinkIds.length === 0) {
      setError('Select at least one sink.')
      return
    }

    setSaving(true)
    try {
      if (editing && routeDeploymentId) {
        await updateDeployment(routeDeploymentId, formToUpdatePayload(form))
      } else {
        await createDeployment(formToCreatePayload(form))
      }
      navigate('/pipelines')
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to save deployment')
    } finally {
      setSaving(false)
    }
  }

  const onPreflight = async () => {
    setPreflighting(true)
    setError(null)
    try {
      const result = await preflightDeployment(formToCreatePayload(form))
      setPreflightResult(result)
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to run deployment preflight')
    } finally {
      setPreflighting(false)
    }
  }

  const preflightViewModel: ActionResultViewModel | null = preflightResult ? preflightToViewModel(preflightResult) : null

  return (
    <section>
      <div className="page-header">
        <div>
          <h2>{editing ? 'Edit Deployment' : 'Compose Deployment'}</h2>
          <p className="muted">
            Compose one deployment from saved adapter and sink objects, then tune deployment-level processing before
            activation.
          </p>
        </div>
        <div className="page-actions">
          <Link className="btn btn-secondary" to="/pipelines">
            Back To Deployments
          </Link>
          <button className="btn btn-secondary" disabled={loading || saving || preflighting} onClick={() => void onPreflight()} type="button">
            {preflighting ? 'Preflighting…' : 'Preflight Deployment'}
          </button>
          <button className="btn" disabled={loading || saving} onClick={() => void onSubmit()} type="button">
            {saving ? 'Saving…' : editing ? 'Update Deployment' : 'Create Deployment'}
          </button>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {loading ? (
        <p>Loading deployment composer...</p>
      ) : (
        <div className="composer-layout">
          <div className="builder-section">
            {preflightViewModel && <ActionResultPanel result={preflightViewModel} />}
            <DeploymentBasicsSection
              deploymentId={form.deploymentId}
              editing={editing}
              gateways={gateways}
              gatewayId={form.gatewayId}
              name={form.name}
              onDeploymentIdChange={(value) => setForm((current) => ({ ...current, deploymentId: value }))}
              onGatewayIdChange={(value) => setForm((current) => ({ ...current, gatewayId: value }))}
              onNameChange={(value) => setForm((current) => ({ ...current, name: value }))}
              onStatusChange={(value) => setForm((current) => ({ ...current, status: value }))}
              status={form.status}
            />
            <AdapterSelectionSection adapters={adapters} onToggle={toggleAdapter} selectedIds={form.adapterIds} />
            <SinkSelectionSection onToggle={toggleSink} selectedIds={form.sinkIds} sinks={sinks} />
            <ValidationConfigSection form={form} onError={setError} setForm={setForm} />
            <EventsConfigSection form={form} onError={setError} setForm={setForm} />
            <AggregatesConfigSection form={form} onError={setError} setForm={setForm} />
          </div>

          <DeploymentReviewPanel
            aggregatesEnabled={form.aggregatesEnabled}
            deploymentId={form.deploymentId}
            eventsEnabled={form.eventsEnabled}
            gatewayId={form.gatewayId}
            selectedAdapters={selectedAdapters}
            selectedSinks={selectedSinks}
            status={form.status}
            validationEnabled={form.validationEnabled}
          />
        </div>
      )}
    </section>
  )
}
