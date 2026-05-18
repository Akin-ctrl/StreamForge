import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import { applyEventsJson, buildEventsJson, type DeploymentFormState } from '../deploymentForm'

type EventsConfigSectionProps = {
  form: DeploymentFormState
  setForm: Dispatch<SetStateAction<DeploymentFormState>>
  onError: (message: string | null) => void
}

export function EventsConfigSection({ form, setForm, onError }: EventsConfigSectionProps) {
  const [jsonDraft, setJsonDraft] = useState(buildEventsJson(form))

  useEffect(() => {
    setJsonDraft(buildEventsJson(form))
  }, [form])

  const onApplyJson = () => {
    try {
      setForm((current) => applyEventsJson(current, jsonDraft))
      onError(null)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Invalid events JSON')
    }
  }

  return (
    <article className="card">
      <div className="page-header">
        <h3>Events</h3>
      </div>
      <label className="toggle-label">
        <input
          type="checkbox"
          checked={form.eventsEnabled}
          onChange={(event) => setForm((current) => ({ ...current, eventsEnabled: event.target.checked }))}
        />
        Enable event validation and clean event publication
      </label>

      <details className="card nested-card advanced-block" open>
        <summary>Advanced</summary>
        <div className="builder-section">
          <div className="inline-grid">
            <label>
              Raw Topic
              <input value={form.eventsRawTopic} onChange={(event) => setForm((current) => ({ ...current, eventsRawTopic: event.target.value }))} />
            </label>
            <label>
              Clean Topic
              <input
                value={form.eventsCleanTopic}
                onChange={(event) => setForm((current) => ({ ...current, eventsCleanTopic: event.target.value }))}
              />
            </label>
            <label>
              DLQ Topic
              <input value={form.eventsDlqTopic} onChange={(event) => setForm((current) => ({ ...current, eventsDlqTopic: event.target.value }))} />
            </label>
          </div>
          <label>
            Events Config JSON
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
