import type { JsonObject } from '../../../shared/types/json'

export type SinkFormState = {
  sinkId: string
  name: string
  sinkType: string
  status: string
  description: string
  sourceTopic: string
  kafkaBootstrap: string
  kafkaGroupId: string
  dbDsn: string
  dbDsnConfigured: boolean
  table: string
  targetBootstrap: string
  targetTopic: string
  url: string
  method: string
  routeType: string
  webhookUrl: string
  webhookUrlConfigured: boolean
  slackWebhookUrl: string
  slackWebhookUrlConfigured: boolean
  passthroughConfig: JsonObject
}
