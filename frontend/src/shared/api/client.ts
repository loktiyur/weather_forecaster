/**
 * Typed access to the backend REST API.
 *
 * Paths, query parameters and response shapes come from `schema.d.ts`, which is generated
 * from the backend's OpenAPI schema (`npm run generate:api`). A changed backend model shows
 * up here as a type error instead of a runtime surprise.
 */
import createClient from 'openapi-fetch'

import type { components, paths } from './schema'

type Schemas = components['schemas']
export type CurrentWeatherResponse = Schemas['CurrentWeatherResponse']
export type ForecastResponse = Schemas['ForecastResponse']
export type DailyForecastDay = Schemas['DailyForecastDay']
export type Location = Schemas['Location']
export type Units = Schemas['Units']
export type Language = Schemas['Language']
type ErrorResponse = Schemas['ErrorResponse']

/** Every failed call ends up as an ApiError carrying the backend's error `code`. */
export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

// Same origin as the page: the Vite dev server (development) or nginx (full stack)
// forwards /api to the backend.
const client = createClient<paths>({
  baseUrl: globalThis.location?.origin ?? '',
  // Look `fetch` up on every call instead of capturing it once at import time, so it can be
  // replaced (tests, polyfills, instrumentation) after this module has loaded.
  fetch: (request) => globalThis.fetch(request),
})

function isErrorResponse(body: unknown): body is ErrorResponse {
  return typeof body === 'object' && body !== null && 'error' in body
}

async function call<T>(
  request: () => Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  let result
  try {
    result = await request()
  } catch {
    throw new ApiError(0, 'NETWORK_ERROR', 'Cannot reach the server. Check your connection.')
  }
  const { data, error, response } = result
  if (data !== undefined) return data
  if (isErrorResponse(error)) {
    throw new ApiError(response.status, error.error.code, error.error.message)
  }
  throw new ApiError(response.status, 'HTTP_ERROR', `Request failed (HTTP ${response.status}).`)
}

/** By `id` (exactly one place, any language) or by `city` (+ `country`, `region`). */
export interface WeatherQuery {
  id?: number
  city?: string
  country?: string
  /** First-level region (a state, ...): picks one of several same-name places in a country. */
  region?: string
  lang: Language
  units: Units
}

export function getCurrentWeather(query: WeatherQuery): Promise<CurrentWeatherResponse> {
  return call(() => client.GET('/api/v1/weather/current', { params: { query } }))
}

export function getForecast(query: WeatherQuery & { days: number }): Promise<ForecastResponse> {
  return call(() => client.GET('/api/v1/weather/forecast', { params: { query } }))
}

export async function searchLocations(
  q: string,
  limit = 5,
  lang: Language = 'en',
): Promise<Location[]> {
  const body = await call(() =>
    client.GET('/api/v1/locations/search', { params: { query: { q, limit, lang } } }),
  )
  return body.results
}
