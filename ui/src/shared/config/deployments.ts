export type DeploymentSummary = {
  adapterCount: number
  sinkCount: number
  validationEnabled: boolean
  eventsConfigured: boolean
  aggregatesConfigured: boolean
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  return value as Record<string, unknown>
}

export function getDeploymentAdapterCount(config: Record<string, unknown>): number {
  const adapters = config.adapters
  return Array.isArray(adapters) ? adapters.length : 0
}

export function getDeploymentValidationEnabled(config: Record<string, unknown>): boolean {
  const validation = asRecord(config.validation)
  return Boolean(validation?.enabled)
}

export function getDeploymentEventsConfigured(config: Record<string, unknown>): boolean {
  const events = asRecord(config.events)
  if (events && Object.keys(events).length > 0) {
    return true
  }

  const adapters = Array.isArray(config.adapters) ? config.adapters : []
  return adapters.some((adapter) => {
    const adapterRecord = asRecord(adapter)
    const adapterConfig = asRecord(adapterRecord?.config)
    const output = asRecord(adapterConfig?.output)
    return typeof output?.events_topic === 'string' && output.events_topic.trim().length > 0
  })
}

export function getDeploymentAggregatesConfigured(config: Record<string, unknown>): boolean {
  const aggregates = asRecord(config.aggregates)
  return Boolean(aggregates?.enabled)
}

export function summarizeDeployment(config: Record<string, unknown>, sinkCount: number): DeploymentSummary {
  return {
    adapterCount: getDeploymentAdapterCount(config),
    sinkCount,
    validationEnabled: getDeploymentValidationEnabled(config),
    eventsConfigured: getDeploymentEventsConfigured(config),
    aggregatesConfigured: getDeploymentAggregatesConfigured(config),
  }
}
