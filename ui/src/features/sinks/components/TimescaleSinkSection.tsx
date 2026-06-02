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
        <div className="card-header-copy">
          <h3>TimescaleDB</h3>
          <p className="muted">
            Choose which processed stream this sink consumes, then set the database table that should receive it.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Source Topic
          <input
            list="timescale-source-topic-options"
            value={form.sourceTopic}
            onChange={(event) => setForm((current) => ({ ...current, sourceTopic: event.target.value }))}
          />
          <datalist id="timescale-source-topic-options">
            <option value="telemetry.clean" />
            <option value="telemetry.1s" />
            <option value="telemetry.1min" />
            <option value="events.clean" />
          </datalist>
          <span className="muted">Examples: telemetry.clean, telemetry.1s, telemetry.1min, events.clean.</span>
        </label>
        <label>
          Consumer Group
          <input
            value={form.kafkaGroupId}
            onChange={(event) => setForm((current) => ({ ...current, kafkaGroupId: event.target.value }))}
          />
          <span className="muted">Use a distinct group when multiple sinks read independently.</span>
        </label>
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
      <p className="muted">Kafka bootstrap remains managed by the local edge runtime unless you override it in JSON.</p>
    </article>
  )
}
