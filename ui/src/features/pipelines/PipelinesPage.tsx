import { FormEvent, useEffect, useState } from 'react'

import {
  GatewayItem,
  PipelineItem,
  createPipeline,
  deletePipeline,
  listGateways,
  listPipelines,
} from '../../shared/api/client'
import { formatDateTime } from '../../shared/format/datetime'
import { useOperatorPreferences } from '../../shared/preferences/PreferencesProvider'

/**
 * Pipelines management page.
 * Supports list/create/delete with JSON config input.
 */
export function PipelinesPage() {
  const { timezone } = useOperatorPreferences()
  const [items, setItems] = useState<PipelineItem[]>([])
  const [gateways, setGateways] = useState<GatewayItem[]>([])
  const [error, setError] = useState<string | null>(null)
  const [name, setName] = useState('demo-pipeline-ui')
  const [gatewayId, setGatewayId] = useState('gateway-demo-01')
  // Seed JSON keeps create flow aligned with the dev demo topology.
  const [configJson, setConfigJson] = useState(
    JSON.stringify(
      {
        adapters: [
          {
            adapter_id: 'modbus-demo-01',
            adapter_type: 'modbus_tcp',
            config: {
              host: 'modbus-simulator',
              port: 5020,
              unit_id: 1,
              poll_interval_ms: 1000,
              registers: [
                {
                  address: 40001,
                  param: 'temperature',
                  type: 'float32',
                  unit: 'celsius',
                },
              ],
              output: {
                kafka_bootstrap: 'kafka:9092',
                topic: 'telemetry.raw',
                asset_id: 'demo_sensor_01',
              },
            },
          },
        ],
        validation: {
          enabled: true,
          raw_topic: 'telemetry.raw',
          clean_topic: 'telemetry.clean',
          dlq_topic: 'dlq.telemetry',
          ranges: {
            temperature: { min: -50, max: 500 },
          },
          rate_of_change: { temperature: 20 },
          gap_detection: { temperature: 5 },
        },
      },
      null,
      2,
    ),
  )

  // Pull pipelines and gateways together so form options always match current state.
  const refresh = async () => {
    const [pipelineRows, gatewayRows] = await Promise.all([listPipelines(), listGateways()])
    setItems(pipelineRows)
    setGateways(gatewayRows)
    if (gatewayRows.length > 0 && !gatewayRows.some((gateway) => gateway.gateway_id === gatewayId)) {
      setGatewayId(gatewayRows[0].gateway_id)
    }
  }

  useEffect(() => {
    const load = async () => {
      setError(null)
      try {
        await refresh()
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : 'Failed to load pipelines')
      }
    }
    void load()
  }, [])

  // Parse JSON config, submit create request, then refresh list.
  const onCreate = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    setError(null)
    try {
      const parsed = JSON.parse(configJson) as Record<string, unknown>
      await createPipeline({
        name,
        gateway_id: gatewayId,
        config: parsed,
      })
      await refresh()
    } catch (createError) {
      setError(createError instanceof Error ? createError.message : 'Failed to create pipeline')
    }
  }

  // Delete selected pipeline and refresh table.
  const onDelete = async (pipelineId: number) => {
    setError(null)
    try {
      await deletePipeline(pipelineId)
      await refresh()
    } catch (deleteError) {
      setError(deleteError instanceof Error ? deleteError.message : 'Failed to delete pipeline')
    }
  }

  return (
    <section>
      <h2>Pipelines</h2>
      {error && <p className="error">{error}</p>}

      <form className="card" onSubmit={onCreate}>
        <h3>Create Pipeline</h3>
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
          Pipeline Config (JSON)
          <textarea rows={12} value={configJson} onChange={(event) => setConfigJson(event.target.value)} />
        </label>
        <button className="btn" type="submit">
          Create Pipeline
        </button>
      </form>

      <table className="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Name</th>
            <th>Gateway</th>
            <th>Created</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.id}</td>
              <td>{item.name}</td>
              <td>{item.gateway_id}</td>
              <td>{formatDateTime(item.created_at, timezone, { includeTimezone: true })}</td>
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
