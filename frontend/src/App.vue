<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import SystemStatus from './components/SystemStatus.vue'
import {
  cancelReview,
  createPreflight,
  createReview,
  getEvidence,
  getPrecedents,
  getPreflight,
  getReplay,
  getReview,
  listReviewEntries,
  revealOutcomes,
} from './lib/api'
import type {
  EntrySummary,
  Evidence,
  Outcome,
  PrecedentReport,
  Preflight,
  ReplayEntry,
  ReviewJob,
} from './lib/api'

const today = new Date()
const defaultStart = new Date(today)
defaultStart.setUTCDate(defaultStart.getUTCDate() - 89)

const wallet = ref('')
const fromDate = ref(defaultStart.toISOString().slice(0, 10))
const toDate = ref(today.toISOString().slice(0, 10))
const maxEntries = ref(5)
const job = ref<ReviewJob | null>(null)
const entries = ref<EntrySummary[]>([])
const replay = ref<ReplayEntry | null>(null)
const outcomes = ref<Outcome[] | null>(null)
const evidence = ref<Evidence[]>([])
const selectedId = ref<string | null>(null)
const busy = ref(false)
const detailBusy = ref(false)
const revealBusy = ref(false)
const evidenceOpen = ref(false)
const precedents = ref<PrecedentReport | null>(null)
const precedentBusy = ref(false)
const precedentHorizon = ref<'24h' | '7d'>('7d')
const candidateToken = ref('')
const preflight = ref<Preflight | null>(null)
const preflightBusy = ref(false)
const error = ref<string | null>(null)
const replayHeading = ref<HTMLElement | null>(null)
const evidenceButton = ref<HTMLButtonElement | null>(null)
const drawerClose = ref<HTMLButtonElement | null>(null)
let pollTimer: number | undefined
let preflightTimer: number | undefined

const active = computed(() => job.value?.status === 'pending' || job.value?.status === 'running')
const terminal = computed(() => job.value && !active.value)
const progress = computed(() => {
  if (!job.value?.entries_total) return 0
  return Math.round((job.value.entries_processed / job.value.entries_total) * 100)
})

function safeMessage(cause: unknown): string {
  return cause instanceof Error ? cause.message : 'The review could not be loaded.'
}

async function startReview(): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = null
  entries.value = []
  replay.value = null
  outcomes.value = null
  selectedId.value = null
  evidenceOpen.value = false
  precedents.value = null
  preflight.value = null
  candidateToken.value = ''
  try {
    job.value = await createReview({
      wallet_address: wallet.value.trim(),
      from_utc: `${fromDate.value}T00:00:00Z`,
      to_utc: `${toDate.value}T23:59:59Z`,
      max_entries: maxEntries.value,
    })
    schedulePoll(250)
  } catch (cause) {
    error.value = safeMessage(cause)
  } finally {
    busy.value = false
  }
}

function schedulePoll(delay = 1500): void {
  if (pollTimer) window.clearTimeout(pollTimer)
  pollTimer = window.setTimeout(() => { void poll() }, delay)
}

async function poll(): Promise<void> {
  if (!job.value) return
  try {
    job.value = await getReview(job.value.review_id)
    if (active.value) schedulePoll()
    else await loadEntries()
  } catch (cause) {
    error.value = safeMessage(cause)
  }
}

async function loadEntries(): Promise<void> {
  if (!job.value) return
  entries.value = await listReviewEntries(job.value.review_id)
  if (entries.value.length && !selectedId.value) await selectEntry(entries.value[0]!)
}

async function selectEntry(entry: EntrySummary): Promise<void> {
  if (!job.value || detailBusy.value) return
  detailBusy.value = true
  error.value = null
  selectedId.value = entry.entry_id
  outcomes.value = null
  evidenceOpen.value = false
  try {
    replay.value = await getReplay(job.value.review_id, entry.entry_id)
    await nextTick()
    replayHeading.value?.focus()
  } catch (cause) {
    error.value = safeMessage(cause)
  } finally {
    detailBusy.value = false
  }
}

async function reveal(): Promise<void> {
  if (!job.value || !selectedId.value || revealBusy.value) return
  revealBusy.value = true
  try {
    outcomes.value = await revealOutcomes(job.value.review_id, selectedId.value)
  } catch (cause) {
    error.value = safeMessage(cause)
  } finally {
    revealBusy.value = false
  }
}

async function openEvidence(): Promise<void> {
  if (!job.value || !selectedId.value) return
  try {
    evidence.value = await getEvidence(job.value.review_id, selectedId.value)
    evidenceOpen.value = true
    await nextTick()
    drawerClose.value?.focus()
  } catch (cause) {
    error.value = safeMessage(cause)
  }
}

async function closeEvidence(): Promise<void> {
  evidenceOpen.value = false
  await nextTick()
  evidenceButton.value?.focus()
}

async function requestCancel(): Promise<void> {
  if (!job.value) return
  try {
    job.value = await cancelReview(job.value.review_id)
  } catch (cause) {
    error.value = safeMessage(cause)
  }
}

async function explorePrecedents(): Promise<void> {
  if (!job.value || precedentBusy.value) return
  precedentBusy.value = true
  error.value = null
  try {
    precedents.value = await getPrecedents(job.value.review_id, precedentHorizon.value)
    preflight.value = null
  } catch (cause) {
    error.value = safeMessage(cause)
  } finally {
    precedentBusy.value = false
  }
}

async function runPreflight(): Promise<void> {
  if (!job.value || !precedents.value || preflightBusy.value) return
  preflightBusy.value = true
  error.value = null
  try {
    preflight.value = await createPreflight(
      job.value.review_id,
      candidateToken.value.trim(),
      precedentHorizon.value,
    )
    schedulePreflightPoll(250)
  } catch (cause) {
    error.value = safeMessage(cause)
    preflightBusy.value = false
  }
}

function schedulePreflightPoll(delay = 1200): void {
  if (preflightTimer) window.clearTimeout(preflightTimer)
  preflightTimer = window.setTimeout(() => { void pollPreflight() }, delay)
}

async function pollPreflight(): Promise<void> {
  if (!job.value || !preflight.value) return
  try {
    preflight.value = await getPreflight(job.value.review_id, preflight.value.preflight_id)
    if (preflight.value.status === 'pending' || preflight.value.status === 'running') {
      schedulePreflightPoll()
    } else {
      preflightBusy.value = false
    }
  } catch (cause) {
    error.value = safeMessage(cause)
    preflightBusy.value = false
  }
}

function compact(value: string): string {
  return value.length > 16 ? `${value.slice(0, 7)}…${value.slice(-5)}` : value
}

function money(value: string | null): string {
  if (value === null) return 'Unavailable'
  return new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 2 }).format(Number(value))
}

function dateTime(value: string): string {
  return new Intl.DateTimeFormat('en-GB', { dateStyle: 'medium', timeStyle: 'short', timeZone: 'UTC' }).format(new Date(value)) + ' UTC'
}

function stageLabel(value: ReviewJob['stage']): string {
  return {
    queued: 'Queued locally',
    importing_entries: 'Finding wallet entries',
    enriching_evidence: 'Reconstructing historical evidence',
    complete: 'Review ready',
    stopped: 'Review stopped',
  }[value]
}

function stateLabel(value: string): string {
  return value.replaceAll('_', ' ').replace(/^./, (character) => character.toUpperCase())
}

function patternLabel(value: string): string {
  return {
    smart_trader_net_inflow: 'Net inflow',
    smart_trader_net_outflow: 'Net outflow',
    smart_trader_no_observed_flow: 'No observed flow',
    smart_trader_active_flat: 'Active, net flat',
    unavailable: 'Unavailable',
  }[value] ?? stateLabel(value)
}

onUnmounted(() => {
  if (pollTimer) window.clearTimeout(pollTimer)
  if (preflightTimer) window.clearTimeout(preflightTimer)
})
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <a class="brand" href="#main" aria-label="Entryglass home">
        <span class="brand-mark" aria-hidden="true">e.</span>
        <span>entryglass</span>
      </a>
      <span class="stage-badge">Private local review</span>
    </header>

    <main id="main">
      <section class="intro-grid" aria-labelledby="page-title">
        <div>
          <p class="eyebrow">Historical entry replay</p>
          <h1 id="page-title">See what came <span>before.</span></h1>
          <p class="intro">Review a public Solana wallet one entry at a time. Later price movement stays hidden until you choose to reveal it.</p>
        </div>
        <SystemStatus />
      </section>

      <section class="review-form-panel" aria-labelledby="review-title">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">01 / Scope</p>
            <h2 id="review-title">Start a private review</h2>
          </div>
          <p class="scope-summary">Solana · up to {{ maxEntries }} entries · 90 days maximum</p>
        </div>
        <form class="review-form" @submit.prevent="startReview">
          <label class="wallet-field">
            <span>Public wallet address</span>
            <input v-model="wallet" name="wallet" required minlength="32" maxlength="44" autocomplete="off" placeholder="Paste a Solana address" />
          </label>
          <label>
            <span>From</span>
            <input v-model="fromDate" name="from" required type="date" />
          </label>
          <label>
            <span>To</span>
            <input v-model="toDate" name="to" required type="date" />
          </label>
          <label>
            <span>Entry limit</span>
            <select v-model="maxEntries" name="limit">
              <option :value="3">3</option>
              <option :value="5">5</option>
              <option :value="10">10</option>
            </select>
          </label>
          <button class="button form-submit" type="submit" :disabled="busy || active">
            {{ busy ? 'Starting…' : active ? 'Review running…' : 'Review wallet' }}
          </button>
        </form>
        <p class="form-note">Visible ceiling: {{ maxEntries }} entries. The server also enforces request and credit budgets; partial work remains inspectable.</p>
      </section>

      <p v-if="error" class="alert alert--error" role="alert">{{ error }}</p>

      <section v-if="job" class="progress-panel" aria-labelledby="progress-title" aria-live="polite">
        <div class="progress-copy">
          <div>
            <p class="eyebrow">02 / Progress</p>
            <h2 id="progress-title">{{ stageLabel(job.stage) }}</h2>
          </div>
          <span class="status-pill" :class="`status-pill--${job.status}`">{{ stateLabel(job.status) }}</span>
        </div>
        <div class="progress-track" role="progressbar" :aria-valuenow="progress" aria-valuemin="0" aria-valuemax="100">
          <span :style="{ width: `${progress}%` }"></span>
        </div>
        <div class="progress-meta">
          <span>{{ job.entries_processed }} / {{ job.entries_total || '—' }} entries enriched</span>
          <span>{{ job.requests_attempted }} requests · {{ job.credits_used }} credits used</span>
          <button v-if="active" class="text-button" type="button" @click="requestCancel">Cancel review</button>
        </div>
        <p v-if="job.status === 'partial'" class="alert alert--warning">This review is partial. The available entries and evidence are shown; missing work was not replaced with zeroes.</p>
        <p v-else-if="job.status === 'failed'" class="alert alert--error">The provider could not complete this review ({{ job.error_code || 'unknown error' }}). No instant result was fabricated.</p>
        <p v-else-if="job.status === 'cancelled'" class="alert alert--warning">The review was cancelled. Any completed entry remains available below.</p>
      </section>

      <section v-if="terminal && entries.length === 0" class="empty-state" aria-live="polite">
        <p class="eyebrow">No reviewable entries</p>
        <h2>No qualifying DEX entries were found in this scope.</h2>
        <p>This is an empty result, not proof that the wallet had no other activity. Try another declared window.</p>
      </section>

      <section v-if="entries.length" class="workspace" aria-label="Review workspace">
        <aside class="entry-list" aria-labelledby="entries-title">
          <p class="eyebrow">03 / Entries</p>
          <h2 id="entries-title">Choose an entry</h2>
          <div class="entry-buttons">
            <button
              v-for="(entry, index) in entries"
              :key="entry.entry_id"
              type="button"
              class="entry-button"
              :class="{ 'entry-button--selected': selectedId === entry.entry_id }"
              :aria-current="selectedId === entry.entry_id ? 'true' : undefined"
              @click="selectEntry(entry)"
            >
              <span class="entry-index">{{ String(index + 1).padStart(2, '0') }}</span>
              <span><strong>{{ compact(entry.token_address) }}</strong><small>{{ dateTime(entry.occurred_at) }}</small></span>
              <span class="coverage-dot" :class="`coverage-dot--${entry.context_coverage}`" :title="`Context: ${entry.context_coverage}`"></span>
            </button>
          </div>
        </aside>

        <article v-if="replay" class="replay-card" :aria-busy="detailBusy">
          <div class="replay-topline">
            <div>
              <p class="eyebrow">Replay / before the entry</p>
              <h2 ref="replayHeading" tabindex="-1">{{ compact(replay.entry.token_address) }}</h2>
            </div>
            <button ref="evidenceButton" class="secondary-button" type="button" @click="openEvidence">Inspect evidence</button>
          </div>

          <dl class="entry-facts">
            <div><dt>Entry time</dt><dd>{{ dateTime(replay.entry.occurred_at) }}</dd></div>
            <div><dt>Entry value</dt><dd>{{ money(replay.entry.trade_value_usd) }}</dd></div>
            <div><dt>Reference entry price</dt><dd>{{ money(replay.entry_price_usd) }}</dd></div>
          </dl>

          <section class="context-block" aria-labelledby="context-title">
            <div class="context-heading">
              <div>
                <p class="eyebrow">24-hour pre-entry window</p>
                <h3 id="context-title">Historical Smart Trader flow</h3>
              </div>
              <span class="coverage-badge">{{ replay.context?.coverage || 'pending' }}</span>
            </div>
            <template v-if="replay.context">
              <p class="period">{{ dateTime(replay.context.window_from_utc) }} → {{ dateTime(replay.context.window_to_utc) }}</p>
              <div class="metric-grid">
                <div><span>Net flow</span><strong>{{ money(replay.context.smart_trader_net_flow_usd) }}</strong></div>
                <div><span>Average flow</span><strong>{{ money(replay.context.smart_trader_avg_flow_usd) }}</strong></div>
                <div><span>Observed wallets</span><strong>{{ replay.context.smart_trader_wallet_count ?? 'Unavailable' }}</strong></div>
              </div>
              <p v-if="replay.context.coverage === 'unavailable'" class="alert alert--warning">Historical coverage was unavailable. Entryglass does not turn that into “no signal.”</p>
            </template>
            <p v-else class="muted">Context has not been completed for this entry.</p>
          </section>

          <section class="outcome-block" aria-labelledby="outcome-title">
            <div>
              <p class="eyebrow">After the entry</p>
              <h3 id="outcome-title">Later reference prices</h3>
              <p class="muted">Kept out of the historical context. These are price observations, not realized PnL.</p>
            </div>
            <button v-if="!outcomes" class="button reveal-button" type="button" :disabled="revealBusy" @click="reveal">
              {{ revealBusy ? 'Revealing…' : 'Reveal what happened next' }}
            </button>
            <div v-else class="outcome-grid" aria-live="polite">
              <article v-for="outcome in outcomes" :key="outcome.horizon" class="outcome-card">
                <span>{{ outcome.horizon }}</span>
                <strong v-if="outcome.state === 'observed'">{{ Number(outcome.price_change_pct).toFixed(1) }}%</strong>
                <strong v-else>{{ stateLabel(outcome.state) }}</strong>
                <small>{{ outcome.observed_price_usd ? money(outcome.observed_price_usd) : 'No completed observation' }}</small>
              </article>
            </div>
          </section>
        </article>
      </section>

      <section v-if="terminal && entries.length" class="precedent-panel" aria-labelledby="precedent-title">
        <div class="panel-heading precedent-heading">
          <div>
            <p class="eyebrow">04 / Personal precedents</p>
            <h2 id="precedent-title">Explore recurring context</h2>
          </div>
          <p class="scope-summary">Same wallet · declared rules · descriptive only</p>
        </div>
        <p class="section-intro">Group the reviewed entries by their historical Smart Trader flow, then inspect the later reference-price outcomes. This reveals aggregated outcomes only when you ask for them.</p>
        <div class="precedent-controls">
          <label>
            <span>Outcome horizon</span>
            <select v-model="precedentHorizon" name="precedent-horizon">
              <option value="24h">24 hours</option>
              <option value="7d">7 days</option>
            </select>
          </label>
          <button class="button" type="button" :disabled="precedentBusy" @click="explorePrecedents">
            {{ precedentBusy ? 'Building precedents…' : precedents ? 'Refresh personal precedents' : 'Explore personal precedents' }}
          </button>
        </div>

        <div v-if="precedents" class="precedent-results" aria-live="polite">
          <div class="baseline-card">
            <div>
              <span class="result-label">Same-wallet baseline / {{ precedents.horizon }}</span>
              <strong>{{ entries.length }} reviewed entries</strong>
              <small>{{ precedents.context_observed }} with observed context · {{ precedents.context_unavailable }} unavailable</small>
            </div>
            <dl class="count-row">
              <div><dt>Gain</dt><dd>{{ precedents.baseline.gain }}</dd></div>
              <div><dt>Flat</dt><dd>{{ precedents.baseline.flat }}</dd></div>
              <div><dt>Decline</dt><dd>{{ precedents.baseline.decline }}</dd></div>
              <div><dt>Unavailable</dt><dd>{{ precedents.baseline.unavailable }}</dd></div>
            </dl>
          </div>

          <div class="pattern-grid">
            <article v-for="pattern in precedents.patterns" :key="pattern.pattern" class="pattern-card">
              <div class="pattern-title">
                <div><span class="result-label">Declared rule</span><h3>{{ patternLabel(pattern.pattern) }}</h3></div>
                <strong>{{ pattern.sample_count }}</strong>
              </div>
              <p>{{ pattern.description }}</p>
              <dl class="count-row count-row--compact">
                <div><dt>Gain</dt><dd>{{ pattern.outcome_counts.gain }}</dd></div>
                <div><dt>Flat</dt><dd>{{ pattern.outcome_counts.flat }}</dd></div>
                <div><dt>Decline</dt><dd>{{ pattern.outcome_counts.decline }}</dd></div>
                <div><dt>N/A</dt><dd>{{ pattern.outcome_counts.unavailable }}</dd></div>
              </dl>
              <ul v-if="pattern.observations.length" class="observation-list">
                <li v-for="item in pattern.observations" :key="item.entry_id">
                  <span>{{ compact(item.token_address) }}</span>
                  <strong>{{ stateLabel(item.outcome_band) }}<template v-if="item.price_change_pct !== null"> · {{ Number(item.price_change_pct).toFixed(1) }}%</template></strong>
                </li>
              </ul>
              <p v-else class="empty-pattern">No reviewed entry matched this rule.</p>
            </article>
          </div>

          <div class="method-note">
            <strong>Rule {{ precedents.rule_version }}</strong>
            <p>This view is descriptive. It does not estimate probability, confidence, realized PnL, or what you should do next.</p>
            <p>Outcome display bands: gain above +2%, flat from -2% through +2%, and decline below -2%.</p>
            <ul><li v-for="limitation in precedents.limitations" :key="limitation">{{ limitation }}</li></ul>
          </div>
        </div>
      </section>

      <section v-if="precedents && (job?.status === 'complete' || job?.status === 'partial')" class="preflight-panel" aria-labelledby="preflight-title">
        <div class="panel-heading">
          <div>
            <p class="eyebrow">05 / Current comparison</p>
            <h2 id="preflight-title">Compare a token before acting</h2>
          </div>
          <p class="scope-summary">One bounded current query · up to 2 attempts · server-side key</p>
        </div>
        <p class="section-intro">Fetch the token's current one-day Smart Trader flow and compare only the declared features with your personal precedents above.</p>
        <form class="preflight-form" @submit.prevent="runPreflight">
          <label>
            <span>Solana token address</span>
            <input v-model="candidateToken" name="candidate-token" required minlength="32" maxlength="44" autocomplete="off" placeholder="Paste a token address" />
          </label>
          <button class="button" type="submit" :disabled="preflightBusy">
            {{ preflightBusy ? 'Comparing…' : 'Run current comparison' }}
          </button>
        </form>

        <div v-if="preflight && (preflight.status === 'pending' || preflight.status === 'running')" class="preflight-wait" aria-live="polite">
          <span class="status-dot"></span>
          <div><strong>Fetching current context…</strong><p>The historical precedents stay fixed while the current observation is retrieved.</p></div>
        </div>
        <p v-else-if="preflight?.status === 'failed'" class="alert alert--error" role="alert">The current comparison could not be completed ({{ preflight.error_code || 'provider error' }}). No result was inferred.</p>

        <div v-else-if="preflight?.status === 'complete' && preflight.current_context && preflight.comparison" class="comparison-results" aria-live="polite">
          <article class="current-card">
            <div class="pattern-title">
              <div><span class="result-label">Current rolling 1 day</span><h3>{{ patternLabel(preflight.comparison.pattern) }}</h3></div>
              <span class="freshness" :class="`freshness--${preflight.current_context.freshness}`">{{ preflight.current_context.freshness === 'fresh' ? 'recent retrieval' : 'stale retrieval' }}</span>
            </div>
            <p class="period">Retrieved {{ dateTime(preflight.current_context.observed_at) }} · {{ preflight.requests_attempted }} {{ preflight.requests_attempted === 1 ? 'attempt' : 'attempts' }} · {{ preflight.credits_used }} credits · freshness is based on local retrieval time</p>
            <div class="metric-grid">
              <div><span>Net flow</span><strong>{{ money(preflight.current_context.smart_trader_net_flow_usd) }}</strong></div>
              <div><span>Average flow</span><strong>{{ money(preflight.current_context.smart_trader_avg_flow_usd) }}</strong></div>
              <div><span>Observed wallets</span><strong>{{ preflight.current_context.smart_trader_wallet_count ?? 'Unavailable' }}</strong></div>
            </div>
          </article>

          <article class="match-card">
            <span class="result-label">Matching personal precedents / {{ preflight.horizon }}</span>
            <h3>{{ preflight.comparison.matching_precedent_count }} matching {{ preflight.comparison.matching_precedent_count === 1 ? 'entry' : 'entries' }}</h3>
            <dl class="count-row">
              <div><dt>Gain</dt><dd>{{ preflight.comparison.outcome_counts.gain }}</dd></div>
              <div><dt>Flat</dt><dd>{{ preflight.comparison.outcome_counts.flat }}</dd></div>
              <div><dt>Decline</dt><dd>{{ preflight.comparison.outcome_counts.decline }}</dd></div>
              <div><dt>Unavailable</dt><dd>{{ preflight.comparison.outcome_counts.unavailable }}</dd></div>
            </dl>
            <ul v-if="preflight.comparison.matching_precedents.length" class="observation-list">
              <li v-for="item in preflight.comparison.matching_precedents" :key="item.entry_id">
                <span>{{ compact(item.token_address) }} · {{ dateTime(item.occurred_at) }}</span>
                <strong>{{ stateLabel(item.outcome_band) }}<template v-if="item.price_change_pct !== null"> · {{ Number(item.price_change_pct).toFixed(1) }}%</template></strong>
              </li>
            </ul>
            <p v-else class="empty-pattern">No historical entry in this review matched the current rule.</p>
          </article>

          <div class="comparison-notes">
            <p v-if="!preflight.comparison.comparable" class="alert alert--warning">Current context is unavailable, so Entryglass keeps this comparison unavailable instead of treating it as no activity.</p>
            <template v-if="preflight.comparison.missing_features.length">
              <strong>Missing current features</strong>
              <ul><li v-for="item in preflight.comparison.missing_features" :key="item">{{ stateLabel(item) }}</li></ul>
            </template>
            <template v-if="preflight.comparison.differences.length">
              <strong>Differences to keep in view</strong>
              <ul><li v-for="item in preflight.comparison.differences" :key="item">{{ item }}</li></ul>
            </template>
            <strong>Comparison limits</strong>
            <ul><li v-for="item in preflight.comparison.limitations" :key="item">{{ item }}</li></ul>
            <p class="non-verdict">No recommendation or risk score is produced.</p>
          </div>
        </div>
      </section>

      <aside v-if="evidenceOpen" class="drawer" role="dialog" aria-modal="true" aria-labelledby="evidence-title" @keydown.esc="closeEvidence">
        <div class="drawer-header">
          <div><p class="eyebrow">Evidence trail</p><h2 id="evidence-title">How this replay was built</h2></div>
          <button ref="drawerClose" class="icon-button" type="button" aria-label="Close evidence" @click="closeEvidence">×</button>
        </div>
        <article v-for="item in evidence" :key="item.request_fingerprint" class="evidence-card">
          <div class="evidence-title"><strong>{{ stateLabel(item.kind) }}</strong><span>{{ item.coverage }}</span></div>
          <dl>
            <div><dt>Source</dt><dd>{{ item.source }}</dd></div>
            <div><dt>Period</dt><dd>{{ dateTime(item.requested_from_utc) }}<br />{{ dateTime(item.requested_to_utc) }}</dd></div>
            <div><dt>Retrieved</dt><dd>{{ dateTime(item.retrieved_at) }}</dd></div>
            <div><dt>Endpoint</dt><dd><code>{{ item.endpoint }}</code></dd></div>
            <div><dt>Request ID</dt><dd>{{ item.request_id || 'Unavailable' }}</dd></div>
            <div><dt>Rule version</dt><dd>{{ item.rule_version }}</dd></div>
          </dl>
          <p v-for="warning in item.warnings" :key="warning" class="alert alert--warning">{{ warning }}</p>
        </article>
        <p v-if="evidence.length === 0" class="muted">No evidence record is available for this entry.</p>
      </aside>
      <button v-if="evidenceOpen" class="drawer-scrim" type="button" aria-label="Close evidence" @click="closeEvidence"></button>

      <aside class="principle">
        <strong>Evidence before labels.</strong>
        <p>Token outflows are not automatically sales. A later price decline is not automatically your realized loss.</p>
      </aside>
    </main>

    <footer class="site-footer"><span>Entryglass / Local research workspace</span><span>Context, not trade execution.</span></footer>
  </div>
</template>
