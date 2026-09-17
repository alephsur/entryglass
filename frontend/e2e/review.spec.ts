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
    stage: 'review', nansen_integration: 'private_review',
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
