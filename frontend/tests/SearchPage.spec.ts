import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, type Router } from 'vue-router'

import * as api from '@/api/client'
import { ApiError } from '@/api/client'
import App from '@/App.vue'
import { FORECAST_DAYS } from '@/composables/useWeatherLookup'
import { createAppI18n } from '@/i18n'
import { createAppRouter } from '@/router'

import {
  currentWeather,
  forecast,
  ODESA_UA,
  ODESSA_MO,
  ODESSA_TX,
  PARIS_FR,
  PRAGUE,
} from './fixtures'

vi.mock('@/api/client', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/api/client')>()
  return {
    ...actual,
    getCurrentWeather: vi.fn(),
    getForecast: vi.fn(),
    searchLocations: vi.fn(),
  }
})

const getCurrentWeather = vi.mocked(api.getCurrentWeather)
const getForecast = vi.mocked(api.getForecast)
const searchLocations = vi.mocked(api.searchLocations)

let router: Router

async function mountAt(url: string) {
  router = createAppRouter(createMemoryHistory())
  await router.push(url)
  const wrapper = mount(App, { global: { plugins: [router, createAppI18n('en')] } })
  await flushPromises()
  return wrapper
}

beforeEach(() => {
  getCurrentWeather.mockResolvedValue(currentWeather(PRAGUE))
  getForecast.mockResolvedValue(forecast(PRAGUE, 3))
  searchLocations.mockResolvedValue([PRAGUE])
})

afterEach(() => {
  localStorage.clear()
})

describe('SearchPage', () => {
  it('shows a hint and calls nothing before a search', async () => {
    const wrapper = await mountAt('/')

    expect(wrapper.text()).toContain('Type a city')
    expect(getCurrentWeather).not.toHaveBeenCalled()
  })

  it('loads the city from the URL and shows current weather and forecast', async () => {
    const wrapper = await mountAt('/?city=Prague')

    expect(getCurrentWeather).toHaveBeenCalledWith({
      city: 'Prague',
      country: undefined,
      lang: 'en',
      units: 'metric',
    })
    expect(getForecast).toHaveBeenCalledWith(
      expect.objectContaining({ city: 'Prague', days: FORECAST_DAYS }),
    )
    expect(wrapper.text()).toContain('Prague, Czechia')
    expect(wrapper.text()).toContain('16°C')
    expect(wrapper.text()).toContain('Clear sky')
    expect(wrapper.findAll('.day')).toHaveLength(3)
  })

  it('puts a new search into the URL', async () => {
    const wrapper = await mountAt('/')

    await wrapper.find('input').setValue('  Brno ')
    await wrapper.find('form').trigger('submit')
    await flushPromises()

    expect(router.currentRoute.value.query).toEqual({ city: 'Brno' })
    expect(getCurrentWeather).toHaveBeenCalledWith(expect.objectContaining({ city: 'Brno' }))
  })

  it('does not submit an empty search', async () => {
    const wrapper = await mountAt('/')

    await wrapper.find('input').setValue('   ')

    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
  })

  it.each(['10001', '123', '42 !'])(
    'does not search for %j, which has no letters',
    async (text) => {
      const wrapper = await mountAt('/')

      await wrapper.find('input').setValue(text)
      await wrapper.find('form').trigger('submit')
      await flushPromises()

      expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeDefined()
      expect(wrapper.find('#city-hint').text()).toContain(
        'Postal codes and numbers are not supported',
      )
      expect(router.currentRoute.value.query).toEqual({})
      expect(getCurrentWeather).not.toHaveBeenCalled()
    },
  )

  it('accepts names in any script', async () => {
    const wrapper = await mountAt('/')

    await wrapper.find('input').setValue('Київ')

    expect(wrapper.find('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.find('#city-hint').exists()).toBe(false)
  })

  it('explains a rejected city name that came from the URL', async () => {
    getCurrentWeather.mockRejectedValue(new ApiError(422, 'VALIDATION_ERROR', 'Invalid request.'))
    const wrapper = await mountAt('/?city=75001')

    expect(wrapper.find('[role="alert"]').text()).toContain('“75001” is not a city name')
    expect(wrapper.find('[role="alert"] button').exists()).toBe(false)
  })

  it('links to every place matching the name and shows the picked one', async () => {
    // "Odessa" finds Odesa (Ukraine) first; the user wanted Odessa, Missouri.
    getCurrentWeather.mockResolvedValue(currentWeather(ODESA_UA))
    getForecast.mockResolvedValue(forecast(ODESA_UA))
    searchLocations.mockResolvedValue([ODESA_UA, ODESSA_TX, ODESSA_MO])
    const wrapper = await mountAt('/?city=Odessa')

    const link = wrapper.find('.more a')
    expect(link.text()).toBe('See 2 other places matching “Odessa”')
    await link.trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/places?q=Odessa')
    expect(searchLocations).toHaveBeenLastCalledWith('Odessa', 20, 'en')
    const entries = wrapper.findAll('.list a')
    expect(
      entries.map((entry) => [entry.find('strong').text(), entry.find('span').text()]),
    ).toEqual([
      ['Odesa', 'Ukraine'],
      ['Odessa', 'Texas, United States'],
      ['Odessa', 'Missouri, United States'],
    ])

    getCurrentWeather.mockResolvedValue(currentWeather(ODESSA_MO))
    getForecast.mockResolvedValue(forecast(ODESSA_MO))
    await entries[2]!.trigger('click')
    await flushPromises()

    // The id selects exactly this place, in any language; the name fills the search box.
    expect(router.currentRoute.value.query).toEqual({ id: '4401659', city: 'Odessa' })
    expect(getCurrentWeather).toHaveBeenLastCalledWith({ id: 4401659, lang: 'en', units: 'metric' })
    expect(wrapper.text()).toContain('Odessa, Missouri, United States')
  })

  it('hides the link when no other place matches', async () => {
    const wrapper = await mountAt('/?city=Prague')

    expect(wrapper.find('.more').exists()).toBe(false)
  })

  it('still links to the list when the match count is unknown', async () => {
    searchLocations.mockRejectedValue(new ApiError(504, 'UPSTREAM_TIMEOUT', 'Too slow.'))
    const wrapper = await mountAt('/?city=Prague')

    expect(wrapper.find('.more a').text()).toBe('See all places matching “Prague”')
  })

  it('shows a friendly message when the city does not exist', async () => {
    getCurrentWeather.mockRejectedValue(new ApiError(404, 'CITY_NOT_FOUND', 'No place found.'))
    const wrapper = await mountAt('/?city=Atlantis')

    expect(wrapper.find('[role="alert"]').text()).toContain(`We couldn’t find “Atlantis”`)
    expect(wrapper.find('[role="alert"] button').exists()).toBe(false)
  })

  it('explains that a country is not a city and links to towns with that name', async () => {
    getCurrentWeather.mockRejectedValue(
      new ApiError(404, 'NOT_A_CITY', "'Germany' is a country, not a city."),
    )
    const wrapper = await mountAt('/?city=Germany')

    const alert = wrapper.find('[role="alert"]')
    expect(alert.text()).toContain('“Germany” is a country, not a city. Enter a city in it')
    expect(alert.find('button').exists()).toBe(false)
    await alert.find('a').trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.fullPath).toBe('/places?q=Germany')
  })

  it('offers a retry when the weather service fails, and recovers', async () => {
    getForecast.mockRejectedValueOnce(new ApiError(502, 'UPSTREAM_ERROR', 'Upstream failed.'))
    const wrapper = await mountAt('/?city=Prague')

    expect(wrapper.find('[role="alert"]').text()).toContain('not answering')
    await wrapper.find('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Prague, Czechia')
  })

  it('still shows the weather when the place search fails', async () => {
    searchLocations.mockRejectedValue(new ApiError(504, 'UPSTREAM_TIMEOUT', 'Too slow.'))
    const wrapper = await mountAt('/?city=Prague')

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.text()).toContain('Prague, Czechia')
  })

  it('reloads in imperial units and remembers the choice', async () => {
    const wrapper = await mountAt('/?city=Prague')

    await wrapper.find('button[role="radio"][title^="Imperial"]').trigger('click')
    await flushPromises()

    expect(getCurrentWeather).toHaveBeenLastCalledWith(
      expect.objectContaining({ units: 'imperial' }),
    )
    expect(localStorage.getItem('weather-forecaster:units')).toBe('imperial')
  })

  it('shows the cached badge when the data came from the cache', async () => {
    getCurrentWeather.mockResolvedValue(currentWeather(PRAGUE, { cached: true }))
    const wrapper = await mountAt('/?city=Prague')

    expect(wrapper.find('.badge').text()).toBe('cached')
  })

  it('ignores a slow answer to an older search', async () => {
    let resolveOld: (value: api.CurrentWeatherResponse) => void = () => {}
    getCurrentWeather.mockImplementationOnce(() => new Promise((resolve) => (resolveOld = resolve)))
    getCurrentWeather.mockResolvedValue(currentWeather(PARIS_FR))
    getForecast.mockResolvedValue(forecast(PARIS_FR))

    const wrapper = await mountAt('/?city=Prague')
    await router.push('/?city=Paris')
    await flushPromises()
    resolveOld(currentWeather(PRAGUE))
    await flushPromises()

    expect(wrapper.text()).toContain('Paris, Île-de-France, France')
    expect(wrapper.text()).not.toContain('Prague, Czechia')
  })

  it('lists no places for a name nothing matches', async () => {
    searchLocations.mockResolvedValue([])
    const wrapper = await mountAt('/places?q=Atlantis')

    expect(wrapper.text()).toContain('No places match “Atlantis”')
  })

  it('says when the place list is cut off', async () => {
    searchLocations.mockResolvedValue(
      Array.from({ length: 20 }, (_, i) => ({ ...ODESSA_TX, latitude: i })),
    )
    const wrapper = await mountAt('/places?q=Odessa')

    expect(wrapper.findAll('.list a')).toHaveLength(20)
    expect(wrapper.text()).toContain('Showing the first 20 matches')
  })

  it('offers a retry when the place list fails to load', async () => {
    searchLocations.mockRejectedValueOnce(new ApiError(502, 'UPSTREAM_ERROR', 'Upstream failed.'))
    searchLocations.mockResolvedValue([ODESSA_TX])
    const wrapper = await mountAt('/places?q=Odessa')

    await wrapper.find('[role="alert"] button').trigger('click')
    await flushPromises()

    expect(wrapper.find('[role="alert"]').exists()).toBe(false)
    expect(wrapper.findAll('.list a')).toHaveLength(1)
  })

  it('switches the language, reloads in it and remembers the choice', async () => {
    const wrapper = await mountAt('/?city=Prague')
    expect(wrapper.text()).toContain('Feels like')

    await wrapper.find('select').setValue('uk')
    await flushPromises()

    expect(wrapper.text()).toContain('Відчувається як')
    expect(wrapper.find('#forecast-title').text()).toBe('Прогноз на 3 дні')
    expect(wrapper.find('input').attributes('placeholder')).toBe('Пошук міста, напр. Прага')
    expect(getCurrentWeather).toHaveBeenLastCalledWith(expect.objectContaining({ lang: 'uk' }))
    expect(searchLocations).toHaveBeenLastCalledWith('Prague', 20, 'uk')
    expect(localStorage.getItem('weather-forecaster:language')).toBe('uk')
    expect(document.documentElement.lang).toBe('uk')
  })

  it('offers the four interface languages, each in its own name', async () => {
    const wrapper = await mountAt('/')

    const options = wrapper.findAll('select option')
    expect(options.map((option) => option.text())).toEqual([
      'English',
      'Українська',
      'Čeština',
      'Русский',
    ])
    expect(options.map((option) => option.attributes('value'))).toEqual(['en', 'uk', 'cs', 'ru'])
  })

  it('loads a place by id and only uses the name for the match count', async () => {
    getCurrentWeather.mockResolvedValue(currentWeather(ODESSA_MO))
    getForecast.mockResolvedValue(forecast(ODESSA_MO))
    searchLocations.mockResolvedValue([ODESA_UA, ODESSA_TX, ODESSA_MO])
    const wrapper = await mountAt('/?id=4401659&city=Odessa')

    expect(getCurrentWeather).toHaveBeenCalledWith({ id: 4401659, lang: 'en', units: 'metric' })
    expect(wrapper.find('input').element.value).toBe('Odessa')
    expect(wrapper.find('.more a').text()).toBe('See 2 other places matching “Odessa”')
  })

  it('ignores an invalid id and needs no place search without a name', async () => {
    const wrapper = await mountAt('/?id=abc')
    expect(wrapper.text()).toContain('Type a city')

    await router.push('/?id=4401659')
    await flushPromises()

    expect(getCurrentWeather).toHaveBeenCalledWith({ id: 4401659, lang: 'en', units: 'metric' })
    expect(searchLocations).not.toHaveBeenCalled()
    expect(wrapper.find('.more').exists()).toBe(false)
  })

  it('explains an id that no longer exists', async () => {
    getCurrentWeather.mockRejectedValue(new ApiError(404, 'LOCATION_NOT_FOUND', 'No place.'))
    const wrapper = await mountAt('/?id=999999999')

    expect(wrapper.find('[role="alert"]').text()).toContain('This place could not be found')
  })

  it('reloads the places list in a new language', async () => {
    searchLocations.mockResolvedValue([ODESSA_TX])
    const wrapper = await mountAt('/places?q=Odessa')

    await wrapper.find('select').setValue('cs')
    await flushPromises()

    expect(searchLocations).toHaveBeenLastCalledWith('Odessa', 20, 'cs')
    expect(wrapper.find('h1').text()).toBe('Místa pro „Odessa“')
  })

  it('sends unknown paths back to the search page', async () => {
    await mountAt('/does/not/exist')

    expect(router.currentRoute.value.path).toBe('/')
  })
})
