<script setup lang="ts">
import SystemStatus from './components/SystemStatus.vue'

const plannedSteps = [
  { number: '01', title: 'Review an entry', detail: 'Import a public wallet and normalize its DEX entries.' },
  { number: '02', title: 'Replay the context', detail: 'Separate the evidence before a trade from the outcome after it.' },
  { number: '03', title: 'Recognize a repeat', detail: 'Compare a new token with clearly explained historical precedents.' },
]
</script>

<template>
  <div class="app-shell">
    <header class="site-header">
      <div class="brand" aria-label="Entryglass">
        <span class="brand-mark" aria-hidden="true">e.</span>
        <span>entryglass</span>
      </div>
      <span class="stage-badge">Initial scaffold</span>
    </header>

    <main>
      <section class="hero" aria-labelledby="hero-title">
        <div class="hero-copy">
          <p class="eyebrow">Historical trade context</p>
          <h1 id="hero-title">Look back.<br /><span>Enter with context.</span></h1>
          <p class="intro">Understand what surrounded your past entries before repeating the same decisions.</p>
          <p class="scope-note">The product is not implemented yet. This repository contains its foundation and an implementation roadmap.</p>
        </div>
        <SystemStatus />
      </section>

      <section class="planned-section" aria-labelledby="journey-title">
        <div class="section-topline">
          <h2 id="journey-title">The experience we are building</h2>
          <span class="label">Planned, not available</span>
        </div>
        <div class="journey-grid">
          <article v-for="step in plannedSteps" :key="step.number" class="journey-card">
            <span class="step-number">{{ step.number }}</span>
            <h3>{{ step.title }}</h3>
            <p class="muted">{{ step.detail }}</p>
          </article>
        </div>
      </section>

      <aside class="principle">
        <strong>Evidence before labels.</strong>
        <p>Token outflows are not automatically sales. A later price decline is not automatically your realized loss.</p>
      </aside>
    </main>

    <footer class="site-footer">
      <span>Entryglass / Development workspace</span>
      <span>Research context, not trade execution.</span>
    </footer>
  </div>
</template>
