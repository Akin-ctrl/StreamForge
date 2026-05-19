import type { JsonObject } from '../../../shared/types/json'
import { asBoolean, asJsonObject } from '../../../shared/config/json'
import type { AdapterSecretsPayload } from '../../../shared/api/client'
import type { AdapterFormState } from './types'

export function isAdapterPasswordConfigured(secretStatus: JsonObject | null, config: JsonObject): boolean {
  const passwordStatus = asJsonObject(secretStatus?.password)
  return (
    asBoolean(passwordStatus?.configured, false) ||
    (typeof config.password === 'string' && config.password.trim().length > 0)
  )
}

export function buildAdapterSecrets(form: AdapterFormState): AdapterSecretsPayload | undefined {
  if (form.adapterType !== 'mqtt' && form.adapterType !== 'opcua') {
    return undefined
  }

  if (!form.password.trim()) {
    return undefined
  }

  return { password: form.password.trim() }
}

export function preserveAdapterSecretState(current: AdapterFormState, next: AdapterFormState): AdapterFormState {
  return {
    ...next,
    password: '',
    passwordConfigured: current.passwordConfigured,
  }
}
