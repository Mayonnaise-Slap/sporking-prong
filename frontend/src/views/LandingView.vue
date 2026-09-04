<script setup lang="ts">
const features = [
  {
    title: 'Automated pre-checks',
    body: 'Every submission is scored for lateness, plagiarism overlap, and signs of AI generation before a TA opens it.',
  },
  {
    title: 'Line-by-line review',
    body: 'A GitHub-style reading view: comments attach to exact lines, sit inline with the text, and stay as drafts until sent.',
  },
  {
    title: 'Reusable comments',
    body: 'When a mistake looks like one already flagged elsewhere in the stream, reuse another TA’s wording instead of retyping it.',
  },
  {
    title: 'Rubric checklist',
    body: 'Mark each criterion full, partial, or none against the assignment author’s own checklist — no manual point math.',
  },
]
</script>

<template>
  <section class="hero">
    <div class="container hero__inner">
      <p class="hero__eyebrow">Assignment review, without the busywork</p>
      <h1 class="hero__title">Grade faster. Read more, retype less.</h1>
      <p class="hero__subtitle">
        (TA)co is an internal tool for course staff: it pre-checks single-file text
        assignments for lateness, overlap, and AI signal, then gives you a
        line-anchored review page with a rubric checklist and a bank of comments
        your team has already written.
      </p>
      <div class="hero__actions">
        <RouterLink to="/register" class="btn btn-primary">Get started</RouterLink>
        <RouterLink to="/login" class="btn btn-outline">Log in</RouterLink>
      </div>
    </div>
  </section>

  <section class="container features">
    <article v-for="feature in features" :key="feature.title" class="card card-pad feature-card">
      <h2 class="feature-card__title">{{ feature.title }}</h2>
      <p class="feature-card__body text-muted">{{ feature.body }}</p>
    </article>
  </section>
</template>

<style scoped>
.hero {
  background: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  padding: var(--space-12) 0;
}

.hero__inner {
  max-width: 640px;
}

.hero__eyebrow {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--color-primary);
  text-transform: uppercase;
  letter-spacing: 0.04em;
  margin-bottom: var(--space-2);
}

.hero__title {
  font-size: var(--text-3xl);
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: var(--space-4);
}

.hero__subtitle {
  color: var(--color-text-muted);
  font-size: var(--text-lg);
  line-height: 1.6;
  margin-bottom: var(--space-6);
}

.hero__actions {
  display: flex;
  gap: var(--space-3);
}

.features {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: var(--space-4);
  padding-top: var(--space-8);
  padding-bottom: var(--space-8);
}

.feature-card__title {
  font-size: var(--text-base);
  font-weight: 700;
  margin-bottom: var(--space-2);
}

.feature-card__body {
  font-size: var(--text-sm);
  line-height: 1.5;
}
</style>
