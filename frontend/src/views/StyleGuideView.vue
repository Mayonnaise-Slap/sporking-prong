<script setup lang="ts">
const colorGroups = [
  {
    name: 'Surfaces',
    swatches: [
      { name: '--color-bg', hex: '#f4f5f7' },
      { name: '--color-surface', hex: '#ffffff' },
      { name: '--color-surface-sunken', hex: '#eceef0' },
      { name: '--color-border', hex: '#d8dce1' },
    ],
  },
  {
    name: 'Ink (header / footer)',
    swatches: [
      { name: '--color-ink', hex: '#16191d' },
      { name: '--color-ink-surface', hex: '#21252b' },
      { name: '--color-ink-border', hex: '#33383f' },
    ],
  },
  {
    name: 'Brand',
    swatches: [
      { name: '--color-primary', hex: '#1f5fa8' },
      { name: '--color-primary-hover', hex: '#184b87' },
      { name: '--color-primary-bg', hex: '#e8f1fb' },
    ],
  },
  {
    name: 'Status',
    swatches: [
      { name: '--color-success', hex: '#2f7a33' },
      { name: '--color-warning', hex: '#c07c10' },
      { name: '--color-danger', hex: '#a52a2a' },
      { name: '--color-neutral', hex: '#6b747e' },
    ],
  },
]

const criteria = [
  {
    title: 'Interfaces between components are defined (format, in/out, errors)',
    status: 'full',
    label: 'Fully met',
    points: 'min 0.5 · max 1 · lines 27–61',
    note: 'REST contracts are complete; the event contract leaves the payload unspecified.',
  },
  {
    title: 'C4 diagrams (context and container)',
    status: 'none',
    label: 'Not met',
    points: 'min 1 · max 1 · section 77',
    note: 'Diagrams skip C4 notation entirely — no actors, system boundary, or technology on the links.',
  },
  {
    title: 'Coupling analysis with reduction proposals',
    status: 'partial',
    label: 'Partially met',
    points: 'min 0 · max 0.5 · lines 73–75',
    note: 'Proposed, but without justifying the tradeoff.',
  },
  {
    title: 'Structure, formatting, and completeness of the document',
    status: 'unmarked',
    label: 'Not marked',
    points: 'min 0 · max 0.5 · whole submission',
    note: '',
  },
]

const statusBadge: Record<string, string> = {
  full: 'badge-success',
  partial: 'badge-warning',
  none: 'badge-danger',
  unmarked: 'badge-neutral',
}
</script>

<template>
  <section class="container guide">
    <header class="guide__header">
      <p class="card-label">Internal — not linked from the product</p>
      <h1 class="guide__title">Style guide</h1>
      <p class="text-muted">
        Hardcoded samples of the basic building blocks, for a design pass before
        we wire up real functionality.
      </p>
    </header>

    <section class="guide__section">
      <h2 class="guide__section-title">Colors</h2>
      <div class="color-groups">
        <div v-for="group in colorGroups" :key="group.name" class="color-group">
          <h3 class="color-group__title">{{ group.name }}</h3>
          <div class="swatch" v-for="swatch in group.swatches" :key="swatch.name">
            <span class="swatch__chip" :style="{ background: swatch.hex }" />
            <span class="swatch__name text-mono">{{ swatch.name }}</span>
            <span class="swatch__hex text-mono text-muted">{{ swatch.hex }}</span>
          </div>
        </div>
      </div>
    </section>

    <section class="guide__section">
      <h2 class="guide__section-title">Typography</h2>
      <div class="card card-pad type-scale">
        <p class="type-row" style="font-size: var(--text-3xl); font-weight: 700">Aa — 3xl / 700</p>
        <p class="type-row" style="font-size: var(--text-2xl); font-weight: 700">Aa — 2xl / 700</p>
        <p class="type-row" style="font-size: var(--text-xl); font-weight: 700">Aa — xl / 700</p>
        <p class="type-row" style="font-size: var(--text-lg)">Aa — lg / 400</p>
        <p class="type-row" style="font-size: var(--text-base)">Aa — base / 400 (body text)</p>
        <p class="type-row text-muted" style="font-size: var(--text-sm)">Aa — sm / 400, muted</p>
        <p class="type-row card-label">Aa — xs / 700, uppercase label</p>
        <p class="type-row text-mono" style="font-size: var(--text-sm)">1  const value = parseSubmission(text) — mono / sm, for line-numbered text</p>
      </div>
    </section>

    <section class="guide__section">
      <h2 class="guide__section-title">Buttons</h2>
      <div class="card card-pad button-row">
        <button class="btn btn-primary">Primary</button>
        <button class="btn btn-outline">Outline</button>
        <button class="btn btn-primary btn-sm">Primary sm</button>
        <button class="btn btn-outline btn-sm">Outline sm</button>
        <span class="button-row__dark">
          <button class="btn btn-ghost btn-sm">Ghost (on ink)</button>
        </span>
      </div>
    </section>

    <section class="guide__section">
      <h2 class="guide__section-title">Status badges</h2>
      <div class="card card-pad badge-row">
        <span class="badge badge-success"><span class="badge-dot" />Full / on time</span>
        <span class="badge badge-warning"><span class="badge-dot" />Partial / needs attention</span>
        <span class="badge badge-danger"><span class="badge-dot" />None / overdue</span>
        <span class="badge badge-neutral"><span class="badge-dot" />Unmarked / info</span>
      </div>
    </section>

    <section class="guide__section">
      <h2 class="guide__section-title">Cards</h2>
      <div class="card-samples">
        <!-- Submission metadata card -->
        <article class="card card-pad">
          <p class="card-label">Submission</p>
          <h3 class="sample-card__name">Dmitry Sokolov</h3>
          <p class="text-muted" style="font-size: var(--text-sm)">BIV-231 · attempt 1 of 3</p>
          <dl class="meta-grid">
            <div>
              <dt class="text-muted">File</dt>
              <dd class="text-mono">lab3_inventory.md · 78 lines</dd>
            </div>
            <div>
              <dt class="text-muted">Submitted</dt>
              <dd>Sep 30, 18:02 (MSK)</dd>
            </div>
            <div>
              <dt class="text-muted">Deadline</dt>
              <dd><span class="badge badge-success"><span class="badge-dot" />5h 57m to spare</span></dd>
            </div>
          </dl>
        </article>

        <!-- Rubric criterion card -->
        <article class="card card-pad">
          <p class="card-label">Rubric criterion</p>
          <div class="criterion" v-for="c in criteria" :key="c.title">
            <div class="criterion__head">
              <span :class="['badge', statusBadge[c.status]]"><span class="badge-dot" />{{ c.label }}</span>
              <span class="text-muted" style="font-size: var(--text-xs)">{{ c.points }}</span>
            </div>
            <p class="criterion__title">{{ c.title }}</p>
            <p v-if="c.note" class="criterion__note text-muted">{{ c.note }}</p>
          </div>
        </article>

        <!-- Line comment card -->
        <article class="card card-pad">
          <p class="card-label">Line comment</p>
          <div class="comment">
            <div class="comment__head">
              <span class="badge badge-success"><span class="badge-dot" />sent</span>
              <strong>M. Kovalev</strong>
              <span class="text-muted">assistant · lines 12–16</span>
            </div>
            <p class="comment__body">
              These list the system's external consumers, not roles — decomposition by
              role means grouping by user type and what actions they're allowed. Credited,
              but the justification is thin: <strong>&minus;0.25</strong>.
            </p>
          </div>
        </article>

        <!-- Suggestion card -->
        <article class="card card-pad suggestion">
          <div class="suggestion__head">
            <span class="badge badge-success"><span class="badge-dot" />reuse a comment · seen in 5 submissions</span>
            <span class="text-muted" style="font-size: var(--text-xs)">match 0.88</span>
          </div>
          <p class="text-muted" style="font-size: var(--text-sm)">
            from <strong>D. Prokhorova</strong>, submission st-2290 (lines 48–50)
          </p>
          <blockquote class="suggestion__quote">
            "The event contract leaves the payload empty, so it's incomplete: each event
            type needs its payload shape and versioning rules spelled out. Partition key
            is correct." &minus;0.25
          </blockquote>
          <div class="suggestion__actions">
            <button class="btn btn-primary btn-sm">Apply as mine</button>
            <button class="btn btn-outline btn-sm">Apply and edit</button>
          </div>
        </article>
      </div>
    </section>
  </section>
</template>

<style scoped>
.guide {
  padding: var(--space-8) var(--space-6) var(--space-12);
}

.guide__header {
  max-width: 640px;
  margin-bottom: var(--space-8);
}

.guide__title {
  font-size: var(--text-2xl);
  font-weight: 700;
  margin: var(--space-1) 0 var(--space-2);
}

.guide__section {
  margin-bottom: var(--space-8);
}

.guide__section-title {
  font-size: var(--text-lg);
  font-weight: 700;
  margin-bottom: var(--space-4);
}

/* Colors */
.color-groups {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-6);
}

.color-group__title {
  font-size: var(--text-sm);
  font-weight: 700;
  margin-bottom: var(--space-2);
}

.swatch {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-1) 0;
  font-size: var(--text-sm);
}

.swatch__chip {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--color-border);
  flex: none;
}

.swatch__name {
  flex: 1;
}

/* Typography */
.type-scale {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* Buttons */
.button-row {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-3);
}

.button-row__dark {
  background: var(--color-ink);
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-sm);
  display: inline-flex;
}

/* Badges */
.badge-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

/* Cards */
.card-samples {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: var(--space-4);
  align-items: start;
}

.sample-card__name {
  font-size: var(--text-lg);
  font-weight: 700;
  margin: var(--space-1) 0 0;
}

.meta-grid {
  margin: var(--space-4) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  font-size: var(--text-sm);
}

.meta-grid dt {
  font-size: var(--text-xs);
}

.meta-grid dd {
  margin: 0;
}

.criterion {
  padding: var(--space-3) 0;
  border-top: 1px solid var(--color-border);
}

.criterion:first-of-type {
  border-top: none;
  padding-top: var(--space-2);
}

.criterion__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-1);
}

.criterion__title {
  font-size: var(--text-sm);
  font-weight: 600;
}

.criterion__note {
  font-size: var(--text-xs);
  margin-top: var(--space-1);
}

.comment__head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-sm);
  margin-bottom: var(--space-2);
}

.comment__body {
  font-size: var(--text-sm);
  line-height: 1.6;
}

.suggestion {
  border-color: var(--color-primary-bg);
  background: var(--color-primary-bg);
}

.suggestion__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.suggestion__quote {
  margin: var(--space-2) 0 var(--space-3);
  padding-left: var(--space-3);
  border-left: 3px solid var(--color-primary);
  font-size: var(--text-sm);
  line-height: 1.6;
}

.suggestion__actions {
  display: flex;
  gap: var(--space-2);
}
</style>
