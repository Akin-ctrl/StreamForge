import type { JsonObject, JsonPrimitive } from '../types/json'

const CONTROL_PLANE_URL = import.meta.env.VITE_CONTROL_PLANE_URL?.toString() || ''

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  if (!headers.has('Content-Type') && init?.body) {
    headers.set('Content-Type', 'application/json')
  }

  const response = await fetch(`${CONTROL_PLANE_URL}${path}`, {
    ...init,
    cache: 'no-store',
    credentials: 'include',
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
  hardware_info?: JsonObject | null
  status: string
  approved: boolean
  last_config_sync_at?: string | null
  last_config_version?: string | null
  last_seen_at?: string | null
  runtime_health?: JsonObject | null
  system_metrics?: JsonObject | null
  created_at: string
}

export type GatewayEnrollmentItem = {
  enrollment_id: string
  name: string
  token_preview: string
  site_name?: string | null
  site_code?: string | null
  expires_at?: string | null
  max_uses?: number | null
  used_count: number
  disabled: boolean
  last_used_at?: string | null
  created_by?: string | null
  created_at: string
  updated_at: string
}

export type GatewayEnrollmentCreateResponse = GatewayEnrollmentItem & {
  token: string
}

export type SecretFieldStatus = {
  configured: boolean
}

export type AdapterItem = {
  adapter_id: string
  name: string
  adapter_type: string
  status: string
  config: JsonObject
  secret_status: Record<string, SecretFieldStatus>
  description?: string | null
  created_at: string
  updated_at: string
}

export type SinkItem = {
  sink_id: string
  name: string
  sink_type: string
  config: JsonObject
  secret_status: Record<string, SecretFieldStatus>
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
  validation_config: JsonObject
  events_config: JsonObject
  aggregates_config: JsonObject
  created_at: string
  updated_at: string
}

export type EventItem = {
  source_sink_id: string
  source_table: string
  record_id: number
  gateway_id?: string | null
  asset_id: string
  event_type: string
  classification: string
  gateway_time: string
  device_time?: string | null
  previous_state: JsonObject
  new_state: JsonObject
  metadata: JsonObject
  payload: JsonObject
}

export type AggregateResolution = '1s' | '1min'

export type AggregateItem = {
  resolution: AggregateResolution
  source_sink_id: string
  source_table: string
  record_id: number
  gateway_id?: string | null
  asset_id: string
  parameter: string
  unit?: string | null
  classification: string
  window_start: string
  window_end: string
  avg: number
  min: number
  max: number
  stddev: number
  count: number
  p50: number
  p95: number
  p99: number
  good_samples: number
  suspect_samples: number
  uncertain_samples: number
  bad_samples: number
  pct_good: number
  payload: JsonObject
}

export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR' | 'CRITICAL'

export type LogEntry = {
  timestamp: string
  gateway_id: string
  level: LogLevel | string
  logger: string
  component: string
  message: string
  exception?: string | null
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
  metadata: JsonObject
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
  original_payload: JsonObject
  preview_payload: JsonObject
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

export type UserRole = 'Viewer' | 'Operator' | 'Engineer' | 'Admin'

export type UserItem = {
  username: string
  role: UserRole
  roles: UserRole[]
  permissions: string[]
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
  default: JsonPrimitive
  help_text?: string | null
  advanced?: boolean
  repeatable?: boolean
  secret?: boolean
  internal?: boolean
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

export type ValidationIssue = {
  field_path?: string | null
  message: string
  severity: 'error' | 'warning'
}

export type ValidationResult = {
  valid: boolean
  errors: string[]
  warnings: string[]
  field_issues: ValidationIssue[]
}

export type ConnectionProbeResult = {
  name: string
  status: 'passed' | 'failed' | 'warning' | 'unsupported'
  message: string
}

export type ConnectionTestResult = {
  ok: boolean
  status: 'passed' | 'failed' | 'unsupported_here' | 'cannot_test_from_control_plane' | 'cannot_test_from_gateway'
  message: string
  warnings: string[]
  probes: ConnectionProbeResult[]
}

export type GatewayConnectionTestItem = {
  request_id: string
  gateway_id: string
  target_kind: 'adapter' | 'sink'
  target_id: string
  target_type: string
  status: 'REQUESTED' | 'RUNNING' | 'PASSED' | 'FAILED' | 'UNSUPPORTED'
  result?: ConnectionTestResult | null
  last_error?: string | null
  requested_by?: string | null
  started_at?: string | null
  completed_at?: string | null
  created_at: string
  updated_at: string
}

export type GatewayConnectionTestCreatePayload = {
  gateway_id: string
  target_kind: 'adapter' | 'sink'
  target_id: string
}

export type DeploymentPreflightResult = {
  ready: boolean
  errors: string[]
  warnings: string[]
  field_issues: ValidationIssue[]
}

export type BootstrapStatusResponse = {
  bootstrap_required: boolean
}

export type UserCreatePayload = {
  username: string
  password: string
  role?: UserRole
}

export type GatewayCreatePayload = {
  gateway_id: string
  hostname: string
  hardware_info?: JsonObject
  approved?: boolean
}

export type GatewayEnrollmentCreatePayload = {
  name: string
  site_name?: string | null
  site_code?: string | null
  expires_at?: string | null
  max_uses?: number | null
}

export type AdapterSecretsPayload = Record<string, string | null>

export type AdapterCreatePayload = {
  adapter_id: string
  name: string
  adapter_type: string
  status: string
  config: JsonObject
  secrets?: AdapterSecretsPayload
  description?: string | null
}

export type AdapterUpdatePayload = {
  name?: string
  status?: string
  config?: JsonObject
  secrets?: AdapterSecretsPayload
  description?: string | null
}

export type SinkSecretsPayload = Record<string, string | null>

export type SinkCreatePayload = {
  sink_id: string
  name: string
  sink_type: string
  config: JsonObject
  secrets?: SinkSecretsPayload
  status: string
  description?: string | null
}

export type SinkUpdatePayload = {
  name?: string
  sink_type?: string
  config?: JsonObject
  secrets?: SinkSecretsPayload
  status?: string
  description?: string | null
}

export type DeploymentCreatePayload = {
  deployment_id: string
  name: string
  gateway_id: string
  status: string
  adapter_ids: string[]
  sink_ids: string[]
  validation_config: JsonObject
  events_config: JsonObject
  aggregates_config: JsonObject
}

export type DeploymentUpdatePayload = {
  name?: string
  status?: string
  adapter_ids?: string[]
  sink_ids?: string[]
  validation_config?: JsonObject
  events_config?: JsonObject
  aggregates_config?: JsonObject
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
    credentials: 'include',
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
  const response = await fetch(`${CONTROL_PLANE_URL}/api/v1/auth/bootstrap/status`, { cache: 'no-store', credentials: 'include' })
  if (!response.ok) {
    throw new Error(await readError(response, 'Unable to determine bootstrap status'))
  }
  return (await response.json()) as BootstrapStatusResponse
}

export async function bootstrapFirstUser(username: string, password: string): Promise<UserTokenResponse> {
  const response = await fetch(`${CONTROL_PLANE_URL}/api/v1/auth/bootstrap/first-user`, {
    method: 'POST',
    cache: 'no-store',
    credentials: 'include',
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

export function logout() {
  return request<{ logged_out: boolean }>('/api/v1/auth/logout', {
    method: 'POST',
  })
}

export function listUsers() {
  return request<UserItem[]>('/api/v1/users')
}

export function getCurrentUser() {
  return request<UserItem>('/api/v1/auth/me')
}

export function createUser(payload: UserCreatePayload) {
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

export function createGateway(payload: GatewayCreatePayload) {
  return request<GatewayItem>('/api/v1/gateways', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function listGatewayEnrollments() {
  return request<GatewayEnrollmentItem[]>('/api/v1/gateway-enrollments')
}

export function createGatewayEnrollment(payload: GatewayEnrollmentCreatePayload) {
  return request<GatewayEnrollmentCreateResponse>('/api/v1/gateway-enrollments', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function disableGatewayEnrollment(enrollmentId: string) {
  return request<{ enrollment_id: string; disabled: boolean }>(
    `/api/v1/gateway-enrollments/${encodeURIComponent(enrollmentId)}/disable`,
    { method: 'POST' },
  )
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

export function createAdapter(payload: AdapterCreatePayload) {
  return request<AdapterItem>('/api/v1/adapters', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function validateAdapterDraft(payload: AdapterCreatePayload) {
  return request<ValidationResult>('/api/v1/adapters/validate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function testAdapterConnection(payload: AdapterCreatePayload) {
  return request<ConnectionTestResult>('/api/v1/adapters/test-connection', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function requestGatewayConnectionTest(payload: GatewayConnectionTestCreatePayload) {
  return request<GatewayConnectionTestItem>('/api/v1/gateway-connection-tests', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getGatewayConnectionTest(requestId: string) {
  return request<GatewayConnectionTestItem>(`/api/v1/gateway-connection-tests/${encodeURIComponent(requestId)}`)
}

export function updateAdapter(adapterId: string, payload: AdapterUpdatePayload) {
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

export function createSink(payload: SinkCreatePayload) {
  return request<SinkItem>('/api/v1/sinks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function validateSinkDraft(payload: SinkCreatePayload) {
  return request<ValidationResult>('/api/v1/sinks/validate', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function testSinkConnection(payload: SinkCreatePayload) {
  return request<ConnectionTestResult>('/api/v1/sinks/test-connection', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateSink(sinkId: string, payload: SinkUpdatePayload) {
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

export function createDeployment(payload: DeploymentCreatePayload) {
  return request<DeploymentItem>('/api/v1/deployments', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function preflightDeployment(payload: DeploymentCreatePayload) {
  return request<DeploymentPreflightResult>('/api/v1/deployments/preflight', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateDeployment(deploymentId: string, payload: DeploymentUpdatePayload) {
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

export function listEvents(filters?: {
  gateway_id?: string
  asset_id?: string
  event_type?: string
  classification?: string
  start_time?: string
  end_time?: string
  limit?: number
}) {
  const params = new URLSearchParams()

  if (filters?.gateway_id) {
    params.set('gateway_id', filters.gateway_id)
  }
  if (filters?.asset_id) {
    params.set('asset_id', filters.asset_id)
  }
  if (filters?.event_type) {
    params.set('event_type', filters.event_type)
  }
  if (filters?.classification) {
    params.set('classification', filters.classification)
  }
  if (filters?.start_time) {
    params.set('start_time', filters.start_time)
  }
  if (filters?.end_time) {
    params.set('end_time', filters.end_time)
  }
  if (filters?.limit) {
    params.set('limit', String(filters.limit))
  }

  const suffix = params.toString()
  return request<EventItem[]>(`/api/v1/events${suffix ? `?${suffix}` : ''}`)
}

export function listAggregates(filters: {
  resolution: AggregateResolution
  gateway_id?: string
  asset_id?: string
  parameter?: string
  classification?: string
  start_time?: string
  end_time?: string
  limit?: number
}) {
  const params = new URLSearchParams()
  params.set('resolution', filters.resolution)

  if (filters.gateway_id) {
    params.set('gateway_id', filters.gateway_id)
  }
  if (filters.asset_id) {
    params.set('asset_id', filters.asset_id)
  }
  if (filters.parameter) {
    params.set('parameter', filters.parameter)
  }
  if (filters.classification) {
    params.set('classification', filters.classification)
  }
  if (filters.start_time) {
    params.set('start_time', filters.start_time)
  }
  if (filters.end_time) {
    params.set('end_time', filters.end_time)
  }
  if (filters.limit) {
    params.set('limit', String(filters.limit))
  }

  return request<AggregateItem[]>(`/api/v1/aggregates?${params.toString()}`)
}

export function listLogs(filters?: {
  gateway_id?: string
  component?: string
  level?: string
  limit?: number
}) {
  const params = new URLSearchParams()

  if (filters?.gateway_id) {
    params.set('gateway_id', filters.gateway_id)
  }
  if (filters?.component) {
    params.set('component', filters.component)
  }
  if (filters?.level) {
    params.set('level', filters.level)
  }
  if (filters?.limit) {
    params.set('limit', String(filters.limit))
  }

  const suffix = params.toString()
  return request<LogEntry[]>(`/api/v1/logs${suffix ? `?${suffix}` : ''}`)
}
