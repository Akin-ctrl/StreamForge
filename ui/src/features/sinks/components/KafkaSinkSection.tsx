import type { Dispatch, SetStateAction } from 'react'

import type { CatalogSinkType } from '../../../shared/api/client'
import type { SinkFormState } from '../sinkForm'

type KafkaSinkSectionProps = {
  contract?: CatalogSinkType
  form: SinkFormState
  setForm: Dispatch<SetStateAction<SinkFormState>>
}

export function KafkaSinkSection({ form, setForm }: KafkaSinkSectionProps) {
  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>Kafka-Compatible Forwarder</h3>
          <p className="muted">
            Define the downstream Kafka-compatible destination while the platform keeps source routing and ingestion wiring stable.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Target Bootstrap
          <input value={form.targetBootstrap} onChange={(event) => setForm((current) => ({ ...current, targetBootstrap: event.target.value }))} />
        </label>
        <label>
          Target Topic
          <input value={form.targetTopic} onChange={(event) => setForm((current) => ({ ...current, targetTopic: event.target.value }))} />
        </label>
      </div>
      <p className="muted">Source-topic routing is managed by the platform for Kafka-compatible forwarder sinks.</p>
    </article>
  )
}
