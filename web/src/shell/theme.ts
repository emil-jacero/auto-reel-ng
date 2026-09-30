import { useCallback, useState } from 'react'

/*
 * The operator's color scheme: System (follow the operating system), Light or
 * Dark. A per-browser preference, kept in localStorage — not service state.
 *
 * Light and Dark set `data-theme` on <html>, which `tokens.css` turns into a
 * `color-scheme`; System removes it. `index.html` applies the stored choice
 * before the first paint with an inline script reading the same key. Storage
 * may throw (a private window, blocked site data): reading then falls back to
 * System, and a choice made then holds for this page only.
 */

export type ThemeChoice = 'system' | 'light' | 'dark'

// Also read by the inline script in index.html; keep the two in step.
const STORAGE_KEY = 'auto-reel:theme'

/** The stored choice: 'system' when there is none, it is not recognized, or storage throws. */
export function readThemeChoice(): ThemeChoice {
  try {
    const stored = window.localStorage.getItem(STORAGE_KEY)
    return stored === 'light' || stored === 'dark' ? stored : 'system'
  } catch {
    return 'system'
  }
}

/** Apply a choice to the page, then store it (System removes the stored key). */
export function applyThemeChoice(choice: ThemeChoice): void {
  const root = document.documentElement
  if (choice === 'system') {
    delete root.dataset.theme
  } else {
    root.dataset.theme = choice
  }
  try {
    if (choice === 'system') {
      window.localStorage.removeItem(STORAGE_KEY)
    } else {
      window.localStorage.setItem(STORAGE_KEY, choice)
    }
  } catch {
    // Storage refused: the choice still holds for this page.
  }
}

/** The current choice, and a setter that applies and stores it. */
export function useThemeChoice(): [ThemeChoice, (choice: ThemeChoice) => void] {
  const [choice, setChoice] = useState(readThemeChoice)
  const choose = useCallback((next: ThemeChoice) => {
    applyThemeChoice(next)
    setChoice(next)
  }, [])
  return [choice, choose]
}
