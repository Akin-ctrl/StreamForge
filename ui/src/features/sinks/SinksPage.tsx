import { FormEvent, useEffect, useState } from 'react'

import {
  PipelineItem,
  SinkItem,
  createSink,
  deleteSink,
  listPipelines,
  listSinks,
} from '../../shared/api/client'

/**
 * Sink management page.
 * Supports list/create/delete for pipeline sink targets.
 */
export function SinksPage() {
  const [items, setItems] = useState<SinkItem[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [pipelineId, setPipelineId] = useState<number>(1)
  const [sinkType, setSinkType] = useState('timescaledb')
  const [status, setStatus] = useState('active')
  // Default sink config for TimescaleDB dev flow.
  const [configJson, setConfigJson] = useState(
    JSON.stringify(
      {
        kafka_bootstrap: 'kafka:9092',
        topic: 'telemetry.clean',
        group_id: 'sf-sink-timescaledb',
        db_dsn: 'postgresql://streamforge:streamforge@timescaledb:5432/streamforge',
        table: 'telemetry_clean',
      },
      null,
      2,
    ),
  )

  // Fetch sinks and pipelines together to keep selector options synchronized.
  const refresh = async () => {
    const [sinkRows, pipelineRows] = await Promise.all([listSinks(), listPipelines()])
    setItems(sinkRows)
    setPipelines(pipelineRows)
    if (pipelineRows.length > 0 && !pipelineRows.some((pipeline) => pipeline.id === pipelineId)) {
      setPipelineId(pipelineRows[0].id)
    }
  }

  useEffect(() => {
    const load = async () => {
      setError(null)
      try {
        await refresh()
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load sinks')
      }
    }
    void load()
  }, [])

  // Parse JSON config, create sink, and refresh list.
  const onCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    try {
      const parsed = JSON.parse(configJson) as Record<string, unknown>
      await createSink({
        pipeline_id: pipelineId,
        sink_type: sinkType,
        status,
        config: parsed,
      })
      await refresh()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create sink')
    }
  }

  // Delete selected sink and refresh table.
  const onDelete = async (sinkId: number) => {
    setError(null)
    try {
      await deleteSink(sinkId)
      await refresh()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete sink')
    }
  }

  return (
    <section>
      <h2>Sinks</h2>
      <p className="muted">
        Sinks are destination connectors attached to gateway deployments. In the current backend model, sink records are
        owned by a pipeline/deployment record even though they are presented here as their own operator surface.
      </p>
      {error && <p className="error">{error}</p>}

      <form className="card" onSubmit={onCreate}>
        <h3>Create Sink</h3>
        <p className="muted">Use this low-level page to define a deployment sink target directly.</p>
        <label>
          Pipeline
          <select
            value={pipelineId}
            onChange={(event) => setPipelineId(Number(event.target.value))}
          >
            {pipelines.map((pipeline) => (
              <option key={pipeline.id} value={pipeline.id}>
                {pipeline.id} - {pipeline.name}
              </option>
            ))}
          </select>
        </label>
        <label>
          Sink Type
          <input value={sinkType} onChange={(event) => setSinkType(event.target.value)} />
        </label>
        <label>
          Status
          <select value={status} onChange={(event) => setStatus(event.target.value)}>
            <option value="active">active</option>
            <option value="paused">paused</option>
          </select>
        </label>
        <label>
          Sink Config (JSON)
          <textarea rows={10} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
        </label>
        <button className="btn" type="submit">
          Create Sink
        </button>
      </form>

      <table className="table">
        <thead>
            <tr>
              <th>ID</th>
              <th>Deployment ID</th>
              <th>Type</th>
              <th>Status</th>
              <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.pipeline_id}</td>
              <td>{item.sink_type}</td>
              <td>{item.status}</td>
              <td>
                <button className="btn btn-secondary" onClick={() => void onDelete(item.id)}>
                  Delete
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  )
}
