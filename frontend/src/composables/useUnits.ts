import { ref, watch, type Ref } from 'vue'

import type { Units } from '@/api/client'

const STORAGE_KEY = 'weather-forecaster:units'

function readStoredUnits(): Units {
  try {
    const stored = localStorage.getItem(STORAGE_KEY)
    return stored === 'imperial' ? 'imperial' : 'metric'
  } catch {
    // Storage can be blocked (private mode, strict settings): fall back to the default.
    return 'metric'
  }
}

/** Metric / imperial choice, remembered in this browser. */
export function useUnits(): Ref<Units> {
  const units = ref<Units>(readStoredUnits())
  watch(units, (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // Not being able to remember the choice is not an error worth showing.
    }
  })
  return units
}
