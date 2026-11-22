import type { SelectionBinding } from '../edit/workspace/useSelection.ts'
import type { EditBinding } from './editing'
import { useClipMenu } from './useClipMenu'

/**
 * The clip's menu while the track is not drawn (`plain-clip-bin` D5): a clip without a ready proxy
 * keeps the Prepare control in the Timeline's place, and the bin's rows still open their menu. The
 * Timeline mounts the same menu with the track's facts; this has none, so every clip is one the
 * track does not draw. Its words go to the editor's one live region.
 */
export function ClipMenuHost({
  editing,
  selection,
}: {
  editing: EditBinding
  selection: SelectionBinding
}) {
  const menu = useClipMenu({
    editing,
    selection,
    announce: (words) => editing.announce(words),
    track: null,
  })
  return <>{menu.element}</>
}
