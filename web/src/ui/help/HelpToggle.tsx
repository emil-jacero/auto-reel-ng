import { useId } from 'react'
import type { ReactNode } from 'react'

import { Icon } from '../Icon'
import './help.css'
import { HELP_LABEL, helpIds, panelAttributes, toggleAttributes } from './helpModel.ts'
import type { HelpIds } from './helpModel.ts'
import { useHelp } from './useHelp.ts'
import type { HelpSection } from './helpState.ts'

/**
 * A section's Help: a toggle for its header and a panel for under it, tied by one state and
 * one pair of ids. Use `useSectionHelp` once per section and place the two where they belong.
 */
export interface SectionHelp {
  open: boolean
  ids: HelpIds
  toggle: () => void
}

export function useSectionHelp(section: HelpSection): SectionHelp {
  const base = useId()
  const { open, toggle } = useHelp(section)
  return { open, toggle, ids: helpIds(base) }
}

/** The "ⓘ Help" button; the section's name is its accessible description. */
export function HelpToggle({ help, section }: { help: SectionHelp; section: string }) {
  return (
    <button
      type="button"
      className="btn btn-ghost help-toggle"
      {...toggleAttributes(help.ids, help.open)}
      aria-label={`Help: ${section}`}
      onClick={help.toggle}
    >
      <Icon name="info" />
      {HELP_LABEL}
    </button>
  )
}

/** The explanations: muted paragraphs, in the document while closed. */
export function HelpPanel({ help, children }: { help: SectionHelp; children: ReactNode }) {
  return (
    <div className="help-panel" role="group" {...panelAttributes(help.ids, help.open)}>
      {children}
    </div>
  )
}
