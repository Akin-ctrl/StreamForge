import type { Dispatch, SetStateAction } from 'react'

import type { AdapterFormState } from '../adapterForm'
import { ModbusPointsEditor } from './ModbusPointsEditor'

type ModbusTcpConfigSectionProps = {
  form: AdapterFormState
  setForm: Dispatch<SetStateAction<AdapterFormState>>
}

export function ModbusTcpConfigSection({ form, setForm }: ModbusTcpConfigSectionProps) {
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
      <ModbusPointsEditor form={form} setForm={setForm} />
      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <div className="inline-grid">
          <label>
            Telemetry Topic
            <input value={form.outputTopic} onChange={(event) => setForm((current) => ({ ...current, outputTopic: event.target.value }))} />
          </label>
          <label>
            Events Topic
            <input value={form.eventsTopic} onChange={(event) => setForm((current) => ({ ...current, eventsTopic: event.target.value }))} />
          </label>
        </div>
      </details>
    </article>
  )
}
