<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute } from 'vue-router'

import { ApiError, searchLocations, type Location } from '@/shared/api/client'
import ErrorBanner from '@/shared/components/ErrorBanner.vue'
import { useLanguage } from '@/shared/i18n'
import { queryValue } from '@/shared/query'
import { MAX_PLACES, placeQuery } from '@/features/weather/places'

const route = useRoute()
const { t } = useI18n()
const locale = useLanguage()
const q = computed(() => queryValue(route.query.q))

const status = ref<'loading' | 'success' | 'error'>('loading')
const places = ref<Location[]>([])
const error = ref<ApiError | null>(null)
let latestRequest = 0

async function load(): Promise<void> {
  if (!q.value) {
    places.value = []
    status.value = 'success'
    return
  }
  const requestId = ++latestRequest
  status.value = 'loading'
  error.value = null
  try {
    const found = await searchLocations(q.value, MAX_PLACES, locale.value)
    if (requestId !== latestRequest) return
    places.value = found
    status.value = 'success'
  } catch (reason) {
    if (requestId !== latestRequest) return
    error.value =
      reason instanceof ApiError ? reason : new ApiError(0, 'UNKNOWN_ERROR', String(reason))
    status.value = 'error'
  }
}

// A new language reloads the list: place names, regions and countries are translated.
watch([q, locale], load, { immediate: true })

/** "Texas, United States": the part that tells same-name places apart. */
function where(place: Location): string {
  return [place.region !== place.name ? place.region : null, place.country]
    .filter(Boolean)
    .join(', ')
}
</script>

<template>
  <div class="page">
    <RouterLink class="back" :to="q ? { name: 'search', query: { city: q } } : { name: 'search' }">
      {{ t('places.back') }}
    </RouterLink>

    <h1>{{ t('places.title', { name: q }) }}</h1>

    <ErrorBanner v-if="status === 'error' && error" :error="error" :city="q" @retry="load" />

    <div
      v-if="status === 'loading'"
      class="card block"
      aria-busy="true"
      :aria-label="t('places.loading')"
    ></div>

    <template v-if="status === 'success'">
      <p v-if="!places.length" class="muted">{{ t('places.none', { name: q }) }}</p>

      <ul v-else class="card list">
        <li v-for="place in places" :key="place.id ?? `${place.latitude},${place.longitude}`">
          <RouterLink :to="{ name: 'search', query: placeQuery(place) }">
            <strong>{{ place.name }}</strong>
            <span class="muted">{{ where(place) }}</span>
          </RouterLink>
        </li>
      </ul>

      <p v-if="places.length === MAX_PLACES" class="muted note">
        {{ t('places.cutOff', { n: MAX_PLACES }) }}
      </p>
    </template>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  grid-template-columns: minmax(0, 1fr);
  gap: 14px;
}

.back {
  justify-self: start;
  text-decoration: none;
}

h1 {
  margin: 0;
  font-size: 1.3rem;
  overflow-wrap: anywhere;
}

.list {
  margin: 0;
  padding: 4px 0;
  list-style: none;
}

.list li + li {
  border-top: 1px solid var(--border);
}

.list a {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 4px 10px;
  padding: 12px 20px;
  color: var(--text);
  text-decoration: none;
}

.list a:hover,
.list a:focus-visible {
  background: var(--surface-muted);
}

.note {
  margin: 0;
  font-size: 0.9rem;
}

.block {
  height: 220px;
  animation: pulse 1.2s ease-in-out infinite;
}

@keyframes pulse {
  50% {
    opacity: 0.55;
  }
}

@media (prefers-reduced-motion: reduce) {
  .block {
    animation: none;
  }
}
</style>
