import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import { applyAggregatesJson, buildAggregatesJson, type DeploymentFormState } from '../deploymentForm'

type AggregatesConfigSectionProps = {
  form: DeploymentFormState
  setForm: Dispatch<SetStateAction<DeploymentFormState>>
  onError: (message: string | null) => void
}

export function AggregatesConfigSection({ form, setForm, onError }: AggregatesConfigSectionProps) {
  const [jsonDraft, setJsonDraft] = useState(buildAggregatesJson(form))

  useEffect(() => {
    setJsonDraft(buildAggregatesJson(form))
  }, [form])

  const onApplyJson = () => {
    try {
      setForm((current) => applyAggregatesJson(current, jsonDraft))
      onError(null)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Invalid aggregates JSON')
    }
  }

  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>Aggregates</h3>
          <p className="muted">
            Decide whether this deployment should publish aggregate windows and keep the stream settings readable before
            activation.
          </p>
        </div>
      </div>
      <label className="toggle-label">
        <input
          type="checkbox"
          checked={form.aggregatesEnabled}
          onChange={(event) => setForm((current) => ({ ...current, aggregatesEnabled: event.target.checked }))}
        />
        Enable aggregate streams for clean telemetry
      </label>

      <div className="nested-card card builder-section">
        <p className="muted">Choose the source stream and enable only the aggregate windows this gateway needs.</p>
        <label>
          Source Topic
          <input
            value={form.aggregatesSourceTopic}
            onChange={(event) => setForm((current) => ({ ...current, aggregatesSourceTopic: event.target.value }))}
          />
        </label>
        <div className="inline-grid">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={form.aggregate1sEnabled}
              onChange={(event) => setForm((current) => ({ ...current, aggregate1sEnabled: event.target.checked }))}
            />
            1s stream
          </label>
          <label>
            1s Topic
            <input
              value={form.aggregate1sTopic}
              onChange={(event) => setForm((current) => ({ ...current, aggregate1sTopic: event.target.value }))}
            />
          </label>
          <label>
            1s Window Seconds
            <input
              value={form.aggregate1sWindowSeconds}
              onChange={(event) => setForm((current) => ({ ...current, aggregate1sWindowSeconds: event.target.value }))}
            />
          </label>
        </div>
        <div className="inline-grid">
          <label className="toggle-label">
            <input
              type="checkbox"
              checked={form.aggregate1minEnabled}
              onChange={(event) => setForm((current) => ({ ...current, aggregate1minEnabled: event.target.checked }))}
            />
            1min stream
          </label>
          <label>
            1min Topic
            <input
              value={form.aggregate1minTopic}
              onChange={(event) => setForm((current) => ({ ...current, aggregate1minTopic: event.target.value }))}
            />
          </label>
          <label>
            1min Window Seconds
            <input
              value={form.aggregate1minWindowSeconds}
              onChange={(event) => setForm((current) => ({ ...current, aggregate1minWindowSeconds: event.target.value }))}
            />
          </label>
        </div>
      </div>

      <details className="card nested-card advanced-block">
        <summary>Advanced JSON</summary>
        <div className="builder-section">
          <p className="muted">Use the JSON editor to review or bulk-edit the aggregate wiring when needed.</p>
          <label>
            Aggregates Config JSON
            <textarea rows={8} value={jsonDraft} onChange={(event) => setJsonDraft(event.target.value)} />
          </label>
          <button className="btn btn-secondary" onClick={onApplyJson} type="button">
            Apply JSON
          </button>
        </div>
      </details>
    </article>
  )
}
