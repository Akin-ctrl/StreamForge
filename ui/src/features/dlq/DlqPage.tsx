import { useEffect, useMemo, useState } from 'react'

import {
  DlqItem,
  DlqStatus,
  approveDlqMessage,
  bulkApproveDlqMessages,
  discardDlqMessage,
  listDlq,
} from '../../shared/api/client'

const statusOptions: Array<DlqStatus | 'ALL'> = [
  'ALL',
  'PENDING',
  'REPROCESS_REQUESTED',
  'REPROCESSED',
  'DISCARD_REQUESTED',
  'DISCARDED',
  'REPROCESS_FAILED',
]

function formatDateTime(value: string | null) {
  if (!value) {
    return 'Not set'
  }

  return new Date(value).toLocaleString()
}

function canApprove(item: DlqItem) {
  return item.status === 'PENDING' || item.status === 'REPROCESS_FAILED'
}

function canDiscard(item: DlqItem) {
  return item.status === 'PENDING' || item.status === 'REPROCESS_FAILED'
}

/**
 * DLQ workflow page.
 * Supports filtering, detail inspection, single-message actions, and bulk reprocess requests.
 */
export function DlqPage() {
  const [items, setItems] = useState<DlqItem[]>([])
  const [selectedMessageId, setSelectedMessageId] = useState<string | null>(null)
  const [selectedIds, setSelectedIds] = useState<string[]>([])
  const [statusFilter, setStatusFilter] = useState<DlqStatus | 'ALL'>('ALL')
  const [gatewayFilter, setGatewayFilter] = useState('ALL')
  const [reasonFilter, setReasonFilter] = useState('ALL')
  const [loading, setLoading] = useState(true)
  const [busyId, setBusyId] = useState<string | null>(null)
  const [bulkBusy, setBulkBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const refresh = async () => {
    setLoading(true)
    setError(null)
    try {
      const rows = await listDlq({
        status: statusFilter === 'ALL' ? undefined : statusFilter,
        gateway_id: gatewayFilter === 'ALL' ? undefined : gatewayFilter,
        reason: reasonFilter === 'ALL' ? undefined : reasonFilter,
        limit: 200,
      })
      setItems(rows)
      setSelectedIds((current) => current.filter((messageId) => rows.some((row) => row.message_id === messageId)))
      if (!selectedMessageId && rows.length > 0) {
        setSelectedMessageId(rows[0].message_id)
      }
      if (selectedMessageId && !rows.some((row) => row.message_id === selectedMessageId)) {
        setSelectedMessageId(rows[0]?.message_id ?? null)
      }
    } catch (loadError) {
      setError(loadError instanceof Error ? loadError.message : 'Failed to load DLQ messages')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void refresh()
  }, [statusFilter, gatewayFilter, reasonFilter])

  const selectedItem = items.find((item) => item.message_id === selectedMessageId) ?? null
  const gatewayOptions = useMemo(
    () => Array.from(new Set(items.map((item) => item.gateway_id))).sort(),
    [items],
  )
  const reasonOptions = useMemo(
    () => Array.from(new Set(items.map((item) => item.reason))).sort(),
    [items],
  )
  const selectableIds = useMemo(
    () => items.filter((item) => canApprove(item)).map((item) => item.message_id),
    [items],
  )

  const onToggleSelected = (messageId: string) => {
    setSelectedIds((current) =>
      current.includes(messageId) ? current.filter((item) => item !== messageId) : [...current, messageId],
    )
  }

  const onApprove = async (messageId: string) => {
    setBusyId(messageId)
    setError(null)
    try {
      await approveDlqMessage(messageId)
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to approve DLQ message')
    } finally {
      setBusyId(null)
    }
  }

  const onDiscard = async (messageId: string) => {
    setBusyId(messageId)
    setError(null)
    try {
      await discardDlqMessage(messageId)
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to discard DLQ message')
    } finally {
      setBusyId(null)
    }
  }

  const onBulkApprove = async () => {
    if (selectedIds.length === 0) {
      return
    }

    setBulkBusy(true)
    setError(null)
    try {
      await bulkApproveDlqMessages(selectedIds)
      setSelectedIds([])
      await refresh()
    } catch (actionError) {
      setError(actionError instanceof Error ? actionError.message : 'Failed to bulk approve DLQ messages')
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <section className="section-grid">
      <div className="page-header">
        <div>
          <h2>DLQ</h2>
          <p className="muted">Review rejected telemetry, compare preview payloads, and request gateway-side reprocess or discard.</p>
        </div>
        <div className="page-actions">
          <button className="btn btn-secondary" disabled={bulkBusy || selectedIds.length === 0} onClick={() => void onBulkApprove()}>
            Bulk Approve
          </button>
          <button className="btn" onClick={() => void refresh()}>
            Refresh
          </button>
        </div>
      </div>

      <div className="card alarm-filters">
        <label>
          Status
          <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value as DlqStatus | 'ALL')}>
            {statusOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label>
          Gateway
          <select value={gatewayFilter} onChange={(event) => setGatewayFilter(event.target.value)}>
            <option value="ALL">ALL</option>
            {gatewayOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>

        <label>
          Error Type
          <select value={reasonFilter} onChange={(event) => setReasonFilter(event.target.value)}>
            <option value="ALL">ALL</option>
            {reasonOptions.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </label>
      </div>

      {loading && <p>Loading DLQ messages...</p>}
      {error && <p className="error">{error}</p>}

      {!loading && (
        <div className="alarm-layout">
          <div className="card">
            <table className="table">
              <thead>
                <tr>
                  <th>
                    <input
                      type="checkbox"
                      checked={selectableIds.length > 0 && selectedIds.length === selectableIds.length}
                      onChange={(event) => setSelectedIds(event.target.checked ? selectableIds : [])}
                    />
                  </th>
                  <th>Reason</th>
                  <th>Status</th>
                  <th>Gateway</th>
                  <th>Asset</th>
                  <th>Failed</th>
                  <th>Actions</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => {
                  const isBusy = busyId === item.message_id
                  const isSelected = selectedMessageId === item.message_id
                  const selectable = canApprove(item)
                  return (
                    <tr
                      key={item.message_id}
                      className={isSelected ? 'alarm-row-selected' : undefined}
                      onClick={() => setSelectedMessageId(item.message_id)}
                    >
                      <td>
                        <input
                          type="checkbox"
                          checked={selectedIds.includes(item.message_id)}
                          disabled={!selectable}
                          onChange={(event) => {
                            event.stopPropagation()
                            onToggleSelected(item.message_id)
                          }}
                        />
                      </td>
                      <td>
                        <strong>{item.reason}</strong>
                        <div className="muted">{item.message_id}</div>
                      </td>
                      <td>{item.status}</td>
                      <td>{item.gateway_id}</td>
                      <td>{item.asset_id ?? 'Unknown'}</td>
                      <td>{formatDateTime(item.failed_at)}</td>
                      <td>
                        {canApprove(item) && (
                          <button
                            className="btn btn-secondary"
                            disabled={isBusy}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onApprove(item.message_id)
                            }}
                          >
                            Approve
                          </button>
                        )}
                        {canDiscard(item) && (
                          <button
                            className="btn btn-secondary"
                            disabled={isBusy}
                            onClick={(event) => {
                              event.stopPropagation()
                              void onDiscard(item.message_id)
                            }}
                          >
                            Discard
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
                {items.length === 0 && (
                  <tr>
                    <td colSpan={7}>No DLQ messages match the current filters.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>

          <div className="card alarm-detail">
            <h3>DLQ Detail</h3>
            {!selectedItem && <p className="muted">Select a DLQ message to inspect the failed payload and reprocess preview.</p>}
            {selectedItem && (
              <div className="review-grid">
                <p>
                  <strong>Source Topic:</strong> {selectedItem.source_topic}
                </p>
                <p>
                  <strong>Clean Topic:</strong> {selectedItem.clean_topic}
                </p>
                <p>
                  <strong>Reviewed By:</strong> {selectedItem.reviewed_by ?? 'Not reviewed'}
                </p>
                <p>
                  <strong>Reviewed At:</strong> {formatDateTime(selectedItem.reviewed_at)}
                </p>
                <p>
                  <strong>Action Completed:</strong> {formatDateTime(selectedItem.action_completed_at)}
                </p>
                <p>
                  <strong>Last Error:</strong> {selectedItem.last_error ?? 'None'}
                </p>
                <div>
                  <strong>Original Payload</strong>
                  <pre className="json-preview">{JSON.stringify(selectedItem.original_payload, null, 2)}</pre>
                </div>
                <div>
                  <strong>Reprocess Preview</strong>
                  <pre className="json-preview">{JSON.stringify(selectedItem.preview_payload, null, 2)}</pre>
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </section>
  )
}
