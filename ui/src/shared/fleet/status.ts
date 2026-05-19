import type { GatewayItem } from '../api/client'
import type { JsonObject } from '../types/json'

export type HeartbeatState = 'fresh' | 'stale' | 'offline' | 'never-seen' | 'unknown'
export type FleetTone = 'good' | 'warn' | 'bad' | 'neutral'

type RuntimeComponentEntry = {
  name: string
  status: string
  details: JsonObject
}

function asObject(value: unknown): JsonObject {
  return value && typeof value === 'object' && !Array.isArray(value) ? (value as JsonObject) : {}
}

export function metricNumber(metrics: JsonObject | null | undefined, key: string): number | null {
  const value = metrics?.[key]
  return typeof value === 'number' ? value : null
}

export function runtimeStatus(gateway: GatewayItem): string {
  const status = gateway.runtime_health?.status
  return typeof status === 'string' ? status : 'unknown'
}

export function runtimeTone(status: string): FleetTone {
  if (status === 'healthy') {
    return 'good'
  }
  if (status === 'degraded') {
    return 'warn'
  }
  if (status === 'unhealthy') {
    return 'bad'
  }
  return 'neutral'
}

export function heartbeatState(lastSeenAt: string | null | undefined): HeartbeatState {
  if (!lastSeenAt) {
    return 'never-seen'
  }

  const seen = new Date(lastSeenAt).getTime()
  if (Number.isNaN(seen)) {
    return 'unknown'
  }

  const ageMinutes = (Date.now() - seen) / 60000
  if (ageMinutes <= 5) {
    return 'fresh'
  }
  if (ageMinutes <= 30) {
    return 'stale'
  }
  return 'offline'
}

export function heartbeatTone(state: HeartbeatState): FleetTone {
  if (state === 'fresh') {
    return 'good'
  }
  if (state === 'stale') {
    return 'warn'
  }
  if (state === 'offline') {
    return 'bad'
  }
  return 'neutral'
}

export function heartbeatLabel(state: HeartbeatState): string {
  if (state === 'never-seen') {
    return 'never seen'
  }
  return state
}

export function componentEntries(gateway: GatewayItem): RuntimeComponentEntry[] {
  const runtimeHealth = asObject(gateway.runtime_health)
  const components = asObject(runtimeHealth.components)
  return Object.entries(components).map(([name, value]) => {
    const component = asObject(value)
    const status = typeof component.status === 'string' ? component.status : 'unknown'
    return {
      name,
      status,
      details: asObject(component.details),
    }
  })
}

export function gatewayIssues(gateway: GatewayItem, activeDeploymentCount: number): string[] {
  const issues: string[] = []
  const heartbeat = heartbeatState(gateway.last_seen_at)
  const runtime = runtimeStatus(gateway)

  if (!gateway.approved) {
    issues.push('Gateway is awaiting approval.')
  }
  if (heartbeat === 'offline') {
    issues.push('Gateway heartbeat is offline.')
  } else if (heartbeat === 'stale') {
    issues.push('Gateway heartbeat is stale.')
  }
  if (runtime === 'unhealthy') {
    issues.push('Runtime reported unhealthy status.')
  } else if (runtime === 'degraded') {
    issues.push('Runtime reported degraded status.')
  }
  if (activeDeploymentCount === 0) {
    issues.push('No active deployment is attached.')
  }

  return issues
}
