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
            Choose the internal stream to mirror, then define the downstream Kafka-compatible destination.
          </p>
        </div>
      </div>
      <div className="inline-grid">
        <label>
          Source Topic
          <input
            list="sink-source-topic-options"
            value={form.sourceTopic}
            onChange={(event) => setForm((current) => ({ ...current, sourceTopic: event.target.value }))}
          />
        </label>
        <label>
          Consumer Group
          <input
            value={form.kafkaGroupId}
            onChange={(event) => setForm((current) => ({ ...current, kafkaGroupId: event.target.value }))}
          />
        </label>
        <label>
          Target Bootstrap
          <input value={form.targetBootstrap} onChange={(event) => setForm((current) => ({ ...current, targetBootstrap: event.target.value }))} />
        </label>
        <label>
          Target Topic
          <input value={form.targetTopic} onChange={(event) => setForm((current) => ({ ...current, targetTopic: event.target.value }))} />
        </label>
      </div>
      <datalist id="sink-source-topic-options">
        <option value="telemetry.clean" />
        <option value="telemetry.1s" />
        <option value="telemetry.1min" />
        <option value="events.clean" />
        <option value="alarms.raw" />
      </datalist>
      <p className="muted">Use a distinct consumer group when this sink must read independently from other sinks.</p>
    </article>
  )
}
