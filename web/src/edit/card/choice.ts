/*
 * The segmented choices of a card (Background, Position), as pure rules (`title-card-toggle`):
 * the options with their helper words, and which option is shown pressed. A choice with a value
 * of its own shows that option chosen; one without shows the value it inherits as pressed in a
 * muted style (never chosen: the draft holds nothing for it until the operator presses it); one
 * whose inherited value is not known shows none (nothing is guessed, Principle I).
 */

export type ChoiceOption = { value: string; label: string; words: string | null }

/** Black or Video: `words` follow the label (`Black: text on black, before the chapter`). */
export const BACKGROUND_OPTIONS: readonly ChoiceOption[] = [
  { value: 'black', label: 'Black', words: 'text on black, before the chapter' },
  { value: 'video', label: 'Video', words: 'text over the start of the chapter’s first clip' },
]

export const POSITION_OPTIONS: readonly ChoiceOption[] = [
  { value: 'top', label: 'Top', words: null },
  { value: 'center', label: 'Center', words: null },
  { value: 'bottom', label: 'Bottom', words: null },
]

/** How one option is shown. */
export type OptionState = 'chosen' | 'inherited' | 'none'

/** The state of `option`: chosen by `value`, else the inherited one while `value` is null. */
export function optionState(
  option: string,
  value: string | null,
  inherited: string | null | undefined,
): OptionState {
  if (value !== null) {
    return option === value ? 'chosen' : 'none'
  }
  return inherited != null && option === inherited ? 'inherited' : 'none'
}

/** The tag after an inherited option: `(event style)` from the layer's tag `Event style`. */
export function inheritedTag(layer: string): string {
  return `(${layer.toLowerCase()})`
}
