import type { SinkSecretsPayload } from '../../../shared/api/client'
import type { SinkFormState } from './types'

export function buildSinkSecrets(form: SinkFormState): SinkSecretsPayload | undefined {
  if (form.sinkType === 'timescaledb') {
    if (!form.dbDsn.trim()) {
      return undefined
    }

    return { db_dsn: form.dbDsn.trim() }
  }

  if (form.sinkType === 'alert_router') {
    if (form.routeType === 'slack') {
      if (!form.slackWebhookUrl.trim()) {
        return undefined
      }

      return { webhook_url: form.slackWebhookUrl.trim() }
    }

    if (!form.webhookUrl.trim()) {
      return undefined
    }

    return { url: form.webhookUrl.trim() }
  }

  return undefined
}

export function preserveSinkSecretState(current: SinkFormState, next: SinkFormState): SinkFormState {
  return {
    ...next,
    dbDsn: '',
    dbDsnConfigured: current.dbDsnConfigured,
    webhookUrl: '',
    webhookUrlConfigured: current.webhookUrlConfigured,
    slackWebhookUrl: '',
    slackWebhookUrlConfigured: current.slackWebhookUrlConfigured,
  }
}
