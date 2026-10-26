<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import { LANGUAGES } from '@/shared/i18n'

const { t, locale } = useI18n()
</script>

<template>
  <label class="language">
    <span aria-hidden="true">🌐</span>
    <span class="visually-hidden">{{ t('app.language') }}</span>
    <select v-model="locale">
      <option
        v-for="language in LANGUAGES"
        :key="language.code"
        :value="language.code"
        :lang="language.code"
      >
        {{ language.name }}
      </option>
    </select>
  </label>
</template>

<style scoped>
.language {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

select {
  padding: 6px 8px;
  font: inherit;
  font-size: 0.9rem;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  cursor: pointer;
}

select:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}
</style>
