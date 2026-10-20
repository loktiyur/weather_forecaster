<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'

const props = defineProps<{ initialCity?: string; disabled?: boolean }>()
const emit = defineEmits<{ search: [city: string] }>()
const { t } = useI18n()

const city = ref(props.initialCity ?? '')
watch(
  () => props.initialCity,
  (value) => {
    city.value = value ?? ''
  },
)

const trimmed = computed(() => city.value.trim())
// Same rule as the API: a name needs a letter (postal codes and numbers are not looked up).
const hasLetter = computed(() => /\p{L}/u.test(trimmed.value))
const showHint = computed(() => trimmed.value !== '' && !hasLetter.value)

function submit(): void {
  if (hasLetter.value) emit('search', trimmed.value)
}
</script>

<template>
  <form class="search" role="search" @submit.prevent="submit">
    <label class="visually-hidden" for="city">{{ t('search.label') }}</label>
    <input
      id="city"
      v-model="city"
      type="search"
      name="city"
      :placeholder="t('search.placeholder')"
      maxlength="100"
      autocomplete="off"
      enterkeyhint="search"
      :aria-invalid="showHint"
      aria-describedby="city-hint"
    />
    <button type="submit" :disabled="disabled || !hasLetter">{{ t('search.submit') }}</button>
    <p v-if="showHint" id="city-hint" class="hint">{{ t('search.needsLetter') }}</p>
  </form>
</template>

<style scoped>
.search {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.hint {
  flex-basis: 100%;
  margin: 0;
  font-size: 0.85rem;
  color: var(--danger-text);
}

input {
  flex: 1;
  min-width: 0;
  padding: 12px 14px;
  font: inherit;
  color: var(--text);
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
}

input:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 1px;
}

button {
  padding: 12px 18px;
  font: inherit;
  font-weight: 600;
  color: var(--on-accent);
  background: var(--accent);
  border: none;
  border-radius: var(--radius);
  cursor: pointer;
}

button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
