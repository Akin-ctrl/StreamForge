import { useEffect, useState, type Dispatch, type SetStateAction } from 'react'

import {
  applyValidationJson,
  buildValidationJson,
  type AlarmRuleForm,
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
      rangeRules: [...current.rangeRules, { parameter: '', min: '', max: '' }],
    }))
  }

  const addRateRule = () => {
    setForm((current) => ({
      ...current,
      rateRules: [...current.rateRules, { parameter: '', limit: '' }],
    }))
  }

  const addGapRule = () => {
    setForm((current) => ({
      ...current,
      gapRules: [...current.gapRules, { parameter: '', seconds: '' }],
    }))
  }

  const addAlarmRule = () => {
    setForm((current) => ({
      ...current,
      alarmRules: [
        ...current.alarmRules,
        { parameter: '', type: '', severity: 'HIGH', operator: '>', threshold: '', message: '', clearMessage: '' },
      ],
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
        <h3>Validation</h3>
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
          <h4>Parameter Ranges</h4>
          <button className="btn btn-secondary" onClick={addRangeRule} type="button">
            Add Range
          </button>
        </div>
        {form.rangeRules.map((rule, index) => (
          <div className="rule-row" key={`${rule.parameter}-${index}`}>
            <input
              placeholder="Parameter"
              value={rule.parameter}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rangeRules: updateArrayItem<RangeRuleForm>(current.rangeRules, index, { ...rule, parameter: event.target.value }),
                }))
              }
            />
            <input
              placeholder="Min"
              value={rule.min}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rangeRules: updateArrayItem<RangeRuleForm>(current.rangeRules, index, { ...rule, min: event.target.value }),
                }))
              }
            />
            <input
              placeholder="Max"
              value={rule.max}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rangeRules: updateArrayItem<RangeRuleForm>(current.rangeRules, index, { ...rule, max: event.target.value }),
                }))
              }
            />
            <button
              className="btn btn-secondary"
              onClick={() => setForm((current) => ({ ...current, rangeRules: current.rangeRules.filter((_, itemIndex) => itemIndex !== index) }))}
              type="button"
            >
              Remove
            </button>
          </div>
        ))}
        {form.rangeRules.length === 0 && <p className="muted">No range rules yet.</p>}
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <h4>Rate Of Change</h4>
          <button className="btn btn-secondary" onClick={addRateRule} type="button">
            Add Limit
          </button>
        </div>
        {form.rateRules.map((rule, index) => (
          <div className="rule-row" key={`${rule.parameter}-${index}`}>
            <input
              placeholder="Parameter"
              value={rule.parameter}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rateRules: updateArrayItem<RateRuleForm>(current.rateRules, index, { ...rule, parameter: event.target.value }),
                }))
              }
            />
            <input
              placeholder="Max delta"
              value={rule.limit}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  rateRules: updateArrayItem<RateRuleForm>(current.rateRules, index, { ...rule, limit: event.target.value }),
                }))
              }
            />
            <button
              className="btn btn-secondary"
              onClick={() => setForm((current) => ({ ...current, rateRules: current.rateRules.filter((_, itemIndex) => itemIndex !== index) }))}
              type="button"
            >
              Remove
            </button>
          </div>
        ))}
        {form.rateRules.length === 0 && <p className="muted">No rate-of-change rules yet.</p>}
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <h4>Gap Detection</h4>
          <button className="btn btn-secondary" onClick={addGapRule} type="button">
            Add Gap Rule
          </button>
        </div>
        {form.gapRules.map((rule, index) => (
          <div className="rule-row" key={`${rule.parameter}-${index}`}>
            <input
              placeholder="Parameter"
              value={rule.parameter}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  gapRules: updateArrayItem<GapRuleForm>(current.gapRules, index, { ...rule, parameter: event.target.value }),
                }))
              }
            />
            <input
              placeholder="Seconds"
              value={rule.seconds}
              onChange={(event) =>
                setForm((current) => ({
                  ...current,
                  gapRules: updateArrayItem<GapRuleForm>(current.gapRules, index, { ...rule, seconds: event.target.value }),
                }))
              }
            />
            <button
              className="btn btn-secondary"
              onClick={() => setForm((current) => ({ ...current, gapRules: current.gapRules.filter((_, itemIndex) => itemIndex !== index) }))}
              type="button"
            >
              Remove
            </button>
          </div>
        ))}
        {form.gapRules.length === 0 && <p className="muted">No gap-detection rules yet.</p>}
      </div>

      <div className="nested-card card builder-section">
        <div className="page-header">
          <h4>Alarm Rules</h4>
          <button className="btn btn-secondary" onClick={addAlarmRule} type="button">
            Add Alarm
          </button>
        </div>
        {form.alarmRules.map((rule, index) => (
          <div className="rule-stack" key={`${rule.type}-${index}`}>
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
              <button
                className="btn btn-secondary"
                onClick={() => setForm((current) => ({ ...current, alarmRules: current.alarmRules.filter((_, itemIndex) => itemIndex !== index) }))}
                type="button"
              >
                Remove
              </button>
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
