import { ref } from 'vue'

import {
  ApiError,
  getCurrentWeather,
  getForecast,
  searchLocations,
  type CurrentWeatherResponse,
  type ForecastResponse,
  type Location,
  type WeatherQuery,
} from '@/api/client'
import { isSamePlace, MAX_PLACES } from '@/weather/places'

export const FORECAST_DAYS = 7

export type LookupStatus = 'idle' | 'loading' | 'success' | 'error'

export type LookupRequest = WeatherQuery

/**
 * Loads current weather, forecast and the number of other places matching the city name.
 *
 * The three requests run in parallel. Only the latest lookup may update the state, so a slow
 * answer to an older search can never overwrite the result of a newer one.
 */
export function useWeatherLookup() {
  const status = ref<LookupStatus>('idle')
  const current = ref<CurrentWeatherResponse | null>(null)
  const forecast = ref<ForecastResponse | null>(null)
  /** How many other places match the typed name; null when the place search failed. */
  const otherMatches = ref<number | null>(null)
  const error = ref<ApiError | null>(null)

  let latestRequest = 0

  async function lookup(request: LookupRequest): Promise<void> {
    const requestId = ++latestRequest
    status.value = 'loading'
    error.value = null

    // An id selects exactly one place; the name is then only needed for the match count.
    const query: WeatherQuery =
      request.id !== undefined
        ? { id: request.id, lang: request.lang, units: request.units }
        : request
    const [currentResult, forecastResult, placesResult] = await Promise.allSettled([
      getCurrentWeather(query),
      getForecast({ ...query, days: FORECAST_DAYS }),
      // The match count is a nice-to-have: its failure must not hide the weather.
      request.city
        ? searchLocations(request.city, MAX_PLACES, request.lang)
        : Promise.resolve<Location[] | null>(null),
    ])
    if (requestId !== latestRequest) return

    if (currentResult.status === 'rejected' || forecastResult.status === 'rejected') {
      const reason =
        currentResult.status === 'rejected'
          ? currentResult.reason
          : (forecastResult as PromiseRejectedResult).reason
      error.value =
        reason instanceof ApiError
          ? reason
          : new ApiError(0, 'UNKNOWN_ERROR', 'Something went wrong. Please try again.')
      current.value = null
      forecast.value = null
      otherMatches.value = null
      status.value = 'error'
      return
    }

    current.value = currentResult.value
    forecast.value = forecastResult.value
    const shown = currentResult.value.location
    otherMatches.value =
      placesResult.status === 'fulfilled' && placesResult.value
        ? placesResult.value.filter((place) => !isSamePlace(place, shown)).length
        : null
    status.value = 'success'
  }

  function reset(): void {
    latestRequest++
    status.value = 'idle'
    current.value = null
    forecast.value = null
    otherMatches.value = null
    error.value = null
  }

  return { status, current, forecast, otherMatches, error, lookup, reset }
}
