import { useEffect, useMemo, useState } from 'react'

import {
  type AdapterItem,
  type CatalogAdapterType,
  createAdapter,
  deleteAdapter,
  getCatalog,
  listAdapters,
  listDeployments,
  updateAdapter,
} from '../../shared/api/client'
import { buildAdapterUsage, summarizeAdapterConfig } from '../../shared/config/deployments'
import {
  adapterToForm,
  applyAdapterConfigJson,
  buildAdapterConfigJson,
  buildDefaultAdapterForm,
  formToCreateAdapterPayload,
  formToUpdateAdapterPayload,
  type AdapterFormState,
} from './adapterForm'
import { AdapterBasicsSection } from './components/AdapterBasicsSection'
import { AdapterReviewPanel } from './components/AdapterReviewPanel'
import { ModbusRtuConfigSection } from './components/ModbusRtuConfigSection'
import { ModbusTcpConfigSection } from './components/ModbusTcpConfigSection'
import { MqttConfigSection } from './components/MqttConfigSection'
import { OpcuaConfigSection } from './components/OpcuaConfigSection'

export function AdaptersPage() {
  const [catalogAdapters, setCatalogAdapters] = useState<CatalogAdapterType[]>([])
  const [items, setItems] = useState<AdapterItem[]>([])
  const [deployments, setDeployments] = useState<any[]>([])
  const [editingId, setEditingId] = useState<string | null>(null)
  const [form, setForm] = useState<AdapterFormState>(buildDefaultAdapterForm('modbus_tcp'))
  const [configJson, setConfigJson] = useState(buildAdapterConfigJson(buildDefaultAdapterForm('modbus_tcp')))
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

  useEffect(() => {
    setConfigJson(buildAdapterConfigJson(form))
  }, [form])

  const usageRows = useMemo(() => buildAdapterUsage(items, deployments), [items, deployments])

  const resetForm = (nextType = form.adapterType) => {
    setEditingId(null)
    setForm(buildDefaultAdapterForm(nextType))
  }

  const startCreate = (nextType: string) => {
    resetForm(nextType)
  }

  const startEdit = (item: AdapterItem) => {
    setEditingId(item.adapter_id)
    setForm(adapterToForm(item))
  }

  const onSubmit = async () => {
    setError(null)
    try {
      if (editingId) {
        await updateAdapter(editingId, formToUpdateAdapterPayload(form))
      } else {
        await createAdapter(formToCreateAdapterPayload(form))
      }
      await refresh()
      resetForm(form.adapterType)
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
        resetForm(form.adapterType)
      }
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete adapter')
    }
  }

  const renderProtocolSection = () => {
    if (form.adapterType === 'modbus_rtu') {
      return <ModbusRtuConfigSection form={form} setForm={setForm} />
    }

    if (form.adapterType === 'mqtt') {
      return <MqttConfigSection form={form} setForm={setForm} />
    }

    if (form.adapterType === 'opcua') {
      return <OpcuaConfigSection form={form} setForm={setForm} />
    }

    return <ModbusTcpConfigSection form={form} setForm={setForm} />
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

      <div className="composer-layout">
        <div className="builder-section">
          <article className="card">
            <div className="page-header">
              <h3>{editingId ? 'Edit Adapter' : 'Create Adapter'}</h3>
              {editingId && (
                <button className="btn btn-secondary" onClick={() => resetForm(form.adapterType)} type="button">
                  Cancel Edit
                </button>
              )}
            </div>
            <AdapterBasicsSection
              adapterId={form.adapterId}
              adapterOptions={catalogAdapters.map((adapter) => ({ value: adapter.adapter_type, label: adapter.label }))}
              adapterType={form.adapterType}
              description={form.description}
              editing={Boolean(editingId)}
              name={form.name}
              onAdapterIdChange={(value) => setForm((current) => ({ ...current, adapterId: value }))}
              onAdapterTypeChange={(value) => setForm(buildDefaultAdapterForm(value))}
              onDescriptionChange={(value) => setForm((current) => ({ ...current, description: value }))}
              onNameChange={(value) => setForm((current) => ({ ...current, name: value }))}
              onStatusChange={(value) => setForm((current) => ({ ...current, status: value }))}
              status={form.status}
            />
            {renderProtocolSection()}
            <details className="card nested-card advanced-block">
              <summary>Advanced JSON</summary>
              <div className="builder-section">
                <label>
                  Adapter Config JSON
                  <textarea rows={14} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
                </label>
                <button
                  className="btn btn-secondary"
                  onClick={() => {
                    try {
                      setForm((current) => applyAdapterConfigJson(current, configJson))
                      setError(null)
                    } catch (jsonError) {
                      setError(jsonError instanceof Error ? jsonError.message : 'Invalid adapter JSON')
                    }
                  }}
                  type="button"
                >
                  Apply JSON
                </button>
              </div>
            </details>
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
                  <th>Adapter</th>
                  <th>Fields</th>
                  <th>Usage</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {catalogAdapters.map((adapter) => (
                  <tr key={adapter.adapter_type}>
                    <td>{adapter.label}</td>
                    <td>{adapter.fields.length}</td>
                    <td>{usageRows.filter((usage) => usage.adapter.adapter_type === adapter.adapter_type).length} configured</td>
                    <td>
                      <button className="btn btn-secondary" onClick={() => startCreate(adapter.adapter_type)} type="button">
                        Start Config
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </article>
        </div>

        <AdapterReviewPanel form={form} />
      </div>

      <div className="overview-grid">
        <article className="card">
          <h3>Configured Adapters</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Adapter ID</th>
                <th>Name</th>
                <th>Type</th>
                <th>Status</th>
                <th>Usage</th>
                <th>Summary</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {usageRows.map((usage) => (
                <tr key={usage.adapter.adapter_id}>
                  <td>{usage.adapter.adapter_id}</td>
                  <td>{usage.adapter.name}</td>
                  <td>{usage.adapter.adapter_type}</td>
                  <td>{usage.adapter.status}</td>
                  <td>{usage.deploymentIds.length} deployment(s)</td>
                  <td>{summarizeAdapterConfig(usage.adapter.adapter_type, usage.adapter.config)}</td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => startEdit(usage.adapter)} type="button">
                      Edit
                    </button>{' '}
                    <button className="btn btn-secondary" onClick={() => void onDelete(usage.adapter.adapter_id)} type="button">
                      Delete
                    </button>
                  </td>
                </tr>
              ))}
              {usageRows.length === 0 && (
                <tr>
                  <td className="muted" colSpan={7}>
                    No adapters configured yet.
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
