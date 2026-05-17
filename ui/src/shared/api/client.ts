import { getAccessToken } from '../auth/session'

const CONTROL_PLANE_URL = import.meta.env.VITE_CONTROL_PLANE_URL?.toString() || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken()

  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json')
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  const response = await fetch(`${CONTROL_PLANE_URL}${path}`, {
    ...init,
    cache: 'no-store',
    headers,
  })

  if (!response.ok) {
    const text = await response.text()
    throw new Error(text || `Request failed: ${response.status}`)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return (await response.json()) as T
}

export type GatewayItem = {
  gateway_id: string
  hostname: string
  status: string
  approved: boolean
  last_config_sync_at?: string | null
  last_config_version?: string | null
  last_seen_at?: string | null
  runtime_health?: Record<string, unknown> | null
  system_metrics?: Record<string, unknown> | null
  created_at: string
}

export type AdapterItem = {
  adapter_id: string
  name: string
  adapter_type: string
  status: string
  config: Record<string, unknown>
  description?: string | null
  created_at: string
  updated_at: string
}

export type SinkItem = {
  sink_id: string
  name: string
  sink_type: string
  config: Record<string, unknown>
  status: string
  description?: string | null
  created_at: string
  updated_at: string
}

export type DeploymentItem = {
  deployment_id: string
  name: string
  gateway_id: string
  status: string
  adapter_ids: string[]
  sink_ids: string[]
  validation_config: Record<string, unknown>
  events_config: Record<string, unknown>
  aggregates_config: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type AlarmSeverity = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW' | 'INFO'
export type AlarmState = 'ACTIVE' | 'ACKNOWLEDGED' | 'CLEARED' | 'SUPPRESSED'

export type AlarmItem = {
  alarm_id: string
  gateway_id: string
  asset_id: string
  type: string
  severity: AlarmSeverity
  state: AlarmState
  classification: string
  message: string
  value: number | null
  threshold: number | null
  unit: string | null
  raised_at: string
  acked_at: string | null
  acked_by: string | null
  cleared_at: string | null
  suppressed_at: string | null
  suppressed_by: string | null
  duration_seconds: number | null
  metadata: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type AlarmListItem = AlarmItem & {
  is_active: boolean
}

export type DlqStatus =
  | 'PENDING'
  | 'REPROCESS_REQUESTED'
  | 'REPROCESSED'
  | 'DISCARD_REQUESTED'
  | 'DISCARDED'
  | 'REPROCESS_FAILED'

export type DlqAction = 'REPROCESS' | 'DISCARD'

export type DlqItem = {
  message_id: string
  gateway_id: string
  asset_id: string | null
  source_topic: string
  clean_topic: string
  reason: string
  status: DlqStatus
  requested_action: DlqAction | null
  reviewed_by: string | null
  reviewed_at: string | null
  action_completed_at: string | null
  last_error: string | null
  failed_at: string
  original_payload: Record<string, unknown>
  preview_payload: Record<string, unknown>
  created_at: string
  updated_at: string
}

export type HealthResponse = {
  status: string
  service: string
  dependencies?: Record<string, string>
  counts?: Record<string, number>
  gateway_states?: Record<string, number>
  gateways?: GatewayItem[]
}

export type UserTokenResponse = {
  access_token: string
  expires_at: string
}

export type UserItem = {
  username: string
  is_admin: boolean
  roles: string[]
  created_at: string
}

export type CatalogOption = {
  value: string
  label: string
}

export type CatalogField = {
  key: string
  label: string
  input_type: string
  required: boolean
  default: string | number | boolean | null
  help_text?: string | null
  advanced?: boolean
  repeatable?: boolean
  options?: CatalogOption[]
  children?: CatalogField[]
}

export type CatalogSection = {
  key: string
  label: string
  repeatable?: boolean
  help_text?: string | null
  fields: CatalogField[]
}

export type CatalogAdapterType = {
  adapter_type: string
  label: string
  supports_registers: boolean
  fields: CatalogField[]
  sections?: CatalogSection[]
}

export type CatalogSinkType = {
  sink_type: string
  label: string
  fields: CatalogField[]
  sections?: CatalogSection[]
}

export type CatalogResponse = {
  adapters: CatalogAdapterType[]
  sinks: CatalogSinkType[]
}

export type BootstrapStatusResponse = {
  bootstrap_required: boolean
}

async function readError(response: Response, fallbackMessage: string): Promise<string> {
  const text = await response.text()
  if (!text) {
    return fallbackMessage
  }

  try {
    const parsed = JSON.parse(text) as { detail?: string }
    return parsed.detail || fallbackMessage
  } catch {
    return text
  }
}

export async function login(username: string, password: string): Promise<UserTokenResponse> {
  const body = new URLSearchParams()
  body.set('username', username)
  body.set('password', password)

  const response = await fetch(`${CONTROL_PLANE_URL}/api/v1/auth/token`, {
    method: 'POST',
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Invalid credentials'))
  }

  return (await response.json()) as UserTokenResponse
}

export async function getBootstrapStatus(): Promise<BootstrapStatusResponse> {
  const response = await fetch(`${CONTROL_PLANE_URL}/api/v1/auth/bootstrap/status`, { cache: 'no-store' })
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to determine bootstrap status'))
  }
  return (await response.json()) as BootstrapStatusResponse
}

export async function bootstrapFirstUser(username: string, password: string): Promise<UserTokenResponse> {
  const response = await fetch(`${CONTROL_PLANE_URL}/api/v1/auth/bootstrap/first-user`, {
    method: 'POST',
    cache: 'no-store',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  })

  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to create the first admin user'))
  }

  return (await response.json()) as UserTokenResponse
}

export function listUsers() {
  return request<UserItem[]>('/api/v1/users')
}

export function getCurrentUser() {
  return request<UserItem>('/api/v1/auth/me')
}

export function createUser(payload: {
  username: string
  password: string
  is_admin?: boolean
}) {
  return request<UserItem>('/api/v1/users', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteUser(username: string) {
  return request<{ deleted: boolean; username: string }>(`/api/v1/users/${encodeURIComponent(username)}`, {
    method: 'DELETE',
  })
}

export function listGateways() {
  return request<GatewayItem[]>('/api/v1/gateways')
}

export function createGateway(payload: {
  gateway_id: string
  hostname: string
  hardware_info?: Record<string, unknown>
  approved?: boolean
}) {
  return request<GatewayItem>('/api/v1/gateways', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function approveGateway(gatewayId: string) {
  return request<{ gateway_id: string; status: string; approved: boolean }>(
    `/api/v1/gateways/${gatewayId}/approve`,
    { method: 'POST' },
  )
}

export function listAdapters() {
  return request<AdapterItem[]>('/api/v1/adapters')
}

export function createAdapter(payload: {
  adapter_id: string
  name: string
  adapter_type: string
  status: string
  config: Record<string, unknown>
  description?: string | null
}) {
  return request<AdapterItem>('/api/v1/adapters', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateAdapter(
  adapterId: string,
  payload: {
    name?: string
    status?: string
    config?: Record<string, unknown>
    description?: string | null
  },
) {
  return request<AdapterItem>(`/api/v1/adapters/${encodeURIComponent(adapterId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteAdapter(adapterId: string) {
  return request<{ deleted: boolean; adapter_id: string }>(`/api/v1/adapters/${encodeURIComponent(adapterId)}`, {
    method: 'DELETE',
  })
}

export function listSinks() {
  return request<SinkItem[]>('/api/v1/sinks')
}

export function createSink(payload: {
  sink_id: string
  name: string
  sink_type: string
  config: Record<string, unknown>
  status: string
  description?: string | null
}) {
  return request<SinkItem>('/api/v1/sinks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateSink(
  sinkId: string,
  payload: {
    name?: string
    sink_type?: string
    config?: Record<string, unknown>
    status?: string
    description?: string | null
  },
) {
  return request<SinkItem>(`/api/v1/sinks/${encodeURIComponent(sinkId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteSink(sinkId: string) {
  return request<{ deleted: boolean; sink_id: string }>(`/api/v1/sinks/${encodeURIComponent(sinkId)}`, {
    method: 'DELETE',
  })
}

export function listDeployments() {
  return request<DeploymentItem[]>('/api/v1/deployments')
}

export function getDeployment(deploymentId: string) {
  return request<DeploymentItem>(`/api/v1/deployments/${encodeURIComponent(deploymentId)}`)
}

export function createDeployment(payload: {
  deployment_id: string
  name: string
  gateway_id: string
  status: string
  adapter_ids: string[]
  sink_ids: string[]
  validation_config: Record<string, unknown>
  events_config: Record<string, unknown>
  aggregates_config: Record<string, unknown>
}) {
  return request<DeploymentItem>('/api/v1/deployments', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateDeployment(
  deploymentId: string,
  payload: {
    name?: string
    status?: string
    adapter_ids?: string[]
    sink_ids?: string[]
    validation_config?: Record<string, unknown>
    events_config?: Record<string, unknown>
    aggregates_config?: Record<string, unknown>
  },
) {
  return request<DeploymentItem>(`/api/v1/deployments/${encodeURIComponent(deploymentId)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteDeployment(deploymentId: string) {
  return request<{ deleted: boolean; deployment_id: string }>(`/api/v1/deployments/${encodeURIComponent(deploymentId)}`, {
    method: 'DELETE',
  })
}

export function getHealth() {
  return request<HealthResponse>('/api/v1/health')
}

export function getCatalog() {
  return request<CatalogResponse>('/api/v1/catalog')
}

export function listAlarms(filters?: {
  state?: AlarmState
  severity?: AlarmSeverity
  gateway_id?: string
  asset_id?: string
  active_only?: boolean
  limit?: number
}) {
  const params = new URLSearchParams()

  if (filters?.state) {
    params.set('state', filters.state)
  }
  if (filters?.severity) {
    params.set('severity', filters.severity)
  }
  if (filters?.gateway_id) {
    params.set('gateway_id', filters.gateway_id)
  }
  if (filters?.asset_id) {
    params.set('asset_id', filters.asset_id)
  }
  if (filters?.active_only) {
    params.set('active_only', 'true')
  }
  if (filters?.limit) {
    params.set('limit', String(filters.limit))
  }

  const suffix = params.toString()
  return request<AlarmListItem[]>(`/api/v1/alarms${suffix ? `?${suffix}` : ''}`)
}

export function acknowledgeAlarm(alarmId: string, ackedBy?: string) {
  return request<AlarmItem>(`/api/v1/alarms/${alarmId}/acknowledge`, {
    method: 'POST',
    body: ackedBy ? JSON.stringify({ acked_by: ackedBy }) : undefined,
  })
}

export function suppressAlarm(alarmId: string, suppressedBy?: string) {
  return request<AlarmItem>(`/api/v1/alarms/${alarmId}/suppress`, {
    method: 'POST',
    body: suppressedBy ? JSON.stringify({ suppressed_by: suppressedBy }) : undefined,
  })
}

export function listDlq(filters?: {
  status?: DlqStatus
  gateway_id?: string
  reason?: string
  limit?: number
}) {
  const params = new URLSearchParams()

  if (filters?.status) {
    params.set('status', filters.status)
  }
  if (filters?.gateway_id) {
    params.set('gateway_id', filters.gateway_id)
  }
  if (filters?.reason) {
    params.set('reason', filters.reason)
  }
  if (filters?.limit) {
    params.set('limit', String(filters.limit))
  }

  const suffix = params.toString()
  return request<DlqItem[]>(`/api/v1/dlq${suffix ? `?${suffix}` : ''}`)
}

export function approveDlqMessage(messageId: string, reviewedBy?: string) {
  return request<DlqItem>(`/api/v1/dlq/messages/${messageId}/approve`, {
    method: 'POST',
    body: reviewedBy ? JSON.stringify({ reviewed_by: reviewedBy }) : undefined,
  })
}

export function bulkApproveDlqMessages(messageIds: string[], reviewedBy?: string) {
  return request<DlqItem[]>('/api/v1/dlq/bulk/approve', {
    method: 'POST',
    body: JSON.stringify({
      message_ids: messageIds,
      reviewed_by: reviewedBy,
    }),
  })
}

export function discardDlqMessage(messageId: string, reviewedBy?: string) {
  return request<DlqItem>(`/api/v1/dlq/messages/${messageId}/discard`, {
    method: 'POST',
    body: reviewedBy ? JSON.stringify({ reviewed_by: reviewedBy }) : undefined,
  })
}
