import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { createReview, getApiHealth, revealOutcomes } from '../src/lib/api.ts'

const health = {
  status: 'ok',
  service: 'Entryglass API',
  version: '0.1.0',
  stage: 'review',
  nansen_integration: 'private_review',
}

afterEach(() => { mock.restoreAll() })

test('loads the actual health contract through the local proxy path', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/health')
    assert.equal(options.headers.Accept, 'application/json')
    assert.ok(options.signal instanceof AbortSignal)
    return Response.json(health)
  })
  assert.deepEqual(await getApiHealth(), health)
})

test('does not turn HTTP errors into healthy results', async () => {
  mock.method(globalThis, 'fetch', async () => new Response('', { status: 503 }))
  await assert.rejects(getApiHealth(), /HTTP 503/)
})

test('rejects an incompatible or incomplete response', async () => {
  mock.method(globalThis, 'fetch', async () => Response.json({ status: 'ok' }))
  await assert.rejects(getApiHealth(), /unexpected health response/)
})

test('rejects a null response', async () => {
  mock.method(globalThis, 'fetch', async () => Response.json(null))
  await assert.rejects(getApiHealth(), /unexpected health response/)
})

test('propagates network failures instead of showing cached success', async () => {
  mock.method(globalThis, 'fetch', async () => { throw new TypeError('Network unavailable') })
  await assert.rejects(getApiHealth(), /Network unavailable/)
})

test('forwards a caller cancellation signal', async () => {
  const controller = new AbortController()
  mock.method(globalThis, 'fetch', async (_url, options) => {
    assert.equal(options.signal, controller.signal)
    return Response.json(health)
  })
  assert.deepEqual(await getApiHealth(controller.signal), health)
})

test('starts a review with an explicit visible scope', async () => {
  const input = {
    wallet_address: '11111111111111111111111111111111',
    from_utc: '2026-06-01T00:00:00Z',
    to_utc: '2026-06-30T23:59:59Z',
    max_entries: 5,
  }
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/reviews')
    assert.equal(options.method, 'POST')
    assert.deepEqual(JSON.parse(options.body), input)
    return Response.json({ review_id: 'review-1', status: 'pending' })
  })
  const response = await createReview(input)
  assert.equal(response.review_id, 'review-1')
})

test('later outcomes use a separate explicit reveal endpoint', async () => {
  mock.method(globalThis, 'fetch', async (url, options) => {
    assert.equal(url, '/api/v1/reviews/review-1/entries/entry-1/outcomes')
    assert.equal(options.method, undefined)
    return Response.json([{ horizon: '24h', state: 'pending' }])
  })
  const response = await revealOutcomes('review-1', 'entry-1')
  assert.equal(response[0].state, 'pending')
})

test('surfaces safe API detail instead of a fabricated result', async () => {
  mock.method(globalThis, 'fetch', async () => Response.json(
    { detail: { code: 'provider_not_configured', message: 'Configure the provider.' } },
    { status: 503 },
  ))
  await assert.rejects(createReview({
    wallet_address: '11111111111111111111111111111111',
    from_utc: '2026-06-01T00:00:00Z',
    to_utc: '2026-06-30T23:59:59Z',
    max_entries: 5,
  }), /Configure the provider/)
})
