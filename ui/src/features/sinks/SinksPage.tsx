import { useEffect, useMemo, useState } from 'react'

import {
  type CatalogSinkType,
  type DeploymentItem,
  type SinkItem,
  createSink,
  deleteSink,
  getCatalog,
  listDeployments,
  listSinks,
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
import { applySinkConfigJson, buildDefaultSinkForm, buildSinkConfigJson, formToCreateSinkPayload, formToUpdateSinkPayload, sinkToForm, type SinkFormState } from './sinkForm'
import { AlertRouterSinkSection } from './components/AlertRouterSinkSection'
import { HttpSinkSection } from './components/HttpSinkSection'
import { KafkaSinkSection } from './components/KafkaSinkSection'
import { SinkBasicsSection } from './components/SinkBasicsSection'
import { SinkReviewPanel } from './components/SinkReviewPanel'
import { TimescaleSinkSection } from './components/TimescaleSinkSection'

export function SinksPage() {
  const [catalogSinks, setCatalogSinks] = useState<CatalogSinkType[]>([])
  const [items, setItems] = useState<SinkItem[]>([])
  const [deployments, setDeployments] = useState<DeploymentItem[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<SinkFormState>(buildDefaultSinkForm('timescaledb'))
  const [configJson, setConfigJson] = useState(buildSinkConfigJson(buildDefaultSinkForm('timescaledb')))
  const [error, setError] = useState<string | null>(null)
  const [actionResult, setActionResult] = useState<ActionResultViewModel | null>(null)
  const [actionPending, setActionPending] = useState<'validate' | 'test' | null>(null)

  const refresh = async () => {
    setError(null)
    try {
      const [catalog, sinkRows, deploymentRows] = await Promise.all([getCatalog(), listSinks(), listDeployments()])
      setCatalogSinks(catalog.sinks)
      setItems(sinkRows)
      setDeployments(deploymentRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load sinks')
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

  const usageRows = useMemo(() => buildSinkUsage(items, deployments), [items, deployments])

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
    <section>
      <div className="page-header">
        <h2>Sinks</h2>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <p className="muted">
        Configure reusable delivery targets here, then attach those saved sink objects to deployments. Sink instances
        are first-class control-plane objects and no longer belong to an embedded pipeline record.
      </p>

      {error && <p className="error">{error}</p>}

      <div className="composer-layout">
        <div className="builder-section">
          <article className="card">
            <div className="page-header">
              <h3>{editingId ? 'Edit Saved Sink' : 'Create Saved Sink'}</h3>
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
              <button className="btn btn-secondary" disabled={actionPending !== null} onClick={() => void onValidate()} type="button">
                {actionPending === 'validate' ? 'Validating…' : 'Validate'}
              </button>
              <button className="btn btn-secondary" disabled={actionPending !== null} onClick={() => void onTestConnection()} type="button">
                {actionPending === 'test' ? 'Testing…' : 'Test Connection'}
              </button>
              <button className="btn" disabled={actionPending !== null} onClick={() => void onSubmit()} type="button">
                {editingId ? 'Update Sink' : 'Create Sink'}
              </button>
            </div>
          </article>
        </div>

        <SinkReviewPanel form={form} />
      </div>

      <div className="overview-grid">
        <article className="card">
          <h3>Configured Sinks</h3>
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
                    <button className="btn btn-secondary" onClick={() => startEdit(usage.sink)} type="button">
                      Edit
                    </button>{' '}
                    <button className="btn btn-secondary" onClick={() => void onDelete(usage.sink.sink_id)} type="button">
                      Delete
                    </button>
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
        </article>
      </div>
    </section>
  )
}
