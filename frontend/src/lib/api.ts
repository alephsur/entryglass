export type ApiHealth = {
  status: 'ok'
  service: string
  version: string
  stage: 'scaffold'
  nansen_integration: 'validation_only'
}

function isApiHealth(value: unknown): value is ApiHealth {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return (
    item.status === 'ok' &&
    typeof item.service === 'string' &&
    typeof item.version === 'string' &&
    item.stage === 'scaffold' &&
    item.nansen_integration === 'validation_only'
  )
}

export async function getApiHealth(signal?: AbortSignal): Promise<ApiHealth> {
  const response = await fetch('/api/v1/health', {
    headers: { Accept: 'application/json' },
    signal: signal ?? AbortSignal.timeout(5000),
  })
  if (!response.ok) {
    throw new Error(`API returned HTTP ${response.status}.`)
  }
  const payload: unknown = await response.json()
  if (!isApiHealth(payload)) {
    throw new Error('API returned an unexpected health response.')
  }
  return payload
}
