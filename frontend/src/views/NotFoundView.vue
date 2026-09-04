<script setup lang="ts"></script>

<template>
  <section class="not-found container">
    <p class="not-found__code text-mono">404</p>
    <h1 class="not-found__title">This page doesn't exist.</h1>
    <p class="not-found__body text-muted">
      Check the link, or head back to somewhere that does.
    </p>
    <RouterLink to="/" class="btn btn-primary">Back to home</RouterLink>
  </section>
</template>

<style scoped>
.not-found {
  min-height: calc(100vh - var(--header-height) - 96px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  text-align: center;
  gap: var(--space-2);
  padding-top: var(--space-12);
  padding-bottom: var(--space-12);
}

.not-found__code {
  font-size: var(--text-3xl);
  font-weight: 700;
  color: var(--color-text-faint);
}

.not-found__title {
  font-size: var(--text-xl);
  font-weight: 700;
}

.not-found__body {
  margin-bottom: var(--space-4);
}
</style>
