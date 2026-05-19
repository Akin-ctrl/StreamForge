import { useEffect, useState } from 'react'

import { type CatalogSinkType, type SinkItem, createSink, deleteSink, getCatalog, listSinks, updateSink } from '../../shared/api/client'
import { summarizeSinkConfig } from '../../shared/config/deployments'
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
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<SinkFormState>(buildDefaultSinkForm('timescaledb'))
  const [configJson, setConfigJson] = useState(buildSinkConfigJson(buildDefaultSinkForm('timescaledb')))
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setError(null)
    try {
      const [catalog, sinkRows] = await Promise.all([getCatalog(), listSinks()])
      setCatalogSinks(catalog.sinks)
      setItems(sinkRows)
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
  }

  const startEdit = (item: SinkItem) => {
    setEditingId(item.sink_id)
    setForm(sinkToForm(item, catalogSinks.find((sink) => sink.sink_type === item.sink_type)))
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
        Configure delivery targets here, then attach them to deployments. Sink instances are first-class objects in the
        control plane and no longer belong to an embedded pipeline record.
      </p>

      {error && <p className="error">{error}</p>}

      <div className="composer-layout">
        <div className="builder-section">
          <article className="card">
            <div className="page-header">
              <h3>{editingId ? 'Edit Sink' : 'Create Sink'}</h3>
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
            <button className="btn" onClick={() => void onSubmit()} type="button">
              {editingId ? 'Update Sink' : 'Create Sink'}
            </button>
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
                <th>Summary</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.sink_id}>
                  <td>{item.sink_id}</td>
                  <td>{item.name}</td>
                  <td>{item.sink_type}</td>
                  <td>{item.status}</td>
                  <td>{summarizeSinkConfig(item.sink_type, item.config)}</td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => startEdit(item)} type="button">
                      Edit
                    </button>{' '}
                    <button className="btn btn-secondary" onClick={() => void onDelete(item.sink_id)} type="button">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {items.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
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
