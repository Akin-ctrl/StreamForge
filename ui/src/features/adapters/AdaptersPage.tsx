import { useEffect, useMemo, useState } from 'react'

import { CatalogAdapterType, PipelineItem, getCatalog, listPipelines } from '../../shared/api/client'
import { getDeploymentAdapterCount } from '../../shared/config/deployments'

type ConfiguredAdapter = {
  pipelineId: number
  pipelineName: string
  gatewayId: string
  adapterId: string
  adapterType: string
}

function extractConfiguredAdapters(pipelines: PipelineItem[]): ConfiguredAdapter[] {
  const rows: ConfiguredAdapter[] = []

  for (const pipeline of pipelines) {
    const adapters = Array.isArray(pipeline.config.adapters) ? pipeline.config.adapters : []
    for (const adapter of adapters) {
      if (!adapter || typeof adapter !== 'object' || Array.isArray(adapter)) {
        continue
      }
      const record = adapter as Record<string, unknown>
      rows.push({
        pipelineId: pipeline.id,
        pipelineName: pipeline.name,
        gatewayId: pipeline.gateway_id,
        adapterId: String(record.adapter_id || 'unknown-adapter'),
        adapterType: String(record.adapter_type || 'unknown'),
      })
    }
  }

  return rows
}

/**
 * Adapter inventory page.
 * First-pass IA correction page: exposes supported adapter types and shows how
 * they are currently configured inside gateway deployment records.
 */
export function AdaptersPage() {
  const [catalogAdapters, setCatalogAdapters] = useState<CatalogAdapterType[]>([])
  const [pipelines, setPipelines] = useState<PipelineItem[]>([])
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

  const usageByType = useMemo(() => {
    const counts = new Map<string, number>()
    for (const pipeline of pipelines) {
      const adapters = Array.isArray(pipeline.config.adapters) ? pipeline.config.adapters : []
      for (const adapter of adapters) {
        if (!adapter || typeof adapter !== 'object' || Array.isArray(adapter)) {
          continue
        }
        const adapterType = String((adapter as Record<string, unknown>).adapter_type || 'unknown')
        counts.set(adapterType, (counts.get(adapterType) || 0) + 1)
      }
    }
    return counts
  }, [pipelines])

  const deploymentsUsingAdapters = useMemo(
    () => pipelines.filter((pipeline) => getDeploymentAdapterCount(pipeline.config) > 0).length,
    [pipelines],
  )

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
        In the current backend model, adapters are configured inside gateway pipeline/deployment records. This page
        makes that inventory visible now, while fuller first-class adapter management is implemented next.
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
          <h3>Supported Adapter Types</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Type</th>
                <th>Label</th>
                <th>Fields</th>
                <th>Configured</th>
              </tr>
            </thead>
            <tbody>
              {catalogAdapters.map((adapter) => (
                <tr key={adapter.adapter_type}>
                  <td>{adapter.adapter_type}</td>
                  <td>{adapter.label}</td>
                  <td>{adapter.fields.length}</td>
                  <td>{usageByType.get(adapter.adapter_type) || 0}</td>
                </tr>
              ))}
              {catalogAdapters.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No adapter types published by the catalog.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </article>

        <article className="card">
          <h3>Configured Adapter Inventory</h3>
          <table className="table">
            <thead>
              <tr>
                <th>Adapter ID</th>
                <th>Type</th>
                <th>Deployment</th>
                <th>Gateway</th>
              </tr>
            </thead>
            <tbody>
              {configuredAdapters.slice(0, 16).map((adapter) => (
                <tr key={`${adapter.pipelineId}-${adapter.adapterId}`}>
                  <td>{adapter.adapterId}</td>
                  <td>{adapter.adapterType}</td>
                  <td>
                    {adapter.pipelineId} - {adapter.pipelineName}
                  </td>
                  <td>{adapter.gatewayId}</td>
                </tr>
              ))}
              {configuredAdapters.length === 0 && (
                <tr>
                  <td colSpan={4} className="muted">
                    No configured adapters found yet. Compose a deployment to attach adapters to a gateway.
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
