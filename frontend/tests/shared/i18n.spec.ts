import { afterEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'

import { createAppI18n, dateLocale, detectLanguage, LANGUAGES } from '@/shared/i18n'
import cs from '@/shared/i18n/locales/cs.json'
import en from '@/shared/i18n/locales/en.json'
import ru from '@/shared/i18n/locales/ru.json'
import uk from '@/shared/i18n/locales/uk.json'

type Messages = { [key: string]: string | Messages }

function keys(messages: Messages, prefix = ''): string[] {
  return Object.entries(messages).flatMap(([key, value]) =>
    typeof value === 'string' ? [`${prefix}${key}`] : keys(value, `${prefix}${key}.`),
  )
}

function values(messages: Messages): string[] {
  return Object.values(messages).flatMap((value) =>
    typeof value === 'string' ? [value] : values(value),
  )
}

afterEach(() => {
  localStorage.clear()
})

describe('messages', () => {
  it.each([
    ['uk', uk],
    ['cs', cs],
    ['ru', ru],
  ])('%s has exactly the keys of en, none empty', (_language, messages) => {
    expect(keys(messages).sort()).toEqual(keys(en).sort())
    expect(values(messages).every((text) => text.trim() !== '')).toBe(true)
  })

  it('offers every language in its own name', () => {
    expect(LANGUAGES.map((language) => language.name)).toEqual([
      'English',
      'Українська',
      'Čeština',
      'Русский',
    ])
  })
})

describe('plural forms', () => {
  const seeOther = (language: 'en' | 'uk' | 'cs' | 'ru', n: number) =>
    createAppI18n(language).global.t('places.seeOther', { name: 'X' }, n)

  it('English: one / other', () => {
    expect(seeOther('en', 1)).toBe('See 1 other place matching “X”')
    expect(seeOther('en', 19)).toBe('See 19 other places matching “X”')
  })

  it('Ukrainian: 1 місце, 2 місця, 5 місць, 21 місце', () => {
    expect(seeOther('uk', 1)).toContain('1 місце ')
    expect(seeOther('uk', 3)).toContain('3 місця ')
    expect(seeOther('uk', 11)).toContain('11 місць ')
    expect(seeOther('uk', 21)).toContain('21 місце ')
  })

  it('Russian: 1 место, 2 места, 5 мест', () => {
    expect(seeOther('ru', 1)).toContain('1 место ')
    expect(seeOther('ru', 4)).toContain('4 места ')
    expect(seeOther('ru', 19)).toContain('19 мест ')
  })

  it('Czech: 1 místo, 2 místa, 5 míst', () => {
    expect(seeOther('cs', 1)).toBe('Zobrazit 1 další místo pro „X“')
    expect(seeOther('cs', 2)).toBe('Zobrazit 2 další místa pro „X“')
    expect(seeOther('cs', 19)).toBe('Zobrazit 19 dalších míst pro „X“')
  })

  it('the forecast title follows the same rules', () => {
    const title = (language: 'uk' | 'cs', n: number) =>
      createAppI18n(language).global.t('weather.forecastTitle', n)

    expect(title('uk', 7)).toBe('Прогноз на 7 днів')
    expect(title('uk', 3)).toBe('Прогноз на 3 дні')
    expect(title('cs', 1)).toBe('Předpověď na 1 den')
  })
})

describe('detectLanguage', () => {
  it('prefers the remembered choice', () => {
    localStorage.setItem('weather-forecaster:language', 'ru')

    expect(detectLanguage()).toBe('ru')
  })

  it("uses the browser's first supported language", () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['de-DE', 'cs-CZ', 'en'])

    expect(detectLanguage()).toBe('cs')
  })

  it('falls back to English', () => {
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['de-DE'])
    localStorage.setItem('weather-forecaster:language', 'klingon')

    expect(detectLanguage()).toBe('en')
  })

  it('still works when storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(navigator, 'languages', 'get').mockReturnValue(['uk-UA'])

    expect(detectLanguage()).toBe('uk')
  })
})

describe('createAppI18n', () => {
  it('sets <html lang> and remembers a new choice', async () => {
    const i18n = createAppI18n('en')
    expect(document.documentElement.lang).toBe('en')

    i18n.global.locale.value = 'cs'
    await nextTick()

    expect(document.documentElement.lang).toBe('cs')
    expect(localStorage.getItem('weather-forecaster:language')).toBe('cs')
  })

  it('does not fail when the choice cannot be stored', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const i18n = createAppI18n('en')

    i18n.global.locale.value = 'uk'
    await nextTick()

    expect(document.documentElement.lang).toBe('uk')
  })

  it('formats English dates day-first', () => {
    expect(dateLocale('en')).toBe('en-GB')
    expect(dateLocale('uk')).toBe('uk')
  })
})
