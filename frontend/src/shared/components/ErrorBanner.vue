<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink } from 'vue-router'

import type { ApiError } from '@/shared/api/client'

const props = defineProps<{ error: ApiError; city?: string }>()
const emit = defineEmits<{ retry: [] }>()
const { t } = useI18n()

/** Text per backend error code, in the interface language (the API's messages are English). */
const message = computed(() => {
  const city = props.city ?? ''
  switch (props.error.code) {
    case 'CITY_NOT_FOUND':
      return t('errors.cityNotFound', { city })
    case 'NOT_A_CITY':
      return t('errors.notACity', { city })
    case 'VALIDATION_ERROR':
      return t('errors.notACityName', { city })
    case 'LOCATION_NOT_FOUND':
      return t('errors.locationNotFound')
    case 'NOT_SUPPORTED':
      return t('errors.notSupported')
    case 'UPSTREAM_TIMEOUT':
    case 'UPSTREAM_ERROR':
      return t('errors.upstream')
    case 'NETWORK_ERROR':
      return t('errors.network')
    default:
      return t('errors.unknown')
  }
})

const canRetry = computed(() =>
  ['UPSTREAM_TIMEOUT', 'UPSTREAM_ERROR', 'NETWORK_ERROR', 'HTTP_ERROR'].includes(props.error.code),
)
</script>

<template>
  <div class="banner" role="alert">
    <span>{{ message }}</span>
    <!-- Towns can share a country's name (Germany, Georgia, US): let the user pick one. -->
    <RouterLink
      v-if="error.code === 'NOT_A_CITY' && city"
      :to="{ name: 'places', query: { q: city } }"
    >
      {{ t('errors.placesNamed', { city }) }}
    </RouterLink>
    <button v-if="canRetry" type="button" @click="emit('retry')">{{ t('errors.retry') }}</button>
  </div>
</template>

<style scoped>
.banner {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 14px 16px;
  color: var(--danger-text);
  background: var(--danger-bg);
  border: 1px solid var(--danger-border);
  border-radius: var(--radius);
}

a {
  font-weight: 600;
  color: inherit;
}

button {
  padding: 6px 12px;
  font: inherit;
  font-weight: 600;
  color: inherit;
  background: transparent;
  border: 1px solid currentColor;
  border-radius: var(--radius);
  cursor: pointer;
}
</style>
