import { watch, type WritableComputedRef } from 'vue'
import { createI18n, useI18n } from 'vue-i18n'

import type { Language } from '@/shared/api/client'

import cs from './locales/cs.json'
import en from './locales/en.json'
import ru from './locales/ru.json'
import uk from './locales/uk.json'

/** English defines the messages: the other files must have the same keys (type-checked). */
export type MessageSchema = typeof en

declare module 'vue-i18n' {
  // Typed `t('...')` keys: a misspelt key is a type error, not a raw key on the page.
  // eslint-disable-next-line @typescript-eslint/no-empty-object-type
  export interface DefineLocaleMessage extends MessageSchema {}
}

/** The interface languages, each written in itself so everyone finds their own. */
export const LANGUAGES: readonly { code: Language; name: string }[] = [
  { code: 'en', name: 'English' },
  { code: 'uk', name: 'Українська' },
  { code: 'cs', name: 'Čeština' },
  { code: 'ru', name: 'Русский' },
]

const STORAGE_KEY = 'weather-forecaster:language'

function isLanguage(value: unknown): value is Language {
  return LANGUAGES.some((language) => language.code === value)
}

/** The remembered choice, else the browser's first supported language, else English. */
export function detectLanguage(): Language {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    if (isLanguage(stored)) return stored
  } catch {
    // Storage can be blocked (private mode, strict settings): use the browser's language.
  }
  for (const tag of globalThis.navigator?.languages ?? []) {
    const code = tag.split('-')[0]?.toLowerCase()
    if (isLanguage(code)) return code
  }
  return 'en'
}

/** The interface language; setting it switches the whole page. Only `LANGUAGES` are set. */
export function useLanguage(): WritableComputedRef<Language> {
  return useI18n().locale as WritableComputedRef<Language>
}

/** Locale for dates: "en-GB" writes "Mon 19 Oct" (day before month). */
export function dateLocale(language: string): string {
  return language === 'en' ? 'en-GB' : language
}

// Plural forms in the order the messages list them ("1 place | 2 places"). Ukrainian and
// Russian have three (1 місце, 2 місця, 5 місць), so does Czech (1 místo, 2 místa, 5 míst).
const PLURAL_FORMS: Record<Language, Intl.LDMLPluralRule[]> = {
  en: ['one', 'other'],
  uk: ['one', 'few', 'many'],
  cs: ['one', 'few', 'other'],
  ru: ['one', 'few', 'many'],
}

function pluralRule(language: Language) {
  const rules = new Intl.PluralRules(language)
  const forms = PLURAL_FORMS[language]
  return (choice: number, choicesLength: number): number => {
    const index = forms.indexOf(rules.select(choice))
    // Categories not listed (fractions) take the last form.
    return Math.min(index === -1 ? forms.length - 1 : index, choicesLength - 1)
  }
}

export function createAppI18n(locale: Language = detectLanguage()) {
  const i18n = createI18n<[MessageSchema], Language, false>({
    legacy: false,
    locale,
    fallbackLocale: 'en',
    messages: { en, uk, cs, ru },
    pluralRules: {
      en: pluralRule('en'),
      uk: pluralRule('uk'),
      cs: pluralRule('cs'),
      ru: pluralRule('ru'),
    },
  })

  const current = i18n.global.locale
  // Screen readers and the browser's spell checking follow <html lang>.
  document.documentElement.lang = current.value
  watch(current, (language) => {
    document.documentElement.lang = language
    try {
      localStorage.setItem(STORAGE_KEY, language)
    } catch {
      // Not being able to remember the choice is not an error worth showing.
    }
  })
  return i18n
}
