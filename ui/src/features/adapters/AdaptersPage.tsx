import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'

import { CatalogAdapterType, PipelineItem, getCatalog, listPipelines } from '../../shared/api/client'
import {
  ConfiguredAdapter,
  PipelineComposerState,
  extractConfiguredAdapters,
  getDeploymentAdapterCount,
} from '../../shared/config/deployments'

/**
 * Adapter inventory and workflow page.
 * Adapters are still deployment-scoped in the backend model, so this page
 * exposes supported types, configured adapters discovered in deployments, and
 * adapter-first entry into the deployment composer.
 */
export function AdaptersPage() {
  const navigate = useNavigate()
  const [catalogAdapters, setCatalogAdapters] = useState<CatalogAdapterType[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
  const [selectedAdapter, setSelectedAdapter] = useState<ConfiguredAdapter | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const [catalog, pipelineRows] = await Promise.all([getCatalog(), listPipelines()])
      setCatalogAdapters(catalog.adapters)
      setPipelines(pipelineRows)
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load adapters')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [])

  const configuredAdapters = useMemo(() => extractConfiguredAdapters(pipelines), [pipelines])

  useEffect(() => {
    if (!selectedAdapter && configuredAdapters.length > 0) {
      setSelectedAdapter(configuredAdapters[0])
      return
    }
    if (selectedAdapter && !configuredAdapters.some((adapter) => adapter.pipelineId === selectedAdapter.pipelineId && adapter.adapterId === selectedAdapter.adapterId)) {
      setSelectedAdapter(configuredAdapters[0] || null)
    }
  }, [configuredAdapters, selectedAdapter])

  const usageByType = useMemo(() => {
    const counts = new Map<string, number>()
    for (const adapter of configuredAdapters) {
      counts.set(adapter.adapterType, (counts.get(adapter.adapterType) || 0) + 1)
    }
    return counts
  }, [configuredAdapters])

  const deploymentsUsingAdapters = useMemo(
    () => pipelines.filter((pipeline) => getDeploymentAdapterCount(pipeline.config) > 0).length,
    [pipelines],
  )

  const startConfigFromType = (adapterType: string) => {
    const state: PipelineComposerState = {
      mode: 'create',
      source: 'adapter-catalog',
      adapterDraft: {
        adapter_id: '',
        adapter_type: adapterType,
        config_values: {},
        registers: [],
        mqtt_subscriptions: [],
        mqtt_mappings: [],
        opcua_monitored_items: [],
      },
    }
    navigate('/create-pipeline', { state })
  }

  const duplicateIntoComposer = (adapter: ConfiguredAdapter) => {
    const state: PipelineComposerState = {
      mode: 'create',
      source: 'adapter-duplicate',
      adapterDraft: {
        ...adapter.draft,
        adapter_id: `${adapter.draft.adapter_id}-copy`,
      },
    }
    navigate('/create-pipeline', { state })
  }

  const editInDeployment = (adapter: ConfiguredAdapter) => {
    const state: PipelineComposerState = {
      mode: 'edit',
      source: 'adapter-edit',
      pipelineId: adapter.pipelineId,
      pipelineName: adapter.pipelineName,
      gatewayId: adapter.gatewayId,
      adapterDraft: adapter.draft,
    }
    navigate('/create-pipeline', { state })
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
        Adapters are protocol ingress connectors. They read from industrial sources like Modbus, MQTT, and OPC UA,
        then publish normalized data into the gateway deployment&apos;s local dataflow.
      </p>
      <p className="muted">
        In the current backend model, adapters are still stored inside pipeline/deployment records. This page makes
        them first-class in the UI workflow while remaining honest about that deployment-scoped ownership.
      </p>

      {error && <p className="error">{error}</p>}
      {loading && <p>Loading adapters...</p>}

      <div className="overview-kpis">
        <article className="card">
          <h3>Supported Types</h3>
          <p className="overview-kpi-value">{catalogAdapters.length}</p>
          <p className="muted">Published by the control-plane catalog</p>
        </article>
        <article className="card">
          <h3>Configured Adapters</h3>
          <p className="overview-kpi-value">{configuredAdapters.length}</p>
          <p className="muted">Across all gateway deployments</p>
        </article>
        <article className="card">
          <h3>Deployments Using Adapters</h3>
          <p className="overview-kpi-value">{deploymentsUsingAdapters}</p>
          <p className="muted">Pipeline records with adapter definitions</p>
        </article>
      </div>

      <div className="overview-grid">
        <article className="card">
          <div className="page-header">
            <h3>Supported Adapter Types</h3>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Label</th>
                <th>Fields</th>
                <th>Configured</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {catalogAdapters.map((adapter) => (
                <tr key={adapter.adapter_type}>
                  <td>{adapter.adapter_type}</td>
                  <td>{adapter.label}</td>
                  <td>{adapter.fields.length}</td>
                  <td>{usageByType.get(adapter.adapter_type) || 0}</td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => startConfigFromType(adapter.adapter_type)} type="button">
                      Start Config
                    </button>
                  </td>
                </tr>
              ))}
              {catalogAdapters.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">
                    No adapter types published by the catalog.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>

        <article className="card">
          <div className="page-header">
            <h3>Configured Adapter Inventory</h3>
            <button className="btn" onClick={() => startConfigFromType(catalogAdapters[0]?.adapter_type || 'modbus_tcp')} type="button">
              Create Adapter Config
            </button>
          </div>
          <table className="table">
            <thead>
              <tr>
                <th>Adapter ID</th>
                <th>Type</th>
                <th>Deployment</th>
                <th>Gateway</th>
                <th>Summary</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {configuredAdapters.slice(0, 24).map((adapter) => (
                <tr key={`${adapter.pipelineId}-${adapter.adapterId}`}>
                  <td>{adapter.adapterId}</td>
                  <td>{adapter.adapterType}</td>
                  <td>
                    {adapter.pipelineId} - {adapter.pipelineName}
                  </td>
                  <td>{adapter.gatewayId}</td>
                  <td>{adapter.summary}</td>
                  <td>
                    <button className="btn btn-secondary" onClick={() => setSelectedAdapter(adapter)} type="button">
                      Inspect
                    </button>{' '}
                    <button className="btn btn-secondary" onClick={() => editInDeployment(adapter)} type="button">
                      Edit In Deployment
                    </button>{' '}
                    <button className="btn btn-secondary" onClick={() => duplicateIntoComposer(adapter)} type="button">
                      Duplicate
                    </button>
                  </td>
                </tr>
              ))}
              {configuredAdapters.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">
                    No configured adapters found yet. Start a protocol config from this page, then attach it through the
                    deployment composer.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>
      </div>

      {selectedAdapter && (
        <article className="card">
          <div className="page-header">
            <h3>Adapter Details</h3>
            <div>
              <button className="btn btn-secondary" onClick={() => editInDeployment(selectedAdapter)} type="button">
                Edit In Deployment
              </button>{' '}
              <button className="btn btn-secondary" onClick={() => duplicateIntoComposer(selectedAdapter)} type="button">
                Duplicate Into Composer
              </button>
            </div>
          </div>
          <div className="review-grid">
            <p>
              <strong>Adapter ID:</strong> {selectedAdapter.adapterId}
            </p>
            <p>
              <strong>Type:</strong> {selectedAdapter.adapterType}
            </p>
            <p>
              <strong>Deployment:</strong> {selectedAdapter.pipelineId} - {selectedAdapter.pipelineName}
            </p>
            <p>
              <strong>Gateway:</strong> {selectedAdapter.gatewayId}
            </p>
            <p>
              <strong>Summary:</strong> {selectedAdapter.summary}
            </p>
            <p>
              <strong>Ownership:</strong> Deployment-scoped adapter config
            </p>
          </div>

          <h4>Compiled Adapter Config</h4>
          <pre className="json-preview">{JSON.stringify(selectedAdapter.config, null, 2)}</pre>
        </article>
      )}
    </section>
  )
}
