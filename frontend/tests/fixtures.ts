import type {
  CurrentWeatherResponse,
  DailyForecastDay,
  ForecastResponse,
  Location,
} from '@/api/client'

export const PRAGUE: Location = {
  id: 3067696,
  name: 'Prague',
  country: 'Czechia',
  country_code: 'CZ',
  region: 'Prague',
  latitude: 50.08804,
  longitude: 14.42076,
  timezone: 'Europe/Prague',
}

export const PARIS_FR: Location = {
  id: 2988507,
  name: 'Paris',
  country: 'France',
  country_code: 'FR',
  region: 'Île-de-France',
  latitude: 48.85341,
  longitude: 2.3488,
  timezone: 'Europe/Paris',
}

export const PARIS_TX: Location = {
  ...PARIS_FR,
  id: 4717560,
  country: 'United States',
  country_code: 'US',
  region: 'Texas',
  latitude: 33.66094,
  longitude: -95.55551,
}

export const ODESA_UA: Location = {
  id: 698740,
  name: 'Odesa',
  country: 'Ukraine',
  country_code: 'UA',
  region: 'Odesa',
  latitude: 46.48572,
  longitude: 30.74383,
  timezone: 'Europe/Kyiv',
}

export const ODESSA_TX: Location = {
  id: 5527554,
  name: 'Odessa',
  country: 'United States',
  country_code: 'US',
  region: 'Texas',
  latitude: 31.84568,
  longitude: -102.36764,
  timezone: 'America/Chicago',
}

export const ODESSA_MO: Location = {
  ...ODESSA_TX,
  id: 4401659,
  region: 'Missouri',
  latitude: 38.99917,
  longitude: -93.95356,
}

export function currentWeather(
  location: Location = PRAGUE,
  overrides: Partial<CurrentWeatherResponse> = {},
): CurrentWeatherResponse {
  return {
    location,
    current: {
      time: '2026-10-16T14:15:00',
      temperature: 16.04,
      apparent_temperature: 15.2,
      relative_humidity: 60,
      wind_speed: 2.6,
      weather_code: 0,
      description: 'Clear sky',
      is_day: true,
    },
    units: { temperature: '°C', wind_speed: 'km/h' },
    cached: false,
    ...overrides,
  }
}

const DAY: DailyForecastDay = {
  date: '2026-10-16',
  temperature_max: 17.3,
  temperature_min: 4.9,
  relative_humidity_mean: 84,
  weather_code: 45,
  description: 'Fog',
  sunrise: '2026-10-16T07:25:00',
  sunset: '2026-10-16T18:09:00',
}

export function forecast(location: Location = PRAGUE, days = 3): ForecastResponse {
  return {
    location,
    daily: Array.from({ length: days }, (_, i) => ({
      ...DAY,
      date: `2026-10-${16 + i}`,
    })),
    units: { temperature: '°C', wind_speed: 'km/h' },
    cached: false,
  }
}
