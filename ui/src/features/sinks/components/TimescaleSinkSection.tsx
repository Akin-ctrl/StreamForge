import type { Dispatch, SetStateAction } from 'react'

import type { CatalogSinkType } from '../../../shared/api/client'
import type { SinkFormState } from '../sinkForm'

type TimescaleSinkSectionProps = {
  contract?: CatalogSinkType
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

export function TimescaleSinkSection({ form, setForm }: TimescaleSinkSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <h3>TimescaleDB</h3>
      </div>
      <div className="inline-grid">
        <label>
          Database DSN
          <input
            placeholder={form.dbDsnConfigured ? 'Leave blank to keep current DSN' : ''}
            value={form.dbDsn}
            onChange={(event) => setForm((current) => ({ ...current, dbDsn: event.target.value }))}
          />
          {form.dbDsnConfigured && <span className="muted">Database credentials are already configured.</span>}
        </label>
        <label>
          Table
          <input value={form.table} onChange={(event) => setForm((current) => ({ ...current, table: event.target.value }))} />
        </label>
      </div>
      <p className="muted">Ingress routing, Kafka bootstrap, and consumer-group wiring are managed by the platform for TimescaleDB sinks.</p>
    </article>
  )
}
