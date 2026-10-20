import { describe, expect, it } from 'vitest'

import { isSamePlace, placeQuery } from '@/weather/places'

import { ODESSA_MO, ODESSA_TX, PARIS_FR } from './fixtures'

describe('placeQuery', () => {
  it('selects the place by id; the name is only for the search box', () => {
    expect(placeQuery(ODESSA_MO)).toEqual({ id: '4401659', city: 'Odessa' })
  })

  it('falls back to name, country and region without an id', () => {
    expect(placeQuery({ ...ODESSA_MO, id: null })).toEqual({
      city: 'Odessa',
      country: 'US',
      region: 'Missouri',
    })
  })

  it('leaves out what the place does not have', () => {
    expect(placeQuery({ ...PARIS_FR, id: null, country_code: null, region: null })).toEqual({
      city: 'Paris',
    })
  })
})

describe('isSamePlace', () => {
  it('compares ids, so names in another language still match', () => {
    expect(isSamePlace(ODESSA_TX, { ...ODESSA_TX, name: 'Одеса' })).toBe(true)
    expect(isSamePlace(ODESSA_TX, ODESSA_MO)).toBe(false)
  })

  it('compares coordinates when an id is missing', () => {
    expect(isSamePlace({ ...ODESSA_TX, id: null }, { ...ODESSA_TX, name: 'Одеса' })).toBe(true)
    expect(isSamePlace({ ...ODESSA_TX, id: null }, ODESSA_MO)).toBe(false)
  })
})
