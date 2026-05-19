import type { AdapterItem, DeploymentItem, GatewayItem, SinkItem } from '../api/client'

export type GatewayTopologyContext = {
  gateway: GatewayItem
  deployments: DeploymentItem[]
  activeDeployment: DeploymentItem | null
  adapters: AdapterItem[]
  sinks: SinkItem[]
}

export function deploymentsForGateway(gatewayId: string, deployments: DeploymentItem[]): DeploymentItem[] {
  return deployments.filter((deployment) => deployment.gateway_id === gatewayId)
}

export function activeDeploymentForGateway(gatewayId: string, deployments: DeploymentItem[]): DeploymentItem | null {
  const activeRows = deploymentsForGateway(gatewayId, deployments).filter((deployment) => deployment.status === 'active')
  if (activeRows.length === 0) {
    return null
  }

  return [...activeRows].sort((left, right) => {
    return new Date(right.updated_at).getTime() - new Date(left.updated_at).getTime()
  })[0]
}

export function resolveDeploymentAdapters(
  deployment: DeploymentItem | null,
  adapters: AdapterItem[],
): AdapterItem[] {
  if (!deployment) {
    return []
  }

  const byId = new Map(adapters.map((adapter) => [adapter.adapter_id, adapter]))
  return deployment.adapter_ids
    .map((adapterId) => byId.get(adapterId))
    .filter((adapter): adapter is AdapterItem => Boolean(adapter))
}

export function resolveDeploymentSinks(
  deployment: DeploymentItem | null,
  sinks: SinkItem[],
): SinkItem[] {
  if (!deployment) {
    return []
  }

  const byId = new Map(sinks.map((sink) => [sink.sink_id, sink]))
  return deployment.sink_ids
    .map((sinkId) => byId.get(sinkId))
    .filter((sink): sink is SinkItem => Boolean(sink))
}

export function buildGatewayTopologyContext(
  gateway: GatewayItem,
  deployments: DeploymentItem[],
  adapters: AdapterItem[],
  sinks: SinkItem[],
): GatewayTopologyContext {
  const gatewayDeployments = deploymentsForGateway(gateway.gateway_id, deployments)
  const activeDeployment = activeDeploymentForGateway(gateway.gateway_id, deployments)
  return {
    gateway,
    deployments: gatewayDeployments,
    activeDeployment,
    adapters: resolveDeploymentAdapters(activeDeployment, adapters),
    sinks: resolveDeploymentSinks(activeDeployment, sinks),
  }
}
