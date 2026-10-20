<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { Units } from '@/api/client'

const units = defineModel<Units>({ required: true })
const { t } = useI18n()

const options = computed<{ value: Units; label: string; title: string }[]>(() => [
  { value: 'metric', label: '°C', title: t('units.metric') },
  { value: 'imperial', label: '°F', title: t('units.imperial') },
])
</script>

<template>
  <div class="toggle" role="radiogroup" :aria-label="t('units.label')">
    <button
      v-for="option in options"
      :key="option.value"
      type="button"
      role="radio"
      :aria-checked="units === option.value"
      :title="option.title"
      :class="{ active: units === option.value }"
      @click="units = option.value"
    >
      {{ option.label }}
    </button>
  </div>
</template>

<style scoped>
.toggle {
  display: inline-flex;
  padding: 3px;
  background: var(--surface-muted);
  border: 1px solid var(--border);
  border-radius: 999px;
}

button {
  min-width: 44px;
  padding: 6px 10px;
  font: inherit;
  font-weight: 600;
  color: var(--text-muted);
  background: transparent;
  border: none;
  border-radius: 999px;
  cursor: pointer;
}

button.active {
  color: var(--text);
  background: var(--surface);
  box-shadow: var(--shadow-sm);
}
</style>
