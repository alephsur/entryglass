import assert from 'node:assert/strict'
import { afterEach, mock, test } from 'node:test'
import { getApiHealth } from '../src/lib/api.ts'

const health = {
  status: 'ok',
  service: 'Entryglass API',
  version: '0.1.0',
  stage: 'scaffold',
  nansen_integration: 'not_implemented',
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
