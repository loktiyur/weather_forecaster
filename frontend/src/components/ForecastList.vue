<script setup lang="ts">
import { useI18n } from 'vue-i18n'

import type { ForecastResponse } from '@/api/client'
import { dateLocale } from '@/i18n'
import { formatDay, formatNumber, formatTime, weatherIcon } from '@/weather/format'

defineProps<{ forecast: ForecastResponse }>()
const { t, locale } = useI18n()
</script>

<template>
  <section class="card" aria-labelledby="forecast-title">
    <h2 id="forecast-title">{{ t('weather.forecastTitle', forecast.daily.length) }}</h2>
    <ol class="days">
      <li v-for="day in forecast.daily" :key="day.date" class="day">
        <span class="date">{{ formatDay(day.date, dateLocale(locale)) }}</span>
        <span class="icon" :title="day.description ?? ''" aria-hidden="true">
          {{ weatherIcon(day.weather_code) }}
        </span>
        <span class="description">{{ day.description ?? '–' }}</span>
        <span class="temps">
          <strong>{{ formatNumber(day.temperature_max) }}°</strong>
          <span class="muted"> / {{ formatNumber(day.temperature_min) }}°</span>
        </span>
        <span class="extra muted">
          💧 {{ formatNumber(day.relative_humidity_mean) }} % · ↑ {{ formatTime(day.sunrise) }} · ↓
          {{ formatTime(day.sunset) }}
        </span>
      </li>
    </ol>
  </section>
</template>

<style scoped>
h2 {
  margin: 0 0 8px;
  font-size: 1.05rem;
}

.days {
  margin: 0;
  padding: 0;
  list-style: none;
}

.day {
  display: grid;
  grid-template-columns: 7.5em 2em 1fr auto;
  grid-template-areas:
    'date icon description temps'
    'date icon extra extra';
  align-items: center;
  column-gap: 10px;
  padding: 10px 0;
  border-top: 1px solid var(--border);
}

.day:first-child {
  border-top: none;
}

.date {
  grid-area: date;
  font-weight: 600;
}

.icon {
  grid-area: icon;
  font-size: 1.5rem;
}

.description {
  grid-area: description;
}

.temps {
  grid-area: temps;
  white-space: nowrap;
}

.extra {
  grid-area: extra;
  font-size: 0.85rem;
}

@media (max-width: 480px) {
  .day {
    grid-template-columns: 2em 1fr auto;
    grid-template-areas:
      'icon date temps'
      'icon description description'
      'icon extra extra';
  }
}
</style>
