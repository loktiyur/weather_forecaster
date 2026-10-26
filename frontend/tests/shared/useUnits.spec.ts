import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { useUnits } from '@/shared/composables/useUnits'

afterEach(() => {
  localStorage.clear()
})

describe('useUnits', () => {
  it('defaults to metric', () => {
    expect(useUnits().value).toBe('metric')
  })

  it('remembers the choice in localStorage', async () => {
    const units = useUnits()
    units.value = 'imperial'
    await nextTick()

    expect(useUnits().value).toBe('imperial')
  })

  it('ignores unknown stored values', () => {
    localStorage.setItem('weather-forecaster:units', 'kelvin')

    expect(useUnits().value).toBe('metric')
  })

  it('still works when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })

    expect(useUnits().value).toBe('metric')
  })
})
