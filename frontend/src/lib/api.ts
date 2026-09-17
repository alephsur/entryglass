export type ApiHealth = {
  status: 'ok'
  service: string
  version: string
  stage: 'review'
  nansen_integration: 'private_review'
}

export type ReviewJob = {
  review_id: string
  wallet_address: string
  from_utc: string
  to_utc: string
  status: 'pending' | 'running' | 'complete' | 'partial' | 'failed' | 'cancelled'
  stage: 'queued' | 'importing_entries' | 'enriching_evidence' | 'complete' | 'stopped'
  entries_total: number
  entries_processed: number
  requests_attempted: number
  credits_used: number
  max_entries: number
  max_requests: number
  max_credits: number
  cancellation_requested: boolean
  error_code: string | null
}

export type EntrySummary = {
  entry_id: string
  occurred_at: string
  token_address: string
  quote_address: string
  trade_value_usd: string
  context_coverage: 'pending' | 'observed' | 'unavailable'
  outcome_states: Record<string, string>
}

export type HistoricalContext = {
  coverage: 'observed' | 'unavailable'
  window_from_utc: string
  window_to_utc: string
  smart_trader_net_flow_usd: string | null
  smart_trader_avg_flow_usd: string | null
  smart_trader_wallet_count: number | null
  warnings: string[]
}

export type ReplayEntry = {
  entry: EntrySummary
  token_amount: string
  quote_amount: string
  entry_price_usd: string
  context: HistoricalContext | null
  outcome_values_hidden: true
}

export type Outcome = {
  horizon: '24h' | '7d'
  target_at: string
  state: string
  observed_at: string | null
  observed_price_usd: string | null
  price_change_pct: string | null
  interpretation: string
}

export type Evidence = {
  kind: 'historical_context' | 'later_price'
  source: 'Nansen'
  endpoint: string
  requested_from_utc: string
  requested_to_utc: string
  retrieved_at: string
  request_id: string | null
  request_fingerprint: string
  response_hash: string
  warnings: string[]
  coverage: 'complete' | 'truncated'
  quoted_credits: number | null
  used_credits: number | null
  attempt_count: number
  rule_version: string
}

export type CreateReviewInput = {
  wallet_address: string
  from_utc: string
  to_utc: string
  max_entries: number
}

function isApiHealth(value: unknown): value is ApiHealth {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return (
    item.status === 'ok' &&
    typeof item.service === 'string' &&
    typeof item.version === 'string' &&
    item.stage === 'review' &&
    item.nansen_integration === 'private_review'
  )
}

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    ...init,
    headers: {
      Accept: 'application/json',
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    signal: init?.signal ?? AbortSignal.timeout(20_000),
  })
  if (!response.ok) {
    let message = `API returned HTTP ${response.status}.`
    try {
      const payload = await response.json() as { detail?: string | { message?: string } }
      if (typeof payload.detail === 'string') message = payload.detail
      else if (payload.detail?.message) message = payload.detail.message
    } catch { /* Keep the safe HTTP message. */ }
    throw new Error(message)
  }
  return await response.json() as T
}

export async function getApiHealth(signal?: AbortSignal): Promise<ApiHealth> {
  const payload = await fetchJson<unknown>('/api/v1/health', { signal })
  if (!isApiHealth(payload)) throw new Error('API returned an unexpected health response.')
  return payload
}

export function createReview(input: CreateReviewInput): Promise<ReviewJob> {
  return fetchJson('/api/v1/reviews', { method: 'POST', body: JSON.stringify(input) })
}

export function getReview(reviewId: string): Promise<ReviewJob> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}`)
}

export function cancelReview(reviewId: string): Promise<ReviewJob> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/cancel`, { method: 'POST' })
}

export function listReviewEntries(reviewId: string): Promise<EntrySummary[]> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/entries`)
}

export function getReplay(reviewId: string, entryId: string): Promise<ReplayEntry> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/entries/${encodeURIComponent(entryId)}`)
}

export function revealOutcomes(reviewId: string, entryId: string): Promise<Outcome[]> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/entries/${encodeURIComponent(entryId)}/outcomes`)
}

export function getEvidence(reviewId: string, entryId: string): Promise<Evidence[]> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/entries/${encodeURIComponent(entryId)}/evidence`)
}
