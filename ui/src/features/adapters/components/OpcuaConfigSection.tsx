import type { Dispatch, SetStateAction } from 'react'

import type { CatalogAdapterType } from '../../../shared/api/client'
import { getCatalogOptionsForValue, getCatalogSection } from '../../../shared/config/catalog'
import { createDefaultMonitoredItemForm, type AdapterFormState, type OpcuaMonitoredItemForm } from '../adapterForm'

type OpcuaConfigSectionProps = {
  contract?: CatalogAdapterType
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

export function OpcuaConfigSection({ contract, form, setForm }: OpcuaConfigSectionProps) {
  const securityModeOptions = getCatalogOptionsForValue(contract, 'advanced', 'security_mode', form.securityMode)
  const securityPolicyOptions = getCatalogOptionsForValue(contract, 'advanced', 'security_policy', form.securityPolicy)
  const advancedHelpText = getCatalogSection(contract, 'advanced')?.help_text
  const runtimeSecurityIsFixed =
    securityModeOptions.length <= 1 &&
    securityPolicyOptions.length <= 1 &&
    securityModeOptions.every((option) => option.value === 'None') &&
    securityPolicyOptions.every((option) => option.value === 'None')

  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>OPC UA</h3>
          <p className="muted">
            Define the endpoint, session behavior, and monitored items so the session reads as one understandable
            source connection.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Endpoint
          <input value={form.endpoint} onChange={(event) => setForm((current) => ({ ...current, endpoint: event.target.value }))} />
        </label>
        <label>
          Authentication
          <select value={form.authMode} onChange={(event) => setForm((current) => ({ ...current, authMode: event.target.value }))}>
            {getCatalogOptionsForValue(contract, 'connection', 'auth_mode', form.authMode).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
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
              placeholder={form.passwordConfigured ? 'Leave blank to keep current password' : ''}
              value={form.password}
              onChange={(event) => setForm((current) => ({ ...current, password: event.target.value }))}
            />
            {form.passwordConfigured && <span className="muted">A password is already configured for this session.</span>}
          </label>
        </div>
      )}

      <div className="nested-card card builder-section">
        <div className="page-header">
          <div className="card-header-copy">
            <h4>Monitored Items</h4>
            <p className="muted">Each monitored item should clearly tie a node to the normalized parameter it emits.</p>
          </div>
          <button
            className="btn btn-secondary"
            onClick={() =>
              setForm((current) => ({ ...current, monitoredItems: [...current.monitoredItems, createDefaultMonitoredItemForm(contract)] }))
            }
            type="button"
          >
            Add Item
          </button>
        </div>
        {form.monitoredItems.length === 0 ? (
          <p className="muted">Add the nodes this session should monitor.</p>
        ) : (
          form.monitoredItems.map((item, index) => (
            <div className="rule-card" key={item.uiId}>
              <div className="rule-card-header">
                <div>
                  <strong>Monitored Item {index + 1}</strong>
                  <p className="muted">Describe the node, normalized parameter, and runtime sampling behavior.</p>
                </div>
              </div>
              <div className="rule-stack">
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
                  {getCatalogOptionsForValue(contract, 'monitored_items', 'monitoring_mode', item.monitoring_mode).map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
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
            </div>
          ))
        )}
      </div>

      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        {runtimeSecurityIsFixed ? (
          <p className="muted">{advancedHelpText || 'Current runtime supports only Security Mode None and Security Policy None.'}</p>
        ) : (
          <div className="inline-grid">
            <label>
              Security Mode
              <select value={form.securityMode} onChange={(event) => setForm((current) => ({ ...current, securityMode: event.target.value }))}>
                {securityModeOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Security Policy
              <select value={form.securityPolicy} onChange={(event) => setForm((current) => ({ ...current, securityPolicy: event.target.value }))}>
                {securityPolicyOptions.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}
        <p className="muted">Internal telemetry routing is managed by the platform for OPC UA adapters.</p>
      </details>
    </article>
  )
}
