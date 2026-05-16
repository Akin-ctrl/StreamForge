import { useEffect, useMemo, useState } from 'react'

import {
  AdapterItem,
  CatalogAdapterType,
  createAdapter,
  deleteAdapter,
  getCatalog,
  listAdapters,
  listDeployments,
  updateAdapter,
} from '../../shared/api/client'
import { buildAdapterUsage, summarizeAdapterConfig } from '../../shared/config/deployments'

function defaultAdapterConfig(adapterType: string): Record<string, unknown> {
  if (adapterType === 'modbus_rtu') {
    return {
      serial_port: '/dev/ttyUSB0',
      baudrate: 9600,
      bytesize: 8,
      parity: 'N',
      stopbits: 1,
      timeout: 1,
      unit_id: 1,
      poll_interval_ms: 1000,
      points: [],
      output: { asset_id: 'asset-01', topic: 'telemetry.raw', events_topic: 'events.raw' },
    }
  }

  if (adapterType === 'mqtt') {
    return {
      broker_host: 'mqtt-broker',
      broker_port: 1883,
      client_id: 'streamforge-mqtt',
      subscriptions: [],
      output: { asset_id: 'asset-01', topic: 'telemetry.raw', events_topic: 'events.raw' },
      advanced: { keepalive_seconds: 60, connect_timeout_seconds: 5, clean_start: true },
    }
  }

  if (adapterType === 'opcua') {
    return {
      endpoint: 'opc.tcp://opcua-server:4840',
      auth_mode: 'anonymous',
      subscription: { publishing_interval_ms: 1000 },
      monitored_items: [],
      output: { asset_id: 'asset-01', topic: 'telemetry.raw' },
      advanced: { security_mode: 'None', security_policy: 'None' },
    }
  }

  return {
    host: 'modbus-simulator',
    port: 502,
    unit_id: 1,
    poll_interval_ms: 1000,
    points: [],
    output: { asset_id: 'asset-01', topic: 'telemetry.raw', events_topic: 'events.raw' },
  }
}

function prettyJson(value: Record<string, unknown>): string {
  return JSON.stringify(value, null, 2)
}

export function AdaptersPage() {
  const [catalogAdapters, setCatalogAdapters] = useState<CatalogAdapterType[]>([])
  const [items, setItems] = useState<AdapterItem[]>([])
  const [deployments, setDeployments] = useState<any[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [adapterId, setAdapterId] = useState('adapter-01')
  const [name, setName] = useState('Adapter 01')
  const [adapterType, setAdapterType] = useState('modbus_tcp')
  const [status, setStatus] = useState('active')
  const [description, setDescription] = useState('')
  const [configJson, setConfigJson] = useState(prettyJson(defaultAdapterConfig('modbus_tcp')))
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [catalog, adapters, deploymentRows] = await Promise.all([getCatalog(), listAdapters(), listDeployments()])
      setCatalogAdapters(catalog.adapters)
      setItems(adapters)
      setDeployments(deploymentRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load adapters')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const usageRows = useMemo(() => buildAdapterUsage(items, deployments), [items, deployments])

  const resetForm = (nextType = adapterType) => {
    setEditingId(null)
    setAdapterId('adapter-01')
    setName('Adapter 01')
    setAdapterType(nextType)
    setStatus('active')
    setDescription('')
    setConfigJson(prettyJson(defaultAdapterConfig(nextType)))
  }

  const startCreate = (nextType: string) => {
    resetForm(nextType)
  }

  const startEdit = (item: AdapterItem) => {
    setEditingId(item.adapter_id)
    setAdapterId(item.adapter_id)
    setName(item.name)
    setAdapterType(item.adapter_type)
    setStatus(item.status)
    setDescription(item.description || '')
    setConfigJson(prettyJson(item.config))
  }

  const onSubmit = async () => {
    setError(null)
    try {
      const parsed = JSON.parse(configJson) as Record<string, unknown>
      if (editingId) {
        await updateAdapter(editingId, { name, status, config: parsed, description: description || null })
      } else {
        await createAdapter({
          adapter_id: adapterId,
          name,
          adapter_type: adapterType,
          status,
          config: parsed,
          description: description || null,
        })
      }
      await refresh()
      resetForm(adapterType)
    } catch (submitError) {
      setError(submitError instanceof Error ? submitError.message : 'Failed to save adapter')
    }
  }

  const onDelete = async (targetAdapterId: string) => {
    setError(null)
    try {
      await deleteAdapter(targetAdapterId)
      await refresh()
      if (editingId === targetAdapterId) {
        resetForm(adapterType)
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete adapter')
    }
  }

  return (
    <section>
      <div className="page-header">
        <h2>Adapters</h2>
        <button className="btn" onClick={() => void refresh()} type="button">
          Refresh
        </button>
      </div>

      <p className="muted">
        Configure protocol connections here, then attach them to deployments. One adapter instance represents one source
        connection or session and may contain many mapped parameters inside its config.
      </p>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading adapters...</p>}

      <div className="overview-kpis">
        <article className="card">
          <h3>Supported Types</h3>
          <p className="overview-kpi-value">{catalogAdapters.length}</p>
          <p className="muted">Published by the catalog</p>
        </article>
        <article className="card">
          <h3>Configured Adapters</h3>
          <p className="overview-kpi-value">{items.length}</p>
          <p className="muted">Persisted adapter instances</p>
        </article>
        <article className="card">
          <h3>Deployments Using Adapters</h3>
          <p className="overview-kpi-value">{deployments.filter((deployment) => deployment.adapter_ids.length > 0).length}</p>
          <p className="muted">Deployment compositions with ingress sources</p>
        </article>
      </div>

      <div className="overview-grid">
        <article className="card">
          <div className="page-header">
            <h3>{editingId ? 'Edit Adapter' : 'Create Adapter'}</h3>
            {editingId && (
              <button className="btn btn-secondary" onClick={() => resetForm(adapterType)} type="button">
                Cancel Edit
              </button>
            )}
          </div>
          <label>
            Adapter ID
            <input disabled={Boolean(editingId)} value={adapterId} onChange={(event) => setAdapterId(event.target.value)} />
          </label>
          <label>
            Name
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <label>
            Type
            <select
              disabled={Boolean(editingId)}
              value={adapterType}
              onChange={(event) => {
                const nextType = event.target.value
                setAdapterType(nextType)
                if (!editingId) {
                  setConfigJson(prettyJson(defaultAdapterConfig(nextType)))
                }
              }}
            >
              {catalogAdapters.map((adapter) => (
                <option key={adapter.adapter_type} value={adapter.adapter_type}>
                  {adapter.label}
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
            <textarea rows={16} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
          </label>
          <button className="btn" onClick={() => void onSubmit()} type="button">
            {editingId ? 'Update Adapter' : 'Create Adapter'}
          </button>
        </article>

        <article className="card">
          <div className="page-header">
            <h3>Supported Types</h3>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Label</th>
                <th>Fields</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {catalogAdapters.map((adapter) => (
                <tr key={adapter.adapter_type}>
                  <td>{adapter.adapter_type}</td>
                  <td>{adapter.label}</td>
                  <td>{adapter.fields.length}</td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => startCreate(adapter.adapter_type)} type="button">
                      New
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </article>
      </div>

      <article className="card">
        <h3>Configured Adapters</h3>
        <table className="table">
          <thead>
            <tr>
              <th>Adapter ID</th>
              <th>Name</th>
              <th>Type</th>
              <th>Status</th>
              <th>Summary</th>
              <th>Deployments</th>
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {usageRows.map(({ adapter, deploymentIds }) => (
              <tr key={adapter.adapter_id}>
                <td>{adapter.adapter_id}</td>
                <td>{adapter.name}</td>
                <td>{adapter.adapter_type}</td>
                <td>{adapter.status}</td>
                <td>{summarizeAdapterConfig(adapter.adapter_type, adapter.config)}</td>
                <td>{deploymentIds.length > 0 ? deploymentIds.join(', ') : 'Unused'}</td>
                <td>
                  <button className="btn btn-secondary" onClick={() => startEdit(adapter)} type="button">
                    Edit
                  </button>{' '}
                  <button className="btn btn-secondary" onClick={() => void onDelete(adapter.adapter_id)} type="button">
                    Delete
                  </button>
                </td>
              </tr>
            ))}
            {usageRows.length === 0 && (
              <tr>
                <td colSpan={7} className="muted">
                  No adapters configured yet.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </article>
    </section>
  )
}
