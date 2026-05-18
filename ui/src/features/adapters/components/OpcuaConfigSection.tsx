import type { Dispatch, SetStateAction } from 'react'

import { createDefaultMonitoredItemForm, type AdapterFormState, type OpcuaMonitoredItemForm } from '../adapterForm'

type OpcuaConfigSectionProps = {
  form: AdapterFormState
  setForm: Dispatch<SetStateAction<AdapterFormState>>
}

function updateMonitoredItem(
  items: OpcuaMonitoredItemForm[],
  index: number,
  nextItem: OpcuaMonitoredItemForm,
) {
  return items.map((item, itemIndex) => (itemIndex === index ? nextItem : item))
}

export function OpcuaConfigSection({ form, setForm }: OpcuaConfigSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>OPC UA</h3>
      </div>
      <div className="inline-grid">
        <label>
          Endpoint
          <input value={form.endpoint} onChange={(event) => setForm((current) => ({ ...current, endpoint: event.target.value }))} />
        </label>
        <label>
          Authentication
          <select value={form.authMode} onChange={(event) => setForm((current) => ({ ...current, authMode: event.target.value }))}>
            <option value="anonymous">Anonymous</option>
            <option value="username_password">Username / Password</option>
          </select>
        </label>
        <label>
          Default Asset ID
          <input value={form.defaultAssetId} onChange={(event) => setForm((current) => ({ ...current, defaultAssetId: event.target.value }))} />
        </label>
        <label>
          Publishing Interval (ms)
          <input
            value={form.publishingIntervalMs}
            onChange={(event) => setForm((current) => ({ ...current, publishingIntervalMs: event.target.value }))}
          />
        </label>
      </div>

      {form.authMode === 'username_password' && (
        <div className="inline-grid">
          <label>
            Username
            <input value={form.username} onChange={(event) => setForm((current) => ({ ...current, username: event.target.value }))} />
          </label>
          <label>
            Password
            <input
              type="password"
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            />
          </label>
        </div>
      )}

      <div className="nested-card card builder-section">
        <div className="page-header">
          <h4>Monitored Items</h4>
          <button
            className="btn btn-secondary"
            onClick={() => setForm((current) => ({ ...current, monitoredItems: [...current.monitoredItems, createDefaultMonitoredItemForm()] }))}
            type="button"
          >
            Add Item
          </button>
        </div>
        {form.monitoredItems.length === 0 ? (
          <p className="muted">Add the nodes this session should monitor.</p>
        ) : (
          form.monitoredItems.map((item, index) => (
            <div className="rule-stack" key={`${item.node_id}-${index}`}>
              <div className="inline-grid">
                <input
                  placeholder="Node ID"
                  value={item.node_id}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, node_id: event.target.value }),
                    }))
                  }
                />
                <input
                  placeholder="Parameter"
                  value={item.parameter}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, parameter: event.target.value }),
                    }))
                  }
                />
                <input
                  placeholder="Unit"
                  value={item.unit}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, unit: event.target.value }),
                    }))
                  }
                />
                <input
                  placeholder="Asset override"
                  value={item.asset_id_override}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, asset_id_override: event.target.value }),
                    }))
                  }
                />
              </div>
              <div className="inline-grid">
                <input
                  placeholder="Sampling interval (ms)"
                  value={item.sampling_interval_ms}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, sampling_interval_ms: event.target.value }),
                    }))
                  }
                />
                <input
                  placeholder="Queue size"
                  value={item.queue_size}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, queue_size: event.target.value }),
                    }))
                  }
                />
                <select
                  value={item.monitoring_mode}
                  onChange={(event) =>
                    setForm((current) => ({
                      ...current,
                      monitoredItems: updateMonitoredItem(current.monitoredItems, index, { ...item, monitoring_mode: event.target.value }),
                    }))
                  }
                >
                  <option value="reporting">Reporting</option>
                </select>
                <button
                  className="btn btn-secondary"
                  onClick={() => setForm((current) => ({ ...current, monitoredItems: current.monitoredItems.filter((_, itemIndex) => itemIndex !== index) }))}
                  type="button"
                >
                  Remove
                </button>
              </div>
            </div>
          ))
        )}
      </div>

      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <div className="inline-grid">
          <label>
            Security Mode
            <select value={form.securityMode} onChange={(event) => setForm((current) => ({ ...current, securityMode: event.target.value }))}>
              <option value="None">None</option>
            </select>
          </label>
          <label>
            Security Policy
            <select value={form.securityPolicy} onChange={(event) => setForm((current) => ({ ...current, securityPolicy: event.target.value }))}>
              <option value="None">None</option>
            </select>
          </label>
          <label>
            Telemetry Topic
            <input value={form.outputTopic} onChange={(event) => setForm((current) => ({ ...current, outputTopic: event.target.value }))} />
          </label>
        </div>
      </details>
    </article>
  )
}
