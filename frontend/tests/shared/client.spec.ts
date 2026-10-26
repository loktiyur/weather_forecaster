import { afterEach, describe, expect, it, vi } from 'vitest'

import { ApiError, getCurrentWeather, getForecast, searchLocations } from '@/shared/api/client'

import { currentWeather, PRAGUE } from '../fixtures'

function respond(status: number, body: unknown, contentType = 'application/json') {
  const text = typeof body === 'string' ? body : JSON.stringify(body)
  const fetchMock = vi.fn(
    async (_request: Request) =>
      new Response(text, { status, headers: { 'content-type': contentType } }),
  )
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

function requestedUrl(fetchMock: ReturnType<typeof respond>): URL {
  const request = fetchMock.mock.calls[0]?.[0]
  if (!request) throw new Error('fetch was not called')
  return new URL(request.url)
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('API client', () => {
  it('returns the parsed body and sends the query parameters', async () => {
    const fetchMock = respond(200, currentWeather())

    const result = await getCurrentWeather({
      city: 'Prague',
      country: 'CZ',
      lang: 'uk',
      units: 'imperial',
    })

    expect(result.location.name).toBe('Prague')
    const url = requestedUrl(fetchMock)
    expect(url.pathname).toBe('/api/v1/weather/current')
    expect(Object.fromEntries(url.searchParams)).toEqual({
      city: 'Prague',
      country: 'CZ',
      lang: 'uk',
      units: 'imperial',
    })
  })

  it('leaves out a missing country instead of sending "undefined"', async () => {
    const fetchMock = respond(200, currentWeather())

    await getForecast({ city: 'Prague', lang: 'en', units: 'metric', days: 7 })

    const params = requestedUrl(fetchMock).searchParams
    expect(params.has('country')).toBe(false)
    expect(params.get('days')).toBe('7')
  })

  it('unwraps the search results', async () => {
    respond(200, { results: [PRAGUE] })

    expect(await searchLocations('Prague', 3)).toEqual([PRAGUE])
  })

  it('turns the backend error format into an ApiError with its code', async () => {
    respond(404, { error: { code: 'CITY_NOT_FOUND', message: "No place found for 'X'." } })

    const error = await getCurrentWeather({ city: 'X', lang: 'en', units: 'metric' }).catch(
      (e: unknown) => e,
    )

    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 404, code: 'CITY_NOT_FOUND' })
  })

  it('handles errors that are not in the backend format', async () => {
    respond(502, '<html>Bad gateway</html>', 'text/html')

    const error = await getCurrentWeather({ city: 'X', lang: 'en', units: 'metric' }).catch(
      (e: unknown) => e,
    )

    expect(error).toMatchObject({ status: 502, code: 'HTTP_ERROR' })
  })

  it('reports a network failure as NETWORK_ERROR', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))),
    )

    const error = await getCurrentWeather({ city: 'X', lang: 'en', units: 'metric' }).catch(
      (e: unknown) => e,
    )

    expect(error).toMatchObject({ status: 0, code: 'NETWORK_ERROR' })
  })
})
