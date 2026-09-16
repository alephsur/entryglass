<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { getApiHealth } from '../lib/api'
import type { ApiHealth } from '../lib/api'

const health = ref<ApiHealth | null>(null)
const busy = ref(false)
const error = ref<string | null>(null)

async function refresh(): Promise<void> {
  if (busy.value) return
  busy.value = true
  error.value = null
  health.value = null
  try {
    health.value = await getApiHealth()
  } catch (cause) {
    error.value = cause instanceof Error ? cause.message : 'API is unavailable.'
  } finally {
    busy.value = false
  }
}

onMounted(() => { void refresh() })
</script>

<template>
  <section class="status-panel" aria-labelledby="system-title">
    <div class="section-topline">
      <p class="eyebrow">Local environment</p>
      <span class="label">v0.1.0</span>
    </div>
    <h2 id="system-title">A foundation, not a verdict.</h2>
    <p class="muted">This screen checks the local API. It does not query Nansen or analyze a wallet.</p>
    <div class="system-result" role="status" aria-live="polite" :aria-busy="busy">
      <template v-if="busy">Checking the local API...</template>
      <template v-else-if="health">
        <span class="status-dot" aria-hidden="true"></span>
        {{ health.service }} is online <span class="muted">/ {{ health.version }}</span>
      </template>
      <template v-else>
        <span class="status-dot status-dot--offline" aria-hidden="true"></span>
        API unavailable
      </template>
    </div>
    <p v-if="error" class="error-message">{{ error }} Start the backend and try again.</p>
    <button class="button" type="button" :disabled="busy" @click="refresh">
      {{ busy ? 'Checking...' : 'Check API connection' }}
    </button>
    <p class="panel-note">Data integration: not implemented. No API key required.</p>
  </section>
</template>
