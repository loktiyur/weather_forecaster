<script setup lang="ts">
import { computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { RouterLink, useRoute, useRouter } from 'vue-router'

import CurrentWeatherCard from '@/components/CurrentWeatherCard.vue'
import ErrorBanner from '@/components/ErrorBanner.vue'
import ForecastList from '@/components/ForecastList.vue'
import SearchForm from '@/components/SearchForm.vue'
import UnitsToggle from '@/components/UnitsToggle.vue'
import { useUnits } from '@/composables/useUnits'
import { useWeatherLookup } from '@/composables/useWeatherLookup'
import { useLanguage } from '@/i18n'
import { queryValue } from '@/query'

const route = useRoute()
const router = useRouter()
const units = useUnits()
const { t } = useI18n()
const locale = useLanguage()
const { status, current, forecast, otherMatches, error, lookup, reset } = useWeatherLookup()

// The search lives in the URL (/?city=Prague, or /?id=5527554&city=Odessa for one exact place):
// shareable, bookmarkable, and the browser's back button returns to the previous search.
const city = computed(() => queryValue(route.query.city))
const id = computed(() => {
  const value = Number(queryValue(route.query.id))
  return Number.isInteger(value) && value > 0 ? value : undefined
})
const country = computed(() => queryValue(route.query.country))
const region = computed(() => queryValue(route.query.region))

function load(): void {
  if (city.value || id.value) {
    void lookup({
      id: id.value,
      city: city.value,
      country: country.value,
      region: region.value,
      lang: locale.value,
      units: units.value,
    })
  } else {
    reset()
  }
}

// A new language reloads too: place names and weather descriptions come from the API.
watch([city, id, country, region, units, locale], load, { immediate: true })

function search(newCity: string): void {
  void router.push({ query: { city: newCity } })
}

const placesLinkText = computed(() =>
  otherMatches.value === null
    ? t('places.seeAll', { name: city.value })
    : t('places.seeOther', { name: city.value }, otherMatches.value),
)
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <SearchForm
        class="grow"
        :initial-city="city"
        :disabled="status === 'loading'"
        @search="search"
      />
      <UnitsToggle v-model="units" />
    </div>

    <p v-if="status === 'idle'" class="hint muted">{{ t('search.idle') }}</p>

    <ErrorBanner v-if="status === 'error' && error" :error="error" :city="city" @retry="load" />

    <div
      v-if="status === 'loading'"
      class="skeleton"
      aria-busy="true"
      :aria-label="t('search.loading')"
    >
      <div class="card block tall"></div>
      <div class="card block"></div>
    </div>

    <template v-if="status === 'success' && current && forecast">
      <CurrentWeatherCard :weather="current" />
      <p v-if="city && otherMatches !== 0" class="more">
        <span class="muted">{{ t('places.notMeant') }}</span>
        <RouterLink :to="{ name: 'places', query: { q: city } }">{{ placesLinkText }}</RouterLink>
      </p>
      <ForecastList :forecast="forecast" />
    </template>
  </div>
</template>

<style scoped>
.page {
  display: grid;
  /* minmax(0, 1fr): children may shrink below their content width (no sideways scrolling) */
  grid-template-columns: minmax(0, 1fr);
  gap: 16px;
}

.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
}

.grow {
  flex: 1;
}

.more {
  margin: -4px 0 0;
}

.more .muted {
  margin-right: 6px;
}

.hint {
  margin: 24px 0;
  text-align: center;
}

.skeleton {
  display: grid;
  gap: 16px;
}

.block {
  height: 160px;
  animation: pulse 1.2s ease-in-out infinite;
}

.block.tall {
  height: 230px;
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

@media (max-width: 480px) {
  .toolbar {
    flex-wrap: wrap;
  }
}
</style>
