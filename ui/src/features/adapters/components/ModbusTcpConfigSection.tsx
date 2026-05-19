import type { Dispatch, SetStateAction } from 'react'

import type { CatalogAdapterType } from '../../../shared/api/client'
import type { AdapterFormState } from '../adapterForm'
import { ModbusPointsEditor } from './ModbusPointsEditor'

type ModbusTcpConfigSectionProps = {
  contract?: CatalogAdapterType
  form: AdapterFormState
  setForm: Dispatch<SetStateAction<AdapterFormState>>
}

export function ModbusTcpConfigSection({ contract, form, setForm }: ModbusTcpConfigSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>Modbus TCP</h3>
      </div>
      <div className="inline-grid">
        <label>
          Host
          <input value={form.host} onChange={(event) => setForm((current) => ({ ...current, host: event.target.value }))} />
        </label>
        <label>
          Port
          <input value={form.port} onChange={(event) => setForm((current) => ({ ...current, port: event.target.value }))} />
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
