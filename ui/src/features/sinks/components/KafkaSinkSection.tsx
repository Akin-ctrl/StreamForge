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
        <h3>Kafka Forwarder</h3>
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
      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <label>
          Source Topic
          <input value={form.sourceTopic} onChange={(event) => setForm((current) => ({ ...current, sourceTopic: event.target.value }))} />
        </label>
      </details>
    </article>
  )
}
