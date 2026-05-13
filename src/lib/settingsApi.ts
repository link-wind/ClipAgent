import { requestJson } from './agentApi'

export type RuntimeSettingsSource = 'runtime' | 'env' | 'default' | 'missing'
export type RuntimeSettingsRestart = 'immediate' | 'api' | 'worker' | 'api_worker'

export interface RuntimeSettingsMode {
  id: string
  label: string
  description: string
}

export interface RuntimeSettingsField {
  key: string
  label: string
  group: string
  kind: string
  sensitive: boolean
  configured: boolean
  source: RuntimeSettingsSource
  restart: RuntimeSettingsRestart
  help: string
  value?: string | boolean | null
}

export interface RuntimeSettingsGroup {
  id: string
  title: string
  description: string
  fields: RuntimeSettingsField[]
}

export interface RuntimeSettingsResponse {
  mode: RuntimeSettingsMode
  groups: RuntimeSettingsGroup[]
}

export type RuntimeSettingsUpdateValue = string | boolean

export function getRuntimeSettings(): Promise<RuntimeSettingsResponse> {
  return requestJson<RuntimeSettingsResponse>('/api/config/settings')
}

export function updateRuntimeSettings(
  updates: Record<string, RuntimeSettingsUpdateValue>,
): Promise<RuntimeSettingsResponse> {
  return requestJson<RuntimeSettingsResponse>('/api/config/settings', {
    method: 'PATCH',
    body: { updates },
  })
}

export function clearRuntimeSettings(keys: string[]): Promise<RuntimeSettingsResponse> {
  return requestJson<RuntimeSettingsResponse>('/api/config/settings/clear', {
    method: 'POST',
    body: { keys },
  })
}
