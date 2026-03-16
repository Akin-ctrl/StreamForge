import { getAccessToken } from '../auth/session'

// Empty default keeps all requests same-origin (served via nginx /api proxy).
const CONTROL_PLANE_URL = import.meta.env.VITE_CONTROL_PLANE_URL?.toString() || ''

/**
 * Shared fetch wrapper for authenticated control-plane API calls.
 * Adds bearer token when available and normalizes JSON parsing/errors.
 */
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
  created_at: string
}

export type PipelineItem = {
  id: number
  name: string
  gateway_id: string
  config: Record<string, unknown>
  created_at: string
}

export type SinkItem = {
  id: number
  pipeline_id: number
  sink_type: string
  config: Record<string, unknown>
  status: string
  created_at: string
}

export type HealthResponse = {
  status: string
  service: string
}

export type UserTokenResponse = {
  access_token: string
  expires_at: string
}

/** Exchanges username/password for a JWT access token. */
export async function login(username: string, password: string): Promise<UserTokenResponse> {
  const body = new URLSearchParams()
  body.set('username', username)
  body.set('password', password)

  const response = await fetch(`${CONTROL_PLANE_URL}/api/v1/auth/token`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded',
    },
    body,
  })

  if (!response.ok) {
    throw new Error('Invalid credentials')
  }

  return (await response.json()) as UserTokenResponse
}

export function listGateways() {
  return request<GatewayItem[]>('/api/v1/gateways')
}

/** Approves a discovered gateway for runtime orchestration. */
export function approveGateway(gatewayId: string) {
  return request<{ gateway_id: string; status: string; approved: boolean }>(
    `/api/v1/gateways/${gatewayId}/approve`,
    { method: 'POST' },
  )
}

export function listPipelines() {
  return request<PipelineItem[]>('/api/v1/pipelines')
}

export function createPipeline(payload: {
  name: string
  gateway_id: string
  config: Record<string, unknown>
}) {
  return request<PipelineItem>('/api/v1/pipelines', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deletePipeline(pipelineId: number) {
  return request<{ deleted: boolean; pipeline_id: number }>(`/api/v1/pipelines/${pipelineId}`, {
    method: 'DELETE',
  })
}

export function listSinks() {
  return request<SinkItem[]>('/api/v1/sinks')
}

export function createSink(payload: {
  pipeline_id: number
  sink_type: string
  config: Record<string, unknown>
  status: string
}) {
  return request<SinkItem>('/api/v1/sinks', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function deleteSink(sinkId: number) {
  return request<{ deleted: boolean; sink_id: number }>(`/api/v1/sinks/${sinkId}`, {
    method: 'DELETE',
  })
}

export function getHealth() {
  return request<HealthResponse>('/api/v1/health')
}
