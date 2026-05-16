import { useEffect, useState } from 'react'

import { CatalogSinkType, SinkItem, createSink, deleteSink, getCatalog, listSinks, updateSink } from '../../shared/api/client'

function defaultSinkConfig(sinkType: string): Record<string, unknown> {
  if (sinkType === 'kafka') {
    return {
      source_topic: 'telemetry.clean',
      target_bootstrap: 'kafka:9092',
      target_topic: 'telemetry.outbound',
    }
  }

  if (sinkType === 'http') {
    return {
      source_topic: 'telemetry.clean',
      url: 'http://example.local/telemetry',
      method: 'POST',
    }
  }

  if (sinkType === 'alert_router') {
    return {
      source_topic: 'alarms.raw',
      route_type: 'webhook',
      url: 'http://example.local/alerts',
    }
  }

  return {
    kafka_bootstrap: 'kafka:9092',
    topic: 'telemetry.clean',
    group_id: 'sf-sink-timescaledb',
    db_dsn: 'postgresql://streamforge:streamforge@timescaledb:5432/streamforge',
    table: 'telemetry_clean',
  }
}

function prettyJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2)
}

export function SinksPage() {
  const [catalogSinks, setCatalogSinks] = useState<CatalogSinkType[]>([])
  const [items, setItems] = useState<SinkItem[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [sinkId, setSinkId] = useState('sink-01')
  const [name, setName] = useState('Sink 01')
  const [sinkType, setSinkType] = useState('timescaledb')
  const [status, setStatus] = useState('active')
  const [description, setDescription] = useState('')
  const [configJson, setConfigJson] = useState(prettyJson(defaultSinkConfig('timescaledb')))
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

  const resetForm = (nextType = sinkType) => {
    setEditingId(null)
    setSinkId('sink-01')
    setName('Sink 01')
    setSinkType(nextType)
    setStatus('active')
    setDescription('')
    setConfigJson(prettyJson(defaultSinkConfig(nextType)))
  }

  const startEdit = (item: SinkItem) => {
    setEditingId(item.sink_id)
    setSinkId(item.sink_id)
    setName(item.name)
    setSinkType(item.sink_type)
    setStatus(item.status)
    setDescription(item.description || '')
    setConfigJson(prettyJson(item.config))
  }

  const onSubmit = async () => {
    setError(null)
    try {
      const parsed = JSON.parse(configJson) as Record<string, unknown>
      if (editingId) {
        await updateSink(editingId, { name, sink_type: sinkType, status, config: parsed, description: description || null })
      } else {
        await createSink({
          sink_id: sinkId,
          name,
          sink_type: sinkType,
          status,
          config: parsed,
          description: description || null,
        })
      }
      await refresh()
      resetForm(sinkType)
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
        resetForm(sinkType)
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete sink')
    }
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

      <div className="overview-grid">
        <article className="card">
          <div className="page-header">
            <h3>{editingId ? 'Edit Sink' : 'Create Sink'}</h3>
            {editingId && (
              <button className="btn btn-secondary" onClick={() => resetForm(sinkType)} type="button">
                Cancel Edit
              </button>
            )}
          </div>
          <label>
            Sink ID
            <input disabled={Boolean(editingId)} value={sinkId} onChange={(event) => setSinkId(event.target.value)} />
          </label>
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Type
            <select
              disabled={Boolean(editingId)}
              value={sinkType}
              onChange={(event) => {
                const nextType = event.target.value
                setSinkType(nextType)
                if (!editingId) {
                  setConfigJson(prettyJson(defaultSinkConfig(nextType)))
                }
              }}
            >
              {catalogSinks.map((sink) => (
                <option key={sink.sink_type} value={sink.sink_type}>
                  {sink.label}
                </option>
              ))}
            </select>
          </label>
          <label>
            Status
            <select value={status} onChange={(event) => setStatus(event.target.value)}>
              <option value="active">active</option>
              <option value="paused">paused</option>
              <option value="disabled">disabled</option>
            </select>
          </label>
          <label>
            Description
            <input value={description} onChange={(event) => setDescription(event.target.value)} />
          </label>
          <label>
            Config (JSON)
            <textarea rows={14} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
          </label>
          <button className="btn" onClick={() => void onSubmit()} type="button">
            {editingId ? 'Update Sink' : 'Create Sink'}
          </button>
        </article>

        <article className="card">
          <h3>Configured Sinks</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Sink ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Status</th>
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
                  <td colSpan={5} className="muted">
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
