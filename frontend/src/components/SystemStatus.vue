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
  <section class="status-panel status-panel--compact" aria-labelledby="system-title">
    <div class="section-topline">
      <p class="eyebrow">Local environment</p>
      <span class="label">v0.1.0</span>
    </div>
    <h2 id="system-title">Local review service</h2>
    <p class="muted">The health check spends no provider credits.</p>
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
    <p class="panel-note">Live review and current comparison require a server-side Nansen key. It is never sent to this browser.</p>
  </section>
</template>
