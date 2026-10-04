/*
 * The ids and ARIA attributes of a Help toggle and its panel, from the section's one id.
 * Pure: the toggle names the panel it controls and the panel names nothing else.
 */

export interface HelpIds {
  toggle: string
  panel: string
}

export function helpIds(base: string): HelpIds {
  return { toggle: `${base}-help-toggle`, panel: `${base}-help-panel` }
}

export interface ToggleAttributes {
  id: string
  'aria-expanded': boolean
  'aria-controls': string
}

export function toggleAttributes(ids: HelpIds, open: boolean): ToggleAttributes {
  return { id: ids.toggle, 'aria-expanded': open, 'aria-controls': ids.panel }
}

/** The panel keeps its place in the document when closed: `hidden`, never unmounted. */
export function panelAttributes(ids: HelpIds, open: boolean) {
  return { id: ids.panel, hidden: !open, 'aria-labelledby': ids.toggle }
}

export const HELP_LABEL = 'Help'
