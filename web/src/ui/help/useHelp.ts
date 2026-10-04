import { useCallback, useState } from 'react'

import { browserStorage, readHelp, writeHelp } from './helpState.ts'
import type { HelpSection } from './helpState.ts'

/** A section's open state: read from storage once when it mounts, written when it is toggled. */
export function useHelp(section: HelpSection): { open: boolean; toggle: () => void } {
  const [open, setOpen] = useState(() => readHelp(section, browserStorage()))
  const toggle = useCallback(() => {
    setOpen((was) => {
      writeHelp(section, !was, browserStorage())
      return !was
    })
  }, [section])
  return { open, toggle }
}
