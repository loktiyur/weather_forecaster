<script setup lang="ts">
import { I18nT, useI18n } from 'vue-i18n'
import { RouterView } from 'vue-router'

import LanguageSelect from '@/components/LanguageSelect.vue'

const { t } = useI18n()
</script>

<template>
  <header class="app-header">
    <a class="brand" href="/">
      <span aria-hidden="true">🌤️</span>
      {{ t('app.title') }}
    </a>
    <LanguageSelect />
  </header>

  <main class="app-main">
    <RouterView />
  </main>

  <footer class="app-footer muted">
    <I18nT keypath="app.attribution" tag="span" scope="global">
      <template #source>
        <a href="https://open-meteo.com/" target="_blank" rel="noopener">Open-Meteo</a>
      </template>
    </I18nT>
  </footer>
</template>

<style scoped>
.app-header,
.app-main,
.app-footer {
  width: min(720px, 100% - 32px);
  margin-inline: auto;
}

.app-header {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 8px 16px;
  padding: 20px 0 12px;
}

.brand {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--text);
  text-decoration: none;
}

.app-footer {
  padding: 32px 0 24px;
  font-size: 0.85rem;
  text-align: center;
}
</style>
