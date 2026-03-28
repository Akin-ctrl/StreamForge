import { useEffect, useState } from 'react'

import {
  AlarmListItem,
  AlarmSeverity,
  AlarmState,
  acknowledgeAlarm,
  listAlarms,
  suppressAlarm,
} from '../../shared/api/client'

const severityOptions: Array<AlarmSeverity | 'ALL'> = ['ALL', 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
const stateOptions: Array<AlarmState | 'ALL'> = ['ALL', 'ACTIVE', 'ACKNOWLEDGED', 'SUPPRESSED', 'CLEARED']

function formatDateTime(value: string | null) {
  if (!value) {
    return 'Not set'
  }

  return new Date(value).toLocaleString()
}

function formatValue(value: number | null, unit: string | null) {
  if (value === null || value === undefined) {
    return 'N/A'
  }

  return unit ? `${value} ${unit}` : String(value)
}

/**
 * Alarm operations view.
 * Supports filtering plus acknowledge/suppress lifecycle actions.
 */
export function AlarmsPage() {
  const [items, setItems] = useState<AlarmListItem[]>([])
  const [selectedAlarmId, setSelectedAlarmId] = useState<string | null>(null)
  const [stateFilter, setStateFilter] = useState<AlarmState | 'ALL'>('ALL')
  const [severityFilter, setSeverityFilter] = useState<AlarmSeverity | 'ALL'>('ALL')
  const [showActiveOnly, setShowActiveOnly] = useState(true)
  const [loading, setLoading] = useState(true)
  const [busyAlarmId, setBusyAlarmId] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const alarms = await listAlarms({
        state: stateFilter === 'ALL' ? undefined : stateFilter,
        severity: severityFilter === 'ALL' ? undefined : severityFilter,
        active_only: showActiveOnly,
        limit: 200,
      })
      setItems(alarms)
      if (!selectedAlarmId && alarms.length > 0) {
        setSelectedAlarmId(alarms[0].alarm_id)
      }
      if (selectedAlarmId && !alarms.some((alarm) => alarm.alarm_id === selectedAlarmId)) {
        setSelectedAlarmId(alarms[0]?.alarm_id ?? null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load alarms')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [stateFilter, severityFilter, showActiveOnly])

  const selectedAlarm = items.find((alarm) => alarm.alarm_id === selectedAlarmId) ?? null

  const onAcknowledge = async (alarmId: string) => {
    setBusyAlarmId(alarmId)
    setError(null)
    try {
      await acknowledgeAlarm(alarmId)
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to acknowledge alarm')
    } finally {
      setBusyAlarmId(null)
    }
  }

  const onSuppress = async (alarmId: string) => {
    setBusyAlarmId(alarmId)
    setError(null)
    try {
      await suppressAlarm(alarmId)
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to suppress alarm')
    } finally {
      setBusyAlarmId(null)
    }
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>Alarms</h2>
          <p className="muted">Monitor active alarm conditions and manage acknowledge/suppress lifecycle actions.</p>
        </div>
        <button className="btn" onClick={() => void refresh()}>
          Refresh
        </button>
      </div>

      <div className="card alarm-filters">
        <label>
          State
          <select value={stateFilter} onChange={(event) => setStateFilter(event.target.value as AlarmState | 'ALL')}>
            {stateOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label>
          Severity
          <select
            value={severityFilter}
            onChange={(event) => setSeverityFilter(event.target.value as AlarmSeverity | 'ALL')}
          >
            {severityOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label className="toggle-label">
          <input
            type="checkbox"
            checked={showActiveOnly}
            onChange={(event) => setShowActiveOnly(event.target.checked)}
          />
          Active only
        </label>
      </div>

      {loading && <p>Loading alarms...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <div className="alarm-layout">
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>Alarm</th>
                  <th>Severity</th>
                  <th>State</th>
                  <th>Asset</th>
                  <th>Raised</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((alarm) => {
                  const isBusy = busyAlarmId === alarm.alarm_id
                  return (
                    <tr
                      key={alarm.alarm_id}
                      className={selectedAlarmId === alarm.alarm_id ? 'alarm-row-selected' : undefined}
                      onClick={() => setSelectedAlarmId(alarm.alarm_id)}
                    >
                      <td>
                        <strong>{alarm.type}</strong>
                        <div className="muted">{alarm.alarm_id}</div>
                      </td>
                      <td>
                        <span className={`badge badge-${alarm.severity.toLowerCase()}`}>{alarm.severity}</span>
                      </td>
                      <td>{alarm.state}</td>
                      <td>{alarm.asset_id}</td>
                      <td>{formatDateTime(alarm.raised_at)}</td>
                      <td>
                        {alarm.state === 'ACTIVE' && (
                          <button
                            className="btn btn-secondary"
                            disabled={isBusy}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onAcknowledge(alarm.alarm_id)
                            }}
                          >
                            Acknowledge
                          </button>
                        )}
                        {(alarm.state === 'ACTIVE' || alarm.state === 'ACKNOWLEDGED') && (
                          <button
                            className="btn btn-secondary"
                            disabled={isBusy}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onSuppress(alarm.alarm_id)
                            }}
                          >
                            Suppress
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={6}>No alarms match the current filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="card alarm-detail">
            <h3>Alarm Detail</h3>
            {!selectedAlarm && <p className="muted">Select an alarm to inspect its lifecycle and payload.</p>}
            {selectedAlarm && (
              <div className="review-grid">
                <p>
                  <strong>Gateway:</strong> {selectedAlarm.gateway_id}
                </p>
                <p>
                  <strong>Asset:</strong> {selectedAlarm.asset_id}
                </p>
                <p>
                  <strong>Message:</strong> {selectedAlarm.message}
                </p>
                <p>
                  <strong>Current value:</strong> {formatValue(selectedAlarm.value, selectedAlarm.unit)}
                </p>
                <p>
                  <strong>Threshold:</strong> {formatValue(selectedAlarm.threshold, selectedAlarm.unit)}
                </p>
                <p>
                  <strong>Raised:</strong> {formatDateTime(selectedAlarm.raised_at)}
                </p>
                <p>
                  <strong>Acknowledged:</strong> {formatDateTime(selectedAlarm.acked_at)}
                </p>
                <p>
                  <strong>Acknowledged by:</strong> {selectedAlarm.acked_by ?? 'Not set'}
                </p>
                <p>
                  <strong>Suppressed:</strong> {formatDateTime(selectedAlarm.suppressed_at)}
                </p>
                <p>
                  <strong>Suppressed by:</strong> {selectedAlarm.suppressed_by ?? 'Not set'}
                </p>
                <p>
                  <strong>Cleared:</strong> {formatDateTime(selectedAlarm.cleared_at)}
                </p>
                <p>
                  <strong>Duration:</strong>{' '}
                  {selectedAlarm.duration_seconds !== null ? `${selectedAlarm.duration_seconds}s` : 'Not cleared'}
                </p>
                <div>
                  <strong>Metadata</strong>
                  <pre className="json-preview">{JSON.stringify(selectedAlarm.metadata, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
