import { useEffect, useMemo, useState } from 'react'

import {
  type CatalogSinkType,
  type DeploymentItem,
  type SinkItem,
  createSink,
  deleteSink,
  getCatalog,
  getGatewayConnectionTest,
  listDeployments,
  listSinks,
  requestGatewayConnectionTest,
  testSinkConnection,
  updateSink,
  validateSinkDraft,
} from '../../shared/api/client'
import { buildSinkUsage, summarizeSinkConfig } from '../../shared/config/deployments'
import { ActionResultPanel } from '../../shared/forms/ActionResultPanel'
import {
  connectionTestToViewModel,
  type ActionResultViewModel,
  validationResultToViewModel,
} from '../../shared/forms/validationIssues'
import { MetricCard } from '../../shared/data-display/MetricCard'
import { PageCallout } from '../../shared/layout/PageCallout'
import { applySinkConfigJson, buildDefaultSinkForm, buildSinkConfigJson, formToCreateSinkPayload, formToUpdateSinkPayload, sinkToForm, type SinkFormState } from './sinkForm'
import { AlertRouterSinkSection } from './components/AlertRouterSinkSection'
import { HttpSinkSection } from './components/HttpSinkSection'
import { KafkaSinkSection } from './components/KafkaSinkSection'
import { SinkBasicsSection } from './components/SinkBasicsSection'
import { SinkReviewPanel } from './components/SinkReviewPanel'
import { TimescaleSinkSection } from './components/TimescaleSinkSection'

const gatewayTestTerminalStatuses = new Set(['PASSED', 'FAILED', 'UNSUPPORTED'])

function sleep(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

export function SinksPage() {
  const [catalogSinks, setCatalogSinks] = useState<CatalogSinkType[]>([])
  const [items, setItems] = useState<SinkItem[]>([])
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<SinkFormState>(buildDefaultSinkForm('timescaledb'))
  const [configJson, setConfigJson] = useState(buildSinkConfigJson(buildDefaultSinkForm('timescaledb')))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<ActionResultViewModel | null>(null)
  const [actionPending, setActionPending] = useState<'validate' | 'test' | null>(null)
  const [gatewayTestPendingId, setGatewayTestPendingId] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [catalog, sinkRows, deploymentRows] = await Promise.all([getCatalog(), listSinks(), listDeployments()])
      setCatalogSinks(catalog.sinks)
      setItems(sinkRows)
      setDeployments(deploymentRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load sinks')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const currentContract = catalogSinks.find((sink) => sink.sink_type === form.sinkType)

  useEffect(() => {
    setConfigJson(buildSinkConfigJson(form, currentContract))
  }, [form, currentContract])

  const resetForm = (nextType = form.sinkType) => {
    setEditingId(null)
    setForm(buildDefaultSinkForm(nextType, catalogSinks.find((sink) => sink.sink_type === nextType)))
    setActionResult(null)
  }

  const startEdit = (item: SinkItem) => {
    setEditingId(item.sink_id)
    setForm(sinkToForm(item, catalogSinks.find((sink) => sink.sink_type === item.sink_type)))
    setActionResult(null)
  }

  const onSubmit = async () => {
    setError(null)
    try {
      if (editingId) {
        await updateSink(editingId, formToUpdateSinkPayload(form))
      } else {
        await createSink(formToCreateSinkPayload(form))
      }
      await refresh()
      resetForm(form.sinkType)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to save sink')
    }
  }

  const onValidate = async () => {
    setActionPending('validate')
    setError(null)
    try {
      const result = await validateSinkDraft(formToCreateSinkPayload(form))
      setActionResult(validationResultToViewModel('Sink Validation', result))
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to validate sink')
    } finally {
      setActionPending(null)
    }
  }

  const onTestConnection = async () => {
    setActionPending('test')
    setError(null)
    try {
      const result = await testSinkConnection(formToCreateSinkPayload(form))
      setActionResult(connectionTestToViewModel('Sink Connection Test', result))
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to test sink connection')
    } finally {
      setActionPending(null)
    }
  }

  const waitForGatewayConnectionTest = async (requestId: string) => {
    for (let attempt = 0; attempt < 24; attempt += 1) {
      const current = await getGatewayConnectionTest(requestId)
      if (gatewayTestTerminalStatuses.has(current.status) && current.result) {
        return current
      }
      await sleep(2000)
    }
    throw new Error('Gateway-side connection test did not finish within 48 seconds')
  }

  const onGatewayConnectionTest = async (targetSinkId: string, gatewayIds: string[]) => {
    const gatewayId = gatewayIds[0]
    if (!gatewayId) {
      setError('Attach this sink to an active gateway deployment before running a gateway-side connection test.')
      return
    }

    setGatewayTestPendingId(targetSinkId)
    setError(null)
    try {
      const requested = await requestGatewayConnectionTest({
        gateway_id: gatewayId,
        target_kind: 'sink',
        target_id: targetSinkId,
      })
      const completed = await waitForGatewayConnectionTest(requested.request_id)
      if (!completed.result) {
        throw new Error('Gateway-side connection test finished without a result')
      }
      setActionResult(connectionTestToViewModel(`Gateway Connection Test · ${gatewayId}`, completed.result))
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to run gateway-side connection test')
    } finally {
      setGatewayTestPendingId(null)
    }
  }

  const usageRows = useMemo(() => buildSinkUsage(items, deployments), [items, deployments])
  const deploymentsUsingSinks = useMemo(
    () => deployments.filter((deployment) => deployment.sink_ids.length > 0).length,
    [deployments],
  )

  const onDelete = async (targetSinkId: string) => {
    setError(null)
    try {
      await deleteSink(targetSinkId)
      await refresh()
      if (editingId === targetSinkId) {
        resetForm(form.sinkType)
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete sink')
    }
  }

  const renderSinkSection = () => {
    if (form.sinkType === 'kafka') {
      return <KafkaSinkSection contract={currentContract} form={form} setForm={setForm} />
    }

    if (form.sinkType === 'http') {
      return <HttpSinkSection contract={currentContract} form={form} setForm={setForm} />
    }

    if (form.sinkType === 'alert_router') {
      return <AlertRouterSinkSection contract={currentContract} form={form} setForm={setForm} />
    }

    return <TimescaleSinkSection contract={currentContract} form={form} setForm={setForm} />
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Sinks</h2>
          <p className="muted">
            Configure reusable delivery targets here, then attach those saved sink objects to deployments. Sink
            instances are first-class control-plane objects and no longer belong to an embedded pipeline record.
          </p>
        </div>
        <div className="page-actions">
          <button className="btn" onClick={() => void refresh()} type="button">
            Refresh
          </button>
        </div>
      </div>

      <PageCallout title="Recommended workflow">
        <p className="muted">
          Define the destination, validate it, run a connection test when supported, then reuse the saved sink across
          one or more deployments.
        </p>
      </PageCallout>

      {error && <p className="error">{error}</p>}
      {loading && (
        <article className="card empty-state">
          <p>Loading sinks...</p>
          <p className="muted">Fetching saved sinks, deployment usage, and control-plane catalog metadata.</p>
        </article>
      )}

      {!loading && (
        <>
          <div className="overview-kpis">
            <MetricCard detail="Published by the catalog" title="Supported Types" value={catalogSinks.length} />
            <MetricCard detail="Persisted delivery targets" title="Configured Sinks" value={items.length} />
            <MetricCard
              detail="Deployment compositions with delivery output"
              title="Deployments Using Sinks"
              value={deploymentsUsingSinks}
            />
          </div>

          <div className="wizard-steps" aria-label="Sink authoring flow">
            <span className="wizard-step active">1. Define</span>
            <span className="wizard-step active">2. Validate</span>
            <span className="wizard-step active">3. Test</span>
            <span className="wizard-step">4. Save For Reuse</span>
          </div>

          <div className="composer-layout">
            <div className="builder-section">
              <article className="card">
                <div className="page-header">
                  <div className="card-header-copy">
                    <h3>{editingId ? 'Edit Saved Sink' : 'Create Saved Sink'}</h3>
                    <p className="muted">
                      Keep the delivery target readable here, then use the summary on the right to confirm destination
                      posture before saving.
                    </p>
                  </div>
                  {editingId && (
                    <button className="btn btn-secondary" onClick={() => resetForm(form.sinkType)} type="button">
                      Cancel Edit
                    </button>
                  )}
                </div>
                <SinkBasicsSection
                  description={form.description}
                  editing={Boolean(editingId)}
                  name={form.name}
                  onDescriptionChange={(value) => setForm((current) => ({ ...current, description: value }))}
                  onNameChange={(value) => setForm((current) => ({ ...current, name: value }))}
                  onSinkIdChange={(value) => setForm((current) => ({ ...current, sinkId: value }))}
                  onSinkTypeChange={(value) =>
                    setForm(buildDefaultSinkForm(value, catalogSinks.find((sink) => sink.sink_type === value)))
                  }
                  onStatusChange={(value) => setForm((current) => ({ ...current, status: value }))}
                  sinkId={form.sinkId}
                  sinkOptions={catalogSinks.map((sink) => ({ value: sink.sink_type, label: sink.label }))}
                  sinkType={form.sinkType}
                  status={form.status}
                />
                {renderSinkSection()}
                <details className="card nested-card advanced-block">
                  <summary>Advanced JSON</summary>
                  <div className="builder-section">
                    <p className="muted">
                      Use the JSON editor for catalog-backed fields that are easier to review in bulk. Secret values are
                      still handled separately.
                    </p>
                    <label>
                      Sink Config JSON
                      <textarea rows={12} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
                    </label>
                    <button
                      className="btn btn-secondary"
                      onClick={() => {
                        try {
                          setForm((current) => applySinkConfigJson(current, configJson, currentContract))
                          setError(null)
                        } catch (jsonError) {
                          setError(jsonError instanceof Error ? jsonError.message : 'Invalid sink JSON')
                        }
                      }}
                      type="button"
                    >
                      Apply JSON
                    </button>
                  </div>
                </details>
                {actionResult && <ActionResultPanel result={actionResult} />}
                <div className="page-actions">
                  <button
                    className="btn btn-secondary"
                    disabled={actionPending !== null}
                    onClick={() => void onValidate()}
                    type="button"
                  >
                    {actionPending === 'validate' ? 'Validating…' : 'Validate'}
                  </button>
                  <button
                    className="btn btn-secondary"
                    disabled={actionPending !== null}
                    onClick={() => void onTestConnection()}
                    type="button"
                  >
                    {actionPending === 'test' ? 'Testing…' : 'Test Connection'}
                  </button>
                  <button className="btn" disabled={actionPending !== null} onClick={() => void onSubmit()} type="button">
                    {editingId ? 'Update Sink' : 'Create Sink'}
                  </button>
                </div>
              </article>

              <article className="card table-card">
                <div className="card-header-copy">
                  <h3>Supported Types</h3>
                  <p className="muted table-caption">Start a new sink from a catalog-backed destination template.</p>
                </div>
                <div className="table-scroll">
                  <table className="table">
                    <thead>
                      <tr>
                        <th>Sink</th>
                        <th>Fields</th>
                        <th>Usage</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {catalogSinks.map((sink) => (
                        <tr key={sink.sink_type}>
                          <td>{sink.label}</td>
                          <td>{sink.fields.length}</td>
                          <td>{usageRows.filter((usage) => usage.sink.sink_type === sink.sink_type).length} configured</td>
                          <td>
                            <div className="table-actions">
                              <button
                                className="btn btn-secondary"
                                onClick={() => resetForm(sink.sink_type)}
                                type="button"
                              >
                                Start Config
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </article>
            </div>

            <SinkReviewPanel form={form} />
          </div>

          <div className="overview-grid">
            <article className="card table-card">
              <div className="card-header-copy">
                <h3>Configured Sinks</h3>
                <p className="muted table-caption">
                  Review saved delivery targets, where they are reused, and the destination posture each one represents.
                </p>
              </div>
              <div className="table-scroll">
                <table className="table">
                  <thead>
                    <tr>
                      <th>Sink ID</th>
                      <th>Name</th>
                      <th>Type</th>
                      <th>Status</th>
                      <th>Used By</th>
                      <th>Summary</th>
                      <th>Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {usageRows.map((usage) => (
                      <tr key={usage.sink.sink_id}>
                        <td>{usage.sink.sink_id}</td>
                        <td>{usage.sink.name}</td>
                        <td>{usage.sink.sink_type}</td>
                        <td>{usage.sink.status}</td>
                        <td>
                          {usage.deploymentIds.length} deployment(s)
                          {usage.gatewayIds.length > 0 ? ` across ${usage.gatewayIds.length} gateway(s)` : ''}
                        </td>
                        <td>{summarizeSinkConfig(usage.sink.sink_type, usage.sink.config)}</td>
                        <td>
                          <div className="table-actions">
                            <button className="btn btn-secondary" onClick={() => startEdit(usage.sink)} type="button">
                              Edit
                            </button>
                            <button
                              className="btn btn-secondary"
                              disabled={gatewayTestPendingId !== null}
                              onClick={() => void onGatewayConnectionTest(usage.sink.sink_id, usage.gatewayIds)}
                              type="button"
                            >
                              {gatewayTestPendingId === usage.sink.sink_id ? 'Testing On Gateway…' : 'Test On Gateway'}
                            </button>
                            <button
                              className="btn btn-secondary"
                              onClick={() => void onDelete(usage.sink.sink_id)}
                              type="button"
                            >
                              Delete
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                    {usageRows.length === 0 && (
                      <tr>
                        <td colSpan={7} className="muted">
                          No sinks configured yet.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            </article>
          </div>
        </>
      )}
    </section>
  )
}
