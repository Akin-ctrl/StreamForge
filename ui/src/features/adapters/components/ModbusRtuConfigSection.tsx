import type { Dispatch, SetStateAction } from 'react'

import type { CatalogAdapterType } from '../../../shared/api/client'
import { getCatalogOptionsForValue } from '../../../shared/config/catalog'
import type { AdapterFormState } from '../adapterForm'
import { ModbusPointsEditor } from './ModbusPointsEditor'

type ModbusRtuConfigSectionProps = {
  contract?: CatalogAdapterType
  form: AdapterFormState
  setForm: Dispatch<SetStateAction<AdapterFormState>>
}

export function ModbusRtuConfigSection({ contract, form, setForm }: ModbusRtuConfigSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>Modbus RTU</h3>
      </div>
      <div className="inline-grid">
        <label>
          Serial Port
          <input value={form.serialPort} onChange={(event) => setForm((current) => ({ ...current, serialPort: event.target.value }))} />
        </label>
        <label>
          Baud Rate
          <input value={form.baudrate} onChange={(event) => setForm((current) => ({ ...current, baudrate: event.target.value }))} />
        </label>
        <label>
          Data Bits
          <input value={form.bytesize} onChange={(event) => setForm((current) => ({ ...current, bytesize: event.target.value }))} />
        </label>
        <label>
          Parity
          <select value={form.parity} onChange={(event) => setForm((current) => ({ ...current, parity: event.target.value }))}>
            {getCatalogOptionsForValue(contract, 'connection', 'parity', form.parity).map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="inline-grid">
        <label>
          Stop Bits
          <input value={form.stopbits} onChange={(event) => setForm((current) => ({ ...current, stopbits: event.target.value }))} />
        </label>
        <label>
          Timeout (s)
          <input value={form.timeout} onChange={(event) => setForm((current) => ({ ...current, timeout: event.target.value }))} />
        </label>
        <label>
          Unit ID
          <input value={form.unitId} onChange={(event) => setForm((current) => ({ ...current, unitId: event.target.value }))} />
        </label>
        <label>
          Poll Interval (ms)
          <input value={form.pollIntervalMs} onChange={(event) => setForm((current) => ({ ...current, pollIntervalMs: event.target.value }))} />
        </label>
      </div>
      <label>
        Default Asset ID
        <input value={form.defaultAssetId} onChange={(event) => setForm((current) => ({ ...current, defaultAssetId: event.target.value }))} />
      </label>
      <ModbusPointsEditor contract={contract} form={form} setForm={setForm} />
      <p className="muted">Internal telemetry and event routing topics are managed by the platform for Modbus adapters.</p>
    </article>
  )
}
