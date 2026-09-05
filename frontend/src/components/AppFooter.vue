<script setup lang="ts">
const year = new Date().getFullYear()
</script>

<template>
  <footer class="app-footer">
    <div class="container app-footer__inner">
      <p class="app-footer__copy">&copy; {{ year }} (TA)co. Built for a hackathon, not for production.</p>
      <nav class="app-footer__links">
        <RouterLink to="/">Home</RouterLink>
        <RouterLink to="/styleguide">Style guide</RouterLink>
        <a href="https://github.com/Mayonnaise-Slap/sporking-prong" target="_blank" rel="noopener noreferrer">GitHub</a>
      </nav>
    </div>
  </footer>
</template>

<style scoped>
.app-footer {
  margin-top: var(--space-12);
  background: var(--color-ink);
  border-top: 1px solid var(--color-ink-border);
}

.app-footer__inner {
  padding: var(--space-6);
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-4);
  align-items: center;
  justify-content: space-between;
}

.app-footer__copy {
  color: var(--color-ink-text-muted);
  font-size: var(--text-sm);
}

.app-footer__links {
  display: flex;
  gap: var(--space-4);
  font-size: var(--text-sm);
}

.app-footer__links a {
  color: var(--color-ink-text-muted);
}

.app-footer__links a:hover {
  color: var(--color-ink-text);
}
</style>
