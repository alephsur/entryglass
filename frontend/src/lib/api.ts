export type ApiHealth = {
  status: 'ok'
  service: string
  version: string
  stage: 'preflight'
  nansen_integration: 'private_review_and_preflight'
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

export type OutcomeCounts = {
  gain: number
  flat: number
  decline: number
  unavailable: number
}

export type PrecedentObservation = {
  entry_id: string
  occurred_at: string
  token_address: string
  pattern: string
  outcome_band: 'gain' | 'flat' | 'decline' | 'unavailable'
  price_change_pct: string | null
}

export type PatternSummary = {
  pattern: string
  description: string
  sample_count: number
  outcome_counts: OutcomeCounts
  observations: PrecedentObservation[]
}

export type PrecedentReport = {
  review_id: string
  horizon: '24h' | '7d'
  rule_version: string
  patterns: PatternSummary[]
  baseline: OutcomeCounts
  context_observed: number
  context_unavailable: number
  evaluation_mode: 'descriptive_only'
  evaluation_status: 'not_run_no_predictive_claim'
  limitations: string[]
}

export type Preflight = {
  preflight_id: string
  review_id: string
  token_address: string
  horizon: '24h' | '7d'
  status: 'pending' | 'running' | 'complete' | 'failed'
  requests_attempted: number
  credits_used: number
  error_code: string | null
  current_context: null | {
    observed_at: string
    timeframe: '1d'
    coverage: 'observed' | 'unavailable'
    smart_trader_net_flow_usd: string | null
    smart_trader_avg_flow_usd: string | null
    smart_trader_wallet_count: number | null
    warnings: string[]
    freshness: 'fresh' | 'stale'
    freshness_basis: 'entryglass_retrieval_time'
  }
  comparison: null | {
    pattern: string
    rule_version: string
    comparable: boolean
    matching_precedent_count: number
    matching_precedents: PrecedentObservation[]
    outcome_counts: OutcomeCounts
    missing_features: string[]
    differences: string[]
    limitations: string[]
    recommendation: null
    risk_score: null
  }
  evidence: null | {
    source: 'Nansen'
    endpoint: string
    timeframe: '1d'
    requested_from_utc: string
    requested_to_utc: string
    retrieved_at: string
    request_id: string | null
    warnings: string[]
    quoted_credits: number | null
    used_credits: number | null
    attempt_count: number
  }
}

function isApiHealth(value: unknown): value is ApiHealth {
  if (typeof value !== 'object' || value === null) return false
  const item = value as Record<string, unknown>
  return (
    item.status === 'ok' &&
    typeof item.service === 'string' &&
    typeof item.version === 'string' &&
    item.stage === 'preflight' &&
    item.nansen_integration === 'private_review_and_preflight'
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

export function getPrecedents(
  reviewId: string,
  horizon: '24h' | '7d' = '7d',
): Promise<PrecedentReport> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/precedents?horizon=${horizon}`)
}

export function createPreflight(
  reviewId: string,
  tokenAddress: string,
  horizon: '24h' | '7d',
): Promise<Preflight> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/preflights`, {
    method: 'POST',
    body: JSON.stringify({ token_address: tokenAddress, horizon }),
  })
}

export function getPreflight(reviewId: string, preflightId: string): Promise<Preflight> {
  return fetchJson(`/api/v1/reviews/${encodeURIComponent(reviewId)}/preflights/${encodeURIComponent(preflightId)}`)
}
