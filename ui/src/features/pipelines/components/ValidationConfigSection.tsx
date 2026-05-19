import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import {
  applyValidationJson,
  buildValidationJson,
  type AlarmRuleForm,
  createDefaultAlarmRuleForm,
  createDefaultGapRuleForm,
  createDefaultRangeRuleForm,
  createDefaultRateRuleForm,
  type DeploymentFormState,
  type GapRuleForm,
  type RangeRuleForm,
  type RateRuleForm,
} from '../deploymentForm'

type ValidationConfigSectionProps = {
  form: DeploymentFormState
  setForm: Dispatch<SetStateAction<DeploymentFormState>>
  onError: (message: string | null) => void
}

function updateArrayItem<T>(items: T[], index: number, nextItem: T): T[] {
  return items.map((item, itemIndex) => (itemIndex === index ? nextItem : item))
}

export function ValidationConfigSection({ form, setForm, onError }: ValidationConfigSectionProps) {
  const [jsonDraft, setJsonDraft] = useState(buildValidationJson(form))

  useEffect(() => {
    setJsonDraft(buildValidationJson(form))
  }, [form])

  const addRangeRule = () => {
    setForm((current) => ({
      ...current,
      rangeRules: [...current.rangeRules, createDefaultRangeRuleForm()],
    }))
  }

  const addRateRule = () => {
    setForm((current) => ({
      ...current,
      rateRules: [...current.rateRules, createDefaultRateRuleForm()],
    }))
  }

  const addGapRule = () => {
    setForm((current) => ({
      ...current,
      gapRules: [...current.gapRules, createDefaultGapRuleForm()],
    }))
  }

  const addAlarmRule = () => {
    setForm((current) => ({
      ...current,
      alarmRules: [...current.alarmRules, createDefaultAlarmRuleForm()],
    }))
  }

  const onApplyJson = () => {
    try {
      setForm((current) => applyValidationJson(current, jsonDraft))
      onError(null)
    } catch (error) {
      onError(error instanceof Error ? error.message : 'Invalid validation JSON')
    }
  }

  return (
    <article className="card">
      <div className="page-header">
        <div className="card-header-copy">
          <h3>Validation</h3>
          <p className="muted">Define parameter quality rules and alarm conditions at the deployment level so operators can reason about one processing policy per gateway composition.</p>
        </div>
      </div>
      <label className="toggle-label">
        <input
          type="checkbox"
          checked={form.validationEnabled}
          onChange={(event) => setForm((current) => ({ ...current, validationEnabled: event.target.checked }))}
        />
        Enable telemetry validation and alarm generation
      </label>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <div className="card-header-copy">
            <h4>Parameter Ranges</h4>
            <p className="muted">Set expected operating bands for parameters that should stay within a stable range.</p>
          </div>
          <button className="btn btn-secondary" onClick={addRangeRule} type="button">
            Add Range
          </button>
        </div>
        {form.rangeRules.map((rule, index) => (
          <div className="rule-card" key={rule.uiId}>
            <div className="rule-card-header">
              <div>
                <strong>Range Rule {index + 1}</strong>
                <p className="muted">Describe the parameter and its acceptable lower and upper bounds.</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    rangeRules: current.rangeRules.filter((_, itemIndex) => itemIndex !== index),
                  }))
                }
                type="button"
              >
                Remove
              </button>
            </div>
            <div className="rule-row">
              <input
                placeholder="Parameter"
                value={rule.parameter}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    rangeRules: updateArrayItem<RangeRuleForm>(current.rangeRules, index, {
                      ...rule,
                      parameter: event.target.value,
                    }),
                  }))
                }
              />
              <input
                placeholder="Min"
                value={rule.min}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    rangeRules: updateArrayItem<RangeRuleForm>(current.rangeRules, index, {
                      ...rule,
                      min: event.target.value,
                    }),
                  }))
                }
              />
              <input
                placeholder="Max"
                value={rule.max}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    rangeRules: updateArrayItem<RangeRuleForm>(current.rangeRules, index, {
                      ...rule,
                      max: event.target.value,
                    }),
                  }))
                }
              />
            </div>
          </div>
        ))}
        {form.rangeRules.length === 0 && <p className="muted">No range rules yet.</p>}
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <div className="card-header-copy">
            <h4>Rate Of Change</h4>
            <p className="muted">Catch spikes or impossible jumps by limiting how far a parameter can move per sample.</p>
          </div>
          <button className="btn btn-secondary" onClick={addRateRule} type="button">
            Add Limit
          </button>
        </div>
        {form.rateRules.map((rule, index) => (
          <div className="rule-card" key={rule.uiId}>
            <div className="rule-card-header">
              <div>
                <strong>Rate Rule {index + 1}</strong>
                <p className="muted">Specify the parameter and its maximum allowed change between samples.</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    rateRules: current.rateRules.filter((_, itemIndex) => itemIndex !== index),
                  }))
                }
                type="button"
              >
                Remove
              </button>
            </div>
            <div className="rule-row">
              <input
                placeholder="Parameter"
                value={rule.parameter}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    rateRules: updateArrayItem<RateRuleForm>(current.rateRules, index, {
                      ...rule,
                      parameter: event.target.value,
                    }),
                  }))
                }
              />
              <input
                placeholder="Max delta"
                value={rule.limit}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    rateRules: updateArrayItem<RateRuleForm>(current.rateRules, index, {
                      ...rule,
                      limit: event.target.value,
                    }),
                  }))
                }
              />
            </div>
          </div>
        ))}
        {form.rateRules.length === 0 && <p className="muted">No rate-of-change rules yet.</p>}
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <div className="card-header-copy">
            <h4>Gap Detection</h4>
            <p className="muted">Describe when a parameter should be treated as missing or stalled.</p>
          </div>
          <button className="btn btn-secondary" onClick={addGapRule} type="button">
            Add Gap Rule
          </button>
        </div>
        {form.gapRules.map((rule, index) => (
          <div className="rule-card" key={rule.uiId}>
            <div className="rule-card-header">
              <div>
                <strong>Gap Rule {index + 1}</strong>
                <p className="muted">Specify the parameter and how many seconds can pass before it is considered absent.</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    gapRules: current.gapRules.filter((_, itemIndex) => itemIndex !== index),
                  }))
                }
                type="button"
              >
                Remove
              </button>
            </div>
            <div className="rule-row">
              <input
                placeholder="Parameter"
                value={rule.parameter}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    gapRules: updateArrayItem<GapRuleForm>(current.gapRules, index, {
                      ...rule,
                      parameter: event.target.value,
                    }),
                  }))
                }
              />
              <input
                placeholder="Seconds"
                value={rule.seconds}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    gapRules: updateArrayItem<GapRuleForm>(current.gapRules, index, {
                      ...rule,
                      seconds: event.target.value,
                    }),
                  }))
                }
              />
            </div>
          </div>
        ))}
        {form.gapRules.length === 0 && <p className="muted">No gap-detection rules yet.</p>}
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <div className="card-header-copy">
            <h4>Alarm Rules</h4>
            <p className="muted">Define operator-facing alarms that should be emitted when validation or thresholds fire.</p>
          </div>
          <button className="btn btn-secondary" onClick={addAlarmRule} type="button">
            Add Alarm
          </button>
        </div>
        {form.alarmRules.map((rule, index) => (
          <div className="rule-card" key={rule.uiId}>
            <div className="rule-card-header">
              <div>
                <strong>Alarm Rule {index + 1}</strong>
                <p className="muted">Describe the parameter, alarm classification, and the messages operators should see.</p>
              </div>
              <button
                className="btn btn-secondary"
                onClick={() =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: current.alarmRules.filter((_, itemIndex) => itemIndex !== index),
                  }))
                }
                type="button"
              >
                Remove
              </button>
            </div>
            <div className="rule-stack">
            <div className="inline-grid">
              <input
                placeholder="Parameter"
                value={rule.parameter}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, parameter: event.target.value }),
                  }))
                }
              />
              <input
                placeholder="Alarm type"
                value={rule.type}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, type: event.target.value }),
                  }))
                }
              />
              <select
                value={rule.severity}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, severity: event.target.value }),
                  }))
                }
              >
                <option value="CRITICAL">CRITICAL</option>
                <option value="HIGH">HIGH</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="LOW">LOW</option>
                <option value="INFO">INFO</option>
              </select>
              <select
                value={rule.operator}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, operator: event.target.value }),
                  }))
                }
              >
                <option value=">">{'>'}</option>
                <option value=">=">{'>='}</option>
                <option value="<">{'<'}</option>
                <option value="<=">{'<='}</option>
                <option value="==">==</option>
              </select>
              <input
                placeholder="Threshold"
                value={rule.threshold}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, threshold: event.target.value }),
                  }))
                }
              />
            </div>
            <div className="inline-grid">
              <input
                placeholder="Raise message"
                value={rule.message}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, message: event.target.value }),
                  }))
                }
              />
              <input
                placeholder="Clear message"
                value={rule.clearMessage}
                onChange={(event) =>
                  setForm((current) => ({
                    ...current,
                    alarmRules: updateArrayItem<AlarmRuleForm>(current.alarmRules, index, { ...rule, clearMessage: event.target.value }),
                  }))
                }
              />
            </div>
            </div>
          </div>
        ))}
        {form.alarmRules.length === 0 && <p className="muted">No alarm rules yet.</p>}
      </div>

      <details className="card nested-card advanced-block">
        <summary>Advanced</summary>
        <div className="builder-section">
          <div className="inline-grid">
            <label>
              Raw Topic
              <input
                value={form.validationRawTopic}
                onChange={(event) => setForm((current) => ({ ...current, validationRawTopic: event.target.value }))}
              />
            </label>
            <label>
              Clean Topic
              <input
                value={form.validationCleanTopic}
                onChange={(event) => setForm((current) => ({ ...current, validationCleanTopic: event.target.value }))}
              />
            </label>
            <label>
              DLQ Topic
              <input
                value={form.validationDlqTopic}
                onChange={(event) => setForm((current) => ({ ...current, validationDlqTopic: event.target.value }))}
              />
            </label>
            <label>
              Alarm Topic
              <input
                value={form.validationAlarmTopic}
                onChange={(event) => setForm((current) => ({ ...current, validationAlarmTopic: event.target.value }))}
              />
            </label>
          </div>
          <label>
            Validation Config JSON
            <textarea rows={10} value={jsonDraft} onChange={(event) => setJsonDraft(event.target.value)} />
          </label>
          <button className="btn btn-secondary" onClick={onApplyJson} type="button">
            Apply JSON
          </button>
        </div>
      </details>
    </article>
  )
}
