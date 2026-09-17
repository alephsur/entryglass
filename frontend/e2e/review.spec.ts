import { expect, test } from '@playwright/test'

const wallet = '11111111111111111111111111111111'
const entryId = 'entry-1'

const job = {
  review_id: 'review-1',
  wallet_address: wallet,
  from_utc: '2026-06-01T00:00:00Z',
  to_utc: '2026-06-30T23:59:59Z',
  status: 'complete',
  stage: 'complete',
  entries_total: 1,
  entries_processed: 1,
  requests_attempted: 3,
  credits_used: 7,
  max_entries: 5,
  max_requests: 15,
  max_credits: 32,
  cancellation_requested: false,
  error_code: null,
}

const entry = {
  entry_id: entryId,
  occurred_at: '2026-06-15T12:00:00Z',
  token_address: 'EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v',
  quote_address: 'So11111111111111111111111111111111111111112',
  trade_value_usd: '42.00',
  context_coverage: 'observed',
  outcome_states: { '24h': 'observed', '7d': 'observed' },
}

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/health', route => route.fulfill({ json: {
    status: 'ok', service: 'Entryglass API', version: '0.1.0',
    stage: 'preflight', nansen_integration: 'private_review_and_preflight',
  } }))
})

test('reviews, replays, reveals, and inspects evidence', async ({ page }) => {
  await page.route('**/api/v1/reviews', route => route.fulfill({ status: 202, json: job }))
  await page.route('**/api/v1/reviews/review-1', route => route.fulfill({ json: job }))
  await page.route('**/api/v1/reviews/review-1/entries', route => route.fulfill({ json: [entry] }))
  await page.route(`**/api/v1/reviews/review-1/entries/${entryId}`, route => route.fulfill({ json: {
    entry,
    token_amount: '2',
    quote_amount: '1',
    entry_price_usd: '21',
    context: {
      coverage: 'observed',
      window_from_utc: '2026-06-14T11:59:59Z',
      window_to_utc: '2026-06-15T11:59:59Z',
      smart_trader_net_flow_usd: '-12.5',
      smart_trader_avg_flow_usd: null,
      smart_trader_wallet_count: 2,
      warnings: [],
    },
    outcome_values_hidden: true,
  } }))
  await page.route(`**/api/v1/reviews/review-1/entries/${entryId}/outcomes`, route => route.fulfill({ json: [{
    horizon: '24h', target_at: '2026-06-16T12:00:00Z', state: 'observed',
    observed_at: '2026-06-16T12:00:00Z', observed_price_usd: '18',
    price_change_pct: '-14.2857', interpretation: 'Reference price change, not realized PnL.',
  }] }))
  await page.route(`**/api/v1/reviews/review-1/entries/${entryId}/evidence`, route => route.fulfill({ json: [{
    kind: 'historical_context', source: 'Nansen', endpoint: '/historical-context',
    requested_from_utc: '2026-06-14T11:59:59Z', requested_to_utc: '2026-06-15T11:59:59Z',
    retrieved_at: '2026-09-17T12:00:00Z', request_id: 'request-1',
    request_fingerprint: 'a'.repeat(64), response_hash: 'b'.repeat(64), warnings: [],
    coverage: 'complete', quoted_credits: 5, used_credits: 5, attempt_count: 1,
    rule_version: 'entryglass-methodology-v1',
  }] }))
  await page.route('**/api/v1/reviews/review-1/precedents?horizon=7d', route => route.fulfill({ json: {
    review_id: 'review-1', horizon: '7d', rule_version: 'smart-trader-flow-v1',
    patterns: [
      {
        pattern: 'smart_trader_net_inflow', description: 'Observed Smart Trader net flow is above zero.',
        sample_count: 0, outcome_counts: { gain: 0, flat: 0, decline: 0, unavailable: 0 }, observations: [],
      },
      {
        pattern: 'smart_trader_net_outflow', description: 'Observed Smart Trader net flow is below zero.',
        sample_count: 1, outcome_counts: { gain: 0, flat: 0, decline: 1, unavailable: 0 },
        observations: [{
          entry_id: entryId, occurred_at: entry.occurred_at, token_address: entry.token_address,
          pattern: 'smart_trader_net_outflow', outcome_band: 'decline', price_change_pct: '-14.2857',
        }],
      },
      {
        pattern: 'smart_trader_no_observed_flow', description: 'No Smart Trader wallets or flow were observed.',
        sample_count: 0, outcome_counts: { gain: 0, flat: 0, decline: 0, unavailable: 0 }, observations: [],
      },
      {
        pattern: 'smart_trader_active_flat', description: 'Wallet activity was observed while net flow was zero.',
        sample_count: 0, outcome_counts: { gain: 0, flat: 0, decline: 0, unavailable: 0 }, observations: [],
      },
    ],
    baseline: { gain: 0, flat: 0, decline: 1, unavailable: 0 },
    context_observed: 1, context_unavailable: 0,
    evaluation_mode: 'descriptive_only', evaluation_status: 'not_run_no_predictive_claim',
    limitations: ['Patterns are descriptive personal precedents, not probabilities.'],
  } }))
  await page.route('**/api/v1/reviews/review-1/preflights', route => route.fulfill({ status: 202, json: {
    preflight_id: 'preflight-1', review_id: 'review-1', token_address: entry.token_address, horizon: '7d',
    status: 'pending', requests_attempted: 0, credits_used: 0, error_code: null,
    current_context: null, comparison: null, evidence: null,
  } }))
  await page.route('**/api/v1/reviews/review-1/preflights/preflight-1', route => route.fulfill({ json: {
    preflight_id: 'preflight-1', review_id: 'review-1', token_address: entry.token_address, horizon: '7d',
    status: 'complete', requests_attempted: 1, credits_used: 1, error_code: null,
    current_context: {
      observed_at: '2026-09-17T12:00:00Z', timeframe: '1d', coverage: 'observed',
      smart_trader_net_flow_usd: '-30', smart_trader_avg_flow_usd: '-15',
      smart_trader_wallet_count: 2, warnings: [], freshness: 'fresh',
      freshness_basis: 'entryglass_retrieval_time',
    },
    comparison: {
      pattern: 'smart_trader_net_outflow', rule_version: 'smart-trader-flow-v1', comparable: true,
      matching_precedent_count: 1,
      matching_precedents: [{
        entry_id: entryId, occurred_at: entry.occurred_at, token_address: entry.token_address,
        pattern: 'smart_trader_net_outflow', outcome_band: 'decline', price_change_pct: '-14.2857',
      }],
      outcome_counts: { gain: 0, flat: 0, decline: 1, unavailable: 0 },
      missing_features: [], differences: [],
      limitations: ["Current data uses Nansen's rolling 1d timeframe; history uses an explicit 24-hour UTC window."],
      recommendation: null, risk_score: null,
    },
    evidence: null,
  } }))

  await page.goto('/')
  await page.getByLabel('Public wallet address').fill(wallet)
  await page.getByRole('button', { name: 'Review wallet' }).click()

  await expect(page.getByRole('heading', { name: 'Historical Smart Trader flow' })).toBeVisible()
  await expect(page.getByText('-14.3%')).toHaveCount(0)
  await page.getByRole('button', { name: 'Reveal what happened next' }).click()
  await expect(page.getByText('-14.3%')).toBeVisible()
  await page.getByRole('button', { name: 'Inspect evidence' }).click()
  await expect(page.getByRole('dialog')).toContainText('entryglass-methodology-v1')
  await page.keyboard.press('Escape')
  await expect(page.getByRole('dialog')).toHaveCount(0)

  await page.getByRole('button', { name: 'Explore personal precedents' }).click()
  await expect(page.getByRole('heading', { name: 'Net outflow' })).toBeVisible()
  await expect(page.getByText('Patterns are descriptive personal precedents')).toBeVisible()

  await page.getByLabel('Solana token address').fill(entry.token_address)
  await page.getByRole('button', { name: 'Run current comparison' }).click()
  await expect(page.getByRole('heading', { name: '1 matching entry' })).toBeVisible()
  await expect(page.getByText('No recommendation or risk score is produced.')).toBeVisible()
})

test('shows provider setup failure without a fake review', async ({ page }) => {
  await page.route('**/api/v1/reviews', route => route.fulfill({
    status: 503,
    json: { detail: { code: 'provider_not_configured', message: 'Configure the server-side Nansen key to start a live review.' } },
  }))
  await page.goto('/')
  await page.getByLabel('Public wallet address').fill(wallet)
  await page.getByRole('button', { name: 'Review wallet' }).click()
  await expect(page.getByRole('alert')).toContainText('Configure the server-side Nansen key')
  await expect(page.getByText('Review ready')).toHaveCount(0)
})

test('distinguishes a completed empty scope', async ({ page }) => {
  await page.route('**/api/v1/reviews', route => route.fulfill({ status: 202, json: { ...job, entries_total: 0, entries_processed: 0 } }))
  await page.route('**/api/v1/reviews/review-1', route => route.fulfill({ json: { ...job, entries_total: 0, entries_processed: 0 } }))
  await page.route('**/api/v1/reviews/review-1/entries', route => route.fulfill({ json: [] }))
  await page.goto('/')
  await page.getByLabel('Public wallet address').fill(wallet)
  await page.getByRole('button', { name: 'Review wallet' }).click()
  await expect(page.getByRole('heading', { name: 'No qualifying DEX entries were found in this scope.' })).toBeVisible()
})
