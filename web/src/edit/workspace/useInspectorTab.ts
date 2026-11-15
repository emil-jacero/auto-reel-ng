import { useCallback, useRef, useState } from 'react'

import { shownTab } from './inspectorTabs.ts'
import type { InspectorTab, PickedTab } from './inspectorTabs.ts'
import type { SelectionBinding } from './useSelection.ts'

/*
 * The inspector's shown tab (`editor-selection`): the selection's, until the operator picks
 * another by hand; the next selection picks again (`shownTab`). `pick` is stable.
 */
export function useInspectorTab(
  selection: Pick<SelectionBinding, 'selection' | 'again'>,
): [InspectorTab, (tab: InspectorTab) => void] {
  const [picked, setPicked] = useState<PickedTab | null>(null)
  const now = useRef(selection)
  now.current = selection
  const pick = useCallback(
    (tab: InspectorTab) =>
      setPicked({ tab, sel: now.current.selection, again: now.current.again }),
    [],
  )
  return [shownTab(picked, selection.selection, selection.again), pick]
}
