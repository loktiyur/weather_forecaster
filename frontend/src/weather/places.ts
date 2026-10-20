import type { Location } from '@/api/client'

/** The most results the backend's /locations/search returns (MAX_SEARCH_RESULTS). */
export const MAX_PLACES = 20

/** True when both entries describe the same place, in whatever language they are named. */
export function isSamePlace(a: Location, b: Location): boolean {
  if (a.id != null && b.id != null) return a.id === b.id
  return a.latitude === b.latitude && a.longitude === b.longitude
}

/**
 * The search page query that shows exactly this place. The id selects it in any language
 * (a shared link still works after switching the language); the name only fills the search
 * box. Without an id: name + country + region.
 */
export function placeQuery(place: Location): Record<string, string> {
  if (place.id != null) return { id: String(place.id), city: place.name }
  const query: Record<string, string> = { city: place.name }
  if (place.country_code) query.country = place.country_code
  if (place.region) query.region = place.region
  return query
}
