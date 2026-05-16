import { useEffect, useMemo, useState } from 'react'

import {
  AdapterItem,
  DeploymentItem,
  GatewayItem,
  SinkItem,
  createDeployment,
  deleteDeployment,
  listAdapters,
  listDeployments,
  listGateways,
  listSinks,
  updateDeployment,
} from '../../shared/api/client'
import { summarizeDeployment } from '../../shared/config/deployments'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

function prettyJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2)
}

const DEFAULT_VALIDATION = prettyJson({
  enabled: true,
  raw_topic: 'telemetry.raw',
  clean_topic: 'telemetry.clean',
  dlq_topic: 'dlq.telemetry',
})

const DEFAULT_EVENTS = prettyJson({
  enabled: true,
  raw_topic: 'events.raw',
  clean_topic: 'events.clean',
  dlq_topic: 'dlq.events',
})

const DEFAULT_AGGREGATES = prettyJson({
  enabled: true,
  source_topic: 'telemetry.clean',
  resolutions: {
    '1s': { enabled: true, topic: 'telemetry.1s', window_seconds: 1 },
    '1min': { enabled: true, topic: 'telemetry.1min', window_seconds: 60 },
  },
})

export function PipelinesPage() {
  const { timezone } = useOperatorPreferences()
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [adapters, setAdapters] = useState<AdapterItem[]>([])
  const [sinks, setSinks] = useState<SinkItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [editingId, setEditingId] = useState<string | null>(null)
  const [deploymentId, setDeploymentId] = useState('deployment-demo-01')
  const [name, setName] = useState('Demo Deployment')
  const [gatewayId, setGatewayId] = useState('gateway-demo-01')
  const [status, setStatus] = useState('active')
  const [selectedAdapterIds, setSelectedAdapterIds] = useState<string[]>([])
  const [selectedSinkIds, setSelectedSinkIds] = useState<string[]>([])
  const [validationJson, setValidationJson] = useState(DEFAULT_VALIDATION)
  const [eventsJson, setEventsJson] = useState(DEFAULT_EVENTS)
  const [aggregatesJson, setAggregatesJson] = useState(DEFAULT_AGGREGATES)

  const refresh = async () => {
    setError(null)
    try {
      const [deploymentRows, gatewayRows, adapterRows, sinkRows] = await Promise.all([
        listDeployments(),
        listGateways(),
        listAdapters(),
        listSinks(),
      ])
      setDeployments(deploymentRows)
      setGateways(gatewayRows)
      setAdapters(adapterRows)
      setSinks(sinkRows)
      if (gatewayRows.length > 0 && !gatewayRows.some((gateway) => gateway.gateway_id === gatewayId)) {
        setGatewayId(gatewayRows[0].gateway_id)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load deployments')
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const gatewayOptions = useMemo(() => gateways.map((gateway) => gateway.gateway_id), [gateways])

  const resetForm = () => {
    setEditingId(null)
    setDeploymentId('deployment-demo-01')
    setName('Demo Deployment')
    setGatewayId(gatewayOptions[0] || 'gateway-demo-01')
    setStatus('active')
    setSelectedAdapterIds([])
    setSelectedSinkIds([])
    setValidationJson(DEFAULT_VALIDATION)
    setEventsJson(DEFAULT_EVENTS)
    setAggregatesJson(DEFAULT_AGGREGATES)
  }

  const toggleSelection = (values: string[], nextValue: string) =>
    values.includes(nextValue) ? values.filter((value) => value !== nextValue) : [...values, nextValue]

  const startEdit = (deployment: DeploymentItem) => {
    setEditingId(deployment.deployment_id)
    setDeploymentId(deployment.deployment_id)
    setName(deployment.name)
    setGatewayId(deployment.gateway_id)
    setStatus(deployment.status)
    setSelectedAdapterIds(deployment.adapter_ids)
    setSelectedSinkIds(deployment.sink_ids)
    setValidationJson(prettyJson(deployment.validation_config))
    setEventsJson(prettyJson(deployment.events_config))
    setAggregatesJson(prettyJson(deployment.aggregates_config))
  }

  const onSubmit = async () => {
    setError(null)
    try {
      const payload = {
        deployment_id: deploymentId,
        name,
        gateway_id: gatewayId,
        status,
        adapter_ids: selectedAdapterIds,
        sink_ids: selectedSinkIds,
        validation_config: JSON.parse(validationJson) as Record<string, unknown>,
        events_config: JSON.parse(eventsJson) as Record<string, unknown>,
        aggregates_config: JSON.parse(aggregatesJson) as Record<string, unknown>,
      }

      if (editingId) {
        await updateDeployment(editingId, payload)
      } else {
        await createDeployment(payload)
      }
      await refresh()
      resetForm()
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to save deployment')
    }
  }

  const onDelete = async (targetDeploymentId: string) => {
    setError(null)
    try {
      await deleteDeployment(targetDeploymentId)
      await refresh()
      if (editingId === targetDeploymentId) {
        resetForm()
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete deployment')
    }
  }

  return (
    <section>
      <div className="page-header">
        <h2>Deployments</h2>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <p className="muted">
        A deployment selects one gateway, attaches configured adapters and sinks, and defines the validation, event,
        and aggregate rules that become the gateway&apos;s active runtime config.
      </p>
      {error && <p className="error">{error}</p>}

      <div className="overview-grid">
        <article className="card">
          <div className="page-header">
            <h3>{editingId ? 'Edit Deployment' : 'Compose Deployment'}</h3>
            {editingId && (
              <button className="btn btn-secondary" onClick={() => resetForm()} type="button">
                Cancel Edit
              </button>
            )}
          </div>
          <label>
            Deployment ID
            <input disabled={Boolean(editingId)} value={deploymentId} onChange={(event) => setDeploymentId(event.target.value)} />
          </label>
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Gateway
            <select value={gatewayId} onChange={(event) => setGatewayId(event.target.value)}>
              {gateways.map((gateway) => (
                <option key={gateway.gateway_id} value={gateway.gateway_id}>
                  {gateway.gateway_id}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="draft">draft</option>
              <option value="active">active</option>
              <option value="disabled">disabled</option>
            </select>
          </label>

          <div className="card nested-card">
            <h4>Adapters</h4>
            {adapters.map((adapter) => (
              <label key={adapter.adapter_id}>
                <input
                  type="checkbox"
                  checked={selectedAdapterIds.includes(adapter.adapter_id)}
                  onChange={() => setSelectedAdapterIds((current) => toggleSelection(current, adapter.adapter_id))}
                />{' '}
                {adapter.adapter_id} ({adapter.adapter_type})
              </label>
            ))}
            {adapters.length === 0 && <p className="muted">Create adapters first.</p>}
          </div>

          <div className="card nested-card">
            <h4>Sinks</h4>
            {sinks.map((sink) => (
              <label key={sink.sink_id}>
                <input
                  type="checkbox"
                  checked={selectedSinkIds.includes(sink.sink_id)}
                  onChange={() => setSelectedSinkIds((current) => toggleSelection(current, sink.sink_id))}
                />{' '}
                {sink.sink_id} ({sink.sink_type})
              </label>
            ))}
            {sinks.length === 0 && <p className="muted">Create sinks first.</p>}
          </div>

          <label>
            Validation Config (JSON)
            <textarea rows={8} value={validationJson} onChange={(event) => setValidationJson(event.target.value)} />
          </label>
          <label>
            Events Config (JSON)
            <textarea rows={6} value={eventsJson} onChange={(event) => setEventsJson(event.target.value)} />
          </label>
          <label>
            Aggregates Config (JSON)
            <textarea rows={8} value={aggregatesJson} onChange={(event) => setAggregatesJson(event.target.value)} />
          </label>
          <button className="btn" onClick={() => void onSubmit()} type="button">
            {editingId ? 'Update Deployment' : 'Create Deployment'}
          </button>
        </article>

        <article className="card">
          <h3>Deployments</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Deployment ID</th>
                <th>Gateway</th>
                <th>Status</th>
                <th>Adapters</th>
                <th>Sinks</th>
                <th>Created</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {deployments.map((deployment) => {
                const summary = summarizeDeployment(deployment)
                return (
                  <tr key={deployment.deployment_id}>
                    <td>{deployment.deployment_id}</td>
                    <td>{deployment.gateway_id}</td>
                    <td>{deployment.status}</td>
                    <td>{summary.adapterCount}</td>
                    <td>{summary.sinkCount}</td>
                    <td>{formatDateTime(deployment.created_at, timezone, { includeTimezone: true })}</td>
                    <td>
                      <button className="btn btn-secondary" onClick={() => startEdit(deployment)} type="button">
                        Edit
                      </button>{' '}
                      <button className="btn btn-secondary" onClick={() => void onDelete(deployment.deployment_id)} type="button">
                        Delete
                      </button>
                    </td>
                  </tr>
                )
              })}
              {deployments.length === 0 && (
                <tr>
                  <td colSpan={7} className="muted">
                    No deployments configured yet.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>
      </div>
    </section>
  )
}
