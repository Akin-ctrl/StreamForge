import type { Dispatch, SetStateAction } from 'react'

import type { SinkFormState } from '../sinkForm'

type TimescaleSinkSectionProps = {
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
          <input value={form.dbDsn} onChange={(event) => setForm((current) => ({ ...current, dbDsn: event.target.value }))} />
        </label>
        <label>
          Table
          <input value={form.table} onChange={(event) => setForm((current) => ({ ...current, table: event.target.value }))} />
        </label>
      </div>
      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <div className="inline-grid">
          <label>
            Kafka Bootstrap
            <input value={form.kafkaBootstrap} onChange={(event) => setForm((current) => ({ ...current, kafkaBootstrap: event.target.value }))} />
          </label>
          <label>
            Source Topic
            <input value={form.sourceTopic} onChange={(event) => setForm((current) => ({ ...current, sourceTopic: event.target.value }))} />
          </label>
          <label>
            Consumer Group
            <input value={form.kafkaGroupId} onChange={(event) => setForm((current) => ({ ...current, kafkaGroupId: event.target.value }))} />
          </label>
        </div>
      </details>
    </article>
  )
}
