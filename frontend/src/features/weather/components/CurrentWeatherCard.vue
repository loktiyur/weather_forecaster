<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'

import type { CurrentWeatherResponse } from '@/shared/api/client'
import { formatNumber, formatTime, placeLabel, weatherIcon } from '@/features/weather/format'

const props = defineProps<{ weather: CurrentWeatherResponse }>()
const { t } = useI18n()

const now = computed(() => props.weather.current)
const units = computed(() => props.weather.units)
</script>

<template>
  <section class="card current" aria-labelledby="current-title">
    <header>
      <h2 id="current-title">{{ placeLabel(weather.location) }}</h2>
      <p class="muted">
        {{ t('weather.localTime', { time: formatTime(now.time) }) }}
        <span v-if="weather.cached" class="badge" :title="t('weather.cachedTitle')">
          {{ t('weather.cached') }}
        </span>
      </p>
    </header>

    <div class="main">
      <span class="icon" aria-hidden="true">{{ weatherIcon(now.weather_code, now.is_day) }}</span>
      <div>
        <p class="temperature">
          {{ formatNumber(now.temperature) }}<span class="unit">{{ units.temperature }}</span>
        </p>
        <p class="description">{{ now.description }}</p>
      </div>
    </div>

    <dl class="details">
      <div>
        <dt>{{ t('weather.feelsLike') }}</dt>
        <dd>{{ formatNumber(now.apparent_temperature) }} {{ units.temperature }}</dd>
      </div>
      <div>
        <dt>{{ t('weather.humidity') }}</dt>
        <dd>{{ formatNumber(now.relative_humidity) }} %</dd>
      </div>
      <div>
        <dt>{{ t('weather.wind') }}</dt>
        <dd>{{ formatNumber(now.wind_speed) }} {{ units.wind_speed }}</dd>
      </div>
    </dl>
  </section>
</template>

<style scoped>
header h2 {
  margin: 0;
  font-size: 1.15rem;
}

header p {
  margin: 4px 0 0;
}

.badge {
  margin-left: 6px;
  padding: 1px 8px;
  font-size: 0.75rem;
  border: 1px solid var(--border);
  border-radius: 999px;
}

.main {
  display: flex;
  align-items: center;
  gap: 16px;
  margin: 18px 0;
}

.icon {
  font-size: 3.5rem;
  line-height: 1;
}

.temperature {
  margin: 0;
  font-size: 3rem;
  font-weight: 700;
  line-height: 1;
}

.unit {
  font-size: 1.4rem;
  font-weight: 500;
  vertical-align: top;
}

.description {
  margin: 6px 0 0;
  color: var(--text-muted);
}

.details {
  display: grid;
  /* Three columns where they fit; on narrow phones the values wrap to the next row. */
  grid-template-columns: repeat(auto-fit, minmax(6rem, 1fr));
  gap: 12px;
  margin: 0;
}

.details div {
  padding: 10px 12px;
  background: var(--surface-muted);
  border-radius: var(--radius);
}

dt {
  font-size: 0.8rem;
  color: var(--text-muted);
}

dd {
  margin: 2px 0 0;
  font-weight: 600;
  /* "11 км/год" stays on one line: a number is never split from its unit. */
  white-space: nowrap;
}
</style>
