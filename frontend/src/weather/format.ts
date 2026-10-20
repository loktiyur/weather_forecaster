/** Display helpers. Times from the API are already in the place's local time. */

/** Emoji for a WMO weather code (same codes as the backend's descriptions). */
export function weatherIcon(code: number | null | undefined, isDay = true): string {
  if (code === null || code === undefined) return '❔'
  if (code === 0) return isDay ? '☀️' : '🌙'
  if (code <= 2) return isDay ? '🌤️' : '☁️'
  if (code === 3) return '☁️'
  if (code === 45 || code === 48) return '🌫️'
  if (code >= 51 && code <= 57) return '🌦️'
  if ((code >= 61 && code <= 67) || (code >= 80 && code <= 82)) return '🌧️'
  if ((code >= 71 && code <= 77) || code === 85 || code === 86) return '❄️'
  if (code >= 95) return '⛈️'
  return '❔'
}

/** "2026-10-16T07:25:00" → "07:25". The value is local time of the place: no time zone math. */
export function formatTime(isoLocal: string | null | undefined): string {
  return isoLocal ? isoLocal.slice(11, 16) : '–'
}

/** "2026-10-16" → "Fri 16 Oct" (parsed as a calendar date, not shifted by the browser's zone). */
export function formatDay(isoDate: string, locale = 'en-GB'): string {
  const [year, month, day] = isoDate.split('-').map(Number)
  const date = new Date(year ?? 1970, (month ?? 1) - 1, day ?? 1)
  return date.toLocaleDateString(locale, { weekday: 'short', day: 'numeric', month: 'short' })
}

export function formatNumber(value: number | null | undefined, digits = 0): string {
  return value === null || value === undefined ? '–' : value.toFixed(digits)
}

/** "Prague, Prague, Czechia" → "Prague, Czechia" when the region repeats the name. */
export function placeLabel(place: {
  name: string
  region?: string | null
  country?: string | null
}): string {
  const parts = [place.name]
  if (place.region && place.region !== place.name) parts.push(place.region)
  if (place.country) parts.push(place.country)
  return parts.join(', ')
}
