import { describe, expect, it } from 'vitest'

import { formatDay, formatNumber, formatTime, placeLabel, weatherIcon } from '@/weather/format'

describe('weatherIcon', () => {
  it.each([
    [0, true, '☀️'],
    [0, false, '🌙'],
    [3, true, '☁️'],
    [45, true, '🌫️'],
    [53, true, '🌦️'],
    [63, true, '🌧️'],
    [81, true, '🌧️'],
    [75, true, '❄️'],
    [95, true, '⛈️'],
    [null, true, '❔'],
  ])('code %s (day: %s) → %s', (code, isDay, icon) => {
    expect(weatherIcon(code, isDay)).toBe(icon)
  })
})

describe('formatting', () => {
  it('shows the local time as it comes from the API', () => {
    expect(formatTime('2026-10-16T07:25:00')).toBe('07:25')
    expect(formatTime(null)).toBe('–')
  })

  it('formats a calendar date without shifting it by the browser time zone', () => {
    expect(formatDay('2026-10-16')).toBe('Fri 16 Oct')
  })

  it('rounds numbers and shows a dash for missing values', () => {
    expect(formatNumber(16.04)).toBe('16')
    expect(formatNumber(2.65, 1)).toBe('2.6')
    expect(formatNumber(null)).toBe('–')
  })

  it('does not repeat a region that equals the place name', () => {
    expect(placeLabel({ name: 'Prague', region: 'Prague', country: 'Czechia' })).toBe(
      'Prague, Czechia',
    )
    expect(placeLabel({ name: 'Paris', region: 'Texas', country: 'United States' })).toBe(
      'Paris, Texas, United States',
    )
  })
})
